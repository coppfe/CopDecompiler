from ...bridge.ast.scope import ASTScope
from ...pipeline.passer import Pass
from ..visitor import ASTTransformer
from ..nodes import (
    CExpr, CCastExpr, CLiteralExpr, CBinaryExpr, CAssignStmt, CStmt, CReturnStmt
)

class CastNormalizer(ASTTransformer):
    """
    Dedicated AST Cast Normalization & Pruning Pass.
    Eliminates redundant, duplicate, and identity type casts.
    """
    __slots__ = ('modified',)

    def __init__(self):
        self.modified: bool = False

    def visit_CLiteralExpr(self, node: CLiteralExpr) -> CExpr:
        return node

    def visit_CCastExpr(self, node: CCastExpr) -> CExpr:
        node.expr = self.visit(node.expr)

        target_type = node.ctype
        inner = node.expr

        if inner.ctype.name == target_type.name and inner.ctype.bit_width == target_type.bit_width:
            self.modified = True
            return inner

        if isinstance(inner, CLiteralExpr) and isinstance(inner.val, int):
            self.modified = True
            inner.ctype = target_type
            return inner

        if isinstance(inner, CCastExpr):
            if not target_type.is_pointer and not inner.ctype.is_pointer:
                if target_type.bit_width == inner.expr.ctype.bit_width and inner.ctype.bit_width < target_type.bit_width:
                    self.modified = True
                    return inner

                if inner.expr.ctype.bit_width == inner.ctype.bit_width:
                    self.modified = True
                    return CCastExpr(target_type, inner.expr)

                if target_type.bit_width <= inner.ctype.bit_width:
                    self.modified = True
                    return CCastExpr(target_type, inner.expr)
        return node

    def visit_CAssignStmt(self, node: CAssignStmt) -> CStmt:
        node.lhs = self.visit(node.lhs)
        if node.expr is not None:
            node.expr = self.visit(node.expr)

            if isinstance(node.expr, CCastExpr):
                if (node.expr.ctype.name == node.lhs.ctype.name and 
                    node.expr.ctype.bit_width == node.lhs.ctype.bit_width):
                    if node.expr.expr.ctype.bit_width <= node.lhs.ctype.bit_width:
                        node.expr = node.expr.expr
                        self.modified = True

        return node

    def visit_CBinaryExpr(self, node: CBinaryExpr) -> CExpr:
        node.lhs = self.visit(node.lhs)
        node.rhs = self.visit(node.rhs)

        if isinstance(node.lhs, CCastExpr) and isinstance(node.rhs, CCastExpr):
            if (node.lhs.ctype.name == node.rhs.ctype.name and 
                node.lhs.ctype.bit_width == node.rhs.ctype.bit_width == node.ctype.bit_width):
                if node.lhs.expr.ctype == node.rhs.expr.ctype == node.ctype:
                    node.lhs = node.lhs.expr
                    node.rhs = node.rhs.expr
                    self.modified = True

        return node

    def visit_CReturnStmt(self, node: CReturnStmt) -> CStmt:
        if node.val is not None:
            node.val = self.visit(node.val)
            if isinstance(node.val, CCastExpr):
                # identity cast: (int64_t)((int64_t)x) -> (int64_t)x
                if node.val.expr.ctype == node.val.ctype:
                    node.val = node.val.expr
                    self.modified = True
                # (uint64_t)0 -> 0
                elif isinstance(node.val.expr, CLiteralExpr) and isinstance(node.val.expr.val, int):
                    node.val.expr.ctype = node.val.ctype
                    node.val = node.val.expr
                    self.modified = True
        return node


class CastNormalizerPass(Pass):
    """AST Pass: normalizes and prunes redundant type conversions."""
    __slots__ = ()

    def run(self, scope: ASTScope) -> bool:
        normalizer = CastNormalizer()
        normalizer.visit(scope.cfunc)
        return normalizer.modified