

from enum import IntEnum, auto
from typing import Optional


class TypeKind(IntEnum):
    """Enumeration of all fundamental type kinds supported in the IR."""
    VOID = auto()
    LABEL = auto()
    INT = auto()
    FLOAT = auto()
    POINTER = auto()
    VECTOR = auto()
    ARRAY = auto()
    STRUCT = auto()
    FUNCTION = auto()


class Type:
    """
    Abstract immutable base class for all types in the compiler IR.
    Adheres to the Flyweight pattern: identical primitive types are guaranteed
    to share the exact same memory address (pointer identity via 'is').
    """
    __slots__ = ('_kind',)

    def __init__(self, kind: TypeKind):
        self._kind = kind

    @property
    def kind(self) -> TypeKind:
        """Returns the TypeKind discriminator of this type."""
        return self._kind

    @property
    def is_void(self) -> bool:
        return self._kind == TypeKind.VOID

    @property
    def is_label(self) -> bool:
        return self._kind == TypeKind.LABEL

    @property
    def is_integer(self) -> bool:
        return self._kind == TypeKind.INT

    @property
    def is_pointer(self) -> bool:
        return self._kind == TypeKind.POINTER

    @property
    def is_vector(self) -> bool:
        return self._kind == TypeKind.VECTOR

    @property
    def is_float(self) -> bool:
        return self._kind == TypeKind.FLOAT

    @property
    def is_sized(self) -> bool:
        """Indicates whether values of this type have a well-defined size in memory."""
        return self._kind not in (TypeKind.VOID, TypeKind.LABEL, TypeKind.FUNCTION)

    @property
    def bit_width(self) -> int:
        """Returns the total bit width of this type. Raises ValueError if unsized."""
        raise ValueError(f"Type '{self}' has no well-defined bit width")

    @property
    def byte_size(self) -> int:
        """Returns the size of this type in bytes, rounded up."""
        width = self.bit_width
        return (width + 7) // 8

    def __repr__(self) -> str:
        return self.__str__()

    def __str__(self) -> str:
        raise NotImplementedError


class VoidType(Type):
    """
    Represents the absence of a value (e.g. for StoreInst, BranchInst, or void CallInst).
    """
    __slots__ = ()
    _instance: Optional['VoidType'] = None

    def __new__(cls) -> 'VoidType':
        if cls._instance is None:
            instance = super(VoidType, cls).__new__(cls)
            instance._kind = TypeKind.VOID
            cls._instance = instance
        return cls._instance

    def __init__(self) -> None:
        pass

    def __str__(self) -> str:
        return "void"


class LabelType(Type):
    """
    Represents a code label destination for Control Flow Graph BasicBlocks.
    Equivalent to LLVM Type::getLabelTy().
    """
    __slots__ = ()
    _instance: Optional['LabelType'] = None

    def __new__(cls) -> 'LabelType':
        if cls._instance is None:
            instance = super(LabelType, cls).__new__(cls)
            instance._kind = TypeKind.LABEL
            cls._instance = instance
        return cls._instance

    def __init__(self) -> None:
        pass

    def __str__(self) -> str:
        return "label"


# Global canonical singleton instances
Void = VoidType()
Label = LabelType()