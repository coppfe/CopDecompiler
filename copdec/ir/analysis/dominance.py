from typing import Dict, List, Set, Optional, Tuple
from ..core.cfg import Function, BasicBlock
from ...pipeline.scope import BaseScope


class DominanceTree:
    """
    Computes Immediate Dominators (idom) and Dominance Frontiers (DF)
    using Cooper-Harvey-Kennedy algorithm.
    Provides O(1) dominance queries via DFS interval timestamps.
    """
    __slots__ = (
        '_func', '_entry', '_post_order', '_post_order_num',
        '_idom', '_dom_frontiers', '_dom_tree_succs',
        '_dfs_in', '_dfs_out', '_dfs_counter'
    )

    def __init__(self, scope: BaseScope):
        self._func: Function = scope.artifact
        self._entry: Optional[BasicBlock] = self._func.entry_block
        self._post_order: List[BasicBlock] = []
        self._post_order_num: Dict[BasicBlock, int] = {}
        self._idom: Dict[BasicBlock, BasicBlock] = {}
        self._dom_frontiers: Dict[BasicBlock, Set[BasicBlock]] = {b: set() for b in self._func.blocks}
        self._dom_tree_succs: Dict[BasicBlock, List[BasicBlock]] = {b: [] for b in self._func.blocks}
        self._dfs_in: Dict[BasicBlock, int] = {}
        self._dfs_out: Dict[BasicBlock, int] = {}
        self._dfs_counter: int = 0

        if self._entry is not None:
            self._compute_post_order()
            self._compute_idom()
            self._build_tree_and_dfs()
            self._compute_frontiers()

    @property
    def idom(self) -> Dict[BasicBlock, BasicBlock]:
        return self._idom

    @property
    def dominance_frontiers(self) -> Dict[BasicBlock, Set[BasicBlock]]:
        return self._dom_frontiers

    def dominates(self, a: BasicBlock, b: BasicBlock) -> bool:
        """O(1) Dominance Query via DFS entry/exit interval inclusion."""
        if a is b:
            return True
        if a not in self._dfs_in or b not in self._dfs_in:
            return False
        return self._dfs_in[a] <= self._dfs_in[b] and self._dfs_out[a] >= self._dfs_out[b]

    def _compute_post_order(self) -> None:
        if self._entry is None:
            return

        visited: Set[BasicBlock] = set()
        stack: List[Tuple[BasicBlock, int]] = [(self._entry, 0)]
        visited.add(self._entry)

        while stack:
            curr, succ_idx = stack[-1]

            if succ_idx < len(curr.successors):
                succ = curr.successors[succ_idx]
                stack[-1] = (curr, succ_idx + 1)

                if succ not in visited:
                    visited.add(succ)
                    stack.append((succ, 0))
            else:
                stack.pop()
                self._post_order_num[curr] = len(self._post_order)
                self._post_order.append(curr)

    def _intersect(self, b1: BasicBlock, b2: BasicBlock) -> BasicBlock:
        finger1 = b1
        finger2 = b2
        while finger1 is not finger2:
            while self._post_order_num[finger1] < self._post_order_num[finger2]:
                finger1 = self._idom[finger1]
            while self._post_order_num[finger2] < self._post_order_num[finger1]:
                finger2 = self._idom[finger2]
        return finger1

    def _compute_idom(self) -> None:
        if self._entry is None:
            return

        self._idom[self._entry] = self._entry
        changed = True
        rpo = self._post_order[::-1]

        while changed:
            changed = False
            for block in rpo:
                if block is self._entry:
                    continue

                processed_preds = [p for p in block.predecessors if p in self._idom]
                if not processed_preds:
                    continue

                new_idom = processed_preds[0]
                for p in processed_preds[1:]:
                    new_idom = self._intersect(p, new_idom)

                if self._idom.get(block) is not new_idom:
                    self._idom[block] = new_idom
                    changed = True

    def _build_tree_and_dfs(self) -> None:
        """Constructs explicit dominance tree edges and computes DFS interval timestamps."""
        for b, parent in self._idom.items():
            if b is not parent and parent in self._dom_tree_succs:
                self._dom_tree_succs[parent].append(b)

        if self._entry is None:
            return

        self._dfs_counter = 0
        stack: List[Tuple[BasicBlock, int]] = [(self._entry, 0)]
        self._dfs_counter += 1
        self._dfs_in[self._entry] = self._dfs_counter

        while stack:
            curr, child_idx = stack[-1]
            children = self._dom_tree_succs.get(curr, [])

            if child_idx < len(children):
                child = children[child_idx]
                stack[-1] = (curr, child_idx + 1)
                self._dfs_counter += 1
                self._dfs_in[child] = self._dfs_counter
                stack.append((child, 0))
            else:
                stack.pop()
                self._dfs_counter += 1
                self._dfs_out[curr] = self._dfs_counter

    def _compute_frontiers(self) -> None:
        for block in self._func.blocks:
            if len(block.predecessors) >= 2:
                for pred in block.predecessors:
                    runner = pred
                    while runner is not self._idom.get(block) and runner in self._idom:
                        self._dom_frontiers[runner].add(block)
                        runner = self._idom[runner]