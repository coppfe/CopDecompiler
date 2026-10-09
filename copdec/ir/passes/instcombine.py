from ...bridge.ir.scope import IRScope

from collections import deque
from typing import Set, Deque, Dict

from ...pipeline.passer import IRPass

from ..core.cfg import Instruction
from ..core.value import Value, UndefValue
from ..instructions.memory import LoadInst, StoreInst, AllocaInst
from ..instructions.special import CallInst, SyscallInst, IntrinsicInst, PhiNode
from ..opcodes import IROpcode

from .utils.instcombine.folder import simplify_instruction


class InstCombinePass(IRPass):
    """
    Instruction Combining, Peephole Algebraic Simplifier & Store-to-Load Forwarder.
    Combines algebraic identities and forwards local store values to subsequent loads.
    """

    def run(self, scope: IRScope) -> bool:
        func = scope.func
        if not func.blocks:
            return False

        changed = False

        phi_changed = True
        while phi_changed:
            phi_changed = False
            for block in func.blocks:
                curr = block.first_instruction
                while isinstance(curr, PhiNode):
                    next_inst = curr.next_node
                    distinct_ops = []
                    for i in range(curr.num_incoming):
                        val = curr.get_incoming_value(i)
                        if val is not curr and not isinstance(val, UndefValue):
                            if val not in distinct_ops:
                                distinct_ops.append(val)

                    if len(distinct_ops) == 0:
                        curr.replace_all_uses_with(UndefValue.get(curr.type))
                        curr.erase_from_parent()
                        phi_changed = True
                        changed = True
                    elif len(distinct_ops) == 1:
                        curr.replace_all_uses_with(distinct_ops[0])
                        curr.erase_from_parent()
                        phi_changed = True
                        changed = True
                    curr = next_inst

        # 1. Local Store-to-Load Forwarding (Forward store values directly to loads)
        if self._forward_store_to_loads(func):
            changed = True

        # 2. Initialize Worklist with all instructions for algebraic folding
        worklist: Deque[Instruction] = deque()
        in_worklist: Set[Instruction] = set()

        for block in func.blocks:
            for inst in block:
                worklist.append(inst)
                in_worklist.add(inst)

        # 3. Fixed-Point Worklist Processing
        while worklist:
            curr = worklist.popleft()
            in_worklist.discard(curr)

            if curr.parent is None:
                continue

            replacement = simplify_instruction(curr)
            if replacement is not None:
                for use in list(curr.uses):
                    user = use.user
                    if isinstance(user, Instruction) and user not in in_worklist:
                        worklist.append(user)
                        in_worklist.add(user)

                if isinstance(replacement, Instruction) and replacement.parent is None:
                    if curr.parent is not None:
                        curr.parent.insert_before(curr, replacement)
                        if replacement not in in_worklist:
                            worklist.append(replacement)
                            in_worklist.add(replacement)
                curr.replace_all_uses_with(replacement)
                curr.erase_from_parent()
                changed = True

        return changed

    def _forward_store_to_loads(self, func) -> bool:
        """
        Eliminates redundant LoadInst instructions following a dominating StoreInst
        to the same stack allocation within the same basic block.
        """
        modified = False
        for block in func.blocks:
            available_stores: Dict[AllocaInst, Value] = {}
            curr = block.first_instruction

            while curr is not None:
                next_inst = curr.next_node

                if isinstance(curr, StoreInst):
                    ptr = curr.pointer
                    if isinstance(ptr, AllocaInst):
                        available_stores[ptr] = curr.value
                    else:
                        available_stores.clear()

                elif isinstance(curr, LoadInst):
                    ptr = curr.pointer
                    if isinstance(ptr, AllocaInst) and ptr in available_stores:
                        stored_val = available_stores[ptr]
                        # Only forward if types match exactly
                        if curr.type == stored_val.type:
                            curr.replace_all_uses_with(stored_val)
                            curr.erase_from_parent()
                            modified = True

                elif isinstance(curr, (CallInst, SyscallInst, IntrinsicInst)):
                    # Clear forwarded stack stores on external calls to prevent stale reads
                    available_stores.clear()

                curr = next_inst

        return modified