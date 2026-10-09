from abc import ABC, abstractmethod
from typing import Any


class Pass(ABC):
    """
    Universal compiler pass contract.
    Operates strictly on the scope provided by the executing Layer.
    """
    __slots__ = ()

    @property
    def name(self) -> str:
        return self.__class__.__name__

    @abstractmethod
    def run(self, scope: Any) -> bool:
        """
        Executes optimization or analysis over the given scope.
        Returns True if the underlying artifact was mutated.
        """
        pass


IRPass = Pass