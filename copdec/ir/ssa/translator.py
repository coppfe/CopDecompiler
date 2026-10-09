from typing import Dict, Optional

from ..core.cfg import BasicBlock
from ..core.value import Value, ConstantInt, ConstantSymbol
from ..instructions.alu import BinaryOperator, UnaryOperator, ICmpInst
from ..instructions.memory import LoadInst, StoreInst
from ..instructions.control import BranchInst, BranchCondInst, IndirectBranchInst, ReturnInst
from ..instructions.special import CallInst, SyscallInst, IntrinsicInst, SelectInst
from ..opcodes import IROpcode, CmpPredicate
from ..types.base import Void
from ...lir.nodes import (
    LIRExpr, LIRInsn, Imm, RegVar, Unary, Binary, Select, Cast,
    Assign, Load, Store, Jump, JumpCond, JumpIndirect, Call, Return, Syscall, Intrinsic, Nop
)

from ...target.binary.memory import BinaryMemoryView
from .engine import BraunSSAEngine
from ..types.utils import TypeUtils

CMP_PREDICATE_MAP: Dict[str, CmpPredicate] = {
    "==": CmpPredicate.EQ,
    "!=": CmpPredicate.NE,
    "<": CmpPredicate.SLT,
    "<=": CmpPredicate.SLE,
    ">": CmpPredicate.SGT,
    ">=": CmpPredicate.SGE,
    "<u": CmpPredicate.ULT,
    "<=u": CmpPredicate.ULE,
    ">u": CmpPredicate.UGT,
    ">=u": CmpPredicate.UGE,
}

ALU_OPCODE_MAP: Dict[str, IROpcode] = {
    "+": IROpcode.ADD,
    "-": IROpcode.SUB,
    "*": IROpcode.MUL,
    "/": IROpcode.SDIV,
    "/u": IROpcode.UDIV,
    "&": IROpcode.AND,
    "|": IROpcode.OR,
    "^": IROpcode.XOR,
    "<<": IROpcode.SHL,
    ">>": IROpcode.LSHR,
    ">>a": IROpcode.ASHR,
}


