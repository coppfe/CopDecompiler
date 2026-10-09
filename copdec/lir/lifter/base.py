from abc import ABC, abstractmethod
from typing import Optional, Any, List
from ..nodes import LIRExpr, LIRInsn
from ..block import LIRBlock, LIRFunction
from ...insn import Insn


class BaseLifterContext(ABC):
    """
    Abstract Lifter Context managing LIR block emissions and target operand translation.
    """
    __slots__ = ('_block', '_arch_bits', '_pc')

    def __init__(self, arch_bits: int):
        self._block: Optional[LIRBlock] = None
        self._arch_bits: int = arch_bits
        self._pc: int = 0

    @property
    def block(self) -> LIRBlock:
        assert self._block is not None, "Active LIRBlock is not set in context"
        return self._block

    @property
    def arch_bits(self) -> int:
        return self._arch_bits

    @property
    def pc(self) -> int:
        return self._pc

    def set_block(self, block: LIRBlock) -> None:
        self._block = block

    def set_pc(self, pc: int) -> None:
        self._pc = pc

    def emit(self, insn: LIRInsn) -> None:
        """Appends instruction to active block, automatically stamping current PC."""
        if insn.pc == 0:
            insn.pc = self._pc
        self.block.append(insn)

    @abstractmethod
    def read(self, op: Any) -> LIRExpr:
        pass

    @abstractmethod
    def write(self, dst: Any, expr: LIRExpr) -> None:
        pass


class BaseLifter(ABC):
    """Abstract Target Instruction Lifter."""
    __slots__ = ()

    @classmethod
    @abstractmethod
    def lift(cls, insns: List[Insn], func_name: str = "sub_entry") -> LIRFunction:
        pass