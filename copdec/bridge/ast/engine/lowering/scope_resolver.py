from typing import Dict, Set
from .....ir.core.cfg import Function, BasicBlock
from .high_var import HighVariableManager

class VariableScopePlacement:
    __slots__ = (
        '_func', '_high_var_mgr', '_var_defs', '_var_uses',
        'hoisted_vars', 'block_local_vars'
    )

    def __init__(self, func: Function, high_var_mgr: HighVariableManager):
        self._func = func
        self._high_var_mgr = high_var_mgr
        
        # var_id -> Set[BasicBlock]
        self._var_defs: Dict[int, Set[BasicBlock]] = {}
        self._var_uses: Dict[int, Set[BasicBlock]] = {}
        
        self.hoisted_vars: Set[int] = set()
        
        self.block_local_vars: Set[int] = set()

        self._analyze()

    def _analyze(self) -> None:
        for bb in self._func.blocks:
            for inst in bb:
                # Instruction result is Def
                hv_def = self._high_var_mgr.get_high_var(inst)
                if hv_def is not None and not hv_def.is_parameter:
                    self._var_defs.setdefault(hv_def.id, set()).add(bb)

                # Operands is Uses
                for i in range(inst.num_operands):
                    op = inst.get_operand(i).resolve()
                    hv_use = self._high_var_mgr.get_high_var(op)
                    if hv_use is not None and not hv_use.is_parameter:
                        self._var_uses.setdefault(hv_use.id, set()).add(bb)

        all_var_ids = set(self._var_defs.keys()) | set(self._var_uses.keys())
        for vid in all_var_ids:
            defs = self._var_defs.get(vid, set())
            uses = self._var_uses.get(vid, set())
            all_blocks = defs | uses

            # first define = local var
            if len(all_blocks) <= 1:
                self.block_local_vars.add(vid)
            else:
                # Var live in more than 1 block so we inline it ahead
                self.hoisted_vars.add(vid)

    def is_hoisted(self, var_id: int) -> bool:
        return var_id in self.hoisted_vars