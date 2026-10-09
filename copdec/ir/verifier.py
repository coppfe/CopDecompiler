

from typing import List, Set, Dict, Optional
from .core.cfg import Function, BasicBlock, Instruction, CFGVerificationError
from .core.value import Value, Constant, Argument
from .instructions.control import (
    TerminatorInst, BranchCondInst, BranchInst, SwitchInst, ReturnInst, UnreachableInst
)
from .instructions.special import PhiNode, SelectInst, CallInst, SyscallInst, IntrinsicInst
from .instructions.alu import BinaryOperator, UnaryOperator, ICmpInst, FCmpInst
from .instructions.cast import CastInst
from .instructions.memory import AllocaInst, LoadInst, StoreInst
from .analysis.dominance import DominanceTree
from .types.base import TypeKind
from .types.integer import Int1


class IRVerifier:
    """
    Comprehensive SSA and Control Flow Graph Invariant Verifier.
    Validates structural CFG symmetry, Def-Use edge bijection,
    dominance properties, and instruction type safety.
    """
    __slots__ = ('_func', '_dom_tree', '_errors')

    def __init__(self, func: Function, dom_tree: Optional[DominanceTree] = None):
        self._func: Function = func
        self._dom_tree: DominanceTree = dom_tree if dom_tree is not None else DominanceTree(func)
        self._errors: List[str] = []

    def verify(self) -> None:
        """
        Executes all verification passes.
        Raises CFGVerificationError with a detailed report if any invariant is violated.
        """
        if not self._func.blocks:
            return

        self._errors.clear()
        self._verify_cfg_topology()
        self._verify_def_use_and_dominance()
        self._verify_type_rules()

        if self._errors:
            report = "\n".join(f"  [{i+1}] {err}" for i, err in enumerate(self._errors))
            raise CFGVerificationError(
                f"IR Verification failed for function '{self._func.name}':\n{report}"
            )

    def _verify_cfg_topology(self) -> None:
        """Validates entry block, block termination, and bidirectional edge symmetry."""
        if self._func.entry_block is None:
            self._errors.append("Function has no designated entry block.")
            return

        if self._func.entry_block.predecessors:
            self._errors.append(
                f"Entry block '%{self._func.entry_block.name}' must not have any predecessors."
            )

        known_blocks: Set[BasicBlock] = set(self._func.blocks)

        for block in self._func.blocks:
            if not block.type.is_label:
                self._errors.append(f"BasicBlock '%{block.name}' must have LabelType, got: {block.type}.")

            if block.parent is not self._func:
                self._errors.append(f"BasicBlock '%{block.name}' parent does not point to current Function.")

            term = block.get_terminator()
            if term is None:
                self._errors.append(f"BasicBlock '%{block.name}' is missing a TerminatorInst at the end.")
            elif term is not block.last_instruction:
                self._errors.append(f"BasicBlock '%{block.name}' contains instructions after its terminator.")

            # Validate that no non-last instruction is a terminator
            curr = block.first_instruction
            while curr is not None and curr is not block.last_instruction:
                if curr.is_terminator:
                    self._errors.append(
                        f"Instruction '{curr}' in block '%{block.name}' is a terminator but not at block end."
                    )
                curr = curr.next_node

            # Edge Symmetry: succ(A) -> B <=> A in pred(B)
            for succ in block.successors:
                if succ not in known_blocks:
                    self._errors.append(f"Block '%{block.name}' references foreign successor '%{succ.name}'.")
                elif block not in succ.predecessors:
                    self._errors.append(
                        f"CFG Edge asymmetry: '%{block.name}' -> '%{succ.name}' missing matching pred-edge."
                    )

            for pred in block.predecessors:
                if pred not in known_blocks:
                    self._errors.append(f"Block '%{block.name}' references foreign predecessor '%{pred.name}'.")
                elif block not in pred.successors:
                    self._errors.append(
                        f"CFG Edge asymmetry: '%{pred.name}' -> '%{block.name}' missing matching succ-edge."
                    )

    def _verify_def_use_and_dominance(self) -> None:
        """Validates Def-Use bijection, SSA dominance, and Phi placement."""
        inst_to_block: Dict[Instruction, BasicBlock] = {}
        for block in self._func.blocks:
            for inst in block:
                inst_to_block[inst] = block

        for block in self._func.blocks:
            saw_non_phi = False

            for inst in block:
                if isinstance(inst, PhiNode):
                    if saw_non_phi:
                        self._errors.append(
                            f"PhiNode '%{inst.name}' appears after non-Phi instruction in block '%{block.name}'."
                        )

                    # Validate Phi bijection with CFG predecessors
                    phi_preds = [inst.get_incoming_block(i) for i in range(inst.num_incoming)]
                    actual_preds = block.predecessors

                    if len(phi_preds) != len(actual_preds) or set(phi_preds) != set(actual_preds):
                        self._errors.append(
                            f"PhiNode '%{inst.name}' incoming blocks {[b.name for b in phi_preds]} "
                            f"do not match CFG predecessors {[b.name for b in actual_preds]}."
                        )
                else:
                    saw_non_phi = True

                # Check operand use-edges and dominance
                for op_idx in range(inst.num_operands):
                    op_val = inst.get_operand(op_idx)
                    use_record = inst.get_use(op_idx)

                    # Def-Use Bijection check
                    if use_record not in op_val.uses:
                        self._errors.append(
                            f"Broken Def-Use edge: '%{inst.name}' operand {op_idx} is not registered in '%{op_val.name}'.uses."
                        )
                    if use_record.user is not inst or use_record.operand_index != op_idx:
                        self._errors.append(
                            f"Corrupted Use record at '%{inst.name}' operand {op_idx}."
                        )

                    # Dominance check for instruction definitions
                    if isinstance(op_val, Instruction):
                        def_block = inst_to_block.get(op_val)
                        if def_block is not None:
                            if isinstance(inst, PhiNode):
                                # For Phi, definition must dominate the corresponding incoming predecessor block
                                incoming_block = inst.get_incoming_block(op_idx)
                                if not self._dom_tree.dominates(def_block, incoming_block):
                                    self._errors.append(
                                        f"SSA Dominance Violation: Def of '%{op_val.name}' in '%{def_block.name}' "
                                        f"does not dominate incoming edge from '%{incoming_block.name}' in Phi '%{inst.name}'."
                                    )
                            else:
                                if def_block is block:
                                    if not self._is_ordered_before(op_val, inst):
                                        self._errors.append(
                                            f"SSA Order Violation: Instruction '%{inst.name}' uses '%{op_val.name}' "
                                            f"before its definition in block '%{block.name}'."
                                        )
                                else:
                                    if not self._dom_tree.dominates(def_block, block):
                                        self._errors.append(
                                            f"SSA Dominance Violation: Def block '%{def_block.name}' does not dominate "
                                            f"use block '%{block.name}' for value '%{op_val.name}' in '%{inst.name}'."
                                        )

    def _verify_type_rules(self) -> None:
        """Validates type consistency of instructions and operators."""
        for block in self._func.blocks:
            for inst in block:
                if isinstance(inst, BinaryOperator):
                    if inst.lhs.type is not inst.rhs.type or inst.lhs.type is not inst.type:
                        self._errors.append(
                            f"BinaryOperator '{inst}' type mismatch: lhs={inst.lhs.type}, rhs={inst.rhs.type}, res={inst.type}."
                        )
                    if not (inst.type.is_integer or inst.type.is_float or inst.type.is_vector):
                        self._errors.append(f"BinaryOperator '{inst}' has invalid non-numeric type: {inst.type}.")

                elif isinstance(inst, UnaryOperator):
                    if inst.operand.type is not inst.type:
                        self._errors.append(
                            f"UnaryOperator '{inst}' type mismatch: operand={inst.operand.type}, res={inst.type}."
                        )

                elif isinstance(inst, ICmpInst):
                    if inst.lhs.type is not inst.rhs.type:
                        self._errors.append(
                            f"ICmpInst '{inst}' operand type mismatch: {inst.lhs.type} vs {inst.rhs.type}."
                        )
                    if not (inst.lhs.type.is_integer or inst.lhs.type.is_pointer):
                        self._errors.append(f"ICmpInst '{inst}' requires integer or pointer operands, got: {inst.lhs.type}.")
                    if inst.type is not Int1:
                        self._errors.append(f"ICmpInst '{inst}' must produce i1 result, got: {inst.type}.")

                elif isinstance(inst, FCmpInst):
                    if inst.lhs.type is not inst.rhs.type:
                        self._errors.append(
                            f"FCmpInst '{inst}' operand type mismatch: {inst.lhs.type} vs {inst.rhs.type}."
                        )
                    if not inst.lhs.type.is_float:
                        self._errors.append(f"FCmpInst '{inst}' requires float operands, got: {inst.lhs.type}.")
                    if inst.type is not Int1:
                        self._errors.append(f"FCmpInst '{inst}' must produce i1 result, got: {inst.type}.")

                elif isinstance(inst, CastInst):
                    try:
                        CastInst._validate_cast(inst.opcode, inst.src.type, inst.dest_type)
                    except TypeError as e:
                        self._errors.append(f"Invalid CastInst '{inst}': {e}")

                elif isinstance(inst, AllocaInst):
                    if not inst.type.is_pointer:
                        self._errors.append(f"AllocaInst '{inst}' must produce PointerType, got: {inst.type}.")
                    if not inst.allocated_type.is_sized:
                        self._errors.append(f"AllocaInst '{inst}' cannot allocate unsized type: {inst.allocated_type}.")

                elif isinstance(inst, LoadInst):
                    if not inst.type.is_sized:
                        self._errors.append(f"LoadInst '{inst}' cannot load unsized type: {inst.type}.")
                    if not (inst.pointer.type.is_pointer or inst.pointer.type.is_integer):
                        self._errors.append(f"LoadInst '{inst}' pointer must be PointerType, got: {inst.pointer.type}.")

                elif isinstance(inst, StoreInst):
                    if not inst.type.is_void:
                        self._errors.append(f"StoreInst '{inst}' result type must be void, got: {inst.type}.")
                    if not inst.value.type.is_sized:
                        self._errors.append(f"StoreInst '{inst}' cannot store unsized value: {inst.value.type}.")
                    if not (inst.pointer.type.is_pointer or inst.pointer.type.is_integer):
                        self._errors.append(f"StoreInst '{inst}' pointer must be PointerType, got: {inst.pointer.type}.")

                elif isinstance(inst, BranchCondInst):
                    if inst.condition.type is not Int1:
                        self._errors.append(f"BranchCondInst '{inst}' condition must be i1, got: {inst.condition.type}.")

                elif isinstance(inst, SwitchInst):
                    if not inst.condition.type.is_integer:
                        self._errors.append(f"SwitchInst '{inst}' condition must be integer, got: {inst.condition.type}.")
                    for val, target in inst.cases:
                        if val.type is not inst.condition.type:
                            self._errors.append(
                                f"SwitchInst '{inst}' case value type mismatch: {val.type} vs {inst.condition.type}."
                            )

                elif isinstance(inst, SelectInst):
                    if inst.condition.type is not Int1:
                        self._errors.append(f"SelectInst '{inst}' condition must be i1, got: {inst.condition.type}.")
                    if inst.true_value.type is not inst.false_value.type or inst.true_value.type is not inst.type:
                        self._errors.append(
                            f"SelectInst '{inst}' branch type mismatch: true={inst.true_value.type}, false={inst.false_value.type}, res={inst.type}."
                        )

                elif isinstance(inst, PhiNode):
                    for i in range(inst.num_incoming):
                        in_val = inst.get_incoming_value(i)
                        if in_val.type is not inst.type:
                            self._errors.append(
                                f"PhiNode '{inst.name}' incoming value {i} type mismatch: expected {inst.type}, got {in_val.type}."
                            )

    @staticmethod
    def _is_ordered_before(first: Instruction, second: Instruction) -> bool:
        """Returns True if instruction 'first' appears strictly before 'second' in the same block."""
        runner = second.prev_node
        while runner is not None:
            if runner is first:
                return True
            runner = runner.prev_node
        return False