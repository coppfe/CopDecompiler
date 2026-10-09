

from typing import Generic, TypeVar, Optional, Any
from .core.value import Value, ConstantInt
from .instructions.alu import BinaryOperator, UnaryOperator, ICmpInst
from .instructions.special import SelectInst
from .opcodes import IROpcode, CmpPredicate

T = TypeVar('T', bound=Value)


class Ref(Generic[T]):
    """
    Type-safe reference cell for capturing matched SSA Values in pattern matchers.
    Zero-overhead container replacing manual variable bindings.
    """
    __slots__ = ('value',)

    def __init__(self, init: Optional[T] = None):
        self.value: Optional[T] = init

    def get(self) -> T:
        assert self.value is not None, "Attempted to dereference unbound Ref cell"
        return self.value

    def reset(self) -> None:
        self.value = None


class Matcher:
    """Base abstract class for all pattern matching combinators."""
    __slots__ = ()

    def match(self, val: Any) -> bool:
        raise NotImplementedError


def match(val: Any, pattern: Matcher) -> bool:
    """Top-level pattern matching entry point."""
    return pattern.match(val)

class ValueMatcher(Matcher):
    __slots__ = ('_ref',)

    def __init__(self, ref: Optional[Ref[Value]] = None):
        self._ref = ref

    def match(self, val: Any) -> bool:
        if isinstance(val, Value):
            if self._ref is not None:
                self._ref.value = val
            return True
        return False


class DeferredValueMatcher(Matcher):
    """Matches if candidate value is identical to previously captured value in Ref."""
    __slots__ = ('_ref',)

    def __init__(self, ref: Ref[Value]):
        self._ref = ref

    def match(self, val: Any) -> bool:
        return self._ref.value is not None and val == self._ref.value


class ConstantIntMatcher(Matcher):
    __slots__ = ('_ref', '_val')

    def __init__(self, ref: Optional[Ref[ConstantInt]] = None, val: Optional[int] = None):
        self._ref = ref
        self._val = val

    def match(self, val: Any) -> bool:
        if isinstance(val, ConstantInt):
            if self._val is not None and val.value != self._val:
                return False
            if self._ref is not None:
                self._ref.value = val
            return True
        return False


class ZeroMatcher(Matcher):
    __slots__ = ()

    def match(self, val: Any) -> bool:
        return isinstance(val, ConstantInt) and val.value == 0


class OneMatcher(Matcher):
    __slots__ = ()

    def match(self, val: Any) -> bool:
        return isinstance(val, ConstantInt) and val.value == 1


class AllOnesMatcher(Matcher):
    __slots__ = ('_ref',)

    def __init__(self, ref: Optional[Ref[ConstantInt]] = None):
        self._ref = ref

    def match(self, val: Any) -> bool:
        if isinstance(val, ConstantInt) and val.type.is_integer:
            mask = val.type.mask  # type: ignore
            if val.value == mask:
                if self._ref is not None:
                    self._ref.value = val
                return True
        return False

class BinaryOpMatcher(Matcher):
    __slots__ = ('_opcode', '_lhs_m', '_rhs_m', '_commutative')

    def __init__(self, opcode: IROpcode, lhs_m: Matcher, rhs_m: Matcher, commutative: bool = False):
        self._opcode = opcode
        self._lhs_m = lhs_m
        self._rhs_m = rhs_m
        self._commutative = commutative

    def match(self, val: Any) -> bool:
        if isinstance(val, BinaryOperator) and val.opcode == self._opcode:
            if self._lhs_m.match(val.lhs) and self._rhs_m.match(val.rhs):
                return True
            if self._commutative:
                if self._lhs_m.match(val.rhs) and self._rhs_m.match(val.lhs):
                    return True
        return False

class UnaryOpMatcher(Matcher):
    __slots__ = ('_opcode', '_op_m')

    def __init__(self, opcode: IROpcode, op_m: Matcher):
        self._opcode = opcode
        self._op_m = op_m

    def match(self, val: Any) -> bool:
        if isinstance(val, UnaryOperator) and val.opcode == self._opcode:
            return self._op_m.match(val.operand)
        return False

class ICmpMatcher(Matcher):
    __slots__ = ('_pred_ref', '_lhs_m', '_rhs_m', '_specific_pred', '_commutative')

    def __init__(
        self,
        lhs_m: Matcher,
        rhs_m: Matcher,
        pred_ref: Optional[Ref[CmpPredicate]] = None,
        specific_pred: Optional[CmpPredicate] = None,
        commutative: bool = False
    ):
        self._lhs_m = lhs_m
        self._rhs_m = rhs_m
        self._pred_ref = pred_ref
        self._specific_pred = specific_pred
        self._commutative = commutative

    def match(self, val: Any) -> bool:
        if isinstance(val, ICmpInst):
            if self._specific_pred is not None and val.predicate != self._specific_pred:
                return False

            if self._lhs_m.match(val.lhs) and self._rhs_m.match(val.rhs):
                if self._pred_ref is not None:
                    self._pred_ref.value = val.predicate
                return True

            if self._commutative and val.predicate in (CmpPredicate.EQ, CmpPredicate.NE):
                if self._lhs_m.match(val.rhs) and self._rhs_m.match(val.lhs):
                    if self._pred_ref is not None:
                        self._pred_ref.value = val.predicate
                    return True

        return False


