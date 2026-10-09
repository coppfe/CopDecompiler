from typing import Optional, Set, Tuple, List, Any
from .....ir.core.cfg import Function, BasicBlock
from .....ir.opcodes import IROpcode
from .....ir.analysis.dominance import DominanceTree
from .....ir.analysis.post_dominance import PostDominanceTree
from .....ir.analysis.loops import LoopInfo, Loop
# from .....ir.instructions.control import SwitchInst

from .hammock import HammockAnalyzer
from .region import (
    BlockRegion, SeqRegion, IfRegion, LoopRegion,
    BreakRegion, ContinueRegion, GotoRegion, SwitchRegion, CaseRegion
)

class ControlTreeBuilder:
    __slots__ = (
        '_func', '_dom_tree', '_pdom_tree', '_loop_info',
        '_hammock_analyzer', '_visited', 'labels_in_use'
    )

    def __init__(
        self,
        func: Function,
        dom_tree: Optional[DominanceTree] = None,
        pdom_tree: Optional[PostDominanceTree] = None,
        loop_info: Optional[LoopInfo] = None
    ):
        self._func = func
        self._dom_tree = dom_tree
        self._pdom_tree = pdom_tree
        self._loop_info = loop_info
        self._hammock_analyzer = HammockAnalyzer(dom_tree, pdom_tree)

        self._visited: Set[BasicBlock] = set()
        self.labels_in_use: Set[str] = set()

    def build(self) -> SeqRegion:
        if not self._func.entry_block:
            return SeqRegion()
        return self._build_sequence(
            curr=self._func.entry_block,
            stop_block=None,
            current_loop=None
        )

    def _build_sequence(
        self,
        curr: Optional[BasicBlock],
        stop_block: Optional[BasicBlock],
        current_loop: Optional[Loop]
    ) -> SeqRegion:
        seq = SeqRegion()
        node = curr

        while node is not None and node is not stop_block:
            if current_loop is not None and node is current_loop.header:
                seq.append(ContinueRegion())
                return seq

            if node in self._visited:
                seq.append(GotoRegion(node.name))
                self.labels_in_use.add(node.name)
                return seq

            self._visited.add(node)

            if self._loop_info is not None:
                loop = self._loop_info.get_loop_for(node)
                if loop is not None and loop.header is node and loop is not current_loop:
                    loop_region, next_node = self._build_loop(node, loop, stop_block)
                    seq.append(loop_region)
                    node = next_node
                    continue

            seq.append(BlockRegion(node))
            term = node.get_terminator()
            if term is None:
                break

            if term.opcode == IROpcode.RET:
                break

            elif term.opcode == IROpcode.BR:
                target = term.target
                if target is stop_block:
                    break

                if current_loop and target is current_loop.header:
                    seq.append(ContinueRegion())
                    break

                if current_loop and target in current_loop.get_exit_blocks():
                    if stop_block and target is stop_block:
                        break
                    seq.append(BreakRegion())
                    break

                if target in self._visited:
                    seq.append(GotoRegion(target.name))
                    self.labels_in_use.add(target.name)
                    break

                node = target

            elif term.opcode == IROpcode.BR_COND:
                if_reg, merge_bb = self._build_if(node, term, stop_block, current_loop)
                seq.append(if_reg)
                node = merge_bb

            elif term.opcode == IROpcode.SWITCH:
                merge_bb = None
                if self._pdom_tree is not None:
                    ipdom = self._pdom_tree.ipdom.get(node)
                    if ipdom is not None and ipdom.name != "__unified_exit__" and ipdom is not node:
                        merge_bb = ipdom
                if merge_bb is None:
                    merge_bb = stop_block

                cases_list: List[CaseRegion] = []
                for val, target_bb in term.cases:
                    case_body = self._build_sequence(target_bb, stop_block=merge_bb, current_loop=current_loop)
                    cases_list.append(CaseRegion(val=val, body=case_body, is_default=False))

                def_region = None
                if term.default_block is not None and term.default_block is not merge_bb:
                    def_body = self._build_sequence(term.default_block, stop_block=merge_bb, current_loop=current_loop)
                    def_region = CaseRegion(val=None, body=def_body, is_default=True)

                switch_reg = SwitchRegion(cond=term.condition, cases=cases_list, default_case=def_region)
                seq.append(switch_reg)
                node = merge_bb

            else:
                break

        return seq

    def _build_loop(
        self,
        header: BasicBlock,
        loop: Loop,
        stop_block: Optional[BasicBlock]
    ) -> Tuple[LoopRegion, Optional[BasicBlock]]:
        exit_blocks = loop.get_exit_blocks()
        loop_exit = exit_blocks[0] if exit_blocks else None
        term = header.get_terminator()

        body_seq = SeqRegion()
        body_seq.append(BlockRegion(header))

        is_do_while = False
        cond_val = None

        is_inv = False
        if term is not None and term.opcode == IROpcode.BR_COND:
            true_in = term.true_block in loop.blocks
            false_in = term.false_block in loop.blocks
            is_do_while = (term.true_block is header) or (term.false_block is header)

            if true_in and not false_in:
                cond_val = term.condition
                is_inv = False
                inner = self._build_sequence(term.true_block, stop_block=loop_exit, current_loop=loop)
                for r in inner.regions:
                    body_seq.append(r)

            elif false_in and not true_in:
                cond_val = term.condition
                is_inv = True
                inner = self._build_sequence(term.false_block, stop_block=loop_exit, current_loop=loop)
                for r in inner.regions:
                    body_seq.append(r)

            else:
                inner = self._build_sequence(term.true_block, stop_block=loop_exit, current_loop=loop)
                for r in inner.regions:
                    body_seq.append(r)

        elif term is not None and term.opcode == IROpcode.BR:
            if term.target in loop.blocks and term.target is not header:
                inner = self._build_sequence(term.target, stop_block=loop_exit, current_loop=loop)
                for r in inner.regions:
                    body_seq.append(r)

        loop_reg = LoopRegion(
            cond=cond_val,
            body=body_seq,
            is_do_while=is_do_while,
            header_bb=header,
            is_inverted=is_inv
        )
        return loop_reg, loop_exit

    def _build_if(
        self,
        node: BasicBlock,
        term: Any,
        stop_block: Optional[BasicBlock],
        current_loop: Optional[Loop]
    ) -> Tuple[IfRegion, Optional[BasicBlock]]:
        merge_bb, is_pure_if, needs_inv = self._hammock_analyzer.find_merge_point(
            cond_block=node,
            true_bb=term.true_block,
            false_bb=term.false_block,
            stop_block=stop_block,
            current_loop=current_loop
        )

        true_target = term.false_block if needs_inv else term.true_block
        false_target = term.true_block if needs_inv else term.false_block

        then_seq = self._build_sequence(true_target, stop_block=merge_bb, current_loop=current_loop)
        else_seq = None

        if not is_pure_if and false_target is not merge_bb:
            else_seq = self._build_sequence(false_target, stop_block=merge_bb, current_loop=current_loop)

        if_reg = IfRegion(
            cond=term.condition,
            then_body=then_seq,
            else_body=else_seq,
            is_inverted=needs_inv
        )
        return if_reg, merge_bb