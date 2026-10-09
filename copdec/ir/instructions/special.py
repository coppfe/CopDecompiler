

from typing import List, Tuple, Optional
from ..opcodes import IROpcode
from ..types.base import Type
from ..types.integer import Int1, Int64
from ..core.value import Value, Use
from ..core.cfg import Instruction, BasicBlock

class PhiNode(Instruction):
    """
    SSA Phi-Node selecting a value based on the predecessor block:
      %dst = phi %type [ %val1, %bb1 ], [ %val2, %bb2 ], ...
    Strict invariant: num_operands == len(_incoming_blocks).
    """
    __slots__ = ('_incoming_blocks',)

    def __init__(self, val_type: Type, name: str = "", pc: int = 0):
        super().__init__(val_type, name=name, pc=pc)
        self._incoming_blocks: List[BasicBlock] = []

    @property
    def opcode(self) -> IROpcode:
        return IROpcode.PHI

    @property
    def num_incoming(self) -> int:
        """Returns the synchronized count of incoming value-block pairs."""
        return min(len(self._operands), len(self._incoming_blocks))

    def add_incoming(self, val: Value, block: BasicBlock) -> None:
        """Appends an incoming (Value, BasicBlock) pair to this Phi node."""
        if val.type is not self.type:
            raise TypeError(
                f"PhiNode '{self.name}' incoming value type mismatch: expected {self.type}, got {val.type}"
            )
        self.add_operand(val)
        self._incoming_blocks.append(block)

    def get_incoming_value(self, index: int) -> Optional[Value]:
        """Safely returns incoming Value at index or None if out of bounds."""
        if 0 <= index < len(self._operands):
            return self.get_operand(index)
        return None

    def set_incoming_value(self, index: int, val: Value) -> None:
        """Updates the value at incoming index while preserving the block."""
        if val.type is not self.type:
            raise TypeError(f"PhiNode type mismatch: expected {self.type}, got {val.type}")
        if 0 <= index < len(self._operands):
            self.set_operand(index, val)

    def get_incoming_block(self, index: int) -> Optional[BasicBlock]:
        """Safely returns incoming BasicBlock at index or None if out of bounds."""
        if 0 <= index < len(self._incoming_blocks):
            return self._incoming_blocks[index]
        return None

    def set_incoming_block(self, index: int, block: BasicBlock) -> None:
        """Updates the incoming block at index."""
        assert 0 <= index < len(self._incoming_blocks), f"Index out of bounds: {index}"
        self._incoming_blocks[index] = block

    def get_incoming_index_for_block(self, block: BasicBlock) -> int:
        """Returns the incoming index corresponding to the given predecessor block, or -1."""
        for i, b in enumerate(self._incoming_blocks):
            if b is block:
                return i
        return -1

    def has_incoming_block(self, block: BasicBlock) -> bool:
        return self.get_incoming_index_for_block(block) != -1

    def get_incoming_value_for_block(self, block: BasicBlock) -> Optional[Value]:
        """Returns the incoming Value associated with the given predecessor block."""
        idx = self.get_incoming_index_for_block(block)
        return self.get_incoming_value(idx) if idx != -1 else None

    def remove_incoming(self, index: int) -> None:
        """Removes an incoming (Value, BasicBlock) pair at the specified index."""
        if not (0 <= index < len(self._operands) and 0 <= index < len(self._incoming_blocks)):
            return

        use = self._operands[index]
        use.value.remove_use(use)
        del self._operands[index]
        del self._incoming_blocks[index]

        # Resynchronize operand indices for remaining uses
        for i, u in enumerate(self._operands):
            u._operand_index = i

    def remove_incoming_block(self, block: BasicBlock) -> bool:
        """
        Removes all incoming values and edges associated with the given BasicBlock.
        Returns True if at least one entry was found and removed, False otherwise.
        """
        indices = [i for i, b in enumerate(self._incoming_blocks) if b is block]
        if not indices:
            return False

        for i in reversed(indices):
            self.remove_incoming(i)
        return True

    def drop_all_references(self) -> None:
        """Synchronously drops all Def-Use references and clears incoming block edges."""
        super().drop_all_references()
        self._incoming_blocks.clear()

    def __repr__(self) -> str:
        pairs = []
        for i in range(self.num_incoming):
            op = self.get_incoming_value(i)
            if op is None:
                op_str = "null"
            elif isinstance(op, Instruction):
                op_str = f"%{op.name}"
            else:
                op_str = str(op)
            blk_name = self._incoming_blocks[i].name if i < len(self._incoming_blocks) else "unknown"
            pairs.append(f"[ {op_str}, %{blk_name} ]")
        return f"%{self.name} = phi {self.type} {', '.join(pairs)}"
