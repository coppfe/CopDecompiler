from typing import Optional

from ....core.value import Value, ConstantInt
from ....core.cfg import Instruction
from ....instructions.alu import BinaryOperator, UnaryOperator, ICmpInst
from ....instructions.cast import CastInst
from ....instructions.special import SelectInst
from ....types.integer import Int1
from ....opcodes import IROpcode, CmpPredicate
from ....matcher import (
    Ref, match, m_Value, m_Deferred, m_Zero, m_One, m_AllOnes,
    m_c_Add, m_Sub, m_c_Mul, m_UDiv, m_SDiv,
    m_And, m_c_And, m_Or, m_c_Or, m_Xor, m_c_Xor,
    m_Shl, m_LShr, m_AShr, m_Not, m_Neg, m_ICmp
)
from ....eval import ConstantEvaluator


def simplify_instruction(inst: Instruction) -> Optional[Value]:
    """
    Attempts to algebraically simplify an instruction using declarative Pattern Matching.
    Returns the simplified replacement Value or None if no rule matches.
    """
    if isinstance(inst, BinaryOperator):
        if isinstance(inst.lhs, ConstantInt) and isinstance(inst.rhs, ConstantInt):
            res = ConstantEvaluator.eval_binary(inst.opcode, inst.lhs.value, inst.rhs.value, inst.type)
            if res is not None:
                return ConstantInt.get(inst.type, res)

    if isinstance(inst, UnaryOperator):
        if isinstance(inst.operand, ConstantInt):
            res = ConstantEvaluator.eval_unary(inst.opcode, inst.operand.value, inst.type)
            if res is not None:
                return ConstantInt.get(inst.type, res)

    if isinstance(inst, ICmpInst):
        if isinstance(inst.lhs, ConstantInt) and isinstance(inst.rhs, ConstantInt):
            res = ConstantEvaluator.eval_icmp(inst.predicate, inst.lhs.value, inst.rhs.value, inst.lhs.type)
            return ConstantInt.get(Int1, 1 if res else 0)

    if isinstance(inst, SelectInst):
        if isinstance(inst.condition, ConstantInt):
            return inst.true_value if inst.condition.value != 0 else inst.false_value
        if inst.true_value == inst.false_value:
            return inst.true_value

    if isinstance(inst, CastInst):
        if inst.src.type is inst.dest_type:
            return inst.src
        if isinstance(inst.src, ConstantInt):
            dest_mask = inst.dest_type.mask
            val = inst.src.value
            if inst.opcode == IROpcode.SEXT:
                val = inst.src.type.sign_extend(val)
            return ConstantInt.get(inst.dest_type, val & dest_mask)

    x = Ref[Value]()
    y = Ref[Value]()
    c = Ref[ConstantInt]()
    pred_ref = Ref[CmpPredicate]()

    if match(inst, m_c_Add(m_Value(x), m_Zero())): return x.get()
    if match(inst, m_Sub(m_Value(x), m_Zero())): return x.get()
    if match(inst, m_Sub(m_Value(x), m_Deferred(x))): return ConstantInt.get(inst.type, 0)
    if match(inst, m_c_Mul(m_Value(), m_Zero())): return ConstantInt.get(inst.type, 0)
    if match(inst, m_c_Mul(m_Value(x), m_One())): return x.get()
    if match(inst, m_UDiv(m_Value(x), m_One())) or match(inst, m_SDiv(m_Value(x), m_One())): return x.get()
    if match(inst, m_UDiv(m_Value(x), m_Deferred(x))) or match(inst, m_SDiv(m_Value(x), m_Deferred(x))): return ConstantInt.get(inst.type, 1)

    if match(inst, m_And(m_Value(x), m_Deferred(x))): return x.get()
    if match(inst, m_c_And(m_Value(), m_Zero())): return ConstantInt.get(inst.type, 0)
    if match(inst, m_c_And(m_Value(x), m_AllOnes())): return x.get()
    if match(inst, m_Or(m_Value(x), m_Deferred(x))): return x.get()
    if match(inst, m_c_Or(m_Value(x), m_Zero())): return x.get()
    if match(inst, m_c_Or(m_Value(), m_AllOnes(c))): return c.get()
    if match(inst, m_Xor(m_Value(x), m_Deferred(x))): return ConstantInt.get(inst.type, 0)
    if match(inst, m_c_Xor(m_Value(x), m_Zero())): return x.get()

    if match(inst, m_Shl(m_Value(x), m_Zero())) or \
       match(inst, m_LShr(m_Value(x), m_Zero())) or \
       match(inst, m_AShr(m_Value(x), m_Zero())):
        return x.get()

    if match(inst, m_Not(m_Not(m_Value(x)))): return x.get()
    if match(inst, m_Neg(m_Neg(m_Value(x)))): return x.get()

    if match(inst, m_ICmp(pred_ref, m_Value(x), m_Deferred(x))):
        p = pred_ref.get()
        if p in (CmpPredicate.EQ, CmpPredicate.UGE, CmpPredicate.SGE, CmpPredicate.ULE, CmpPredicate.SLE):
            return ConstantInt.get(Int1, 1)
        elif p in (CmpPredicate.NE, CmpPredicate.UGT, CmpPredicate.SGT, CmpPredicate.ULT, CmpPredicate.SLT):
            return ConstantInt.get(Int1, 0)

    if match(inst, m_ICmp(pred_ref, m_Sub(m_Value(x), m_Value(y)), m_Zero())):
        p = pred_ref.get()
        if p in (CmpPredicate.EQ, CmpPredicate.NE, CmpPredicate.SLT, CmpPredicate.SLE, CmpPredicate.SGT, CmpPredicate.SGE):
            return ICmpInst(p, x.get(), y.get(), pc=inst.pc)

    return None