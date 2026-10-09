

from dataclasses import dataclass
from typing import Tuple, Optional
from ....core.value import Value, ConstantInt
from ....core.cfg import Instruction
from ....instructions.alu import BinaryOperator, UnaryOperator, ICmpInst
from ....instructions.cast import CastInst
from ....opcodes import IROpcode, CmpPredicate

# Operand Key format: (tag: int, payload: int)
# tag 0 = ConstantInt -> payload = integer value
# tag 1 = SSA Value   -> payload = Value.id
OperandKey = Tuple[int, int]


def get_numeric_operand_key(val: Value) -> OperandKey:
    """Returns a deterministic, allocation-free integer tuple for fast O(1) comparison."""
    if isinstance(val, ConstantInt):
        return (0, val.value)
    return (1, val.id)


@dataclass(frozen=True, slots=True)
class ExpressionKey:
    """
    Strict integer-tuple based hashable key for Congruence Class identification in GVN.
    Guarantees zero-string-allocation hashing and equality checks.
    """
    opcode: int
    type_kind: int
    operands: Tuple[OperandKey, ...]
    extra: int = 0

    @classmethod
    def from_instruction(cls, inst: Instruction) -> Optional['ExpressionKey']:
        if isinstance(inst, BinaryOperator):
            opc = int(inst.opcode)
            k1 = get_numeric_operand_key(inst.lhs)
            k2 = get_numeric_operand_key(inst.rhs)

            # Strict integer tuple order for commutative algebraic canonicalization
            if inst.opcode in (IROpcode.ADD, IROpcode.MUL, IROpcode.AND, IROpcode.OR, IROpcode.XOR):
                if k1 > k2:
                    k1, k2 = k2, k1

            return cls(opcode=opc, type_kind=int(inst.type.kind), operands=(k1, k2))

        elif isinstance(inst, UnaryOperator):
            k1 = get_numeric_operand_key(inst.operand)
            return cls(opcode=int(inst.opcode), type_kind=int(inst.type.kind), operands=(k1,))

        elif isinstance(inst, ICmpInst):
            pred = inst.predicate
            k1 = get_numeric_operand_key(inst.lhs)
            k2 = get_numeric_operand_key(inst.rhs)

            # Canonicalize symmetric comparisons (EQ, NE)
            if pred in (CmpPredicate.EQ, CmpPredicate.NE):
                if k1 > k2:
                    k1, k2 = k2, k1

            return cls(
                opcode=int(IROpcode.ICMP),
                type_kind=int(inst.type.kind),
                operands=(k1, k2),
                extra=int(pred)
            )

        elif isinstance(inst, CastInst):
            k1 = get_numeric_operand_key(inst.src)
            return cls(
                opcode=int(inst.opcode),
                type_kind=int(inst.dest_type.kind),
                operands=(k1,)
            )

        return None