from ...bridge.ir.scope import IRScope

from typing import Set, List

from ...pipeline.passer import IRPass

from ..core.cfg import Instruction
from ..instructions.memory import StoreInst
from ..instructions.control import TerminatorInst
from ..instructions.special import CallInst, SyscallInst, IntrinsicInst


class ADCEPass(IRPass):
    """
    Aggressive Dead Code Elimination (ADCE) Pass:
    Marks critical roots (side-effects) and sweeps dead unreferenced SSA instructions.
    """

    def run(self, scope: IRScope) -> bool:
        func = scope.func
        if not func.blocks:
            return False

        live_instructions: Set[Instruction] = set()
        worklist: List[Instruction] = []

        # 1. Identify Root Instructions (Side-Effects)
        for block in func.blocks:
            for inst in block:
                if isinstance(inst, (StoreInst, TerminatorInst, CallInst, SyscallInst, IntrinsicInst)):
                    live_instructions.add(inst)
                    worklist.append(inst)

        # 2. Backwards Liveness Propagation
        while worklist:
            curr = worklist.pop()
            for idx in range(curr.num_operands):
                op_val = curr.get_operand(idx)
                if isinstance(op_val, Instruction) and op_val not in live_instructions:
                    live_instructions.add(op_val)
                    worklist.append(op_val)

        # 3. Sweep Dead Instructions
        modified = False
        for block in func.blocks:
            curr = block.first_instruction
            while curr is not None:
                next_inst = curr.next_node
                if curr not in live_instructions:
                    curr.erase_from_parent()
                    modified = True
                curr = next_inst

        return modified