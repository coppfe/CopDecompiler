from typing import Dict, List, Set, Optional
from ..core.cfg import Function, BasicBlock
from ..instructions.control import BranchInst
from .dominance import DominanceTree
from ...pipeline.scope import BaseScope


class Loop:
    """Represents a Natural Loop in the Control Flow Graph."""
    __slots__ = ('_header', '_latches', '_blocks', '_parent_loop', '_sub_loops')

    def __init__(self, header: BasicBlock):
        self._header: BasicBlock = header
        self._latches: List[BasicBlock] = []
        self._blocks: Set[BasicBlock] = {header}
        self._parent_loop: Optional['Loop'] = None
        self._sub_loops: List['Loop'] = []

    @property
    def header(self) -> BasicBlock:
        return self._header

    @property
    def latches(self) -> List[BasicBlock]:
        return self._latches

    @property
    def blocks(self) -> Set[BasicBlock]:
        return self._blocks

    @property
    def parent_loop(self) -> Optional['Loop']:
        return self._parent_loop

    @property
    def sub_loops(self) -> List['Loop']:
        return self._sub_loops

    @property
    def depth(self) -> int:
        d = 0
        curr: Optional[Loop] = self
        while curr is not None:
            d += 1
            curr = curr.parent_loop
        return d

    def contains_block(self, block: BasicBlock) -> bool:
        return block in self._blocks

    def contains_loop(self, sub: 'Loop') -> bool:
        return sub._blocks.issubset(self._blocks)

    def add_latch(self, latch: BasicBlock) -> None:
        if latch not in self._latches:
            self._latches.append(latch)

    def add_block(self, block: BasicBlock) -> None:
        self._blocks.add(block)

    def add_sub_loop(self, sub: 'Loop') -> None:
        sub._parent_loop = self
        if sub not in self._sub_loops:
            self._sub_loops.append(sub)

    def get_exiting_blocks(self) -> List[BasicBlock]:
        exiting = []
        for b in self._blocks:
            if any(succ not in self._blocks for succ in b.successors):
                exiting.append(b)
        return exiting

    def get_exit_blocks(self) -> List[BasicBlock]:
        exit_blocks = set()
        for b in self._blocks:
            for succ in b.successors:
                if succ not in self._blocks:
                    exit_blocks.add(succ)
        return list(exit_blocks)

    def __repr__(self) -> str:
        return f"Loop(Header=%{self._header.name}, Blocks={len(self._blocks)}, Depth={self.depth})"


class LoopInfo:
    """Computes natural loops and constructs the Loop Nest Tree hierarchy."""
    __slots__ = ('_func', '_dom_tree', '_top_level_loops', '_loop_map')

    def __init__(self, scope: BaseScope):
        self._func: Function = scope.artifact
        self._dom_tree: DominanceTree = scope.get_analysis(DominanceTree)
        self._top_level_loops: List[Loop] = []
        self._loop_map: Dict[BasicBlock, Loop] = {}

        if self._func.blocks:
            self._analyze_loops()

    @property
    def top_level_loops(self) -> List[Loop]:
        return self._top_level_loops

    def get_loop_for(self, block: BasicBlock) -> Optional[Loop]:
        return self._loop_map.get(block)

    def is_loop_header(self, block: BasicBlock) -> bool:
        loop = self._loop_map.get(block)
        return loop is not None and loop.header is block

    def _analyze_loops(self) -> None:
        raw_loops: Dict[BasicBlock, Loop] = {}

        # 1. Identify Back-edges
        for block in self._func.blocks:
            for succ in block.successors:
                if self._dom_tree.dominates(succ, block):
                    header = succ
                    latch = block

                    if header not in raw_loops:
                        raw_loops[header] = Loop(header)

                    loop = raw_loops[header]
                    loop.add_latch(latch)
                    self._populate_loop_body(loop, latch)

        # 2. Build Loop Nest Tree
        sorted_loops = sorted(raw_loops.values(), key=lambda l: len(l.blocks))

        for loop in sorted_loops:
            for b in loop.blocks:
                if b not in self._loop_map:
                    self._loop_map[b] = loop

            parent: Optional[Loop] = None
            for candidate in sorted_loops:
                if candidate is not loop and candidate.contains_loop(loop):
                    if parent is None or len(candidate.blocks) < len(parent.blocks):
                        parent = candidate

            if parent is not None:
                parent.add_sub_loop(loop)
            else:
                self._top_level_loops.append(loop)

    def _populate_loop_body(self, loop: Loop, latch: BasicBlock) -> None:
        worklist: List[BasicBlock] = [latch]
        loop.add_block(latch)

        while worklist:
            curr = worklist.pop()
            for pred in curr.predecessors:
                if pred not in loop.blocks and pred is not loop.header:
                    loop.add_block(pred)
                    worklist.append(pred)

    def is_reducible(self) -> bool:
        visited: Set[BasicBlock] = set()
        on_stack: Set[BasicBlock] = set()
        is_red = True

        def dfs(node: BasicBlock) -> None:
            nonlocal is_red
            visited.add(node)
            on_stack.add(node)

            for succ in node.successors:
                if succ in on_stack:
                    if not self._dom_tree.dominates(succ, node):
                        is_red = False
                elif succ not in visited:
                    dfs(succ)

            on_stack.remove(node)

        if self._func.entry_block:
            dfs(self._func.entry_block)

        return is_red

    def insert_preheaders(self) -> bool:
        modified = False

        for loop in list(self._loop_map.values()):
            header = loop.header
            external_preds = [p for p in header.predecessors if p not in loop.blocks]

            if len(external_preds) > 1:
                preheader = BasicBlock(name=f"{header.name}_preheader")
                self._func.blocks.append(preheader)
                preheader._parent = self._func

                for pred in external_preds:
                    term = pred.get_terminator()
                    if term is not None:
                        term.replace_uses_of_with(header, preheader)
                    pred.remove_successor(header)
                    pred.add_successor(preheader)
                    header.remove_predecessor(pred)
                    preheader.add_predecessor(pred)

                header_pc = header.first_instruction.pc if header.first_instruction else 0
                br = BranchInst(header, pc=header_pc)
                preheader.append_instruction(br)
                preheader.add_successor(header)
                header.add_predecessor(preheader)

                modified = True

        return modified