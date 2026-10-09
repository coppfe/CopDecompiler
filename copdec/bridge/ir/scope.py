from typing import Optional
from ...pipeline.scope import BaseScope
from ...ir.core.cfg import Function
from ...target.binary.memory import BinaryMemoryView


class IRScope(BaseScope):
    """
    IR Execution Scope.
    Proxies all Function attributes directly: scope.blocks, scope.entry_block, etc.
    """
    __slots__ = ('func',)

    def __init__(self, func: Function, memory: Optional[BinaryMemoryView] = None):
        super().__init__(memory=memory)
        self.func: Function = func

    @property
    def artifact(self) -> Function:
        return self.func