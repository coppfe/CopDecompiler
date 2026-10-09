from typing import List, Tuple
from .base import CASTNode
from .stmt import CBlock
from ..types import CType


class CFunction(CASTNode):
    """Top-level C function representation."""
    __slots__ = ('name', 'return_type', 'params', 'body')

    def __init__(
        self,
        name: str,
        return_type: CType,
        params: List[Tuple[str, CType]],
        body: CBlock
    ):
        self.name: str = name
        self.return_type: CType = return_type
        self.params: List[Tuple[str, CType]] = params
        self.body: CBlock = body

    def __repr__(self) -> str:
        return f"<CFunction {self.name}(...) -> {self.return_type}>"