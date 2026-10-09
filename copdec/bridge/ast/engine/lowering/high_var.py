from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional
from .....ir.core.cfg import Function, Instruction
from .....ir.core.value import Value, Argument, Constant, ExternalValue
from .....ir.opcodes import IROpcode
from .....ir.instructions.special import PhiNode
from .....ir.instructions.memory import AllocaInst
from .....ast.types import CType
from .....ast.nodes import CVarExpr
from .type_mapper import TypeMapper


class HighVariableDSU:
    __slots__ = ('_parent',)

    def __init__(self):
        self._parent: Dict[Value, Value] = {}

    def find(self, v: Value) -> Value:
        v = v.resolve()
        root = self._parent.get(v)
        if root is None:
            self._parent[v] = v
            return v
        if root is not v:
            root = self.find(root)
            self._parent[v] = root
        return root

    def union(self, v1: Value, v2: Value) -> None:
        root1 = self.find(v1)
        root2 = self.find(v2)
        if root1 is root2:
            return

        if isinstance(root1, Constant) and isinstance(root2, Constant):
            return
        if isinstance(root2, Constant):
            root1, root2 = root2, root1

        if isinstance(root1, (Argument, ExternalValue)) and isinstance(root2, (Argument, ExternalValue)):
            return
        if isinstance(root2, (Argument, ExternalValue)):
            root1, root2 = root2, root1

        if (isinstance(root1, AllocaInst) and isinstance(root2, (Argument, ExternalValue))) or \
        (isinstance(root2, AllocaInst) and isinstance(root1, (Argument, ExternalValue))):
            return

        is_alloca1 = isinstance(root1, AllocaInst)
        is_alloca2 = isinstance(root2, AllocaInst)
        if is_alloca1 and is_alloca2:
            return
        if is_alloca2:
            root1, root2 = root2, root1

        self._parent[root2] = root1


@dataclass(slots=True, eq=False)
class HighVariable:
    id: int
    name: str
    ctype: CType
    is_parameter: bool = False
    is_alloca: bool = False
    members: Set[Value] = field(default_factory=set)

    def __hash__(self) -> int:
        return self.id

    def __eq__(self, other: object) -> bool:
        return isinstance(other, HighVariable) and self.id == other.id


class HighVariableManager:
    __slots__ = (
        '_func', '_dsu', '_value_to_high_var', '_high_vars',
        '_cvar_cache', '_counter_var'
    )

    def __init__(self, func: Function):
        self._func = func
        self._dsu = HighVariableDSU()
        self._value_to_high_var: Dict[Value, HighVariable] = {}
        self._high_vars: List[HighVariable] = []
        self._cvar_cache: Dict[int, CVarExpr] = {}
        self._counter_var = 0

        self._build_webs()
        self._assign_high_variables()

    def _generate_semantic_name(self, ctype: CType) -> str:
        self._counter_var += 1
        prefix = "b" if (ctype.name == "bool" or ctype.bit_width == 1) else "v"
        return f"{prefix}{self._counter_var}"

    def get_high_var(self, val: Value) -> Optional[HighVariable]:
        return self._value_to_high_var.get(val.resolve())

    def get_cvar(self, val: Value) -> CVarExpr:
        canonical_val = val.resolve()
        hv = self._value_to_high_var.get(canonical_val)
        
        if hv is not None:
            if hv.id not in self._cvar_cache:
                self._cvar_cache[hv.id] = CVarExpr(hv.name, hv.ctype)
            return self._cvar_cache[hv.id]

        raise KeyError(
            f"[HighVariableManager] Value {canonical_val} (raw={val}, type={val.type}, "
            f"cls={val.__class__.__name__}) has no associated HighVariable! "
            f"Pipeline contract broken."
        )

    def _build_webs(self) -> None:
        for block in self._func.blocks:
            for inst in block:
                if isinstance(inst, PhiNode):
                    for i in range(inst.num_incoming):
                        in_val = inst.get_incoming_value(i)
                        if in_val is not None and not isinstance(in_val.resolve(), Constant):
                            self._dsu.union(inst, in_val)

    def _assign_high_variables(self) -> None:
        root_groups: Dict[Value, Set[Value]] = {}

        all_values: List[Value] = [arg.resolve() for arg in self._func.args]
        for block in self._func.blocks:
            for inst in block:
                if not inst.type.is_void and not inst.type.is_label:
                    all_values.append(inst.resolve())

                for i in range(inst.num_operands):
                    op = inst.get_operand(i).resolve()
                    if not isinstance(op, Constant) and not op.type.is_label:
                        all_values.append(op)

        for val in all_values:
            if isinstance(val, Constant):
                continue
            root = self._dsu.find(val)
            root_groups.setdefault(root, set()).add(val)

        var_id = 1
        used_names: Set[str] = set()

        for root, members in root_groups.items():
            param_member = next((m for m in members if isinstance(m, Argument)), None)
            alloca_member = next((m for m in members if isinstance(m, AllocaInst)), None)
            ext_member = next((m for m in members if isinstance(m, ExternalValue)), None)
    
            if param_member is not None:
                var_name = param_member.name
                ctype = TypeMapper.ir_to_ctype(param_member.type)
                is_param, is_alloca = True, False
    
            elif alloca_member is not None:
                var_name = alloca_member.name
                ctype = TypeMapper.ir_to_ctype(alloca_member.allocated_type)
                is_param, is_alloca = False, True
    
            elif ext_member is not None:
                var_name = ext_member.name
                ctype = TypeMapper.ir_to_ctype(ext_member.type)
                is_param, is_alloca = False, False
    
            else:
                sample_val = next(iter(members))
                ctype = TypeMapper.ir_to_ctype(sample_val.type)
                var_name = self._generate_semantic_name(ctype)
                is_param, is_alloca = False, False

            orig_name = var_name
            suffix_idx = 1
            while var_name in used_names:
                suffix_idx += 1
                var_name = f"{orig_name}_{suffix_idx}"
            used_names.add(var_name)

            hv = HighVariable(
                id=var_id,
                name=var_name,
                ctype=ctype,
                is_parameter=is_param,
                is_alloca=is_alloca,
                members=members
            )
            self._high_vars.append(hv)

            for member in members:
                self._value_to_high_var[member] = hv
            self._value_to_high_var[root] = hv

            var_id += 1