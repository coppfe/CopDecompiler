

from typing import Optional
from ..opcodes import IROpcode, CmpPredicate
from ..types.base import Type
from ..types.integer import Int1
from ..core.value import Value
from ..core.cfg import Instruction


class BinaryOperator(Instruction):
    """
    Represents a standard arithmetic or logical binary operation:
      %dst = opcode %lhs, %rhs
    Invariant: lhs.type == rhs.type == self.type
    """
    __slots__ = ('_opcode',)

    def __init__(self, opcode: IROpcode, lhs: Value, rhs: Value, name: str = "", pc: int = 0):
        if lhs.type is not rhs.type:
            raise TypeError(
                f"BinaryOperator operand type mismatch: lhs={lhs.type}, rhs={rhs.type} for opcode {opcode.name}"
            )
        super().__init__(lhs.type, name=name, pc=pc)
        self._opcode = opcode
        self.add_operand(lhs)
        self.add_operand(rhs)

    @property
    def opcode(self) -> IROpcode:
        return self._opcode

    @property
    def lhs(self) -> Value:
        return self.get_operand(0)

    @property
    def rhs(self) -> Value:
        return self.get_operand(1)

    def __repr__(self) -> str:
        lhs_str = f"%{self.lhs.name}" if hasattr(self.lhs, 'name') and self.lhs.name else str(self.lhs)
        rhs_str = f"%{self.rhs.name}" if hasattr(self.rhs, 'name') and self.rhs.name else str(self.rhs)
        return f"%{self.name} = {self._opcode.name.lower()} {self.type} {lhs_str}, {rhs_str}"


class UnaryOperator(Instruction):
    """
    Represents a unary arithmetic or bitwise negation:
      %dst = opcode %val
    Invariant: val.type == self.type
    """
    __slots__ = ('_opcode',)

    def __init__(self, opcode: IROpcode, val: Value, name: str = "", pc: int = 0):
        super().__init__(val.type, name=name, pc=pc)
        self._opcode = opcode
        self.add_operand(val)

    @property
    def opcode(self) -> IROpcode:
        return self._opcode

    @property
    def operand(self) -> Value:
        return self.get_operand(0)

    def __repr__(self) -> str:
        return f"%{self.name} = {self._opcode.name.lower()} {self.type} {self.operand}"


class ICmpInst(Instruction):
    """
    Integer relational comparison returning an i1 boolean value:
      %dst = icmp predicate %lhs, %rhs
    Invariant: lhs.type == rhs.type, result.type == Int1
    """
    __slots__ = ('_predicate',)

    def __init__(self, predicate: CmpPredicate, lhs: Value, rhs: Value, name: str = "", pc: int = 0):
        if lhs.type is not rhs.type:
            raise TypeError(
                f"ICmpInst operand type mismatch: lhs={lhs.type}, rhs={rhs.type}"
            )
        if not lhs.type.is_integer and not lhs.type.is_pointer:
            raise TypeError(f"ICmpInst requires integer or pointer operands, got: {lhs.type}")

        super().__init__(Int1, name=name, pc=pc)
        self._predicate = predicate
        self.add_operand(lhs)
        self.add_operand(rhs)

    @property
    def opcode(self) -> IROpcode:
        return IROpcode.ICMP

    @property
    def predicate(self) -> CmpPredicate:
        return self._predicate

    @property
    def lhs(self) -> Value:
        return self.get_operand(0)

    @property
    def rhs(self) -> Value:
        return self.get_operand(1)

    def __repr__(self) -> str:
        return f"%{self.name} = icmp {self._predicate.name.lower()} {self.lhs.type} {self.lhs}, {self.rhs}"


class FCmpInst(Instruction):
    """
    Floating-point relational comparison returning an i1 boolean value:
      %dst = fcmp predicate %lhs, %rhs
    """
    __slots__ = ('_predicate',)

    def __init__(self, predicate: CmpPredicate, lhs: Value, rhs: Value, name: str = "", pc: int = 0):
        if lhs.type is not rhs.type:
            raise TypeError(f"FCmpInst operand type mismatch: lhs={lhs.type}, rhs={rhs.type}")
        super().__init__(Int1, name=name, pc=pc)
        self._predicate = predicate
        self.add_operand(lhs)
        self.add_operand(rhs)

    @property
    def opcode(self) -> IROpcode:
        return IROpcode.FCMP

    @property
    def predicate(self) -> CmpPredicate:
        return self._predicate

    def __repr__(self) -> str:
        return f"%{self.name} = fcmp {self._predicate.name.lower()} {self.get_operand(0).type} {self.get_operand(0)}, {self.get_operand(1)}"