from dataclasses import dataclass, field
from typing import Optional, List, Tuple


@dataclass(frozen=True, slots=True)
class CStructField:
    name: str
    ctype: 'CType'
    offset: int
    size: int


@dataclass(frozen=True, slots=True)
class CType:
    """
    Rich C Abstract Syntax Tree Type Representation.
    Pure AST type system with zero dependencies on compiler IR.
    """
    name: str
    is_pointer: bool = False
    is_signed: bool = True
    bit_width: int = 32
    pointee_type: Optional['CType'] = None
    is_array: bool = False
    array_count: int = 0
    element_type: Optional['CType'] = None
    is_struct: bool = False
    struct_fields: Tuple[CStructField, ...] = field(default_factory=tuple)

    @classmethod
    def pointer_to(cls, pointee: 'CType') -> 'CType':
        return cls(
            name=f"{pointee.name}*",
            is_pointer=True,
            is_signed=False,
            bit_width=64,
            pointee_type=pointee
        )

    @classmethod
    def array_of(cls, elem: 'CType', count: int) -> 'CType':
        return cls(
            name=f"{elem.name}[{count}]",
            is_array=True,
            array_count=count,
            element_type=elem,
            bit_width=elem.bit_width * count
        )

    @classmethod
    def struct_type(cls, name: str, fields: List[CStructField]) -> 'CType':
        total_bits = sum(f.size * 8 for f in fields)
        return cls(
            name=name,
            is_struct=True,
            struct_fields=tuple(fields),
            bit_width=total_bits
        )

    def __str__(self) -> str:
        return self.name