from typing import Optional

from ..opcodes import IROpcode
from ..types.base import Type
from ..core.value import Value
from ..core.cfg import Instruction


class CastInst(Instruction):
    """
    Represents explicit type conversion operations:
      %dst = opcode %src to %dest_type
    Supported opcodes: TRUNC, ZEXT, SEXT, FPTRUNC, FPEXT, FPTOSI, FPTOUI,
                       SITOFP, UITOFP, BITCAST, PTRTOINT, INTTOPTR.
    """
    __slots__ = ('_opcode')

    def __init__(self, opcode: IROpcode, src: Value, dest_type: Type, name: str = "", pc: int = 0):
        assert isinstance(dest_type, Type), "dest_type must be an instance of Type"
        self._validate_cast(opcode, src.type, dest_type)
        super().__init__(dest_type, name=name, pc=pc)
        self._opcode = opcode
        self.add_operand(src)

    @property
    def opcode(self) -> IROpcode:
        return self._opcode

    @property
    def src(self) -> Value:
        return self.get_operand(0)

    @property
    def dest_type(self) -> Type:
        return self.type

    @staticmethod
    def _validate_cast(opcode: IROpcode, src_type: Type, dest_type: Type) -> None:
        if opcode == IROpcode.TRUNC:
            if not (src_type.is_integer and dest_type.is_integer and src_type.bit_width > dest_type.bit_width):
                raise TypeError(f"Invalid Trunc: {src_type} -> {dest_type} (source must be wider)")
        elif opcode in (IROpcode.ZEXT, IROpcode.SEXT):
            if not (src_type.is_integer and dest_type.is_integer and src_type.bit_width < dest_type.bit_width):
                raise TypeError(f"Invalid {opcode.name}: {src_type} -> {dest_type} (dest must be wider)")
        elif opcode == IROpcode.FPTRUNC:
            if not (src_type.is_float and dest_type.is_float and src_type.bit_width > dest_type.bit_width):
                raise TypeError(f"Invalid FPTrunc: {src_type} -> {dest_type}")
        elif opcode == IROpcode.FPEXT:
            if not (src_type.is_float and dest_type.is_float and src_type.bit_width < dest_type.bit_width):
                raise TypeError(f"Invalid FPExt: {src_type} -> {dest_type}")
        elif opcode in (IROpcode.FPTOSI, IROpcode.FPTOUI):
            if not (src_type.is_float and dest_type.is_integer):
                raise TypeError(f"Invalid {opcode.name}: {src_type} -> {dest_type}")
        elif opcode in (IROpcode.SITOFP, IROpcode.UITOFP):
            if not (src_type.is_integer and dest_type.is_float):
                raise TypeError(f"Invalid {opcode.name}: {src_type} -> {dest_type}")
        elif opcode == IROpcode.BITCAST:
            if src_type.bit_width != dest_type.bit_width:
                raise TypeError(f"Invalid BitCast: {src_type} -> {dest_type} (bit widths must match)")
        elif opcode == IROpcode.PTRTOINT:
            if not (src_type.is_pointer and dest_type.is_integer):
                raise TypeError(f"Invalid PtrToInt: {src_type} -> {dest_type}")
        elif opcode == IROpcode.INTTOPTR:
            if not (src_type.is_integer and dest_type.is_pointer):
                raise TypeError(f"Invalid IntToPtr: {src_type} -> {dest_type}")
        else:
            raise ValueError(f"Unsupported cast opcode: {opcode}")

    def __repr__(self) -> str:
        return f"%{self.name} = {self._opcode.name.lower()} {self.src.type} {self.src} to {self.dest_type}"