class SelectMatcher(Matcher):
    __slots__ = ('_cond_m', '_true_m', '_false_m')

    def __init__(self, cond_m: Matcher, true_m: Matcher, false_m: Matcher):
        self._cond_m = cond_m
        self._true_m = true_m
        self._false_m = false_m

    def match(self, val: Any) -> bool:
        if isinstance(val, SelectInst):
            return (self._cond_m.match(val.condition) and
                    self._true_m.match(val.true_value) and
                    self._false_m.match(val.false_value))
        return False

def m_Value(ref: Optional[Ref[Value]] = None) -> ValueMatcher:
    return ValueMatcher(ref)

def m_Deferred(ref: Ref[Value]) -> DeferredValueMatcher:
    return DeferredValueMatcher(ref)

def m_ConstantInt(ref: Optional[Ref[ConstantInt]] = None, val: Optional[int] = None) -> ConstantIntMatcher:
    return ConstantIntMatcher(ref, val)

def m_Zero() -> ZeroMatcher:
    return ZeroMatcher()

def m_One() -> OneMatcher:
    return OneMatcher()

def m_AllOnes(ref: Optional[Ref[ConstantInt]] = None) -> AllOnesMatcher:
    return AllOnesMatcher(ref)

def m_Add(lhs: Matcher, rhs: Matcher) -> BinaryOpMatcher:
    return BinaryOpMatcher(IROpcode.ADD, lhs, rhs, commutative=False)

def m_c_Add(lhs: Matcher, rhs: Matcher) -> BinaryOpMatcher:
    return BinaryOpMatcher(IROpcode.ADD, lhs, rhs, commutative=True)

def m_Sub(lhs: Matcher, rhs: Matcher) -> BinaryOpMatcher:
    return BinaryOpMatcher(IROpcode.SUB, lhs, rhs, commutative=False)

def m_Mul(lhs: Matcher, rhs: Matcher) -> BinaryOpMatcher:
    return BinaryOpMatcher(IROpcode.MUL, lhs, rhs, commutative=False)

def m_c_Mul(lhs: Matcher, rhs: Matcher) -> BinaryOpMatcher:
    return BinaryOpMatcher(IROpcode.MUL, lhs, rhs, commutative=True)

def m_UDiv(lhs: Matcher, rhs: Matcher) -> BinaryOpMatcher:
    return BinaryOpMatcher(IROpcode.UDIV, lhs, rhs, commutative=False)

def m_SDiv(lhs: Matcher, rhs: Matcher) -> BinaryOpMatcher:
    return BinaryOpMatcher(IROpcode.SDIV, lhs, rhs, commutative=False)

def m_And(lhs: Matcher, rhs: Matcher) -> BinaryOpMatcher:
    return BinaryOpMatcher(IROpcode.AND, lhs, rhs, commutative=False)

def m_c_And(lhs: Matcher, rhs: Matcher) -> BinaryOpMatcher:
    return BinaryOpMatcher(IROpcode.AND, lhs, rhs, commutative=True)

def m_Or(lhs: Matcher, rhs: Matcher) -> BinaryOpMatcher:
    return BinaryOpMatcher(IROpcode.OR, lhs, rhs, commutative=False)

def m_c_Or(lhs: Matcher, rhs: Matcher) -> BinaryOpMatcher:
    return BinaryOpMatcher(IROpcode.OR, lhs, rhs, commutative=True)

def m_Xor(lhs: Matcher, rhs: Matcher) -> BinaryOpMatcher:
    return BinaryOpMatcher(IROpcode.XOR, lhs, rhs, commutative=False)

def m_c_Xor(lhs: Matcher, rhs: Matcher) -> BinaryOpMatcher:
    return BinaryOpMatcher(IROpcode.XOR, lhs, rhs, commutative=True)

def m_Shl(lhs: Matcher, rhs: Matcher) -> BinaryOpMatcher:
    return BinaryOpMatcher(IROpcode.SHL, lhs, rhs, commutative=False)

def m_LShr(lhs: Matcher, rhs: Matcher) -> BinaryOpMatcher:
    return BinaryOpMatcher(IROpcode.LSHR, lhs, rhs, commutative=False)

def m_AShr(lhs: Matcher, rhs: Matcher) -> BinaryOpMatcher:
    return BinaryOpMatcher(IROpcode.ASHR, lhs, rhs, commutative=False)

def m_Not(op: Matcher) -> UnaryOpMatcher:
    return UnaryOpMatcher(IROpcode.NOT, op)

def m_Neg(op: Matcher) -> UnaryOpMatcher:
    return UnaryOpMatcher(IROpcode.NEG, op)

def m_ICmp(pred_ref: Optional[Ref[CmpPredicate]], lhs: Matcher, rhs: Matcher) -> ICmpMatcher:
    return ICmpMatcher(lhs, rhs, pred_ref=pred_ref, commutative=False)

def m_c_ICmp(pred_ref: Optional[Ref[CmpPredicate]], lhs: Matcher, rhs: Matcher) -> ICmpMatcher:
    return ICmpMatcher(lhs, rhs, pred_ref=pred_ref, commutative=True)

def m_SpecificICmp(pred: CmpPredicate, lhs: Matcher, rhs: Matcher) -> ICmpMatcher:
    return ICmpMatcher(lhs, rhs, specific_pred=pred, commutative=False)

def m_Select(cond: Matcher, true_val: Matcher, false_val: Matcher) -> SelectMatcher:
    return SelectMatcher(cond, true_val, false_val)