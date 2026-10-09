from typing import Dict, Optional, Set, List, Tuple
from ..core.cfg import Function, BasicBlock
from ..core.value import Value, ConstantSymbol, UndefValue, Argument, ExternalValue
from ..instructions.special import PhiNode
from ..types.base import Type
from ...lir.block import LIRBlock, LIRFunction
from ...target.binary.memory import BinaryMemoryView
from ...const import Arch
from ...target.abi import TargetABI
from ...target.factory import get_target_abi
from .engine import BraunSSAEngine
from .translator import LIRTranslator
from ..types.utils import TypeUtils


class SSABuilder:
    """
    Pure Architecture-Neutral SSA Lowering Engine.
    Strictly follows Braun SSA construction without machine-specific assumptions.
    Decouples hardware registers from high-level dataflow semantics via TargetABI.
    """
    __slots__ = ('_lir_func', '_memory', '_arch_bits', '_abi', '_sp_base', '_entry_args', '_entry_ext_vars')

    def __init__(
        self,
        lir_func: LIRFunction,
        memory: Optional[BinaryMemoryView] = None,
        abi: Optional[TargetABI] = None
    ):
        self._lir_func: LIRFunction = lir_func
        self._memory: Optional[BinaryMemoryView] = memory
        self._arch_bits: int = lir_func.arch_bits
        self._abi: TargetABI = abi if abi is not None else get_target_abi(Arch.ARM64)

        # Ambient machine stack base: an immutable symbolic root, NEVER an argument
        word_type = TypeUtils.get_int_type(self._arch_bits)
        self._sp_base: Value = ConstantSymbol.get(word_type, "sp_base")

        self._entry_args: Dict[int, Value] = {}
        self._entry_ext_vars: Dict[str, ExternalValue] = {}

    @staticmethod
    def _compute_rpo(entry_block: LIRBlock, all_blocks: List[LIRBlock]) -> List[LIRBlock]:
        """
        Computes Reverse Post-Order (RPO) over the LIR control flow graph.
        Guarantees that entry is first, and all reachable forward blocks precede their successors.
        Disconnected/unreachable blocks are appended at the end to prevent data loss.
        """
        visited: Set[LIRBlock] = set()
        post_order: List[LIRBlock] = []

        stack: List[Tuple[LIRBlock, int]] = [(entry_block, 0)]
        visited.add(entry_block)

        while stack:
            curr, idx = stack[-1]
            if idx < len(curr.successors):
                succ = curr.successors[idx]
                stack[-1] = (curr, idx + 1)
                if succ not in visited:
                    visited.add(succ)
                    stack.append((succ, 0))
            else:
                stack.pop()
                post_order.append(curr)

        for b in all_blocks:
            if b not in visited:
                stack = [(b, 0)]
                visited.add(b)
                while stack:
                    curr, idx = stack[-1]
                    if idx < len(curr.successors):
                        succ = curr.successors[idx]
                        stack[-1] = (curr, idx + 1)
                        if succ not in visited:
                            visited.add(succ)
                            stack.append((succ, 0))
                    else:
                        stack.pop()
                        post_order.append(curr)

        return post_order[::-1]

    def build(self) -> Function:
        ret_type = TypeUtils.get_int_type(self._arch_bits)
        mir_func = Function(name=self._lir_func.name, return_type=ret_type)

        if not self._lir_func.blocks:
            return mir_func

        entry_lir = self._lir_func.get_block(self._lir_func.entry_addr)
        if entry_lir is None:
            entry_lir = self._lir_func.blocks[0]

        rpo_lir_blocks = self._compute_rpo(entry_lir, self._lir_func.blocks)

        block_map: Dict[int, BasicBlock] = {}
        for lir_b in rpo_lir_blocks:
            mir_b = BasicBlock(name=f"block_0x{lir_b.addr:x}")
            block_map[lir_b.addr] = mir_b
            mir_func.append_block(mir_b)

        entry_block = block_map[entry_lir.addr]

        # Connect CFG edges
        for lir_b in rpo_lir_blocks:
            mir_b = block_map[lir_b.addr]
            for succ in lir_b.successors:
                mir_succ = block_map.get(succ.addr)
                if mir_succ is not None:
                    mir_b.add_successor(mir_succ)
                    mir_succ.add_predecessor(mir_b)

        ssa_engine = BraunSSAEngine()

        def _resolve_entry_variable(name: str, val_type: Type, block: BasicBlock) -> Value:
            if block is not entry_block:
                return UndefValue.get(val_type)

            if self._abi.is_stack_pointer(name):
                return self._sp_base

            if self._abi.is_arg_register(name):
                arg_idx = self._abi.get_argument_index(name)
                if arg_idx in self._entry_args:
                    return self._entry_args[arg_idx]

                arg = mir_func.add_argument(val_type, name=f"a{arg_idx}")
                self._entry_args[arg_idx] = arg
                return arg

            if self._abi.is_sys_register(name):
                return ConstantSymbol.get(val_type, name)

            if name not in self._entry_ext_vars:
                self._entry_ext_vars[name] = ExternalValue(val_type, name=f"ext_{name}")
            return self._entry_ext_vars[name]

        ssa_engine.set_entry_resolver(_resolve_entry_variable)

        # Pre-seed stack pointer in entry block
        ssa_engine.write_variable(self._abi.stack_pointer_name, entry_block, self._sp_base)

        translator = LIRTranslator(
            ssa=ssa_engine,
            block_map=block_map,
            memory=self._memory,
            arch_bits=self._arch_bits
        )

        filled_blocks: Set[BasicBlock] = set()
        ssa_engine.seal_block(entry_block)

        for lir_b in rpo_lir_blocks:
            mir_b = block_map[lir_b.addr]

            # In RPO, if all predecessors are already filled, seal prior to lowering
            if mir_b.predecessors and all(p in filled_blocks for p in mir_b.predecessors):
                ssa_engine.seal_block(mir_b)

            for insn in lir_b.insns:
                translator.lower_insn(insn, mir_b)

            filled_blocks.add(mir_b)

            # Check if any successor can now be sealed
            for succ in mir_b.successors:
                if not ssa_engine.is_sealed(succ):
                    if all(p in filled_blocks for p in succ.predecessors):
                        ssa_engine.seal_block(succ)

        # Seal any remaining loop headers (back-edge cycles)
        for lir_b in rpo_lir_blocks:
            mir_b = block_map[lir_b.addr]
            if not ssa_engine.is_sealed(mir_b):
                ssa_engine.seal_block(mir_b)

        self._eliminate_trivial_phis(mir_func)
        self._canonicalize_function_arguments(mir_func)

        return mir_func

    @staticmethod
    def _eliminate_trivial_phis(func: Function) -> None:
        changed = True
        while changed:
            changed = False
            for block in func.blocks:
                for inst in list(block):
                    if isinstance(inst, PhiNode):
                        same = None
                        is_trivial = True
                        for i in range(inst.num_incoming):
                            op = inst.get_incoming_value(i)
                            if op is not None:
                                op = op.resolve()
                                inst.set_incoming_value(i, op)
                            if op is same or op is inst or isinstance(op, UndefValue):
                                continue
                            if same is not None:
                                is_trivial = False
                                break
                            same = op

                        if is_trivial:
                            target = same if same is not None else UndefValue.get(inst.type)
                            inst.replace_all_uses_with(target)
                            inst.erase_from_parent()
                            changed = True

    def _canonicalize_function_arguments(self, func: Function) -> None:
        if not self._entry_args:
            return

        max_arg_idx = max(self._entry_args.keys())
        word_type = TypeUtils.get_int_type(self._arch_bits)

        for i in range(max_arg_idx + 1):
            if i not in self._entry_args:
                dummy_arg = Argument(word_type, name=f"a{i}", arg_index=i)
                dummy_arg._set_parent(func)
                self._entry_args[i] = dummy_arg

        sorted_args = [self._entry_args[i] for i in sorted(self._entry_args.keys())]

        func.args.clear()
        for real_idx, arg in enumerate(sorted_args):
            arg._arg_index = real_idx
            arg.name = f"a{real_idx}"
            func.args.append(arg)