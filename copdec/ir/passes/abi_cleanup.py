from typing import Set, List, Optional
from ...bridge.ir.scope import IRScope
from ...pipeline.passer import IRPass
from ..core.cfg import Function
from ..core.value import Argument, Value, ConstantSymbol, ConstantInt, UndefValue, ExternalValue
from ..instructions.special import CallInst, PhiNode, SelectInst
from ..instructions.cast import CastInst
from ..instructions.control import ReturnInst, BranchCondInst, SwitchInst
from ..instructions.alu import BinaryOperator, UnaryOperator, ICmpInst, FCmpInst
from ..instructions.memory import StoreInst, LoadInst
from ..types.base import Void


class CallingConventionCleanupPass(IRPass):
    """
    Robust ABI Calling Convention Normalizer:
    1. Prunes dummy tail arguments (a1..a7, UndefValue) emitted by instruction lifters.
    2. Preserves legitimate dataflow arguments (computed values, ExternalValue, constants).
    3. Strips unused formal parameters from func.args without polluting the signature.
    4. Infers void return types.
    """
    __slots__ = ()

    def run(self, scope: IRScope) -> bool:
        func: Function = scope.func
        if not func.blocks or func.entry_block is None:
            return False

        modified = False

        substantive_args = {arg for arg in func.args if self._has_substantive_uses(arg)}
        max_live_idx = max((a.arg_index for a in substantive_args), default=-1)

        for block in func.blocks:
            for inst in block:
                if isinstance(inst, CallInst):
                    known_arity = self._resolve_callee_arity(inst, scope)
                    if known_arity is not None:
                        if len(inst.args) > known_arity:
                            inst.set_args(inst.args[:known_arity])
                            modified = True
                    else:
                        modified |= self._prune_call_tail(inst, substantive_args)

        surviving_args = [a for a in func.args if a.arg_index <= max_live_idx]
        dead_args = [a for a in func.args if a.arg_index > max_live_idx]

        if dead_args:
            for dead_arg in dead_args:
                dead_arg.replace_all_uses_with(UndefValue.get(dead_arg.type))

            func.args.clear()
            for idx, arg in enumerate(surviving_args):
                arg._arg_index = idx
                arg.name = f"a{idx}"
                func.args.append(arg)
            modified = True

        modified |= self._cleanup_return_signature(func)

        return modified

    def _has_substantive_uses(self, val: Value) -> bool:
        for use in val.uses:
            user = use.user
            if isinstance(user, (BinaryOperator, UnaryOperator, ICmpInst, FCmpInst)):
                return True
            if isinstance(user, (StoreInst, LoadInst, BranchCondInst, SwitchInst, ReturnInst)):
                return True
            if isinstance(user, (CastInst, PhiNode, SelectInst)):
                if self._has_substantive_uses(user):
                    return True
            if isinstance(user, CallInst):
                if use.operand_index <= 1:
                    return True
        return False

    def _prune_call_tail(self, call: CallInst, substantive_args: Set[Argument]) -> bool:
        args = call.args
        if not args:
            return False

        new_args = list(args)

        while new_args:
            last = new_args[-1].resolve()

            if isinstance(last, UndefValue):
                new_args.pop()
                continue

            if isinstance(last, Argument) and last not in substantive_args:
                new_args.pop()
                continue

            break

        if len(new_args) != len(args):
            call.set_args(new_args)
            return True

        return False

    def _cleanup_return_signature(self, func: Function) -> bool:
        return_insts = [
            b.get_terminator() for b in func.blocks
            if isinstance(b.get_terminator(), ReturnInst)
        ]
        if not return_insts:
            return False

        modified = False
        all_void = True
        inferred_type = None

        for ret in return_insts:
            val = ret.return_value
            if val is None:
                continue

            resolved = val.resolve()
            if isinstance(resolved, UndefValue):
                ret.remove_operand(0)
                modified = True
            elif isinstance(resolved, Argument) and resolved.arg_index == 0 and len(resolved.uses) <= 1:
                ret.remove_operand(0)
                modified = True
            else:
                all_void = False
                if inferred_type is None:
                    inferred_type = resolved.type

        if all_void and func.type is not Void:
            func._type = Void
            modified = True
        elif not all_void and inferred_type is not None and inferred_type != func.type:
            if not inferred_type.is_void:
                func._type = inferred_type
                modified = True

        return modified

    def _resolve_callee_arity(self, call: CallInst, scope: IRScope) -> Optional[int]:
        if scope.memory is None:
            return None
        callee = call.callee
        if isinstance(callee, ConstantInt):
            return scope.memory.get_symbol_arity(callee.value)
        if isinstance(callee, ConstantSymbol) and callee.address != 0:
            return scope.memory.get_symbol_arity(callee.address)
        return None