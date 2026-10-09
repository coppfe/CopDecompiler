from typing import Optional
from ...pipeline.layer import PassLayer, ExecutionPolicy
from ...pipeline.context import PipelineContext
from ..ir.scope import IRScope
from .scope import ASTScope
from .engine.structurizer import ControlFlowStructurizer


class ASTBridgeLayer(PassLayer):
    """
    Representation Bridge Layer:
    Transforms IRScope into ASTScope via ControlFlowStructurizer.
    Transitions the pipeline from IR domain to AST domain.
    """
    __slots__ = ()

    def __init__(self, name: str = "ast_bridge"):
        super().__init__(name=name, policy=ExecutionPolicy.ONCE)

    def run(self, ctx: PipelineContext) -> bool:
        if not isinstance(ctx.scope, IRScope):
            raise TypeError(f"ASTBridgeLayer expects active IRScope, got: {type(ctx.scope)}")

        structurizer = ControlFlowStructurizer(ctx.scope)
        cfunc = structurizer.structurize()

        ctx.scope = ASTScope(cfunc=cfunc, memory=ctx.memory)
        return True

class ASTLayer(PassLayer):
    """
    Execution layer for AST optimization passes (pipeline/ast/).
    Operates strictly over an active ASTScope.
    """
    __slots__ = ()

    def setUp(self, ctx: PipelineContext) -> None:
        if not isinstance(ctx.scope, ASTScope):
            raise TypeError(f"ASTLayer expects active ASTScope, got: {type(ctx.scope)}")