from typing import Dict, Set, Optional, Callable
from ..core.cfg import BasicBlock
from ..core.value import Value, UndefValue
from ..types.base import Type
from ..instructions.special import PhiNode

EntryResolverFunc = Callable[[str, Type, BasicBlock], Value]


class BraunSSAEngine:
    """
    Pure Implementation of Braun's SSA Construction Algorithm (Braun et al., CC 2013).
    Guarantees minimal SSA with on-the-fly trivial Phi elimination.
    """
    __slots__ = ('_current_def', '_incomplete_phis', '_sealed_blocks', '_entry_resolver')

    def __init__(self):
        # current_def[var_name][block] = Value
        self._current_def: Dict[str, Dict[BasicBlock, Value]] = {}
        # incomplete_phis[block][var_name] = PhiNode
        self._incomplete_phis: Dict[BasicBlock, Dict[str, PhiNode]] = {}
        # sealed_blocks: {block}
        self._sealed_blocks: Set[BasicBlock] = set()
        self._entry_resolver: Optional[EntryResolverFunc] = None

    def set_entry_resolver(self, resolver: EntryResolverFunc) -> None:
        """Registers handler for upward-exposed variable reads at entry blocks."""
        self._entry_resolver = resolver

    def is_sealed(self, block: BasicBlock) -> bool:
        return block in self._sealed_blocks

    def write_variable(self, name: str, block: BasicBlock, val: Value) -> None:
        """Sets the active definition of a variable in the given basic block."""
        name = name.lower()
        if name not in self._current_def:
            self._current_def[name] = {}
        self._current_def[name][block] = val.resolve()

    def read_variable(self, name: str, block: BasicBlock, val_type: Type) -> Value:
        """Reads the active definition of a variable, recursing or creating Phis if needed."""
        name = name.lower()
        block_defs = self._current_def.get(name)
        if block_defs is not None and block in block_defs:
            val = block_defs[block]
            resolved = val.resolve()
            if resolved is not val:
                block_defs[block] = resolved
            return resolved
        return self._read_variable_recursive(name, block, val_type)

    def seal_block(self, block: BasicBlock) -> None:
        """Seals the basic block, completing all incomplete Phi nodes."""
        if block in self._sealed_blocks:
            return

        incomplete = self._incomplete_phis.pop(block, {})
        for name, phi in incomplete.items():
            canonical_val = self._add_phi_operands(name, phi, block)
            self.write_variable(name, block, canonical_val.resolve())

        self._sealed_blocks.add(block)

    def _read_variable_recursive(self, name: str, block: BasicBlock, val_type: Type) -> Value:
        val: Value

        if block not in self._sealed_blocks:
            # Unsealed block: create incomplete Phi node
            block_pc = block.first_instruction.pc if block.first_instruction else 0
            phi = PhiNode(val_type=val_type, name=f"{name}_phi", pc=block_pc)
            self._insert_phi_at_head(block, phi)

            if block not in self._incomplete_phis:
                self._incomplete_phis[block] = {}
            self._incomplete_phis[block][name] = phi
            val = phi

        elif len(block.predecessors) == 0:
            # Entry block with zero predecessors: invoke live-on-entry resolver
            if self._entry_resolver is not None:
                val = self._entry_resolver(name, val_type, block)
            else:
                val = UndefValue.get(val_type)

        elif len(block.predecessors) == 1:
            # Single predecessor: straight forwarding
            val = self.read_variable(name, block.predecessors[0], val_type)

        else:
            # Multiple predecessors: create Phi and collect incoming values
            block_pc = block.first_instruction.pc if block.first_instruction else 0
            phi = PhiNode(val_type=val_type, name=f"{name}_phi", pc=block_pc)
            self._insert_phi_at_head(block, phi)

            # Break cycles before recursion
            self.write_variable(name, block, phi)
            val = self._add_phi_operands(name, phi, block)

        val = val.resolve()
        self.write_variable(name, block, val)
        return val

    def _add_phi_operands(self, name: str, phi: PhiNode, block: BasicBlock) -> Value:
        for pred in block.predecessors:
            op_val = self.read_variable(name, pred, phi.type).resolve()
            phi.add_incoming(op_val, pred)
        return self.try_remove_trivial_phi(phi).resolve()

    @classmethod
    def try_remove_trivial_phi(cls, phi: PhiNode) -> Value:
        """Eliminates redundant or self-referential Phi nodes: phi(v, v) -> v, phi(v, phi) -> v."""
        same: Optional[Value] = None

        for i in range(phi.num_incoming):
            op = phi.get_incoming_value(i)
            if op is not None:
                op = op.resolve()
                
            if op is same or op is phi or isinstance(op, UndefValue):
                continue

            if same is not None:
                return phi

            same = op

        if same is None:
            same = UndefValue.get(phi.type)

        # Collect dependent Phi users for cascading optimization
        dependent_phis: Set[PhiNode] = set()
        for use in phi.uses:
            if isinstance(use.user, PhiNode) and use.user is not phi:
                dependent_phis.add(use.user)

        phi.replace_all_uses_with(same)
        if phi.parent is not None:
            phi.erase_from_parent()

        # Cascading simplification of dependent Phis
        for dep_phi in dependent_phis:
            if dep_phi.parent is not None:
                cls.try_remove_trivial_phi(dep_phi)

        return same

    @staticmethod
    def _insert_phi_at_head(block: BasicBlock, phi: PhiNode) -> None:
        if block.first_instruction is not None:
            block.insert_before(block.first_instruction, phi)
        else:
            block.append_instruction(phi)