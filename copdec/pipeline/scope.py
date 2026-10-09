from abc import ABC, abstractmethod
from typing import Optional, Any, Type, TypeVar, Dict
from ..target.binary.memory import BinaryMemoryView

T = TypeVar('T')


class BaseScope(ABC):
    """
    Strict, self-contained Execution Scope.
    Provides uniform access to artifacts, memory, metadata,
    automatic analysis caching, and transparent attribute delegation.
    """
    __slots__ = ('memory', 'metadata', '_analysis_cache')

    def __init__(self, memory: Optional[BinaryMemoryView] = None):
        self.memory: Optional[BinaryMemoryView] = memory
        self.metadata: Dict[str, Any] = {}
        self._analysis_cache: Dict[Type[Any], Any] = {}

    @property
    @abstractmethod
    def artifact(self) -> Any:
        """Returns the core entity (Function for IR, CFunction for AST)."""
        pass

    def get_analysis(self, analysis_cls: Type[T]) -> T:
        """
        Unified Analysis Factory:
        Every analysis strictly implements Analysis(scope). Zero hasattr inspection.
        """
        if analysis_cls not in self._analysis_cache:
            self._analysis_cache[analysis_cls] = analysis_cls(self)
        return self._analysis_cache[analysis_cls]

    def get_analysis_optional(self, analysis_cls: Type[T]) -> Optional[T]:
        """Safely returns computed analysis or None if analysis fails/unsupported."""
        try:
            return self.get_analysis(analysis_cls)
        except Exception:
            return None

    def invalidate_analyses(self) -> None:
        """Flushes analysis cache on state mutations."""
        self._analysis_cache.clear()

    def __getattr__(self, item: str) -> Any:
        """Transparent delegation: scope.blocks -> scope.artifact.blocks."""
        return getattr(self.artifact, item)