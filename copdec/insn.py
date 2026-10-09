from dataclasses import dataclass
from typing import Tuple, Union, Optional
from .const import ShiftType, ExtendType, Cond


@dataclass(frozen=True, slots=True)
class RegOp:
    """Register operand (e.g. 'x0', 'w1', 'sp', 'xzr', 'd0')."""
    name: str
    size: int                         # Bit-width: 8, 16, 32, 64, 128
    canonical_name: str               # 64-bit physical equivalent (w0 -> x0, wsp -> sp, wzr -> xzr)
    shift_type: Optional[ShiftType] = None
    shift_val: int = 0
    extend_type: Optional[ExtendType] = None
    is_vector: bool = False

    @property
    def is_zero(self) -> bool:
        """Returns True if this is the zero register (xzr or wzr)."""
        return self.canonical_name == "xzr" or self.name in ("xzr", "wzr")

    @property
    def is_sp(self) -> bool:
        """Returns True if this is the stack pointer (sp or wsp)."""
        return self.canonical_name == "sp" or self.name in ("sp", "wsp")

    def __repr__(self) -> str:
        res = self.name
        if self.extend_type is not None:
            res += f", {self.extend_type.name.lower()}"
        if self.shift_val > 0:
            st = self.shift_type.name.lower() if self.shift_type else "lsl"
            res += f", {st} #{self.shift_val}"
        return res


@dataclass(frozen=True, slots=True)
class ImmOp:
    """Immediate literal operand."""
    value: int
    size: int = 64
    shift_val: int = 0
    shift_type: Optional[ShiftType] = None

    def __repr__(self) -> str:
        if self.value > 0xFFF or self.value < -0xFFF:
            return hex(self.value)
        return str(self.value)


@dataclass(frozen=True, slots=True)
class MemOp:
    """
    Universal Memory Addressing Operand.
    Supports Base+Disp, Base+Index, Pre-index [Rn, #imm]!, and Post-index [Rn], #imm.
    """
    base: Optional[str] = None
    index: Optional[str] = None
    disp: int = 0
    size: int = 64                    # Access bit-width (8, 16, 32, 64, 128)
    pre_indexed: bool = False
    post_indexed: bool = False
    shift_type: Optional[ShiftType] = None
    shift_val: int = 0
    extend_type: Optional[ExtendType] = None

    def __repr__(self) -> str:
        parts = []
        if self.base:
            parts.append(self.base)
        if self.index:
            idx_str = self.index
            if self.extend_type is not None:
                idx_str += f" {self.extend_type.name.lower()}"
            if self.shift_val > 0:
                st = self.shift_type.name.lower() if self.shift_type else "lsl"
                idx_str += f" {st} #{self.shift_val}"
            parts.append(idx_str)
        if self.disp != 0 and not self.post_indexed:
            parts.append(f"#{self.disp}")

        body = f"[{', '.join(parts)}]"
        if self.pre_indexed:
            body += "!"
        elif self.post_indexed and self.disp != 0:
            body += f", #{self.disp}"
        return body


# CondOp completely eliminated: only pure data operands remain
MCOperand = Union[RegOp, ImmOp, MemOp]


class Insn:
    """
    Pure Architecture-Agnostic Machine Instruction (MC Layer).
    Condition is a first-class execution predicate on the instruction itself.
    """
    __slots__ = ('id', 'address', 'size', 'mnemonic', 'operands', 'cond', 'raw')

    def __init__(
        self,
        id: int,
        address: int,
        size: int,
        mnemonic: str,
        operands: Tuple[MCOperand, ...],
        cond: Optional[Cond] = None,
        raw: bytes = b""
    ):
        self.id: int = id
        self.address: int = address
        self.size: int = size
        self.mnemonic: str = mnemonic.lower()
        self.operands: Tuple[MCOperand, ...] = operands
        self.cond: Optional[Cond] = cond
        self.raw: bytes = raw

    @property
    def op_count(self) -> int:
        return len(self.operands)

    @property
    def is_conditional(self) -> bool:
        return self.cond is not None

    def op(self, idx: int) -> MCOperand:
        return self.operands[idx]

    def reg(self, idx: int) -> RegOp:
        op = self.operands[idx]
        if not isinstance(op, RegOp):
            raise TypeError(f"Operand {idx} of {self.mnemonic} is {type(op).__name__}, expected RegOp")
        return op

    def imm(self, idx: int) -> int:
        op = self.operands[idx]
        if not isinstance(op, ImmOp):
            raise TypeError(f"Operand {idx} of {self.mnemonic} is {type(op).__name__}, expected ImmOp")
        return op.value

    def mem(self, idx: int) -> MemOp:
        op = self.operands[idx]
        if not isinstance(op, MemOp):
            raise TypeError(f"Operand {idx} of {self.mnemonic} is {type(op).__name__}, expected MemOp")
        return op

    def __repr__(self) -> str:
        ops_str = ", ".join(repr(o) for o in self.operands)
        cond_str = f" [{self.cond.name}]" if self.cond is not None else ""
        return f"<0x{self.address:x}: {self.mnemonic}{cond_str} {ops_str}>"