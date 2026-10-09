from typing import List, Dict, Optional, Iterator
from .nodes import LIRInsn


class LIRBlock:
    """
    Basic block containing a linear sequence of Low-Level micro-instructions.
    Terminated by a jump, branch, or return.
    """
    __slots__ = ('addr', 'insns', 'predecessors', 'successors')

    def __init__(self, addr: int):
        self.addr: int = addr
        self.insns: List[LIRInsn] = []
        self.predecessors: List['LIRBlock'] = []
        self.successors: List['LIRBlock'] = []

    def append(self, insn: LIRInsn) -> None:
        """Appends a micro-instruction to this block."""
        self.insns.append(insn)

    def insert_before(self, target: LIRInsn, insn: LIRInsn) -> None:
        idx = self.insns.index(target)
        self.insns.insert(idx, insn)

    def insert_after(self, target: LIRInsn, insn: LIRInsn) -> None:
        idx = self.insns.index(target)
        self.insns.insert(idx + 1, insn)

    def remove(self, insn: LIRInsn) -> None:
        self.insns.remove(insn)

    def get_terminator(self) -> Optional[LIRInsn]:
        if self.insns and self.insns[-1].is_terminator:
            return self.insns[-1]
        return None

    def add_successor(self, block: 'LIRBlock') -> None:
        if block not in self.successors:
            self.successors.append(block)
        if self not in block.predecessors:
            block.predecessors.append(self)

    def remove_successor(self, block: 'LIRBlock') -> None:
        if block in self.successors:
            self.successors.remove(block)
        if self in block.predecessors:
            block.predecessors.remove(self)

    def __iter__(self) -> Iterator[LIRInsn]:
        return iter(self.insns)

    def __len__(self) -> int:
        return len(self.insns)

    def __repr__(self) -> str:
        preds = ", ".join(f"0x{p.addr:x}" for p in self.predecessors)
        succs = ", ".join(f"0x{s.addr:x}" for s in self.successors)
        header = f"block_0x{self.addr:x}: [preds: {preds}] [succs: {succs}]"
        lines = [header]
        for insn in self.insns:
            lines.append(f"    {insn}")
        return "\n".join(lines)


class LIRFunction:
    """
    Top-level container for a Control Flow Graph of LIR basic blocks.
    Completely architecture-agnostic representation of a subroutine.
    """
    __slots__ = ('name', 'entry_addr', 'blocks', 'arch_bits')

    def __init__(self, name: str, entry_addr: int, arch_bits: int = 32):
        self.name: str = name
        self.entry_addr: int = entry_addr
        self.blocks: List[LIRBlock] = []
        self.arch_bits: int = arch_bits

    @property
    def entry_block(self) -> Optional[LIRBlock]:
        return self.blocks[0] if self.blocks else None

    def append_block(self, block: LIRBlock) -> None:
        self.blocks.append(block)

    def get_block(self, addr: int) -> Optional[LIRBlock]:
        for b in self.blocks:
            if b.addr == addr:
                return b
        return None

    def __iter__(self) -> Iterator[LIRBlock]:
        return iter(self.blocks)

    def __len__(self) -> int:
        return len(self.blocks)

    def __repr__(self) -> str:
        lines = [f"define @{self.name}() [arch={self.arch_bits}bit, entry=0x{self.entry_addr:x}] {{"]
        for b in self.blocks:
            lines.append(str(b))
        lines.append("}")
        return "\n".join(lines)