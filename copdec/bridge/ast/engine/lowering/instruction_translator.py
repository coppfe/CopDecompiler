import json
from typing import Dict, Set, Optional, Callable, Union
from .....ast.types import CType
from .....ast.nodes import (
    CExpr, CBlock, CAssignStmt, CExprStmt, CBinaryExpr,
    CUnaryExpr, CVarExpr, CLiteralExpr, CCallExpr, CCastExpr, CTernaryExpr
)
from .high_var import HighVariableManager
from .type_mapper import TypeMapper
from .....ir.core.value import (
    Value, ConstantInt, ConstantFP, ConstantPointerNull, ConstantSymbol, UndefValue
)
from .....ir.core.cfg import Instruction
from .....ir.instructions.alu import BinaryOperator, UnaryOperator, ICmpInst, FCmpInst
from .....ir.instructions.cast import CastInst
from .....ir.instructions.memory import AllocaInst, LoadInst, StoreInst
from .....ir.instructions.special import CallInst, SyscallInst, IntrinsicInst, SelectInst
from .....ir.opcodes import IROpcode, CmpPredicate
from .....target.binary.memory import BinaryMemoryView

BIN_OP_MAP: Dict[IROpcode, str] = {
    IROpcode.ADD: "+", IROpcode.SUB: "-", IROpcode.MUL: "*",
    IROpcode.UDIV: "/", IROpcode.SDIV: "/",
    IROpcode.FADD: "+", IROpcode.FSUB: "-", IROpcode.FMUL: "*", IROpcode.FDIV: "/",
    IROpcode.AND: "&", IROpcode.OR: "|", IROpcode.XOR: "^",
    IROpcode.SHL: "<<",
    IROpcode.LSHR: ">>_u",
    IROpcode.ASHR: ">>",
}

CMP_PRED_MAP: Dict[CmpPredicate, str] = {
    CmpPredicate.EQ: "==", CmpPredicate.NE: "!=",
    CmpPredicate.UGT: ">", CmpPredicate.UGE: ">=",
    CmpPredicate.ULT: "<", CmpPredicate.ULE: "<=",
    CmpPredicate.SGT: ">", CmpPredicate.SGE: ">=",
    CmpPredicate.SLT: "<", CmpPredicate.SLE: "<=",
    CmpPredicate.OEQ: "==", CmpPredicate.OGT: ">",
    CmpPredicate.OGE: ">=", CmpPredicate.OLT: "<",
    CmpPredicate.OLE: "<=", CmpPredicate.ONE: "!=",
}

UNARY_OP_MAP: Dict[IROpcode, str] = {
    IROpcode.NOT: "~",
    IROpcode.NEG: "-",
    IROpcode.FNEG: "-",
}


