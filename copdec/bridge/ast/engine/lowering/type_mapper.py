from .....ir.types.base import Type
from .....ir.types.composite import PointerType
from .....ast.types import CType


class TypeMapper:
    """Bridges Compiler IR Types into C AST Types."""
    __slots__ = ()

    @classmethod
    def ir_to_ctype(cls, ir_type: Type, is_signed: bool = True) -> CType:
        if ir_type.is_void:
            return CType("void", bit_width=0)

        if ir_type.is_pointer:
            if isinstance(ir_type, PointerType) and ir_type.pointee is not None:
                elem_ctype = cls.ir_to_ctype(ir_type.pointee, is_signed=is_signed)
                return CType.pointer_to(elem_ctype)
            return CType("void*", is_pointer=True, bit_width=ir_type.bit_width, pointee_type=CType("void", bit_width=0))

        if ir_type.is_integer:
            width = ir_type.bit_width
            if width == 1:
                return CType("bool", bit_width=1)
            prefix = "int" if is_signed else "uint"
            return CType(f"{prefix}{width}_t", is_signed=is_signed, bit_width=width)

        if ir_type.is_float:
            width = ir_type.bit_width
            if width == 16:
                return CType("half", bit_width=16)
            if width == 32:
                return CType("float", bit_width=32)
            if width == 64:
                return CType("double", bit_width=64)
            return CType("long double", bit_width=128)

        if ir_type.is_vector:
            return CType("vector128_t", bit_width=128)

        return CType("int64_t", bit_width=64)