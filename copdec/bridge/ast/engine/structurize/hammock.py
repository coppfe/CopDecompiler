from typing import Optional, Tuple, Set, List
from .....ir.core.cfg import BasicBlock
from .....ir.opcodes import IROpcode
from .....ir.analysis.dominance import DominanceTree
from .....ir.analysis.post_dominance import PostDominanceTree
from .....ir.analysis.loops import Loop


class HammockAnalyzer:
    __slots__ = ('_dom_tree', '_pdom_tree')

    def __init__(self, dom_tree: Optional[DominanceTree] = None, pdom_tree: Optional[PostDominanceTree] = None):
        self._dom_tree = dom_tree
        self._pdom_tree = pdom_tree

    @staticmethod
    def _is_terminal_block(bb: BasicBlock) -> bool:
        term = bb.get_terminator()
        return term is not None and term.opcode in (IROpcode.RET, IROpcode.UNREACHABLE)

    def _can_reach(self, start: BasicBlock, target: BasicBlock) -> bool:
        visited: Set[BasicBlock] = set()
        queue: List[BasicBlock] = [start]
        visited.add(start)
        while queue:
            curr = queue.pop(0)
            if curr is target:
                return True
            for succ in curr.successors:
                if succ not in visited:
                    visited.add(succ)
                    queue.append(succ)
        return False

    def find_merge_point(
        self,
        cond_block: BasicBlock,
        true_bb: BasicBlock,
        false_bb: BasicBlock,
        stop_block: Optional[BasicBlock],
        current_loop: Optional[Loop] = None
    ) -> Tuple[Optional[BasicBlock], bool, bool]:
        if false_bb is not true_bb and self._dom_tree is not None:
            if self._dom_tree.dominates(cond_block, true_bb):
                if any(succ is false_bb for succ in true_bb.successors):
                    return false_bb, True, False

        if false_bb is not true_bb and self._dom_tree is not None:
            if self._dom_tree.dominates(cond_block, false_bb):
                if any(succ is true_bb for succ in false_bb.successors):
                    return true_bb, True, True

        if self._is_terminal_block(true_bb) and not self._is_terminal_block(false_bb):
            if not self._can_reach(false_bb, true_bb):
                return false_bb, False, False
            else:
                return true_bb, False, True

        if self._is_terminal_block(false_bb) and not self._is_terminal_block(true_bb):
            if not self._can_reach(true_bb, false_bb):
                return true_bb, False, True
            else:
                return false_bb, False, False

        if self._pdom_tree is not None:
            ipdom = self._pdom_tree.ipdom.get(cond_block)
            if ipdom is not None and ipdom.name != "__unified_exit__" and ipdom is not cond_block:
                if ipdom is false_bb:
                    return false_bb, True, False
                if ipdom is true_bb:
                    return true_bb, True, True

                if current_loop is None or ipdom in current_loop.blocks:
                    if stop_block is None or ipdom is not stop_block:
                        return ipdom, False, False

        forward_merge = self._find_forward_merge_candidate(cond_block, true_bb, false_bb, current_loop)
        if forward_merge is not None:
            return forward_merge, False, False

        true_succs = set(true_bb.successors)
        false_succs = set(false_bb.successors)
        common_succs = true_succs.intersection(false_succs)
        if common_succs:
            candidate = next(iter(common_succs))
            if candidate is not cond_block and (current_loop is None or candidate in current_loop.blocks):
                return candidate, False, False

        return stop_block, False, False

    def _find_forward_merge_candidate(
        self,
        cond_block: BasicBlock,
        true_bb: BasicBlock,
        false_bb: BasicBlock,
        current_loop: Optional[Loop] = None
    ) -> Optional[BasicBlock]:
        if self._dom_tree is None:
            return None

        def get_reachable(start: BasicBlock) -> Set[BasicBlock]:
            visited: Set[BasicBlock] = set()
            queue: List[BasicBlock] = [start]
            visited.add(start)
            while queue:
                curr = queue.pop(0)
                for s in curr.successors:
                    if s not in visited:
                        if current_loop is None or s in current_loop.blocks:
                            visited.add(s)
                            queue.append(s)
            return visited

        reach_true = get_reachable(true_bb)
        reach_false = get_reachable(false_bb)
        common = reach_true & reach_false

        valid_candidates = [
            b for b in common
            if b is not cond_block and self._dom_tree.dominates(cond_block, b)
        ]
        if not valid_candidates:
            return None

        earliest = valid_candidates[0]
        for cand in valid_candidates[1:]:
            if self._dom_tree.dominates(cand, earliest):
                earliest = cand

        return earliest