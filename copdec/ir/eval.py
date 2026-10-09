

from typing import Optional
from .types.base import Type
from .opcodes import IROpcode, CmpPredicate


class ConstantEvaluator:
    """
    Canonical Integer Arithmetic Evaluator.
    Guarantees strict bit-width normalization, two's complement sign extension,
    and safe division handling across all optimization passes.
    """
    __slots__ = ()

    @staticmethod
    def eval_binary(opc: IROpcode, v1: int, v2: int, val_type: Type) -> Optional[int]:
        if not val_type.is_integer:
            return None

        mask = val_type.mask  # type: ignore
        width = val_type.bit_width

        if opc == IROpcode.ADD: return (v1 + v2) & mask
        if opc == IROpcode.SUB: return (v1 - v2) & mask
        if opc == IROpcode.MUL: return (v1 * v2) & mask
        if opc == IROpcode.UDIV: return (v1 // v2) & mask if v2 != 0 else 0
        if opc == IROpcode.SDIV:
            if v2 == 0: return 0
            s1 = val_type.sign_extend(v1)  # type: ignore
            s2 = val_type.sign_extend(v2)  # type: ignore
            # C/LLVM truncation towards zero without float precision loss
            abs_div = abs(s1) // abs(s2)
            res = -abs_div if (s1 < 0) ^ (s2 < 0) else abs_div
            return res & mask

        if opc == IROpcode.AND: return (v1 & v2) & mask
        if opc == IROpcode.OR:  return (v1 | v2) & mask
        if opc == IROpcode.XOR: return (v1 ^ v2) & mask
        if opc == IROpcode.SHL: return (v1 << (v2 & (width - 1))) & mask
        if opc == IROpcode.LSHR: return (v1 >> (v2 & (width - 1))) & mask
        if opc == IROpcode.ASHR:
            s1 = val_type.sign_extend(v1)  # type: ignore
            return (s1 >> (v2 & (width - 1))) & mask

        return None

    @staticmethod
    def eval_unary(opc: IROpcode, val: int, val_type: Type) -> Optional[int]:
        if not val_type.is_integer:
            return None
        mask = val_type.mask  # type: ignore
        if opc == IROpcode.NOT: return (~val) & mask
        if opc == IROpcode.NEG: return (-val) & mask
        return None

    @staticmethod
    def eval_icmp(pred: CmpPredicate, v1: int, v2: int, operand_type: Type) -> bool:
        if pred == CmpPredicate.EQ: return v1 == v2
        if pred == CmpPredicate.NE: return v1 != v2
        if pred == CmpPredicate.UGT: return v1 > v2
        if pred == CmpPredicate.UGE: return v1 >= v2
        if pred == CmpPredicate.ULT: return v1 < v2
        if pred == CmpPredicate.ULE: return v1 <= v2

        s1 = operand_type.sign_extend(v1)  # type: ignore
        s2 = operand_type.sign_extend(v2)  # type: ignore
        if pred == CmpPredicate.SGT: return s1 > s2
        if pred == CmpPredicate.SGE: return s1 >= s2
        if pred == CmpPredicate.SLT: return s1 < s2
        if pred == CmpPredicate.SLE: return s1 <= s2
        return False