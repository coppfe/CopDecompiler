from typing import List, Dict, Type
from ....const import Arch
from ....insn import Insn
from ...block import LIRFunction
from ..base import BaseLifter, BaseLifterContext
from ..arm64.lifter import ARM64LIRLifter

LIFTER_REGISTRY: Dict[Arch, Type[BaseLifter]] = {
    Arch.ARM64: ARM64LIRLifter,
}


class LIRLifter:
    """Unified Target-Agnostic LIR Lifter Facade."""
    __slots__ = ()

    @staticmethod
    def lift_function(insns: List['Insn'], arch: Arch = Arch.ARM64, func_name: str = "sub_entry") -> LIRFunction:
        lifter_cls = LIFTER_REGISTRY.get(arch)
        if lifter_cls is None:
            raise NotImplementedError(f"No LIR Lifter registered for architecture: {arch.name}")
        return lifter_cls.lift(insns, func_name=func_name)


__all__ = ['LIRLifter', 'BaseLifter', 'BaseLifterContext', 'ARM64LIRLifter']