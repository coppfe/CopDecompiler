from typing import Set, Dict, Optional, List, Tuple
from ...bridge.ir.scope import IRScope
from ...pipeline.passer import IRPass
from ..core.cfg import Function, Instruction
from ..core.value import Value, ConstantSymbol, ConstantInt, UndefValue
from ..instructions.memory import LoadInst, StoreInst, AllocaInst
from ..instructions.special import CallInst
from ..instructions.cast import CastInst
from ..instructions.alu import BinaryOperator
from ..opcodes import IROpcode
from ..types.integer import Int32, Int64


class StackFramePromotionPass(IRPass):
    """
    Stack Frame Recognition & Variable Promotion Pass.
    
    1. Prunes dead prologue stores of uninitialized registers (UndefValue) to stack.
    2. Identifies all stack-relative memory accesses (offsets from sp_base).
    3. Promotes strictly non-overlapping stack slots to first-class AllocaInst (local variables).
    """
    __slots__ = ()

    @staticmethod
    def get_sp_offset(val: Value) -> Optional[int]:
        curr = val
        offset = 0
        depth = 0
        while depth < 16:
            depth += 1
            if isinstance(curr, CastInst):
                curr = curr.src
                continue
            if isinstance(curr, BinaryOperator):
                if curr.opcode == IROpcode.ADD:
                    if isinstance(curr.rhs, ConstantInt):
                        offset += curr.rhs.value
                        curr = curr.lhs
                        continue
                    elif isinstance(curr.lhs, ConstantInt):
                        offset += curr.lhs.value
                        curr = curr.rhs
                        continue
                elif curr.opcode == IROpcode.SUB:
                    if isinstance(curr.rhs, ConstantInt):
                        offset -= curr.rhs.value
                        curr = curr.lhs
                        continue
            break

        if isinstance(curr, ConstantSymbol) and curr.name == "sp_base":
            return offset
        return None

    def run(self, scope: IRScope) -> bool:
        func: Function = scope.func
        if not func.blocks or func.entry_block is None:
            return False

        modified = False

        # 1. Prune dead prologue stores of UndefValue to stack
        for block in func.blocks:
            curr = block.first_instruction
            while curr is not None:
                next_inst = curr.next_node
                if isinstance(curr, StoreInst):
                    if isinstance(curr.value, UndefValue):
                        sp_off = self.get_sp_offset(curr.pointer)
                        if sp_off is not None:
                            curr.erase_from_parent()
                            modified = True
                curr = next_inst

        # 2. Collect all stack slot references across Load, Store, and Call
        slot_accesses: Dict[int, List[Tuple[Instruction, int]]] = {}
        slot_sizes: Dict[int, int] = {}

        for block in func.blocks:
            for inst in block:
                if isinstance(inst, LoadInst):
                    sp_off = self.get_sp_offset(inst.pointer)
                    if sp_off is not None and sp_off < 0:
                        slot_id = abs(sp_off)
                        slot_accesses.setdefault(slot_id, []).append((inst, 0))
                        slot_sizes[slot_id] = max(slot_sizes.get(slot_id, 0), inst.type.byte_size)

                elif isinstance(inst, StoreInst):
                    sp_off = self.get_sp_offset(inst.pointer)
                    if sp_off is not None and sp_off < 0:
                        slot_id = abs(sp_off)
                        slot_accesses.setdefault(slot_id, []).append((inst, 1))
                        slot_sizes[slot_id] = max(slot_sizes.get(slot_id, 0), inst.value.type.byte_size)

                    val_sp_off = self.get_sp_offset(inst.value)
                    if val_sp_off is not None and val_sp_off < 0:
                        val_slot_id = abs(val_sp_off)
                        slot_accesses.setdefault(val_slot_id, []).append((inst, 0))
                        slot_sizes[val_slot_id] = max(slot_sizes.get(val_slot_id, 0), 8)

                elif isinstance(inst, CallInst):
                    for arg_idx, arg_val in enumerate(inst.args):
                        sp_off = self.get_sp_offset(arg_val)
                        if sp_off is not None and sp_off < 0:
                            slot_id = abs(sp_off)
                            # In CallInst operands: [callee, arg0, arg1, ...] -> op_index is arg_idx + 1
                            slot_accesses.setdefault(slot_id, []).append((inst, arg_idx + 1))
                            slot_sizes[slot_id] = max(slot_sizes.get(slot_id, 0), 8)

        if not slot_accesses:
            return modified

        invalid_slots = set()
        sorted_slots = sorted(slot_accesses.keys(), reverse=True)
        for i in range(len(sorted_slots)):
            for j in range(i + 1, len(sorted_slots)):
                s1 = sorted_slots[i]
                s2 = sorted_slots[j]
                sz1 = slot_sizes[s1]
                if -s1 + sz1 > -s2:
                    invalid_slots.add(s1)
                    invalid_slots.add(s2)

        for slot_id in invalid_slots:
            del slot_accesses[slot_id]

        if not slot_accesses:
            return modified

        # 3. Create AllocaInst for each unique stack slot at entry block
        allocas: Dict[int, AllocaInst] = {}
        for slot_id in sorted(slot_accesses.keys(), reverse=True):
            byte_sz = slot_sizes.get(slot_id, 8)
            var_type = Int32 if byte_sz <= 4 else Int64
            alloca_inst = AllocaInst(
                allocated_type=var_type,
                alignment=byte_sz,
                name=f"var_{slot_id:x}"
            )
            if func.entry_block.first_instruction is not None:
                func.entry_block.insert_before(func.entry_block.first_instruction, alloca_inst)
            else:
                func.entry_block.append_instruction(alloca_inst)
            allocas[slot_id] = alloca_inst
            modified = True

        # 4. Replace pointer operands with the corresponding AllocaInst
        for slot_id, targets in slot_accesses.items():
            alloca_inst = allocas[slot_id]
            for user_inst, op_idx in targets:
                user_inst.set_operand(op_idx, alloca_inst)
                modified = True

        return modified