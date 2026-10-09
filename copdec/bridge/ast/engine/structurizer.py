from typing import Set, List, Tuple

from ....ir.core.cfg import Function
from ....ir.analysis.dominance import DominanceTree
from ....ir.analysis.post_dominance import PostDominanceTree
from ....ir.analysis.loops import LoopInfo

from ....ast.types import CType
from ....ast.nodes import CBlock, CFunction, CVarExpr, CAssignStmt

from .lowering.high_var import HighVariableManager
from .lowering.type_mapper import TypeMapper
from .lowering.scope_resolver import VariableScopePlacement
from .lowering.instruction_translator import InstructionTranslator
from .structurize.tree_builder import ControlTreeBuilder
from .lowering.c_builder import CASTBuilder
from ...ir.scope import IRScope


class ControlFlowStructurizer:
    __slots__ = (
        '_func', '_dom_tree', '_pdom_tree', '_loop_info',
        '_high_var_mgr', '_declared_vars', '_memory'
    )

    def __init__(self, scope: IRScope):
        self._func: Function = scope.func
        self._dom_tree = scope.get_analysis_optional(DominanceTree)
        self._pdom_tree = scope.get_analysis_optional(PostDominanceTree)
        self._loop_info = scope.get_analysis_optional(LoopInfo)
        self._memory = scope.memory

        self._declared_vars: Set[str] = set()
        self._high_var_mgr = HighVariableManager(self._func)

    def structurize(self) -> CFunction:
        params = self._infer_active_parameters()
        ret_ctype = self._infer_return_type()
        root_block = CBlock()

        scope_placement = VariableScopePlacement(self._func, self._high_var_mgr)
        for vid in sorted(scope_placement.hoisted_vars):
            cvar = self._high_var_mgr._cvar_cache.get(vid)
            if cvar is None:
                for hv in self._high_var_mgr._high_vars:
                    if hv.id == vid:
                        cvar = CVarExpr(hv.name, hv.ctype)
                        break
            if cvar is not None and cvar.name not in self._declared_vars:
                root_block.append(CAssignStmt(cvar, expr=None, is_declaration=True))
                self._declared_vars.add(cvar.name)

        tree_builder = ControlTreeBuilder(
            func=self._func,
            dom_tree=self._dom_tree,
            pdom_tree=self._pdom_tree,
            loop_info=self._loop_info
        )
        region_tree = tree_builder.build()

        translator = InstructionTranslator(
            high_var_mgr=self._high_var_mgr,
            declared_vars=self._declared_vars,
            memory=self._memory
        )
        c_builder = CASTBuilder(
            translator=translator,
            labels_in_use=tree_builder.labels_in_use
        )
        c_builder.lower(region_tree, root_block)

        return CFunction(
            name=self._func.name,
            return_type=ret_ctype,
            params=params,
            body=root_block
        )

    def _infer_active_parameters(self) -> List[Tuple[str, CType]]:
        params: List[Tuple[str, CType]] = []
        for arg in self._func.args:
            ctype = TypeMapper.ir_to_ctype(arg.type)
            name = arg.name if arg.name else f"a{arg.arg_index}"
            self._declared_vars.add(name)
            params.append((name, ctype))
        return params

    def _infer_return_type(self) -> CType:
        if self._func.type.is_void:
            return CType("void", bit_width=0)
        return TypeMapper.ir_to_ctype(self._func.type)