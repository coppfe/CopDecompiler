from enum import IntEnum, auto
from typing import List, Any
from .passer import Pass
from .context import PipelineContext


class ExecutionPolicy(IntEnum):
    """Execution strategy for a pipeline layer."""
    ONCE     = auto()  # Executes passes in sequence exactly once
    FIXPOINT = auto()  # Iterates passes until convergence or max_iterations


class PassLayer:
    """
    Modular execution layer managing sub-passes and lifecycle hooks (setUp / tearDown)
    strictly over ctx.scope.
    """
    __slots__ = ('name', 'policy', 'max_iterations', 'passes')

    def __init__(
        self,
        name: str,
        policy: ExecutionPolicy = ExecutionPolicy.ONCE,
        max_iterations: int = 4
    ):
        self.name: str = name
        self.policy: ExecutionPolicy = policy
        self.max_iterations: int = max(1, max_iterations)
        self.passes: List[Pass] = []

    def add_pass(self, p: Pass) -> 'PassLayer':
        self.passes.append(p)
        return self

    def setUp(self, ctx: PipelineContext) -> None:
        """Lifecycle hook: prepares or wraps ctx.scope before passes execute."""
        pass

    def tearDown(self, ctx: PipelineContext) -> None:
        """Lifecycle hook: cleans up or transfers state after passes execute."""
        pass

    def run(self, ctx: PipelineContext) -> bool:
        self.setUp(ctx)
        changed = False

        try:
            scope = ctx.scope
            if not self.passes or scope is None:
                return False

            if self.policy == ExecutionPolicy.ONCE:
                for p in self.passes:
                    if p.run(scope):
                        changed = True
                        scope.invalidate_analyses()

            elif self.policy == ExecutionPolicy.FIXPOINT:
                for _ in range(self.max_iterations):
                    iter_changed = False
                    for p in self.passes:
                        if p.run(scope):
                            iter_changed = True
                            changed = True
                            scope.invalidate_analyses()
                    if not iter_changed:
                        break
        finally:
            self.tearDown(ctx)

        return changed

    def __repr__(self) -> str:
        return f"<PassLayer '{self.name}' policy={self.policy.name} passes={len(self.passes)}>"