from typing import Dict, List, Set, Tuple
from ..core.cfg import Function, BasicBlock
from ...pipeline.scope import BaseScope


class PostDominanceTree:
    """
    Computes Immediate Post-Dominators (ipdom) and Post-Dominance Frontiers (PDF)
    over reversed Control Flow Graph (CFG^rev) using a unified exit root.
    """
    __slots__ = ('_func', '_virtual_exit', '_post_order', '_post_order_num', '_ipdom', '_post_dom_frontiers')

    def __init__(self, scope: BaseScope):
        self._func: Function = scope.artifact
        self._virtual_exit: BasicBlock = BasicBlock(name="__unified_exit__")
        self._post_order: List[BasicBlock] = []
        self._post_order_num: Dict[BasicBlock, int] = {}
        self._ipdom: Dict[BasicBlock, BasicBlock] = {}
        self._post_dom_frontiers: Dict[BasicBlock, Set[BasicBlock]] = {b: set() for b in self._func.blocks}

        if self._func.blocks:
            self._compute_post_order()
            self._compute_ipdom()
            self._compute_frontiers()

    @property
    def ipdom(self) -> Dict[BasicBlock, BasicBlock]:
        return self._ipdom

    @property
    def post_dominance_frontiers(self) -> Dict[BasicBlock, Set[BasicBlock]]:
        return self._post_dom_frontiers

    def post_dominates(self, a: BasicBlock, b: BasicBlock) -> bool:
        if a is b:
            return True
        if b not in self._ipdom:
            return False
        if a is self._virtual_exit:
            return True

        curr = b
        visited: Set[BasicBlock] = set()

        while curr in self._ipdom and curr is not self._virtual_exit:
            visited.add(curr)
            curr = self._ipdom[curr]
            if curr is a:
                return True
            if curr in visited:
                break

        return False

    def _get_rev_successors(self, block: BasicBlock) -> List[BasicBlock]:
        if block is self._virtual_exit:
            exits = [b for b in self._func.blocks if not b.successors]
            return exits
        return block.predecessors

    def _get_rev_predecessors(self, block: BasicBlock) -> List[BasicBlock]:
        if not block.successors:
            return [self._virtual_exit]
        return block.successors

    def _compute_post_order(self) -> None:
        visited: Set[BasicBlock] = set()
        stack: List[Tuple[BasicBlock, int]] = [(self._virtual_exit, 0)]
        visited.add(self._virtual_exit)

        while stack:
            curr, succ_idx = stack[-1]
            rev_succs = self._get_rev_successors(curr)

            if succ_idx < len(rev_succs):
                succ = rev_succs[succ_idx]
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
                finger1 = self._ipdom[finger1]
            while self._post_order_num[finger2] < self._post_order_num[finger1]:
                finger2 = self._ipdom[finger2]
        return finger1

    def _compute_ipdom(self) -> None:
        self._ipdom[self._virtual_exit] = self._virtual_exit
        changed = True
        rpo = self._post_order[::-1]

        while changed:
            changed = False
            for node in rpo:
                if node is self._virtual_exit:
                    continue

                processed_preds = [p for p in self._get_rev_predecessors(node) if p in self._ipdom]
                if not processed_preds:
                    continue

                new_ipdom = processed_preds[0]
                for p in processed_preds[1:]:
                    new_idom = self._intersect(p, new_ipdom)

                if self._ipdom.get(node) is not new_ipdom:
                    self._ipdom[node] = new_idom
                    changed = True

    def _compute_frontiers(self) -> None:
        for node in self._func.blocks:
            rev_preds = self._get_rev_predecessors(node)
            if len(rev_preds) >= 2:
                for pred in rev_preds:
                    runner = pred
                    while runner is not self._ipdom.get(node) and runner in self._ipdom and runner is not self._virtual_exit:
                        if runner in self._post_dom_frontiers:
                            self._post_dom_frontiers[runner].add(node)
                        runner = self._ipdom[runner]