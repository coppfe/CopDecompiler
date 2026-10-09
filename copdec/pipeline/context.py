from typing import Optional, Any, TYPE_CHECKING
from ..target.binary.memory import BinaryMemoryView

if TYPE_CHECKING:
    from .scope import BaseScope

class PipelineContext:
    """
    Ultra-lean Session Pipeline Context.
    Only holds binary memory, current active execution Scope,
    the final decompiler result, and optional session annotations.
    """
    __slots__ = ('memory', 'scope', 'result', 'annotations')

    def __init__(
        self,
        memory: Optional[BinaryMemoryView] = None,
        initial_scope: Optional[Any] = None
    ):
        self.memory: Optional[BinaryMemoryView] = memory
        self.scope: Optional['BaseScope'] = initial_scope
        self.result: Optional[Any] = None
        self.annotations: dict[str, Any] = {}

    @property
    def has_scope(self) -> bool:
        return self.scope is not None


AnalysisContext = PipelineContext