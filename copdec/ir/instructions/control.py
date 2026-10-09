

from typing import Optional, List, Tuple
from ..opcodes import IROpcode
from ..types.base import Void
from ..types.integer import Int1
from ..core.value import Value, ConstantInt
from ..core.cfg import Instruction, BasicBlock


class TerminatorInst(Instruction):
    """Base abstract class for all control flow terminating instructions."""
    __slots__ = ()

    def __init__(self, pc: int = 0):
        super().__init__(Void, name="", pc=pc)

    @property
    def is_terminator(self) -> bool:
        return True


class BranchInst(TerminatorInst):
    """
    Unconditional jump to a target BasicBlock:
      br label %target_block
    """
    __slots__ = ()

    def __init__(self, target: BasicBlock, pc: int = 0):
        super().__init__(pc=pc)
        self.add_operand(target)

    @property
    def opcode(self) -> IROpcode:
        return IROpcode.BR

    @property
    def target(self) -> BasicBlock:
        return self.get_operand(0)  # type: ignore

    @target.setter
    def target(self, new_target: BasicBlock) -> None:
        self.set_operand(0, new_target)

    def __repr__(self) -> str:
        return f"br label %{self.target.name}"


class BranchCondInst(TerminatorInst):
    """
    Conditional branch based on an i1 boolean condition:
      br i1 %cond, label %true_block, label %false_block
    """
    __slots__ = ()

    def __init__(self, cond: Value, true_block: BasicBlock, false_block: BasicBlock, pc: int = 0):
        if cond.type is not Int1:
            raise TypeError(f"BranchCondInst condition must be of type i1, got: {cond.type}")
        super().__init__(pc=pc)
        self.add_operand(cond)
        self.add_operand(true_block)
        self.add_operand(false_block)

    @property
    def opcode(self) -> IROpcode:
        return IROpcode.BR_COND

    @property
    def condition(self) -> Value:
        return self.get_operand(0)

    @property
    def true_block(self) -> BasicBlock:
        return self.get_operand(1)  # type: ignore

    @property
    def false_block(self) -> BasicBlock:
        return self.get_operand(2)  # type: ignore

    def __repr__(self) -> str:
        return f"br i1 {self.condition}, label %{self.true_block.name}, label %{self.false_block.name}"

class IndirectBranchInst(TerminatorInst):
    """
    Indirect control flow transfer to a dynamic computed target address:
      indirectbr %target_ptr
    """
    __slots__ = ()

    def __init__(self, target_address: Value, pc: int = 0):
        super().__init__(pc=pc)
        self.add_operand(target_address)

    @property
    def opcode(self) -> IROpcode:
        return IROpcode.INDIRECT_BR

    @property
    def target_address(self) -> Value:
        return self.get_operand(0)

    def __repr__(self) -> str:
        return f"indirectbr {self.target_address.type} {self.target_address}"

class SwitchInst(TerminatorInst):
    """
    Multi-way switch branch instruction:
      switch %cond, label %default [ i32 0, label %bb0; i32 1, label %bb1; ... ]
    """
    __slots__ = ()

    def __init__(
        self,
        cond: Value,
        default_block: BasicBlock,
        cases: Optional[List[Tuple[ConstantInt, BasicBlock]]] = None,
        pc: int = 0
    ):
        super().__init__(pc=pc)
        self.add_operand(cond)
        self.add_operand(default_block)
        if cases:
            for val, target in cases:
                self.add_operand(val)
                self.add_operand(target)

    @property
    def opcode(self) -> IROpcode:
        return IROpcode.SWITCH

    @property
    def condition(self) -> Value:
        return self.get_operand(0)

    @property
    def default_block(self) -> BasicBlock:
        return self.get_operand(1)  # type: ignore

    @property
    def num_cases(self) -> int:
        return (self.num_operands - 2) // 2

    @property
    def cases(self) -> List[Tuple[ConstantInt, BasicBlock]]:
        res = []
        for i in range(self.num_cases):
            val = self.get_operand(2 + 2 * i)
            target = self.get_operand(2 + 2 * i + 1)
            res.append((val, target))  # type: ignore
        return res

    def add_case(self, val: ConstantInt, target: BasicBlock) -> None:
        self.add_operand(val)
        self.add_operand(target)

    def get_successors(self) -> List[BasicBlock]:
        succs = [self.default_block]
        for _, target in self.cases:
            if target not in succs:
                succs.append(target)
        return succs

    def __repr__(self) -> str:
        cases_str = ", ".join(f"{val} -> %{target.name}" for val, target in self.cases)
        return f"switch {self.condition.type} {self.condition}, label %{self.default_block.name} [ {cases_str} ]"


class ReturnInst(TerminatorInst):
    """
    Function return instruction:
      ret %type %val / ret void
    """
    __slots__ = ()

    def __init__(self, return_val: Optional[Value] = None, pc: int = 0):
        super().__init__(pc=pc)
        if return_val is not None:
            self.add_operand(return_val)

    @property
    def opcode(self) -> IROpcode:
        return IROpcode.RET

    @property
    def return_value(self) -> Optional[Value]:
        return self.get_operand(0) if self.num_operands > 0 else None

    def __repr__(self) -> str:
        if self.return_value:
            return f"ret {self.return_value.type} {self.return_value}"
        return "ret void"


class UnreachableInst(TerminatorInst):
    """Marks an unreachable code path."""
    __slots__ = ()

    @property
    def opcode(self) -> IROpcode:
        return IROpcode.UNREACHABLE

    def __repr__(self) -> str:
        return "unreachable"