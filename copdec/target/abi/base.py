from abc import ABC, abstractmethod
from typing import Optional
from ...const import Arch


class TargetABI(ABC):
    """
    Abstract Calling Convention & Register Role Specification.
    Strictly describes hardware ABI boundaries without assumptions about compiler flags.
    """
    __slots__ = ()

    @property
    @abstractmethod
    def arch(self) -> Arch:
        """Target architecture associated with this ABI."""
        pass

    @property
    @abstractmethod
    def max_register_args(self) -> int:
        """Maximum number of arguments passed via architectural registers."""
        pass

    @property
    @abstractmethod
    def stack_pointer_name(self) -> str:
        """Canonical name of the stack pointer register."""
        pass

    @abstractmethod
    def is_stack_pointer(self, name: str) -> bool:
        """Predicate checking if register is the hardware stack pointer (sp/rsp)."""
        pass

    @abstractmethod
    def is_arg_register(self, name: str) -> bool:
        """Predicate checking if register is an architectural incoming parameter."""
        pass

    @abstractmethod
    def is_sys_register(self, name: str) -> bool:
        """Predicate checking if register is an system register"""
        pass

    @abstractmethod
    def get_argument_index(self, name: str) -> Optional[int]:
        """Returns the 0-based logical parameter index (a0, a1...) if name is an arg register, else None."""
        pass

    @abstractmethod
    def is_callee_saved(self, name: str) -> bool:
        """Predicate checking if register must be preserved across subroutine calls."""
        pass

    @abstractmethod
    def is_return_register(self, name: str) -> bool:
        """Predicate checking if register is used to return scalar or vector results."""
        pass