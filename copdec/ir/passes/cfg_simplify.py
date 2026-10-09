from ...bridge.ir.scope import IRScope

from typing import Set, List

from ...pipeline.passer import IRPass

from ..core.cfg import BasicBlock
from ..core.value import ConstantInt, UndefValue
from ..instructions.control import BranchInst, BranchCondInst
from ..instructions.special import PhiNode


class CFGSimplifyPass(IRPass):
    """
    Control Flow Graph Simplification Pass:
      1. Folds constant/undef BranchCondInst into unconditional BranchInst.
      2. Prunes unreachable basic blocks and disconnects dead CFG edges.
      3. Merges linear block chains (A -> B).
      4. Maintains strict PhiNode bijection and SSA dominance invariants.
    """

    def run(self, scope: IRScope) -> bool:
        func = scope.func
        if not func.blocks or not func.entry_block:
            return False

        modified = False

        # 1. Constant & Undef Condition Folding: br i1 (const/undef), label %T, label %F
        for block in func.blocks:
            term = block.get_terminator()
            if isinstance(term, BranchCondInst):
                cond = term.condition
                known_val: int | None = None

                if isinstance(cond, ConstantInt):
                    known_val = cond.value
                elif isinstance(cond, UndefValue):
                    known_val = 0  # Default undef condition to false branch

                if known_val is not None:
                    taken_bb = term.true_block if known_val != 0 else term.false_block
                    dead_bb = term.false_block if known_val != 0 else term.true_block

                    # Replace terminator with unconditional jump
                    pc = term.pc
                    term.erase_from_parent()
                    block.append_instruction(BranchInst(taken_bb, pc=pc))

                    # Disconnect dead edge
                    block.remove_successor(dead_bb)
                    dead_bb.remove_predecessor(block)

                    # Update Phi nodes in dead successor
                    curr_phi = dead_bb.first_instruction
                    while curr_phi is not None and isinstance(curr_phi, PhiNode):
                        next_inst = curr_phi.next_node
                        curr_phi.remove_incoming_block(block)
                        if curr_phi.num_incoming == 1:
                            single_val = curr_phi.get_incoming_value(0)
                            curr_phi.replace_all_uses_with(single_val)
                            curr_phi.erase_from_parent()
                        elif curr_phi.num_incoming == 0:
                            curr_phi.erase_from_parent()
                        curr_phi = next_inst

                    modified = True

        # 2. Discover Reachable Blocks from Function Entry
        reachable: Set[BasicBlock] = set()
        stack: List[BasicBlock] = [func.entry_block]
        reachable.add(func.entry_block)

        while stack:
            curr = stack.pop()
            for succ in curr.successors:
                if succ not in reachable:
                    reachable.add(succ)
                    stack.append(succ)

        unreachable = [b for b in func.blocks if b not in reachable]
        if unreachable:
            for dead_block in unreachable:
                for succ in list(dead_block.successors):
                    succ.remove_predecessor(dead_block)
                    if succ in reachable:
                        curr_inst = succ.first_instruction
                        while curr_inst is not None and isinstance(curr_inst, PhiNode):
                            next_inst = curr_inst.next_node
                            curr_inst.remove_incoming_block(dead_block)
                            if curr_inst.num_incoming == 1:
                                single_val = curr_inst.get_incoming_value(0)
                                curr_inst.replace_all_uses_with(single_val)
                                curr_inst.erase_from_parent()
                            elif curr_inst.num_incoming == 0:
                                curr_inst.erase_from_parent()
                            curr_inst = next_inst

                while dead_block.first_instruction is not None:
                    dead_block.first_instruction.erase_from_parent()

                dead_block.drop_all_references()
                func.blocks.remove(dead_block)

            modified = True

        # 3. Merge Linear Block Chains (A -> B where A has 1 succ and B has 1 pred)
        idx = 0
        while idx < len(func.blocks):
            block_a = func.blocks[idx]
            if len(block_a.successors) == 1:
                block_b = block_a.successors[0]
                if len(block_b.predecessors) == 1 and block_b is not func.entry_block:
                    term_a = block_a.get_terminator()
                    if isinstance(term_a, BranchInst) and term_a.target is block_b:
                        term_a.erase_from_parent()

                        while block_b.first_instruction is not None:
                            inst = block_b.first_instruction
                            block_b.remove_instruction(inst)
                            block_a.append_instruction(inst)

                        block_b.replace_all_uses_with(block_a)

                        block_a.successors.clear()
                        for succ in block_b.successors:
                            block_a.add_successor(succ)
                            succ.remove_predecessor(block_b)
                            succ.add_predecessor(block_a)

                            curr_phi = succ.first_instruction
                            while curr_phi is not None and isinstance(curr_phi, PhiNode):
                                idx_b = curr_phi.get_incoming_index_for_block(block_b)
                                if idx_b != -1:
                                    curr_phi.set_incoming_block(idx_b, block_a)
                                curr_phi = curr_phi.next_node

                        block_b.drop_all_references()
                        func.blocks.remove(block_b)
                        modified = True
                        continue

            idx += 1

        return modified