class InstructionTranslator:
    """
    Pure IR-to-AST Instruction & Expression Lowering.
    Performs 1-to-1 conversion from IR instructions to C AST nodes.
    Zero hidden cast syntheses, zero semantic optimizations.
    """
    __slots__ = ('_high_var_mgr', '_declared_vars', '_memory')

    def __init__(
        self,
        high_var_mgr: HighVariableManager,
        declared_vars: Set[str],
        memory: Optional[BinaryMemoryView] = None
    ):
        self._high_var_mgr = high_var_mgr
        self._declared_vars = declared_vars
        self._memory = memory

    def get_var(self, val: Value) -> CExpr:
        if isinstance(val, ConstantSymbol):
            return CVarExpr(val.name, CType("void*", is_pointer=True, bit_width=64))

        if isinstance(val, ConstantPointerNull):
            return CLiteralExpr("NULL", CType("void*", is_pointer=True, bit_width=64))

        if isinstance(val, UndefValue):
            return CLiteralExpr(0, TypeMapper.ir_to_ctype(val.type))

        if isinstance(val, ConstantFP):
            return CLiteralExpr(val.value, TypeMapper.ir_to_ctype(val.type))

        if isinstance(val, ConstantInt):
            addr = val.value

            if self._memory is not None and self._memory.is_mapped(addr):
                if self._memory.is_executable(addr):
                    sym_name = self._memory.get_symbol_name(addr) or f"FUN_{addr:x}"
                    return CUnaryExpr("&", CVarExpr(sym_name, CType("void*", is_pointer=True, bit_width=64)), CType("void*", is_pointer=True, bit_width=64))

                if self._memory.is_readonly(addr):
                    cstr = self._memory.read_cstring(addr)
                    if cstr is not None and len(cstr) > 0:
                        escaped = json.dumps(cstr)
                        return CLiteralExpr(escaped, CType("char*", is_pointer=True, bit_width=64))

                sym_name = self._memory.get_symbol_name(addr) or f"DAT_{addr:x}"
                return CUnaryExpr("&", CVarExpr(sym_name, CType("void*", is_pointer=True, bit_width=64)), CType("void*", is_pointer=True, bit_width=64))

            return CLiteralExpr(val.value, TypeMapper.ir_to_ctype(val.type))

        if isinstance(val, AllocaInst):
            cvar = self._high_var_mgr.get_cvar(val)
            return CUnaryExpr("&", cvar, CType.pointer_to(cvar.ctype))

        return self._high_var_mgr.get_cvar(val)

    def _make_deref(self, ptr_expr: CExpr, target_ctype: CType) -> CExpr:
        if isinstance(ptr_expr, CUnaryExpr) and ptr_expr.op == "&":
            return ptr_expr.operand
        return CUnaryExpr("*", ptr_expr, target_ctype)

    def create_assignment(
        self,
        dst_var: CExpr,
        expr: Optional[CExpr] = None,
        force_decl: bool = False
    ) -> Optional[CAssignStmt]:
        if expr is not None and isinstance(dst_var, CVarExpr) and isinstance(expr, CVarExpr):
            if dst_var is expr or (dst_var.name == expr.name and dst_var.ctype == expr.ctype):
                return None

        is_first_decl = force_decl
        if not is_first_decl and isinstance(dst_var, CVarExpr):
            if dst_var.name not in self._declared_vars:
                is_first_decl = True
                self._declared_vars.add(dst_var.name)

        return CAssignStmt(dst_var, expr, is_declaration=is_first_decl)

    def translate(self, inst: Instruction, block: CBlock) -> None:
        handler = _OPCODE_DISPATCH.get(inst.opcode)
        if handler is not None:
            handler(self, inst, block)
        else:
            self._emit_generic_fallback(inst, block)

    def _emit_binary(self, inst: Instruction, block: CBlock) -> None:
        assert isinstance(inst, BinaryOperator)
        ctype = TypeMapper.ir_to_ctype(inst.type)
        dst_var = self.get_var(inst)
        op_str = BIN_OP_MAP.get(inst.opcode, "?")
        lhs = self.get_var(inst.lhs)
        rhs = self.get_var(inst.rhs)
        
        if inst.opcode == IROpcode.LSHR:
            uint_type = CType(f"uint{inst.type.bit_width}_t", is_signed=False, bit_width=inst.type.bit_width)
            lhs = CCastExpr(uint_type, lhs)
            op_str = ">>"
        elif inst.opcode == IROpcode.UDIV:
            uint_type = CType(f"uint{inst.type.bit_width}_t", is_signed=False, bit_width=inst.type.bit_width)
            lhs = CCastExpr(uint_type, lhs)
            rhs = CCastExpr(uint_type, rhs)

        expr = CBinaryExpr(op_str, lhs, rhs, ctype)
        stmt = self.create_assignment(dst_var, expr)
        if stmt is not None:
            block.append(stmt)

    def _emit_unary(self, inst: Instruction, block: CBlock) -> None:
        assert isinstance(inst, UnaryOperator)
        ctype = TypeMapper.ir_to_ctype(inst.type)
        dst_var = self.get_var(inst)
        op_str = UNARY_OP_MAP.get(inst.opcode, "~")
        operand = self.get_var(inst.operand)
        expr = CUnaryExpr(op_str, operand, ctype)
        stmt = self.create_assignment(dst_var, expr)
        if stmt is not None:
            block.append(stmt)

    def _emit_cmp(self, inst: Instruction, block: CBlock) -> None:
        assert isinstance(inst, (ICmpInst, FCmpInst))
        ctype = TypeMapper.ir_to_ctype(inst.type)
        dst_var = self.get_var(inst)
        predicate = inst.predicate
        pred_str = CMP_PRED_MAP.get(predicate, "==")
        lhs = self.get_var(inst.lhs)
        rhs = self.get_var(inst.rhs)

        if predicate in (CmpPredicate.UGT, CmpPredicate.UGE, CmpPredicate.ULT, CmpPredicate.ULE):
            width = inst.lhs.type.bit_width
            uint_type = CType(f"uint{width}_t", is_signed=False, bit_width=width)
            lhs = CCastExpr(uint_type, lhs)
            if not isinstance(rhs, CLiteralExpr):
                rhs = CCastExpr(uint_type, rhs)
                
        expr = CBinaryExpr(pred_str, lhs, rhs, ctype)
        stmt = self.create_assignment(dst_var, expr)
        if stmt is not None:
            block.append(stmt)

    def _emit_cast(self, inst: Instruction, block: CBlock) -> None:
        assert isinstance(inst, CastInst)
        dst_var = self.get_var(inst)
        src = self.get_var(inst.src)
        dest_ctype = TypeMapper.ir_to_ctype(inst.dest_type)
        
        cast_expr = CCastExpr(dest_ctype, src)
        stmt = self.create_assignment(dst_var, cast_expr)
        if stmt is not None:
            block.append(stmt)

    def _emit_select(self, inst: Instruction, block: CBlock) -> None:
        assert isinstance(inst, SelectInst)
        ctype = TypeMapper.ir_to_ctype(inst.type)
        dst_var = self.get_var(inst)
        cond = self.get_var(inst.condition)
        true_e = self.get_var(inst.true_value)
        false_e = self.get_var(inst.false_value)
        expr = CTernaryExpr(cond, true_e, false_e, ctype)
        stmt = self.create_assignment(dst_var, expr)
        if stmt is not None:
            block.append(stmt)

    def _emit_load(self, inst: Instruction, block: CBlock) -> None:
        assert isinstance(inst, LoadInst)
        ctype = TypeMapper.ir_to_ctype(inst.type)
        dst_var = self.get_var(inst)
        ptr = self.get_var(inst.pointer)
        deref = self._make_deref(ptr, ctype)
        stmt = self.create_assignment(dst_var, deref)
        if stmt is not None:
            block.append(stmt)

    def _emit_store(self, inst: Instruction, block: CBlock) -> None:
        assert isinstance(inst, StoreInst)
        val = self.get_var(inst.value)
        ptr = self.get_var(inst.pointer)
        lhs_target = self._make_deref(ptr, val.ctype)
        stmt = self.create_assignment(lhs_target, val)
        if stmt is not None:
            block.append(stmt)

    def _emit_call(self, inst: Instruction, block: CBlock) -> None:
        assert isinstance(inst, CallInst)
        ctype = TypeMapper.ir_to_ctype(inst.type)
        dst_var = self.get_var(inst)
        callee_op = inst.callee

        if isinstance(callee_op, ConstantSymbol):
            callee_target: Union[str, CExpr] = callee_op.name
        elif isinstance(callee_op, ConstantInt):
            callee_target = f"FUN_{callee_op.value:x}"
        else:
            callee_target = self.get_var(callee_op)

        args = [self.get_var(a) for a in inst.args]
        call_expr = CCallExpr(callee_target, args, ctype)

        if inst.type.is_void or not inst.has_users():
            block.append(CExprStmt(call_expr))
        else:
            stmt = self.create_assignment(dst_var, call_expr)
            if stmt is not None:
                block.append(stmt)

    def _emit_system(self, inst: Instruction, block: CBlock) -> None:
        ctype = TypeMapper.ir_to_ctype(inst.type)
        name = inst.intrinsic_name if isinstance(inst, IntrinsicInst) else "syscall"
        args = [self.get_var(inst.get_operand(i)) for i in range(inst.num_operands)]
        call_expr = CCallExpr(name, args, ctype)

        if inst.type.is_void:
            block.append(CExprStmt(call_expr))
        else:
            dst_var = self.get_var(inst)
            stmt = self.create_assignment(dst_var, call_expr)
            if stmt is not None:
                block.append(stmt)

    def _emit_generic_fallback(self, inst: Instruction, block: CBlock) -> None:
        if inst.is_terminator or inst.opcode == IROpcode.PHI:
            return
        ctype = TypeMapper.ir_to_ctype(inst.type)
        args = [self.get_var(inst.get_operand(i)) for i in range(inst.num_operands)]
        call_expr = CCallExpr(f"__builtin_{inst.opcode.name.lower()}", args, ctype)

        if inst.type.is_void:
            block.append(CExprStmt(call_expr))
        else:
            dst_var = self.get_var(inst)
            stmt = self.create_assignment(dst_var, call_expr)
            if stmt is not None:
                block.append(stmt)

    def _emit_alloca(self, inst: Instruction, block: CBlock) -> None:
        assert isinstance(inst, AllocaInst)
        cvar = self._high_var_mgr.get_cvar(inst)
        stmt = self.create_assignment(cvar, expr=None)
        if stmt is not None:
            block.append(stmt)