class SelectInst(Instruction):
    """
    SSA Functional Select (ternary operator):
      %dst = select i1 %cond, %true_val, %false_val
    """
    __slots__ = ()

    def __init__(self, cond: Value, true_val: Value, false_val: Value, name: str = "", pc: int = 0):
        if cond.type is not Int1:
            raise TypeError(f"Select condition must be of type i1, got: {cond.type}")
        if true_val.type is not false_val.type:
            raise TypeError(
                f"Select branch type mismatch: true_val={true_val.type}, false_val={false_val.type}"
            )

        super().__init__(true_val.type, name=name, pc=pc)
        self.add_operand(cond)
        self.add_operand(true_val)
        self.add_operand(false_val)

    @property
    def opcode(self) -> IROpcode:
        return IROpcode.SELECT

    @property
    def condition(self) -> Value:
        return self.get_operand(0)

    @property
    def true_value(self) -> Value:
        return self.get_operand(1)

    @property
    def false_value(self) -> Value:
        return self.get_operand(2)

    def __repr__(self) -> str:
        return f"%{self.name} = select i1 {self.condition}, {self.true_value.type} {self.true_value}, {self.false_value}"


class CallInst(Instruction):
    """
    Represents a subroutine invocation:
      %dst = call %ret_type %callee(%arg1, %arg2, ...)
    """
    __slots__ = ()

    def __init__(self, callee: Value, args: List[Value], return_type: Type, name: str = "", pc: int = 0):
        super().__init__(return_type, name=name, pc=pc)
        self.add_operand(callee)
        for arg in args:
            self.add_operand(arg)

    @property
    def opcode(self) -> IROpcode:
        return IROpcode.CALL

    @property
    def callee(self) -> Value:
        return self.get_operand(0)

    @property
    def args(self) -> List[Value]:
        return [self.get_operand(i) for i in range(1, self.num_operands)]

    def set_args(self, new_args: List[Value]) -> None:
        """Replaces the argument list while maintaining Def-Use consistency."""
        while self.num_operands > 1:
            self.remove_operand(self.num_operands - 1)
        for arg in new_args:
            self.add_operand(arg)

    def __repr__(self) -> str:
        args_str = ", ".join(f"{arg.type} {arg}" for arg in self.args)
        if self.type.is_void:
            return f"call {self.callee}({args_str})"
        return f"%{self.name} = call {self.type} {self.callee}({args_str})"


class IntrinsicInst(Instruction):
    """
    Represents hardware-specific or specialized micro-operations (e.g. BSL, RBIT, CLZ, DMB, PAC):
      %dst = intrinsic @name(%arg1, ...)
    """
    __slots__ = ('_intrinsic_name',)

    def __init__(self, intrinsic_name: str, args: List[Value], return_type: Type, name: str = "", pc: int = 0):
        super().__init__(return_type, name=name, pc=pc)
        self._intrinsic_name = intrinsic_name
        for arg in args:
            self.add_operand(arg)

    @property
    def opcode(self) -> IROpcode:
        return IROpcode.INTRINSIC

    @property
    def intrinsic_name(self) -> str:
        return self._intrinsic_name

    def __repr__(self) -> str:
        args_str = ", ".join(f"{self.get_operand(i)}" for i in range(self.num_operands))
        return f"%{self.name} = intrinsic @{self._intrinsic_name}({args_str})"


class SyscallInst(Instruction):
    """
    Represents a hardware system call / supervisor call (e.g. SVC, SMC, HVC):
      %dst = syscall %num(%arg1, %arg2, ...)
    """
    __slots__ = ()

    def __init__(self, num: Value, args: List[Value], return_type: Type, name: str = "", pc: int = 0):
        super().__init__(return_type, name=name, pc=pc)
        self.add_operand(num)
        for arg in args:
            self.add_operand(arg)

    @property
    def opcode(self) -> IROpcode:
        return IROpcode.SYSCALL

    @property
    def syscall_number(self) -> Value:
        return self.get_operand(0)

    @property
    def args(self) -> List[Value]:
        return [self.get_operand(i) for i in range(1, self.num_operands)]

    def __repr__(self) -> str:
        args_str = ", ".join(f"{arg.type} {arg}" for arg in self.args)
        if self.type.is_void:
            return f"syscall {self.syscall_number}({args_str})"
        return f"%{self.name} = syscall {self.type} #{self.syscall_number}({args_str})"