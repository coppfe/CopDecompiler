from ...bridge.ir.scope import IRScope

from typing import Dict, List, Optional
from ...pipeline.passer import IRPass

from ..core.cfg import Instruction, BasicBlock
from ..analysis.dominance import DominanceTree
from .utils.gvn.key import ExpressionKey


class GVNPass(IRPass):
    """
    Global Value Numbering (GVN) Pass:
    Eliminates common subexpressions across basic blocks using dominance congruence.
    """

    def run(self, scope: IRScope) -> bool:
        func = scope.func
        if not func.blocks:
            return False

        dom_tree = scope.get_analysis(DominanceTree)
        expr_table: dict[ExpressionKey, list[Instruction]] = {}
        dead_instructions: list[Instruction] = []
        modified = False

        for block in func.blocks:
            curr = block.first_instruction
            while curr is not None:
                next_inst = curr.next_node
                key = ExpressionKey.from_instruction(curr)

                if key is not None:
                    leader = self._find_dominating_leader(key, curr, block, expr_table, dom_tree)

                    if leader is not None and leader is not curr:
                        curr.replace_all_uses_with(leader)
                        dead_instructions.append(curr)
                        modified = True
                    else:
                        if key not in expr_table:
                            expr_table[key] = []
                        expr_table[key].append(curr)

                curr = next_inst

        for dead in dead_instructions:
            dead.erase_from_parent()

        return modified

    def _find_dominating_leader(
        self,
        key: ExpressionKey,
        curr: Instruction,
        block: BasicBlock,
        expr_table: Dict[ExpressionKey, List[Instruction]],
        dom_tree: DominanceTree
    ) -> Optional[Instruction]:
        if key not in expr_table:
            return None

        for candidate in expr_table[key]:
            cand_block = candidate.parent
            if cand_block is None:
                continue

            # Strict dominance check
            if cand_block is not block:
                if dom_tree.dominates(cand_block, block):
                    return candidate
            else:
                runner = curr.prev_node
                while runner is not None:
                    if runner is candidate:
                        return candidate
                    runner = runner.prev_node

        return None