class LIRTranslator:
    """
    Direct, Architecture-Agnostic LIR to IR Instruction & Expression Translator.
    Interacts with BraunSSAEngine strictly via read_variable / write_variable.
    """
    __slots__ = ('_ssa', '_block_map', '_memory', '_arch_bits')

    def __init__(
        self,
        ssa: BraunSSAEngine,
        block_map: Dict[int, BasicBlock],
        memory: Optional[BinaryMemoryView] = None,
        arch_bits: int = 64
    ):
        self._ssa: BraunSSAEngine = ssa
        self._block_map: Dict[int, BasicBlock] = block_map
        self._memory: Optional[BinaryMemoryView] = memory
        self._arch_bits: int = arch_bits

    # =========================================================================
    # Expression Lowering (LIRExpr -> Value)
    # =========================================================================

    def lower_expr(self, expr: LIRExpr, block: BasicBlock, pc: int = 0) -> Value:
        if isinstance(expr, Imm):
            int_type = TypeUtils.get_int_type(expr.size)
            return ConstantInt.get(int_type, expr.val)

        if isinstance(expr, RegVar):
            var_type = TypeUtils.get_int_type(expr.size)
            return self._ssa.read_variable(expr.name, block, var_type)

        if isinstance(expr, Binary):
            lhs_raw = self.lower_expr(expr.lhs, block, pc=pc)
            rhs_raw = self.lower_expr(expr.rhs, block, pc=pc)
            lhs, rhs = TypeUtils.unify_binary_operands(lhs_raw, rhs_raw, block, pc=pc)

            pred = CMP_PREDICATE_MAP.get(expr.op)
            if pred is not None:
                icmp = ICmpInst(pred, lhs, rhs, name="cmp_res", pc=pc)
                block.append_instruction(icmp)
                return icmp

            opc = ALU_OPCODE_MAP.get(expr.op, None)
            if opc is None:
                raise NotImplementedError(f"{expr.op} is not defined in dict")
            bin_inst = BinaryOperator(opc, lhs, rhs, name="bin_op", pc=pc)
            block.append_instruction(bin_inst)
            return bin_inst

        if isinstance(expr, Unary):
            val = self.lower_expr(expr.val, block, pc=pc)
            opc = IROpcode.NEG if expr.op == "-" else IROpcode.NOT
            un_inst = UnaryOperator(opc, val, name="un_op", pc=pc)
            block.append_instruction(un_inst)
            return un_inst

        if isinstance(expr, Cast):
            src_val = self.lower_expr(expr.val, block, pc=pc)
            target_type = TypeUtils.get_int_type(expr.size)
            return TypeUtils.coerce_to_type(src_val, target_type, block, signed=(expr.op == "sext"), pc=pc)

        if isinstance(expr, Select):
            cond = self.lower_expr(expr.cond, block, pc=pc)
            t_raw = self.lower_expr(expr.true_val, block, pc=pc)
            f_raw = self.lower_expr(expr.false_val, block, pc=pc)
            t_val, f_val = TypeUtils.unify_binary_operands(t_raw, f_raw, block, pc=pc)
            sel = SelectInst(cond, t_val, f_val, name="sel_op", pc=pc)
            block.append_instruction(sel)
            return sel

        fallback = ConstantInt.get(TypeUtils.get_int_type(32), None)
        if fallback is None:
            raise NotImplementedError(
                f"Unsupported LIRExpr in lower_expr: {type(expr).__name__} ({expr})"
            )

    # =========================================================================
    # Instruction Lowering (LIRInsn -> Instruction into block)
    # =========================================================================

    def lower_insn(self, insn: LIRInsn, block: BasicBlock) -> None:
        pc = insn.pc

        if isinstance(insn, Assign):
            val = self.lower_expr(insn.src, block, pc=pc)
            reg_type = TypeUtils.get_int_type(insn.dst.size)
            coerced_val = TypeUtils.coerce_to_type(val, reg_type, block, pc=pc)
            self._ssa.write_variable(insn.dst.name, block, coerced_val)

        elif isinstance(insn, Load):
            addr_val = self.lower_expr(insn.addr, block, pc=pc)
            target_type = TypeUtils.get_int_type(insn.size * 8)
            load_inst = LoadInst(target_type, addr_val, alignment=insn.size, name=f"{insn.dst.name}_load", pc=pc)
            block.append_instruction(load_inst)

            loaded_val: Value = load_inst
            if (insn.size * 8) < insn.dst.size:
                dest_type = TypeUtils.get_int_type(insn.dst.size)
                loaded_val = TypeUtils.coerce_to_type(
                    load_inst, dest_type, block, signed=insn.sign_extend, pc=pc
                )

            self._ssa.write_variable(insn.dst.name, block, loaded_val)

        elif isinstance(insn, Store):
            addr_val = self.lower_expr(insn.addr, block, pc=pc)
            stored_val = self.lower_expr(insn.val, block, pc=pc)
            target_type = TypeUtils.get_int_type(insn.size * 8)
            coerced_val = TypeUtils.coerce_to_type(stored_val, target_type, block, pc=pc)
            store_inst = StoreInst(coerced_val, addr_val, alignment=insn.size, pc=pc)
            block.append_instruction(store_inst)

        elif isinstance(insn, Jump):
            target_bb = self._get_or_create_target(insn.target, block, pc)
            block.append_instruction(BranchInst(target_bb, pc=pc))

        elif isinstance(insn, JumpCond):
            cond_val = self.lower_expr(insn.cond, block, pc=pc)
            t_bb = self._get_or_create_target(insn.true_target, block, pc)
            f_bb = self._get_or_create_target(insn.false_target, block, pc)
            block.append_instruction(BranchCondInst(cond_val, t_bb, f_bb, pc=pc))

        elif isinstance(insn, JumpIndirect):
            target_val = self.lower_expr(insn.target, block, pc=pc)
            block.append_instruction(IndirectBranchInst(target_val, pc=pc))

        elif isinstance(insn, Call):
            callee_val = self._resolve_callee(insn.callee, block, pc)
            args = [self.lower_expr(a, block, pc=pc) for a in insn.args]
            ret_type = TypeUtils.get_int_type(self._arch_bits)
            call_inst = CallInst(callee_val, args, ret_type, name="call_res", pc=pc)
            block.append_instruction(call_inst)

            if insn.ret_reg is not None:
                self._ssa.write_variable(insn.ret_reg.name, block, call_inst)

        elif isinstance(insn, Return):
            ret_val = self.lower_expr(insn.val, block, pc=pc) if insn.val is not None else None
            block.append_instruction(ReturnInst(ret_val, pc=pc))

        elif isinstance(insn, Syscall):
            sys_num = self.lower_expr(insn.num, block, pc=pc)
            args = [self.lower_expr(a, block, pc=pc) for a in insn.args]
            ret_type = TypeUtils.get_int_type(self._arch_bits)
            sys_inst = SyscallInst(sys_num, args, ret_type, name="sys_res", pc=pc)
            block.append_instruction(sys_inst)

            if insn.ret_reg is not None:
                self._ssa.write_variable(insn.ret_reg.name, block, sys_inst)

        elif isinstance(insn, Intrinsic):
            args = [self.lower_expr(a, block, pc=pc) for a in insn.args]
            block.append_instruction(IntrinsicInst(insn.name, args, Void, pc=pc))

        elif isinstance(insn, Nop):
            pass

    def _resolve_callee(self, callee_expr: LIRExpr, block: BasicBlock, pc: int) -> Value:
        if isinstance(callee_expr, Imm):
            addr = callee_expr.val
            sym_name = self._memory.get_symbol_name(addr) if self._memory else None
            if sym_name:
                ptr_type = TypeUtils.get_pointer_type(self._arch_bits)
                return ConstantSymbol(ptr_type, name=sym_name, address=addr)
            int_type = TypeUtils.get_int_type(self._arch_bits)
            return ConstantInt.get(int_type, addr)

        return self.lower_expr(callee_expr, block, pc=pc)

    def _get_or_create_target(self, target_addr: int, current_block: BasicBlock, pc: int) -> BasicBlock:
        target_bb = self._block_map.get(target_addr)
        if target_bb is None:
            # Fallback for external/out-of-bounds CFG exits
            target_bb = BasicBlock(name=f"ext_0x{target_addr:x}")
            self._block_map[target_addr] = target_bb
            if current_block.parent:
                current_block.parent.append_block(target_bb)
            target_bb.append_instruction(ReturnInst(pc=pc))
        return target_bb