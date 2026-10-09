from typing import List, Union, Dict, Tuple, Optional, Callable
import capstone as cs
from capstone import CsInsn
from capstone import arm64
from capstone.arm64 import Arm64Op

from ..insn import Insn, RegOp, ImmOp, MemOp, MCOperand
from ..const import ShiftType, ExtendType, Cond
from .base import BaseDecoder

_SHIFT_MAP: Dict[int, ShiftType] = {
    arm64.ARM64_SFT_LSL: ShiftType.LSL,
    arm64.ARM64_SFT_LSR: ShiftType.LSR,
    arm64.ARM64_SFT_ASR: ShiftType.ASR,
    arm64.ARM64_SFT_ROR: ShiftType.ROR,
}

_EXT_MAP: Dict[int, ExtendType] = {
    arm64.ARM64_EXT_UXTB: ExtendType.UXTB,
    arm64.ARM64_EXT_UXTH: ExtendType.UXTH,
    arm64.ARM64_EXT_UXTW: ExtendType.UXTW,
    arm64.ARM64_EXT_UXTX: ExtendType.UXTX,
    arm64.ARM64_EXT_SXTB: ExtendType.SXTB,
    arm64.ARM64_EXT_SXTH: ExtendType.SXTH,
    arm64.ARM64_EXT_SXTW: ExtendType.SXTW,
    arm64.ARM64_EXT_SXTX: ExtendType.SXTX,
}

_CC_MAP: Dict[int, Cond] = {
    arm64.ARM64_CC_EQ: Cond.EQ,
    arm64.ARM64_CC_NE: Cond.NE,
    arm64.ARM64_CC_HS: Cond.CS,
    arm64.ARM64_CC_LO: Cond.CC,
    arm64.ARM64_CC_MI: Cond.MI,
    arm64.ARM64_CC_PL: Cond.PL,
    arm64.ARM64_CC_VS: Cond.VS,
    arm64.ARM64_CC_VC: Cond.VC,
    arm64.ARM64_CC_HI: Cond.HI,
    arm64.ARM64_CC_LS: Cond.LS,
    arm64.ARM64_CC_GE: Cond.GE,
    arm64.ARM64_CC_LT: Cond.LT,
    arm64.ARM64_CC_GT: Cond.GT,
    arm64.ARM64_CC_LE: Cond.LE,
}

_MEM_SIZE_OVERRIDES: Dict[str, int] = {
    "ldrb": 8, "ldrsb": 8, "strb": 8, "sturb": 8, "ldurb": 8, "ldursb": 8,
    "ldrh": 16, "ldrsh": 16, "strh": 16, "sturh": 16, "ldurh": 16, "ldursh": 16,
    "ldarb": 8, "stlrb": 8, "ldarh": 16, "stlrh": 16,
}


def _build_reg_table() -> Dict[str, Tuple[int, bool, str]]:
    table: Dict[str, Tuple[int, bool, str]] = {}

    for i in range(31):
        x_name = f"x{i}"
        w_name = f"w{i}"
        table[x_name] = (64, False, x_name)
        table[w_name] = (32, False, x_name)

    table["sp"] = (64, False, "sp")
    table["wsp"] = (32, False, "sp")
    table["xzr"] = (64, False, "xzr")
    table["wzr"] = (32, False, "xzr")
    table["lr"] = (64, False, "x30")
    table["fp"] = (64, False, "x29")

    for i in range(32):
        table[f"b{i}"] = (8, True, f"b{i}")
        table[f"h{i}"] = (16, True, f"h{i}")
        table[f"s{i}"] = (32, True, f"s{i}")
        table[f"d{i}"] = (64, True, f"d{i}")
        table[f"q{i}"] = (128, True, f"q{i}")
        table[f"v{i}"] = (128, True, f"v{i}")

    return table


_REG_TABLE: Dict[str, Tuple[int, bool, str]] = _build_reg_table()


def _build_sysreg_map() -> Dict[int, str]:
    sysregs: Dict[int, str] = {}
    for attr in dir(arm64):
        if attr.startswith("ARM64_SYSREG_"):
            val = getattr(arm64, attr)
            if isinstance(val, int):
                clean_name = attr[len("ARM64_SYSREG_"):].lower()
                sysregs[val] = clean_name
    return sysregs


_SYSREG_ID_MAP: Dict[int, str] = _build_sysreg_map()

OperandDecoder = Callable[[CsInsn, int], Tuple[MCOperand, int]]


def _decode_reg(ci: CsInsn, idx: int) -> Tuple[RegOp, int]:
    op: Arm64Op = ci.operands[idx]
    reg_name = ci.reg_name(op.reg).lower()
    size, is_vec, canon_name = _REG_TABLE.get(reg_name, (64, False, reg_name))

    shift_type = _SHIFT_MAP.get(op.shift.type) if op.shift.type != arm64.ARM64_SFT_INVALID else None
    shift_val = op.shift.value if shift_type is not None else 0
    ext_type = _EXT_MAP.get(op.ext) if op.ext != arm64.ARM64_EXT_INVALID else None

    reg_op = RegOp(
        name=reg_name,
        size=size,
        canonical_name=canon_name,
        shift_type=shift_type,
        shift_val=shift_val,
        extend_type=ext_type,
        is_vector=is_vec
    )
    return reg_op, 1


