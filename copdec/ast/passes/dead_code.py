from typing import Set, List, Optional, Union
from ...bridge.ast.scope import ASTScope
from ...pipeline.passer import Pass
from ..visitor import ASTVisitor, ASTTransformer
from ..nodes import (
    CBlock, CStmt, CReturnStmt, CGotoStmt, CLabelStmt, CIfStmt,
    CWhileStmt, CExprStmt, CCallExpr, CUnaryExpr, CIndexExpr, CMemberExpr,
    CLiteralExpr, CCastExpr, CExpr
)


class SideEffectChecker(ASTVisitor):
    __slots__ = ('has_side_effects',)

    def __init__(self):
        self.has_side_effects: bool = False

    def visit_CCallExpr(self, node: CCallExpr) -> None:
        self.has_side_effects = True

    def visit_CUnaryExpr(self, node: CUnaryExpr) -> None:
        if node.op in ("*", "++", "--"):
            self.has_side_effects = True
        super().visit_CUnaryExpr(node)

    def visit_CIndexExpr(self, node: CIndexExpr) -> None:
        self.has_side_effects = True

    def visit_CMemberExpr(self, node: CMemberExpr) -> None:
        if node.is_arrow:
            self.has_side_effects = True


class GotoCollector(ASTVisitor):
    __slots__ = ('target_labels',)

    def __init__(self):
        self.target_labels: Set[str] = set()

    def visit_CGotoStmt(self, node: CGotoStmt) -> None:
        self.target_labels.add(node.label)


class DeadCodePruner(ASTTransformer):
    __slots__ = ('_live_gotos', 'modified')

    def __init__(self):
        self._live_gotos: Set[str] = set()
        self.modified: bool = False

    @staticmethod
    def _unwrap_const_bool(cond: CExpr) -> Optional[bool]:
        curr = cond
        while isinstance(curr, CCastExpr):
            curr = curr.expr
        if isinstance(curr, CLiteralExpr):
            if isinstance(curr.val, bool):
                return curr.val
            if isinstance(curr.val, int):
                return curr.val != 0
        return None

    @staticmethod
    def _has_side_effects(expr: CExpr) -> bool:
        checker = SideEffectChecker()
        checker.visit(expr)
        return checker.has_side_effects

    def visit_CFunction(self, node):
        collector = GotoCollector()
        collector.visit(node)
        self._live_gotos = collector.target_labels
        node.body = self.visit(node.body)

        if node.return_type.name == "void" and node.body.stmts:
            last_stmt = node.body.stmts[-1]
            if isinstance(last_stmt, CReturnStmt) and last_stmt.val is None:
                node.body.stmts.pop()
                self.modified = True

        return node

    def visit_CIfStmt(self, node: CIfStmt) -> Union[Optional[CStmt], List[CStmt]]:
        node.cond = self.visit(node.cond)
        node.then_block = self.visit(node.then_block)
        if node.else_block:
            node.else_block = self.visit(node.else_block)

        const_val = self._unwrap_const_bool(node.cond)
        if const_val is True:
            self.modified = True
            return node.then_block.stmts
        elif const_val is False:
            self.modified = True
            if node.else_block and node.else_block.stmts:
                return node.else_block.stmts
            return None

        has_then = bool(node.then_block and node.then_block.stmts)
        has_else = bool(node.else_block and node.else_block.stmts)
        if not has_then and not has_else:
            self.modified = True
            if self._has_side_effects(node.cond):
                return CExprStmt(node.cond)
            return None

        return node

    def visit_CWhileStmt(self, node: CWhileStmt) -> Optional[CStmt]:
        node.cond = self.visit(node.cond)
        node.body = self.visit(node.body)

        # while (false) { ... } => dead body 
        const_val = self._unwrap_const_bool(node.cond)
        if const_val is False:
            self.modified = True
            return None

        return node

    def visit_CBlock(self, node: CBlock) -> CBlock:
        new_stmts: List[CStmt] = []
        saw_terminator = False

        for stmt in node.stmts:
            if isinstance(stmt, CLabelStmt) and stmt.label not in self._live_gotos:
                self.modified = True
                continue

            if isinstance(stmt, CLabelStmt) and stmt.label in self._live_gotos:
                saw_terminator = False

            if saw_terminator:
                self.modified = True
                continue

            res = self.visit(stmt)
            if res is not None:
                if isinstance(res, list):
                    new_stmts.extend(res)
                    for s in res:
                        if isinstance(s, (CReturnStmt, CGotoStmt)):
                            saw_terminator = True
                            break
                else:
                    new_stmts.append(res)
                    if isinstance(res, (CReturnStmt, CGotoStmt)):
                        saw_terminator = True
            elif isinstance(stmt, (CReturnStmt, CGotoStmt)):
                saw_terminator = True

        node.stmts = new_stmts
        return node


class DeadCodePrunerPass(Pass):
    """AST Pass: eliminates unreachable statements, dead if-branches, and unused labels."""
    __slots__ = ()

    def run(self, scope: ASTScope) -> bool:
        pruner = DeadCodePruner()
        pruner.visit(scope.cfunc)
        return pruner.modified