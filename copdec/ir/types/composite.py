

from typing import Dict, Tuple, Optional
from .base import Type, TypeKind


class PointerType(Type):
    """
    Represents a memory pointer type.
    Supports both opaque pointers (LLVM 15+ style) and typed pointers.
    """
    __slots__ = ('_pointee', '_addr_space', '_bit_width')
    _cache: Dict[Tuple[Optional[Type], int, int], 'PointerType'] = {}

    def __new__(cls, pointee: Optional[Type] = None, addr_space: int = 0, bit_width: int = 64) -> 'PointerType':
        key = (pointee, addr_space, bit_width)
        cached = cls._cache.get(key)
        if cached is not None:
            return cached

        instance = super(PointerType, cls).__new__(cls)
        instance._kind = TypeKind.POINTER
        instance._pointee = pointee
        instance._addr_space = addr_space
        instance._bit_width = bit_width

        cls._cache[key] = instance
        return instance

    def __init__(self, pointee: Optional[Type] = None, addr_space: int = 0, bit_width: int = 64) -> None:
        pass

    @classmethod
    def get(cls, pointee: Optional[Type] = None, addr_space: int = 0, bit_width: int = 64) -> 'PointerType':
        return cls(pointee, addr_space, bit_width)

    @classmethod
    def get_opaque(cls, addr_space: int = 0, bit_width: int = 64) -> 'PointerType':
        return cls(None, addr_space, bit_width)

    @property
    def pointee(self) -> Optional[Type]:
        return self._pointee

    @property
    def addr_space(self) -> int:
        return self._addr_space

    @property
    def bit_width(self) -> int:
        return self._bit_width

    def __str__(self) -> str:
        if self._pointee is None:
            return "ptr" if self._addr_space == 0 else f"ptr addrspace({self._addr_space})"
        return f"{self._pointee}*" if self._addr_space == 0 else f"{self._pointee}* addrspace({self._addr_space})"


class FloatType(Type):
    """
    Represents an IEEE 754 floating-point type.
    Supported bit-widths: 16 (Half), 32 (Single), 64 (Double), 128 (Quad).
    """
    __slots__ = ('_bit_width', '_name')
    _cache: Dict[int, 'FloatType'] = {}

    def __new__(cls, bit_width: int) -> 'FloatType':
        if bit_width not in (16, 32, 64, 128):
            raise ValueError(f"Unsupported float bit width: {bit_width}. Must be 16, 32, 64, or 128.")

        cached = cls._cache.get(bit_width)
        if cached is not None:
            return cached

        instance = super(FloatType, cls).__new__(cls)
        instance._kind = TypeKind.FLOAT
        instance._bit_width = bit_width
        names = {16: "half", 32: "float", 64: "double", 128: "fp128"}
        instance._name = names[bit_width]

        cls._cache[bit_width] = instance
        return instance

    def __init__(self, bit_width: int) -> None:
        pass

    @classmethod
    def get(cls, bit_width: int) -> 'FloatType':
        return cls(bit_width)

    @property
    def bit_width(self) -> int:
        return self._bit_width

    def __str__(self) -> str:
        return self._name


class VectorType(Type):
    """
    Represents a SIMD packed vector type: <num_elements x element_type>.
    Example: <16 x i8>, <4 x i32>, <2 x double>.
    """
    __slots__ = ('_element_type', '_num_elements')
    _cache: Dict[Tuple[Type, int], 'VectorType'] = {}

    def __new__(cls, element_type: Type, num_elements: int) -> 'VectorType':
        if not (element_type.is_integer or element_type.is_float or element_type.is_pointer):
            raise TypeError(f"Vector element type must be integer, float, or pointer, got: {element_type}")
        if num_elements <= 0:
            raise ValueError(f"Vector element count must be positive, got: {num_elements}")

        key = (element_type, num_elements)
        cached = cls._cache.get(key)
        if cached is not None:
            return cached

        instance = super(VectorType, cls).__new__(cls)
        instance._kind = TypeKind.VECTOR
        instance._element_type = element_type
        instance._num_elements = num_elements

        cls._cache[key] = instance
        return instance

    def __init__(self, element_type: Type, num_elements: int) -> None:
        pass

    @classmethod
    def get(cls, element_type: Type, num_elements: int) -> 'VectorType':
        return cls(element_type, num_elements)

    @property
    def element_type(self) -> Type:
        return self._element_type

    @property
    def num_elements(self) -> int:
        return self._num_elements

    @property
    def bit_width(self) -> int:
        return self._element_type.bit_width * self._num_elements

    def __str__(self) -> str:
        return f"<{self._num_elements} x {self._element_type}>"


# Canonical global float singletons
Float16 = FloatType.get(16)
Float32 = FloatType.get(32)
Float64 = FloatType.get(64)
Float128 = FloatType.get(128)

# Canonical opaque pointer singletons
Ptr32 = PointerType.get(bit_width=32)
Ptr64 = PointerType.get(bit_width=64)