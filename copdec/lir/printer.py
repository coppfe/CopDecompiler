

from .nodes import LIRExpr, LIRInsn
from .block import LIRBlock, LIRFunction


class LIRPrettyPrinter:
    """
    Human-readable microcode disassembler and pretty-printer for LIR functions and blocks.
    Enables zero-overhead debugging and verification of lifted instructions before SSA.
    """
    __slots__ = ()

    @classmethod
    def format_function(cls, func: LIRFunction) -> str:
        lines = [
            f"// ===========================================================================",
            f"// LIR Function: {func.name} @ 0x{func.entry_addr:x} ({func.arch_bits}-bit)",
            f"// Basic Blocks: {len(func.blocks)}",
            f"// ===========================================================================",
            f"define @{func.name}() {{"
        ]

        for block in func.blocks:
            lines.append(cls.format_block(block, indent=4))

        lines.append("}")
        return "\n".join(lines)

    @classmethod
    def format_block(cls, block: LIRBlock, indent: int = 0) -> str:
        ind = " " * indent
        preds_str = ", ".join(f"0x{p.addr:x}" for p in block.predecessors)
        succs_str = ", ".join(f"0x{s.addr:x}" for s in block.successors)

        meta = []
        if preds_str: meta.append(f"preds: {preds_str}")
        if succs_str: meta.append(f"succs: {succs_str}")
        meta_comment = f" // [{'; '.join(meta)}]" if meta else ""

        lines = [f"\n{ind}block_0x{block.addr:x}:{meta_comment}"]

        for insn in block.insns:
            lines.append(f"{ind}    {cls.format_insn(insn)}")

        return "\n".join(lines)

    @classmethod
    def format_insn(cls, insn: LIRInsn) -> str:
        pc_prefix = f"/* 0x{insn.pc:x} */ " if insn.pc != 0 else ""
        return f"{pc_prefix}{insn}"