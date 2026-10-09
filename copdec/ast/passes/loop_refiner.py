from ...bridge.ast.scope import ASTScope

from ...pipeline.passer import Pass

from ..visitor import ASTTransformer
from ..nodes import (
    CStmt, CWhileStmt, CIfStmt, CBreakStmt, CLiteralExpr, CUnaryExpr, CDoWhileStmt, CContinueStmt
)
from ..types import CType


class LoopRefiner(ASTTransformer):
    __slots__ = ('modified',)

    def __init__(self):
        self.modified: bool = False

    def visit_CWhileStmt(self, node: CWhileStmt) -> CStmt:
        node.body = self.visit(node.body)

        if isinstance(node.cond, CLiteralExpr) and node.cond.val is True:
            if node.body.stmts and isinstance(node.body.stmts[0], CIfStmt):
                first_if = node.body.stmts[0]
                if len(first_if.then_block.stmts) == 1 and isinstance(first_if.then_block.stmts[0], CBreakStmt):
                    if first_if.else_block is None or len(first_if.else_block.stmts) == 0:
                        inv_cond = CUnaryExpr("!", first_if.cond, CType("bool", bit_width=1))
                        node.cond = inv_cond
                        node.body.stmts.pop(0)
                        self.modified = True
                        return node

            if node.body.stmts and isinstance(node.body.stmts[-1], CIfStmt):
                last_if = node.body.stmts[-1]
                if last_if.else_block is None and len(last_if.then_block.stmts) == 1:
                    last_stmt = last_if.then_block.stmts[0]
                    if isinstance(last_stmt, CContinueStmt):
                        cond = last_if.cond
                        node.body.stmts.pop(-1)
                        self.modified = True
                        return CDoWhileStmt(cond, node.body)
                    elif isinstance(last_stmt, CBreakStmt):
                        inv_cond = CUnaryExpr("!", last_if.cond, CType("bool", bit_width=1))
                        node.body.stmts.pop(-1)
                        self.modified = True
                        return CDoWhileStmt(inv_cond, node.body)

        return node

class LoopRefinerPass(Pass):
    """AST Pass: transforms infinite loops into clean while / do-while loops."""
    __slots__ = ()

    def run(self, scope: ASTScope) -> bool:
        refiner = LoopRefiner()
        refiner.visit(scope.cfunc)
        return refiner.modified