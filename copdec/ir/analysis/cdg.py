from typing import Dict, Set
from ..core.cfg import Function, BasicBlock
from .post_dominance import PostDominanceTree
from ...pipeline.scope import BaseScope


class ControlDependenceGraph:
    """
    Control Dependence Graph (CDG):
    Determines which conditional branches directly govern execution of each BasicBlock.
    """
    __slots__ = ('_func', '_pdom_tree', '_dependencies', '_dependents')

    def __init__(self, scope: BaseScope):
        self._func: Function = scope.artifact
        self._pdom_tree: PostDominanceTree = scope.get_analysis(PostDominanceTree)
        self._dependencies: Dict[BasicBlock, Set[BasicBlock]] = {b: set() for b in self._func.blocks}
        self._dependents: Dict[BasicBlock, Set[BasicBlock]] = {b: set() for b in self._func.blocks}

        self._build_cdg()

    @property
    def dependencies(self) -> Dict[BasicBlock, Set[BasicBlock]]:
        return self._dependencies

    @property
    def dependents(self) -> Dict[BasicBlock, Set[BasicBlock]]:
        return self._dependents

    def get_controlling_branches(self, block: BasicBlock) -> Set[BasicBlock]:
        return self._dependencies.get(block, set())

    def get_dependent_blocks(self, branch_block: BasicBlock) -> Set[BasicBlock]:
        return self._dependents.get(branch_block, set())

    def _build_cdg(self) -> None:
        pdf = self._pdom_tree.post_dominance_frontiers
        for y, x_set in pdf.items():
            for x in x_set:
                if x in self._dependencies and y in self._dependents:
                    self._dependencies[y].add(x)
                    self._dependents[x].add(y)