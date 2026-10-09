from typing import Dict, Tuple
from ..core.cfg import BasicBlock
from ..core.value import Value, ConstantInt, UndefValue
from .base import Type
from .integer import (
    Int1, Int8, Int16, Int32, Int64, Int128, IntegerType
)
from .composite import PointerType, Ptr32, Ptr64
from ..instructions.cast import CastInst
from ..opcodes import IROpcode


class TypeUtils:
    """
    Architecture-agnostic Type Resolution & Operand Coercion Utility.
    Enforces strict IR type equality for binary operations and memory sizing.
    """
    __slots__ = ()

    _INT_CACHE: Dict[int, Type] = {
        1: Int1,
        8: Int8,
        16: Int16,
        32: Int32,
        64: Int64,
        128: Int128,
    }

    @classmethod
    def get_int_type(cls, bit_width: int) -> Type:
        """Resolves an integer bit-width into an interned IntegerType."""
        cached = cls._INT_CACHE.get(bit_width)
        if cached is not None:
            return cached
        return IntegerType.get(bit_width)

    @classmethod
    def get_pointer_type(cls, arch_bits: int = 64) -> PointerType:
        """Resolves target pointer type based on machine address bit-width."""
        if arch_bits == 64:
            return Ptr64
        if arch_bits == 32:
            return Ptr32
        return PointerType.get_opaque(bit_width=arch_bits)

    @classmethod
    def coerce_to_type(
        cls,
        val: Value,
        target_type: Type,
        block: BasicBlock,
        signed: bool = False,
        pc: int = 0
    ) -> Value:
        """Coerces val to target_type using constant folding or explicit CastInst."""
        if val.type == target_type:
            return val

        if isinstance(val, UndefValue):
            return UndefValue.get(target_type)

        # 1. Compile-time constant folding
        if isinstance(val, ConstantInt) and target_type.is_integer:
            mask = target_type.mask  # type: ignore
            raw_val = val.value
            if signed and val.type.is_integer:
                raw_val = val.type.sign_extend(raw_val)  # type: ignore
            return ConstantInt.get(target_type, raw_val & mask)

        # 2. Pointer <-> Integer
        if val.type.is_pointer and target_type.is_integer:
            int_ptr_ty = cls.get_int_type(val.type.bit_width)
            p2i = CastInst(IROpcode.PTRTOINT, val, int_ptr_ty, name="p2i", pc=pc)
            block.append_instruction(p2i)
            return cls.coerce_to_type(p2i, target_type, block, signed=signed, pc=pc)

        if val.type.is_integer and target_type.is_pointer:
            int_target_ty = cls.get_int_type(target_type.bit_width)
            sized_int = cls.coerce_to_type(val, int_target_ty, block, signed=signed, pc=pc)
            i2p = CastInst(IROpcode.INTTOPTR, sized_int, target_type, name="i2p", pc=pc)
            block.append_instruction(i2p)
            return i2p

        # 3. Integer <-> Integer
        if val.type.is_integer and target_type.is_integer:
            if val.type.bit_width < target_type.bit_width:
                cast_op = IROpcode.SEXT if signed else IROpcode.ZEXT
            elif val.type.bit_width > target_type.bit_width:
                cast_op = IROpcode.TRUNC
            else:
                return val

            cast_inst = CastInst(cast_op, val, target_type, name="int_conv", pc=pc)
            block.append_instruction(cast_inst)
            return cast_inst

        # 4. Bitcast Fallback
        if val.type.bit_width == target_type.bit_width:
            bcast = CastInst(IROpcode.BITCAST, val, target_type, name="bcast", pc=pc)
            block.append_instruction(bcast)
            return bcast

        return val

    @classmethod
    def unify_binary_operands(
        cls,
        lhs: Value,
        rhs: Value,
        block: BasicBlock,
        signed: bool = False,
        pc: int = 0
    ) -> Tuple[Value, Value]:
        """Ensures lhs.type == rhs.type by promoting to the wider operand width."""
        if lhs.type == rhs.type:
            return lhs, rhs

        # Constant matching against dynamic value
        if isinstance(lhs, ConstantInt) and not isinstance(rhs, ConstantInt):
            return ConstantInt.get(rhs.type, lhs.value), rhs
        if isinstance(rhs, ConstantInt) and not isinstance(lhs, ConstantInt):
            return lhs, ConstantInt.get(lhs.type, rhs.value)

        target_width = max(lhs.type.bit_width, rhs.type.bit_width)
        target_type = cls.get_int_type(target_width)

        new_lhs = cls.coerce_to_type(lhs, target_type, block, signed=signed, pc=pc)
        new_rhs = cls.coerce_to_type(rhs, target_type, block, signed=signed, pc=pc)
        return new_lhs, new_rhs