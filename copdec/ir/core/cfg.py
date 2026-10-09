

from typing import List, Optional, Iterator, TYPE_CHECKING
from .value import Value, User, Argument
from ..types.base import Type, Label

if TYPE_CHECKING:
    from ...ir.opcodes import IROpcode


class CFGVerificationError(Exception):
    """Raised when an invariant of the Control Flow Graph or SSA is violated."""
    pass


class Instruction(User):
    """
    Abstract base class for all executable instructions in the IR.
    Acts as an intrusive doubly-linked list node inside its parent BasicBlock.
    """
    __slots__ = ('_parent', '_prev_node', '_next_node', '_pc')

    def __init__(self, val_type: Type, name: str = "", pc: int = 0):
        super().__init__(val_type, name)
        self._parent: Optional['BasicBlock'] = None
        self._prev_node: Optional['Instruction'] = None
        self._next_node: Optional['Instruction'] = None
        self._pc: int = pc

    @property
    def parent(self) -> Optional['BasicBlock']:
        return self._parent

    @property
    def prev_node(self) -> Optional['Instruction']:
        return self._prev_node

    @property
    def next_node(self) -> Optional['Instruction']:
        return self._next_node

    @property
    def opcode(self) -> 'IROpcode':
        raise NotImplementedError

    @property
    def pc(self) -> int:
        """Original machine program counter corresponding to this instruction."""
        return self._pc

    @property
    def is_terminator(self) -> bool:
        return False

    def insert_before(self, inst: 'Instruction') -> None:
        assert inst.parent is not None, "Target instruction has no parent BasicBlock"
        inst.parent.insert_before(inst, self)

    def insert_after(self, inst: 'Instruction') -> None:
        assert inst.parent is not None, "Target instruction has no parent BasicBlock"
        inst.parent.insert_after(inst, self)

    def erase_from_parent(self) -> None:
        assert self._parent is not None, "Instruction has no parent BasicBlock"
        self._parent.remove_instruction(self)
        self.drop_all_references()


