

from typing import Dict, Optional
from .base import Type, TypeKind


class IntegerType(Type):
    """
    Represents an arbitrary bit-width integer type (e.g., i1, i8, i16, i32, i64, i128).
    Instances are strictly unique and interned per bit-width.
    """
    __slots__ = ('_bit_width', '_mask', '_sign_bit', '_signed_min', '_signed_max', '_unsigned_max')
    _cache: Dict[int, 'IntegerType'] = {}

    def __new__(cls, bit_width: int) -> 'IntegerType':
        if not isinstance(bit_width, int) or bit_width <= 0:
            raise ValueError(f"Integer bit width must be a positive integer, got: {bit_width}")

        cached = cls._cache.get(bit_width)
        if cached is not None:
            return cached

        instance = super(IntegerType, cls).__new__(cls)
        instance._kind = TypeKind.INT

        instance._bit_width = bit_width
        instance._mask = (1 << bit_width) - 1
        instance._sign_bit = 1 << (bit_width - 1)
        instance._signed_min = -(1 << (bit_width - 1)) if bit_width > 1 else 0
        instance._signed_max = (1 << (bit_width - 1)) - 1 if bit_width > 1 else 1
        instance._unsigned_max = (1 << bit_width) - 1

        cls._cache[bit_width] = instance
        return instance

    def __init__(self, bit_width: int) -> None:
        # Override to prevent inherited Type.__init__(kind) from firing with bit_width
        pass

    @classmethod
    def get(cls, bit_width: int) -> 'IntegerType':
        """Factory method to fetch or create an interned IntegerType."""
        return cls(bit_width)

    @property
    def bit_width(self) -> int:
        """Returns the number of bits in this integer type."""
        return self._bit_width

    @property
    def mask(self) -> int:
        """Returns the full bitmask for truncating values to this integer width."""
        return self._mask

    @property
    def sign_bit(self) -> int:
        """Returns the value of the most significant bit (sign bit)."""
        return self._sign_bit

    @property
    def signed_min(self) -> int:
        """Returns the minimum signed value for this width."""
        return self._signed_min

    @property
    def signed_max(self) -> int:
        """Returns the maximum signed value for this width."""
        return self._signed_max

    @property
    def unsigned_max(self) -> int:
        """Returns the maximum unsigned value for this width."""
        return self._unsigned_max

    def truncate(self, val: int) -> int:
        """Truncates an arbitrary integer into the valid unsigned range of this type."""
        return val & self._mask

    def sign_extend(self, val: int) -> int:
        """Sign-extends an unsigned integer value to Python arbitrary precision integer."""
        val &= self._mask
        if val & self._sign_bit:
            return val - (1 << self._bit_width)
        return val

    def is_valid_unsigned(self, val: int) -> bool:
        """Predicate checking if an integer fits in the unsigned range [0, 2^N - 1]."""
        return 0 <= val <= self._unsigned_max

    def is_valid_signed(self, val: int) -> bool:
        """Predicate checking if an integer fits in the signed range."""
        return self._signed_min <= val <= self._signed_max

    def __str__(self) -> str:
        return f"i{self._bit_width}"


# Pre-defined global canonical integer type singletons
Int1 = IntegerType.get(1)      # Boolean / Condition flag
Int8 = IntegerType.get(8)      # Byte / Char
Int16 = IntegerType.get(16)    # Halfword / Short
Int32 = IntegerType.get(32)    # Word / Int
Int64 = IntegerType.get(64)    # Doubleword / Long
Int128 = IntegerType.get(128)  # Quadword / Vector lane accumulator