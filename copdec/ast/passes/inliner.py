import copy
from ...bridge.ast.scope import ASTScope

from typing import Dict, Set, Optional, List

from ...pipeline.passer import Pass

from ..visitor import ASTVisitor, ASTTransformer
from ..nodes import (
    CFunction, CBlock, CStmt, CAssignStmt, CVarExpr, CExpr,
    CUnaryExpr, CLiteralExpr, CCallExpr, CCastExpr,
    CIndexExpr, CMemberExpr, CIfStmt, CWhileStmt, CDoWhileStmt, CForStmt, CSwitchStmt
)


class VariableUsageCollector(ASTVisitor):
    __slots__ = ('use_counts', 'def_counts', 'address_taken_vars')

    def __init__(self):
        self.use_counts: Dict[str, int] = {}
        self.def_counts: Dict[str, int] = {}
        self.address_taken_vars: Set[str] = set()

    def visit_CUnaryExpr(self, node: CUnaryExpr) -> None:
        if node.op == "&" and isinstance(node.operand, CVarExpr):
            self.address_taken_vars.add(node.operand.name)
        else:
            self.visit(node.operand)

    def visit_CVarExpr(self, node: CVarExpr) -> None:
        self.use_counts[node.name] = self.use_counts.get(node.name, 0) + 1

    def visit_CAssignStmt(self, node: CAssignStmt) -> None:
        if isinstance(node.lhs, CVarExpr):
            self.def_counts[node.lhs.name] = self.def_counts.get(node.lhs.name, 0) + 1
        else:
            self.visit(node.lhs)
        if node.expr:
            self.visit(node.expr)


class SideEffectDetector(ASTVisitor):
    __slots__ = ('has_side_effects',)

    def __init__(self):
        self.has_side_effects: bool = False

    def visit_CCallExpr(self, node: CCallExpr) -> None:
        self.has_side_effects = True
        super().visit_CCallExpr(node)

    def visit_CUnaryExpr(self, node: CUnaryExpr) -> None:
        if node.op == "*":
            self.has_side_effects = True
        super().visit_CUnaryExpr(node)

    def visit_CIndexExpr(self, node: CIndexExpr) -> None:
        self.has_side_effects = True
        super().visit_CIndexExpr(node)

    def visit_CMemberExpr(self, node: CMemberExpr) -> None:
        self.has_side_effects = True
        super().visit_CMemberExpr(node)


class ASTSubstitutionTransformer(ASTTransformer):
    __slots__ = ('_substitutions', '_dead_vars', '_visited')

    def __init__(self, substitutions: Dict[str, CExpr], dead_vars: Set[str]):
        self._substitutions = substitutions
        self._dead_vars = dead_vars
        self._visited: Set[str] = set()

    def visit_CBlock(self, node: CBlock) -> CBlock:
        new_stmts: List[CStmt] = []
        for stmt in node.stmts:
            if isinstance(stmt, CAssignStmt) and isinstance(stmt.lhs, CVarExpr):
                var_name = stmt.lhs.name
                if var_name in self._substitutions or var_name in self._dead_vars:
                    continue

            res = self.visit(stmt)
            if res is not None:
                if isinstance(res, list):
                    new_stmts.extend(res)
                else:
                    new_stmts.append(res)
        node.stmts = new_stmts
        return node

    def visit_CAssignStmt(self, node: CAssignStmt) -> Optional[CStmt]:
        if not isinstance(node.lhs, CVarExpr):
            node.lhs = self.visit(node.lhs)
        if node.expr:
            node.expr = self.visit(node.expr)
        return node

    def visit_CUnaryExpr(self, node: CUnaryExpr) -> CExpr:
        if node.op == "&" and isinstance(node.operand, CVarExpr):
            return node
        node.operand = self.visit(node.operand)
        return node

    def visit_CVarExpr(self, node: CVarExpr) -> CExpr:
        if node.name in self._substitutions and node.name not in self._visited:
            self._visited.add(node.name)
            subst = copy.deepcopy(self._substitutions[node.name])
            res = self.visit(subst)
            self._visited.remove(node.name)
            return res
        return node