class BasicBlock(Value):
    """
    Container of linear instructions executed sequentially without branching.
    First-class SSA Value typed as Label (Type::getLabelTy()).
    """
    __slots__ = ('_parent', '_first_inst', '_last_inst', '_size', '_predecessors', '_successors')

    def __init__(self, name: str = ""):
        super().__init__(Label, name)
        self._parent: Optional['Function'] = None
        self._first_inst: Optional[Instruction] = None
        self._last_inst: Optional[Instruction] = None
        self._size: int = 0
        self._predecessors: List['BasicBlock'] = []
        self._successors: List['BasicBlock'] = []

    @property
    def pc(self) -> int:
        """Returns the PC of the first instruction in the block, or 0 if empty."""
        return self._first_inst.pc if self._first_inst is not None else 0

    @property
    def parent(self) -> Optional['Function']:
        return self._parent

    @property
    def first_instruction(self) -> Optional[Instruction]:
        return self._first_inst

    @property
    def last_instruction(self) -> Optional[Instruction]:
        return self._last_inst

    @property
    def size(self) -> int:
        return self._size

    @property
    def is_empty(self) -> bool:
        return self._size == 0

    @property
    def predecessors(self) -> List['BasicBlock']:
        return self._predecessors

    @property
    def successors(self) -> List['BasicBlock']:
        return self._successors

    def get_terminator(self) -> Optional[Instruction]:
        if self._last_inst and self._last_inst.is_terminator:
            return self._last_inst
        return None

    def append_instruction(self, inst: Instruction) -> None:
        assert inst.parent is None, "Instruction is already attached to a BasicBlock"
        if self._last_inst and self._last_inst.is_terminator:
            raise CFGVerificationError(
                f"Cannot append instruction to BasicBlock '{self.name}' because it already has a terminator."
            )

        inst._parent = self
        inst._prev_node = self._last_inst
        inst._next_node = None

        if self._last_inst:
            self._last_inst._next_node = inst
        else:
            self._first_inst = inst

        self._last_inst = inst
        self._size += 1

    def insert_before(self, pos: Instruction, inst: Instruction) -> None:
        assert pos.parent is self, "Anchor instruction does not belong to this BasicBlock"
        assert inst.parent is None, "New instruction is already attached to a BasicBlock"

        inst._parent = self
        inst._next_node = pos
        inst._prev_node = pos._prev_node

        if pos._prev_node:
            pos._prev_node._next_node = inst
        else:
            self._first_inst = inst

        pos._prev_node = inst
        self._size += 1

    def insert_after(self, pos: Instruction, inst: Instruction) -> None:
        assert pos.parent is self, "Anchor instruction does not belong to this BasicBlock"
        assert inst.parent is None, "New instruction is already attached to a BasicBlock"
        if pos.is_terminator:
            raise CFGVerificationError("Cannot insert instruction after a terminator instruction.")

        inst._parent = self
        inst._prev_node = pos
        inst._next_node = pos._next_node

        if pos._next_node:
            pos._next_node._prev_node = inst
        else:
            self._last_inst = inst

        pos._next_node = inst
        self._size += 1

    def remove_instruction(self, inst: Instruction) -> None:
        assert inst.parent is self, "Instruction does not belong to this BasicBlock"

        if inst._prev_node:
            inst._prev_node._next_node = inst._next_node
        else:
            self._first_inst = inst._next_node

        if inst._next_node:
            inst._next_node._prev_node = inst._prev_node
        else:
            self._last_inst = inst._prev_node

        inst._parent = None
        inst._prev_node = None
        inst._next_node = None
        self._size -= 1

    def drop_all_references(self) -> None:
        """Drops all Def-Use references held by instructions inside this block."""
        curr = self._first_inst
        while curr is not None:
            curr.drop_all_references()
            curr = curr.next_node

    def add_predecessor(self, block: 'BasicBlock') -> None:
        if block not in self._predecessors:
            self._predecessors.append(block)

    def remove_predecessor(self, block: 'BasicBlock') -> None:
        if block in self._predecessors:
            self._predecessors.remove(block)

    def add_successor(self, block: 'BasicBlock') -> None:
        if block not in self._successors:
            self._successors.append(block)

    def remove_successor(self, block: 'BasicBlock') -> None:
        if block in self._successors:
            self._successors.remove(block)

    def __iter__(self) -> Iterator[Instruction]:
        curr = self._first_inst
        while curr is not None:
            yield curr
            curr = curr.next_node

    def __repr__(self) -> str:
        return f"{self.name}:"


class Function(Value):
    """
    Top-level IR container representing a callable function / subroutine.
    """
    __slots__ = ('_args', '_blocks', '_entry_block')

    def __init__(self, name: str, return_type: Type):
        super().__init__(return_type, name)
        self._args: List[Argument] = []
        self._blocks: List[BasicBlock] = []
        self._entry_block: Optional[BasicBlock] = None

    @property
    def args(self) -> List[Argument]:
        return self._args

    @property
    def blocks(self) -> List[BasicBlock]:
        return self._blocks

    @property
    def entry_block(self) -> Optional[BasicBlock]:
        return self._entry_block

    def add_argument(self, arg_type: Type, name: str = "") -> Argument:
        idx = len(self._args)
        arg = Argument(arg_type, name=name, arg_index=idx)
        arg._set_parent(self)
        self._args.append(arg)
        return arg

    def append_block(self, block: BasicBlock) -> None:
        assert block.parent is None, "BasicBlock already belongs to a Function"
        block._parent = self
        self._blocks.append(block)
        if self._entry_block is None:
            self._entry_block = block

    def verify(self) -> None:
        from ..verifier import IRVerifier
        verifier = IRVerifier(self)
        verifier.verify()