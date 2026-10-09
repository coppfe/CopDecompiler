from typing import List, Dict, Set
from ...block import LIRBlock, LIRFunction
from ...nodes import Jump, JumpCond, Intrinsic, Return
from ....insn import Insn
from ..base import BaseLifter
from .context import ARM64LifterContext
from .handlers import HANDLER_MAP

# mention: тоже хуета


class ARM64LIRLifter(BaseLifter):
    """AArch64 LIR Lifter."""
    __slots__ = ()

    @classmethod
    def lift(cls, insns: List[Insn], func_name: str = "sub_entry") -> LIRFunction:
        if not insns:
            return LIRFunction(func_name, 0, arch_bits=64)

        start_pc = insns[0].address
        insn_pcs = {i.address for i in insns}

        leaders: Set[int] = {start_pc}

        for insn in insns:
            next_pc = insn.address + insn.size
            mnem = insn.mnemonic

            if (mnem.startswith("b") and not mnem.startswith("bl")) or mnem in ("cbz", "cbnz", "tbz", "tbnz"):
                if insn.op_count > 0:
                    last_op = insn.op(insn.op_count - 1)
                    if hasattr(last_op, 'value') and last_op.value in insn_pcs:
                        leaders.add(last_op.value)
                if next_pc in insn_pcs:
                    leaders.add(next_pc)

            elif mnem == "ret":
                if next_pc in insn_pcs:
                    leaders.add(next_pc)

        func = LIRFunction(func_name, start_pc, arch_bits=64)
        block_map: Dict[int, LIRBlock] = {}

        for pc in sorted(leaders):
            b = LIRBlock(pc)
            block_map[pc] = b
            func.append_block(b)

        ctx = ARM64LifterContext(func_pcs=insn_pcs)
        current_block = block_map[start_pc]
        ctx.set_block(current_block)

        for insn in insns:
            if insn.address in block_map:
                current_block = block_map[insn.address]
                ctx.set_block(current_block)

            ctx.set_pc(insn.address)

            handler = HANDLER_MAP.get(insn.mnemonic)
            if handler is not None:
                handler(ctx, insn)
            elif insn.mnemonic != "nop":
                ctx.emit(Intrinsic(insn.mnemonic, pc=insn.address))

        for i, b in enumerate(func.blocks):
            term = b.get_terminator()

            if term is None:
                if i + 1 < len(func.blocks):
                    next_b = func.blocks[i + 1]
                    fallthrough_pc = b.insns[-1].pc if b.insns else b.addr
                    b.append(Jump(next_b.addr, pc=fallthrough_pc))
                    b.add_successor(next_b)
                else:
                    last_pc = b.insns[-1].pc if b.insns else b.addr
                    b.append(Return(pc=last_pc))

            elif isinstance(term, Jump):
                tgt = block_map.get(term.target)
                if tgt is not None:
                    b.add_successor(tgt)

            elif isinstance(term, JumpCond):
                t_tgt = block_map.get(term.true_target)
                f_tgt = block_map.get(term.false_target)
                if t_tgt is not None:
                    b.add_successor(t_tgt)
                if f_tgt is not None:
                    b.add_successor(f_tgt)

        return func