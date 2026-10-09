from ...pipeline.layer import PassLayer, ExecutionPolicy
from ...pipeline.context import PipelineContext
from .scope import IRScope
from ...ir.core.cfg import Function


class IRLayer(PassLayer):
    """
    Execution layer for IR optimization passes (pipeline/ir/).
    In setUp(), guarantees that ctx.scope is wrapped into a valid IRScope.
    """
    __slots__ = ()

    def setUp(self, ctx: PipelineContext) -> None:
        if not isinstance(ctx.scope, IRScope):
            if isinstance(ctx.scope, Function):
                ctx.scope = IRScope(ctx.scope, memory=ctx.memory)
            elif hasattr(ctx.scope, 'func'):
                ctx.scope = IRScope(ctx.scope.func, memory=ctx.memory)
            else:
                raise TypeError(f"Cannot initialize IRScope from target: {type(ctx.scope)}")