from ...bridge.ast.scope import ASTScope

from ...pipeline.passer import Pass

from ..visitor import ASTTransformer
from ..nodes import CExpr, CBinaryExpr, CUnaryExpr, CLiteralExpr, CIfStmt
from ..types import CType

CMP_INVERT_MAP = {
    "==": "!=", "!=": "==",
    "<": ">=", "<=": ">",
    ">": "<=", ">=": "<"
}


class ConditionNormalizer(ASTTransformer):
    __slots__ = ('modified',)

    def __init__(self):
        self.modified: bool = False

    def visit_CUnaryExpr(self, node: CUnaryExpr) -> CExpr:
        node.operand = self.visit(node.operand)

        if node.op == "!":
            if isinstance(node.operand, CUnaryExpr) and node.operand.op == "!":
                self.modified = True
                return node.operand.operand

            if isinstance(node.operand, CBinaryExpr) and node.operand.op in CMP_INVERT_MAP:
                node.operand.op = CMP_INVERT_MAP[node.operand.op]
                self.modified = True
                return node.operand

        return node

    def visit_CBinaryExpr(self, node: CBinaryExpr) -> CExpr:
        node.lhs = self.visit(node.lhs)
        node.rhs = self.visit(node.rhs)

        if isinstance(node.rhs, CLiteralExpr) and node.rhs.val == 0:
            if isinstance(node.lhs, CBinaryExpr) and node.lhs.op == "-":
                if node.op in CMP_INVERT_MAP:
                    self.modified = True
                    return CBinaryExpr(node.op, node.lhs.lhs, node.lhs.rhs, node.ctype)

        if node.op == "==" and isinstance(node.rhs, CLiteralExpr) and node.rhs.val == 1:
            if isinstance(node.lhs, CBinaryExpr) and node.lhs.ctype.name == "bool":
                self.modified = True
                return node.lhs

        if node.op == "==" and isinstance(node.rhs, CLiteralExpr) and node.rhs.val == 0:
            if isinstance(node.lhs, CBinaryExpr) and node.lhs.op in CMP_INVERT_MAP:
                node.lhs.op = CMP_INVERT_MAP[node.lhs.op]
                self.modified = True
                return node.lhs

        if node.op == "!=" and isinstance(node.rhs, CLiteralExpr) and node.rhs.val == 0:
            if isinstance(node.lhs, CBinaryExpr) and node.lhs.ctype.name == "bool":
                self.modified = True
                return node.lhs

        return node

    def visit_CIfStmt(self, node: CIfStmt) -> CIfStmt:
        node.cond = self.visit(node.cond)
        node.then_block = self.visit(node.then_block)
        if node.else_block:
            node.else_block = self.visit(node.else_block)

        if (not node.then_block.stmts) and (node.else_block and node.else_block.stmts):
            node.cond = self._invert_c_expr(node.cond)
            node.then_block = node.else_block
            node.else_block = None
            self.modified = True

        return node

    def _invert_c_expr(self, cond: CExpr) -> CExpr:
        if isinstance(cond, CBinaryExpr) and cond.op in CMP_INVERT_MAP:
            cond.op = CMP_INVERT_MAP[cond.op]
            return cond
        return CUnaryExpr("!", cond, CType("bool", bit_width=1))


class ConditionNormalizerPass(Pass):
    __slots__ = ()

    def run(self, scope: ASTScope) -> bool:
        normalizer = ConditionNormalizer()
        normalizer.visit(scope.cfunc)
        return normalizer.modified