_OPCODE_DISPATCH: Dict[IROpcode, Callable[[InstructionTranslator, Instruction, CBlock], None]] = {
    IROpcode.ADD: InstructionTranslator._emit_binary,
    IROpcode.SUB: InstructionTranslator._emit_binary,
    IROpcode.MUL: InstructionTranslator._emit_binary,
    IROpcode.UDIV: InstructionTranslator._emit_binary,
    IROpcode.SDIV: InstructionTranslator._emit_binary,
    IROpcode.FADD: InstructionTranslator._emit_binary,
    IROpcode.FSUB: InstructionTranslator._emit_binary,
    IROpcode.FMUL: InstructionTranslator._emit_binary,
    IROpcode.FDIV: InstructionTranslator._emit_binary,
    IROpcode.AND: InstructionTranslator._emit_binary,
    IROpcode.OR: InstructionTranslator._emit_binary,
    IROpcode.XOR: InstructionTranslator._emit_binary,
    IROpcode.SHL: InstructionTranslator._emit_binary,
    IROpcode.LSHR: InstructionTranslator._emit_binary,
    IROpcode.ASHR: InstructionTranslator._emit_binary,

    IROpcode.NOT: InstructionTranslator._emit_unary,
    IROpcode.NEG: InstructionTranslator._emit_unary,
    IROpcode.FNEG: InstructionTranslator._emit_unary,

    IROpcode.ICMP: InstructionTranslator._emit_cmp,
    IROpcode.FCMP: InstructionTranslator._emit_cmp,

    IROpcode.TRUNC: InstructionTranslator._emit_cast,
    IROpcode.ZEXT: InstructionTranslator._emit_cast,
    IROpcode.SEXT: InstructionTranslator._emit_cast,
    IROpcode.BITCAST: InstructionTranslator._emit_cast,
    IROpcode.PTRTOINT: InstructionTranslator._emit_cast,
    IROpcode.INTTOPTR: InstructionTranslator._emit_cast,

    IROpcode.SELECT: InstructionTranslator._emit_select,
    IROpcode.LOAD: InstructionTranslator._emit_load,
    IROpcode.STORE: InstructionTranslator._emit_store,
    IROpcode.CALL: InstructionTranslator._emit_call,
    IROpcode.SYSCALL: InstructionTranslator._emit_system,
    IROpcode.INTRINSIC: InstructionTranslator._emit_system,

    IROpcode.ALLOCA: InstructionTranslator._emit_alloca
}