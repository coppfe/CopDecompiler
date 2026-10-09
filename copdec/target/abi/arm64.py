from typing import Optional, Dict, FrozenSet
from ...const import Arch
from .base import TargetABI


class ARM64ABI(TargetABI):
    """
    Standard AAPCS64 (AArch64) Application Binary Interface Implementation.
    Complies with -fomit-frame-pointer: x29 is treated strictly as a callee-saved GPR.
    """
    __slots__ = ()

    _SP_NAMES: FrozenSet[str] = frozenset({"sp", "wsp"})

    # Argument index mappings (0-based indices for x0-x7, w0-w7, d0-d7, s0-s7, v0-v7)
    _ARG_INDICES: Dict[str, int] = {
        **{f"x{i}": i for i in range(8)},
        **{f"w{i}": i for i in range(8)},
        **{f"d{i}": i for i in range(8)},
        **{f"s{i}": i for i in range(8)},
        **{f"v{i}": i for i in range(8)},
        **{f"q{i}": i for i in range(8)},
    }

    # Callee-saved (non-volatile) registers: x19-x28, x29 (fp), x30 (lr), d8-d15
    # x29 is always callee-saved by ABI, regardless of whether FP is omitted or used
    _CALLEE_SAVED: FrozenSet[str] = frozenset({
        *(f"x{i}" for i in range(19, 29)),
        *(f"w{i}" for i in range(19, 29)),
        "x29", "w29", "fp",
        "x30", "w30", "lr",
        *(f"d{i}" for i in range(8, 16)),
        *(f"s{i}" for i in range(8, 16)),
        *(f"v{i}" for i in range(8, 16)),
    })

    # Return value registers: x0-x7, d0-d7
    _RETURN_REGS: FrozenSet[str] = frozenset({
        *(f"x{i}" for i in range(8)),
        *(f"w{i}" for i in range(8)),
        *(f"d{i}" for i in range(8)),
        *(f"s{i}" for i in range(8)),
    })

    _SYS_REGS: FrozenSet[str] = frozenset({
        "tpidr_el0"
    })

    @property
    def arch(self) -> Arch:
        return Arch.ARM64

    @property
    def max_register_args(self) -> int:
        return 8

    @property
    def stack_pointer_name(self) -> str:
        return "sp"

    def is_stack_pointer(self, name: str) -> bool:
        return name.lower() in self._SP_NAMES

    def is_arg_register(self, name: str) -> bool:
        return name.lower() in self._ARG_INDICES

    def is_sys_register(self, name):
        return name.lower() in self._SYS_REGS

    def get_argument_index(self, name: str) -> Optional[int]:
        return self._ARG_INDICES.get(name.lower())

    def is_callee_saved(self, name: str) -> bool:
        return name.lower() in self._CALLEE_SAVED

    def is_return_register(self, name: str) -> bool:
        return name.lower() in self._RETURN_REGS