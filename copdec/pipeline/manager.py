from typing import List, Optional, Any
from .passer import Pass
from .layer import PassLayer, ExecutionPolicy
from .context import PipelineContext
from ..target.binary.memory import BinaryMemoryView


class PassManager:
    """
    Clean Orchestrator of Pipeline Layers.
    Executes sequential transformations across IR, Bridge, and AST layers.
    """
    __slots__ = ('_layers',)

    def __init__(self):
        self._layers: List[PassLayer] = []

    @property
    def layers(self) -> List[PassLayer]:
        return self._layers

    def add_layer(self, layer: PassLayer) -> 'PassManager':
        self._layers.append(layer)
        return self

    def create_layer(
        self,
        name: str,
        policy: ExecutionPolicy = ExecutionPolicy.ONCE,
        max_iterations: int = 4
    ) -> PassLayer:
        layer = PassLayer(name=name, policy=policy, max_iterations=max_iterations)
        self._layers.append(layer)
        return layer

    def add_pass(self, p: Pass, layer_name: Optional[str] = None) -> 'PassManager':
        if layer_name is not None:
            target_layer = next((l for l in self._layers if l.name == layer_name), None)
            if target_layer is None:
                target_layer = self.create_layer(layer_name)
            target_layer.add_pass(p)
        else:
            if not self._layers:
                self.create_layer("default")
            self._layers[-1].add_pass(p)
        return self

    def clear(self) -> 'PassManager':
        self._layers.clear()
        return self

    def run(
        self,
        target: Any,
        memory: Optional[BinaryMemoryView] = None
    ) -> Any:
        """
        Runs the full pipeline.
        `target` is the initial input (e.g. IRFunction or an existing PipelineContext).
        Returns the final generated artifact (e.g. CFunction).
        """
        if not self._layers:
            return target

        if isinstance(target, PipelineContext):
            ctx = target
        else:
            ctx = PipelineContext(
                memory=memory,
                initial_scope=target
            )

        for layer in self._layers:
            layer.run(ctx)

        if ctx.result is not None:
            return ctx.result
        if ctx.scope is not None:
            return ctx.scope.artifact
        return None

    # =========================================================================
    # Factory Presets (Stubs to be rewritten under the new architecture)
    # =========================================================================

    @classmethod
    def empty(cls) -> 'PassManager':
        from ..bridge.ir.layer import IRLayer
        from ..bridge.ast.layer import ASTBridgeLayer

        pm = cls()

        pm.add_layer(IRLayer("ir_raw"))

        pm.add_layer(ASTBridgeLayer())

        return pm

    @classmethod
    def standard(cls) -> 'PassManager':
        from ..bridge.ir.layer import IRLayer
        from ..bridge.ast.layer import ASTBridgeLayer, ASTLayer

        # IR Passes
        from ..ir.passes.instcombine import InstCombinePass
        from ..ir.passes.cfg_simplify import CFGSimplifyPass
        from ..ir.passes.dce import ADCEPass
        from ..ir.passes.abi_cleanup import CallingConventionCleanupPass
        from ..ir.passes.stack_frame import StackFramePromotionPass

        # AST Passes
        from ..ast.passes.inliner import ExpressionInlinerPass
        from ..ast.passes.cast_norm import CastNormalizerPass
        from ..ast.passes.loop_refiner import LoopRefinerPass
        from ..ast.passes.condition_norm import ConditionNormalizerPass
        from ..ast.passes.dead_code import DeadCodePrunerPass
        from ..ast.passes.expr_simplifier import ExpressionSimplifierPass

        pm = cls()

        ir_opt = IRLayer("ir_optimization", policy=ExecutionPolicy.FIXPOINT, max_iterations=4)
        ir_opt.add_pass(InstCombinePass())
        ir_opt.add_pass(CFGSimplifyPass())
        ir_opt.add_pass(ADCEPass())
        ir_opt.add_pass(CallingConventionCleanupPass())
        ir_opt.add_pass(StackFramePromotionPass())
        pm.add_layer(ir_opt)

        pm.add_layer(ASTBridgeLayer())

        ast_opt = ASTLayer("ast_optimization", policy=ExecutionPolicy.FIXPOINT, max_iterations=4)
        ast_opt.add_pass(ExpressionInlinerPass())
        ast_opt.add_pass(ExpressionSimplifierPass())
        ast_opt.add_pass(CastNormalizerPass())
        ast_opt.add_pass(LoopRefinerPass())
        ast_opt.add_pass(ConditionNormalizerPass())
        ast_opt.add_pass(DeadCodePrunerPass())

        pm.add_layer(ast_opt)
        return pm