def _decode_imm(ci: CsInsn, idx: int) -> Tuple[ImmOp, int]:
    op: Arm64Op = ci.operands[idx]
    shift_type = _SHIFT_MAP.get(op.shift.type) if op.shift.type != arm64.ARM64_SFT_INVALID else None
    shift_val = op.shift.value if shift_type is not None else 0

    val = op.imm & 0xFFFFFFFFFFFFFFFF

    return ImmOp(
        value=val,
        size=64,
        shift_type=shift_type,
        shift_val=shift_val
    ), 1


def _decode_mem(ci: CsInsn, idx: int) -> Tuple[MemOp, int]:
    op: Arm64Op = ci.operands[idx]
    mem = op.mem
    num_ops = len(ci.operands)
    consumed = 1

    base_name = ci.reg_name(mem.base).lower() if mem.base != 0 else None
    index_name = ci.reg_name(mem.index).lower() if mem.index != 0 else None
    disp = mem.disp

    is_post_idx = False
    if idx + 1 < num_ops:
        next_op: Arm64Op = ci.operands[idx + 1]
        if next_op.type == arm64.ARM64_OP_IMM:
            disp = next_op.imm
            is_post_idx = True
            consumed = 2

    is_pre_idx = bool(ci.writeback and not is_post_idx)

    mnemonic_lower = ci.mnemonic.lower()
    if mnemonic_lower in _MEM_SIZE_OVERRIDES:
        mem_size = _MEM_SIZE_OVERRIDES[mnemonic_lower]
    elif ci.operands and ci.operands[0].type == arm64.ARM64_OP_REG:
        first_reg_name = ci.reg_name(ci.operands[0].reg).lower()
        mem_size = _REG_TABLE.get(first_reg_name, (64, False, first_reg_name))[0]
    else:
        mem_size = 64

    shift_type = _SHIFT_MAP.get(op.shift.type) if op.shift.type != arm64.ARM64_SFT_INVALID else None
    shift_val = op.shift.value if shift_type is not None else 0
    ext_type = _EXT_MAP.get(op.ext) if op.ext != arm64.ARM64_EXT_INVALID else None

    mem_op = MemOp(
        base=base_name,
        index=index_name,
        disp=disp,
        size=mem_size,
        pre_indexed=is_pre_idx,
        post_indexed=is_post_idx,
        shift_type=shift_type,
        shift_val=shift_val,
        extend_type=ext_type
    )
    return mem_op, consumed


def _decode_sys(ci: CsInsn, idx: int) -> Tuple[RegOp, int]:
    op: Arm64Op = ci.operands[idx]
    sys_id: int = op.sys if op.type == arm64.ARM64_OP_SYS else op.reg
    sys_name = _SYSREG_ID_MAP.get(sys_id, f"sysreg_0x{sys_id:x}")

    return RegOp(
        name=sys_name,
        size=64,
        canonical_name=sys_name
    ), 1


_DISPATCH_OPERAND: Dict[int, OperandDecoder] = {
    arm64.ARM64_OP_REG: _decode_reg,
    arm64.ARM64_OP_IMM: _decode_imm,
    arm64.ARM64_OP_MEM: _decode_mem,
    arm64.ARM64_OP_SYS: _decode_sys,
    arm64.ARM64_OP_REG_MRS: _decode_sys,
    arm64.ARM64_OP_REG_MSR: _decode_sys,
}


class ARM64Decoder(BaseDecoder):
    __slots__ = ('_md',)

    def __init__(self):
        self._md = cs.Cs(cs.CS_ARCH_ARM64, cs.CS_MODE_ARM)
        self._md.detail = True

    def decode_stream(self, raw_bytes: Union[bytes, bytearray], base_pc: int = 0) -> List[Insn]:
        result: List[Insn] = []

        for ci in self._md.disasm(raw_bytes, base_pc):
            operands: List[MCOperand] = []
            num_ops = len(ci.operands)
            idx = 0

            while idx < num_ops:
                op: Arm64Op = ci.operands[idx]
                decoder = _DISPATCH_OPERAND.get(op.type)

                if decoder is not None:
                    parsed_op, consumed = decoder(ci, idx)
                    operands.append(parsed_op)
                    idx += consumed
                else:
                    idx += 1

            cond: Optional[Cond] = _CC_MAP.get(ci.cc) if ci.cc not in (arm64.ARM64_CC_INVALID, arm64.ARM64_CC_AL) else None

            insn_obj = Insn(
                id=ci.id,
                address=ci.address,
                size=ci.size,
                mnemonic=ci.mnemonic,
                operands=tuple(operands),
                cond=cond,
                raw=bytes(ci.bytes)
            )
            result.append(insn_obj)

        return result