class ExpressionInliner:
    __slots__ = ('_func',)

    def __init__(self, func: CFunction):
        self._func: CFunction = func

    def inline(self) -> bool:
        modified = False
        collector = VariableUsageCollector()
        collector.visit(self._func)
        use_counts = collector.use_counts
        def_counts = collector.def_counts
        address_taken = collector.address_taken_vars

        substitutions: Dict[str, CExpr] = {}
        dead_vars: Set[str] = set()

        self._collect_candidates(
            self._func.body, use_counts, def_counts, address_taken, substitutions, dead_vars
        )

        if not substitutions and not dead_vars:
            return False

        modified = True
        transformer = ASTSubstitutionTransformer(substitutions, dead_vars)
        transformer.visit(self._func)

        return modified

    def _collect_candidates(
        self,
        block: CBlock,
        use_counts: Dict[str, int],
        def_counts: Dict[str, int],
        address_taken: Set[str],
        substitutions: Dict[str, CExpr],
        dead_vars: Set[str]
    ) -> None:
        for stmt in block.stmts:
            if isinstance(stmt, CAssignStmt) and isinstance(stmt.lhs, CVarExpr):
                var_name = stmt.lhs.name
                if stmt.expr is None:
                    continue

                is_struct = stmt.lhs.ctype.is_struct
                is_memory_storage = is_struct or (var_name in address_taken)

                defs = def_counts.get(var_name, 0)
                uses = use_counts.get(var_name, 0)
                has_effects = self._has_side_effects(stmt.expr)

                if defs > 1 or is_memory_storage:
                    continue

                if uses == 0 and not has_effects:
                    dead_vars.add(var_name)
                    continue

                if isinstance(stmt.expr, CVarExpr):
                    if stmt.expr.name == var_name:
                        dead_vars.add(var_name)
                    elif defs == 1:
                        substitutions[var_name] = stmt.expr
                    continue

                if self._is_trivial(stmt.expr) and not has_effects:
                    substitutions[var_name] = stmt.expr
                    continue

                if uses == 1 and not has_effects:
                    substitutions[var_name] = stmt.expr
                    continue

            if isinstance(stmt, CIfStmt):
                self._collect_candidates(stmt.then_block, use_counts, def_counts, address_taken, substitutions, dead_vars)
                if stmt.else_block:
                    self._collect_candidates(stmt.else_block, use_counts, def_counts, address_taken, substitutions, dead_vars)
            elif isinstance(stmt, (CWhileStmt, CDoWhileStmt, CForStmt)):
                self._collect_candidates(stmt.body, use_counts, def_counts, address_taken, substitutions, dead_vars)
            elif isinstance(stmt, CSwitchStmt):
                for case in stmt.cases:
                    self._collect_candidates(case.body, use_counts, def_counts, address_taken, substitutions, dead_vars)
                if stmt.default_case:
                    self._collect_candidates(stmt.default_case.body, use_counts, def_counts, address_taken, substitutions, dead_vars)

    @staticmethod
    def _is_trivial(expr: CExpr) -> bool:
        if isinstance(expr, (CVarExpr, CLiteralExpr)):
            return True
        if isinstance(expr, CUnaryExpr) and expr.op in ("&", "*"):
            return True
        if isinstance(expr, CCastExpr) and isinstance(expr.expr, (CVarExpr, CLiteralExpr)):
            return True
        return False

    @staticmethod
    def _has_side_effects(expr: CExpr) -> bool:
        detector = SideEffectDetector()
        detector.visit(expr)
        return detector.has_side_effects


class ExpressionInlinerPass(Pass):
    """AST Pass: inlines single-use SSA temporaries and prunes dead variables."""
    __slots__ = ()

    def run(self, scope: ASTScope) -> bool:
        return ExpressionInliner(scope.cfunc).inline()