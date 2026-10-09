from typing import Optional
from ...pipeline.scope import BaseScope
from ...ast.nodes import CFunction
from ...target.binary.memory import BinaryMemoryView


class ASTScope(BaseScope):
    """
    AST Execution Scope.
    Proxies all CFunction attributes directly: scope.body, scope.params, etc.
    """
    __slots__ = ('cfunc',)

    def __init__(self, cfunc: CFunction, memory: Optional[BinaryMemoryView] = None):
        super().__init__(memory=memory)
        self.cfunc: CFunction = cfunc

    @property
    def artifact(self) -> CFunction:
        return self.cfunc