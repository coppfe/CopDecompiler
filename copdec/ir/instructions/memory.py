from typing import Optional
from ..opcodes import IROpcode
from ..types.base import Type, Void
from ..types.composite import PointerType
from ..core.value import Value
from ..core.cfg import Instruction


class AllocaInst(Instruction):
    """
    Abstract Stack Memory Allocation:
      %dst = alloca %allocated_type, align %alignment
    Invariant: Result type is always PointerType to allocated_type.
    """
    __slots__ = ('_allocated_type', '_alignment')

    def __init__(
        self,
        allocated_type: Type,
        alignment: int = 8,
        name: str = "",
        pc: int = 0,
        addr_space: int = 0,
        ptr_bit_width: int = 64
    ):
        if not allocated_type.is_sized:
            raise TypeError(f"Cannot allocate unsized type '{allocated_type}' on stack.")

        ptr_type = PointerType.get(allocated_type, addr_space=addr_space, bit_width=ptr_bit_width)
        super().__init__(ptr_type, name=name, pc=pc)
        self._allocated_type = allocated_type
        self._alignment = max(1, alignment)

    @property
    def opcode(self) -> IROpcode:
        return IROpcode.ALLOCA

    @property
    def allocated_type(self) -> Type:
        return self._allocated_type

    @property
    def alignment(self) -> int:
        return self._alignment

    def __repr__(self) -> str:
        return f"%{self.name} = alloca {self._allocated_type}, align {self._alignment}"


class LoadInst(Instruction):
    """
    Reads a typed value from a memory pointer:
      %dst = load %type, ptr %addr, align %alignment
    """
    __slots__ = ('_alignment',)

    def __init__(
        self,
        loaded_type: Type,
        ptr: Value,
        alignment: int = 8,
        name: str = "",
        pc: int = 0
    ):
        if not loaded_type.is_sized:
            raise TypeError(f"Cannot load unsized type '{loaded_type}'.")
        if not (ptr.type.is_pointer or ptr.type.is_integer):
            raise TypeError(f"LoadInst pointer operand must be a PointerType or integer address, got: {ptr.type}")

        super().__init__(loaded_type, name=name, pc=pc)
        self._alignment = max(1, alignment)
        self.add_operand(ptr)

    @property
    def opcode(self) -> IROpcode:
        return IROpcode.LOAD

    @property
    def pointer(self) -> Value:
        return self.get_operand(0)

    @property
    def alignment(self) -> int:
        return self._alignment

    def __repr__(self) -> str:
        return f"%{self.name} = load {self.type}, {self.pointer.type} {self.pointer}, align {self._alignment}"


class StoreInst(Instruction):
    """
    Writes a typed value to a memory pointer:
      store %val, ptr %addr, align %alignment
    Invariant: Result type is always Void.
    """
    __slots__ = ('_alignment',)

    def __init__(
        self,
        val: Value,
        ptr: Value,
        alignment: int = 8,
        pc: int = 0
    ):
        if not val.type.is_sized:
            raise TypeError(f"Cannot store unsized value of type '{val.type}'.")
        if not (ptr.type.is_pointer or ptr.type.is_integer):
            raise TypeError(f"StoreInst pointer operand must be a PointerType or integer address, got: {ptr.type}")

        super().__init__(Void, name="", pc=pc)
        self._alignment = max(1, alignment)
        self.add_operand(val)
        self.add_operand(ptr)

    @property
    def opcode(self) -> IROpcode:
        return IROpcode.STORE

    @property
    def value(self) -> Value:
        return self.get_operand(0)

    @property
    def pointer(self) -> Value:
        return self.get_operand(1)

    @property
    def alignment(self) -> int:
        return self._alignment

    def __repr__(self) -> str:
        return f"store {self.value.type} {self.value}, {self.pointer.type} {self.pointer}, align {self._alignment}"