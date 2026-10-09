from typing import Optional, Union
from ...bridge.ast.scope import ASTScope
from ...pipeline.passer import Pass
from ..visitor import ASTTransformer
from ..nodes import (
    CExpr, CBinaryExpr, CLiteralExpr, CCastExpr, CTernaryExpr, CUnaryExpr, CVarExpr
)
from ..types import CType


class ExpressionSimplifier(ASTTransformer):
    __slots__ = ('modified',)

    def __init__(self):
        self.modified: bool = False

    @staticmethod
    def _unwrap_int_literal(expr: Optional[CExpr]) -> Optional[int]:
        if expr is None:
            return None
        if isinstance(expr, CLiteralExpr):
            if isinstance(expr.val, bool):
                return 1 if expr.val else 0
            if isinstance(expr.val, int):
                return expr.val
        if isinstance(expr, CCastExpr):
            return ExpressionSimplifier._unwrap_int_literal(expr.expr)
        return None

    @classmethod
    def _are_same_expr(cls, e1: Optional[CExpr], e2: Optional[CExpr]) -> bool:
        if e1 is e2:
            return True
        if e1 is None or e2 is None:
            return False
        if type(e1) is not type(e2):
            return False
        if isinstance(e1, CVarExpr):
            return e1.name == e2.name  # type: ignore
        if isinstance(e1, CLiteralExpr):
            return e1.val == e2.val  # type: ignore
        if isinstance(e1, CCastExpr):
            return e1.ctype.name == e2.ctype.name and cls._are_same_expr(e1.expr, e2.expr)  # type: ignore
        if isinstance(e1, CUnaryExpr):
            return e1.op == e2.op and cls._are_same_expr(e1.operand, e2.operand)  # type: ignore
        if isinstance(e1, CBinaryExpr):
            return (e1.op == e2.op and  # type: ignore
                    cls._are_same_expr(e1.lhs, e2.lhs) and 
                    cls._are_same_expr(e1.rhs, e2.rhs))
        return False

    @staticmethod
    def _eval_const_binary(op: str, l: int, r: int, ctype: CType) -> Optional[Union[int, bool]]:
        width = ctype.bit_width if hasattr(ctype, 'bit_width') and ctype.bit_width > 0 else 64
        mask = (1 << width) - 1 if width <= 64 else (1 << 64) - 1

        if op == "+": return (l + r) & mask
        if op == "-": return (l - r) & mask
        if op == "*": return (l * r) & mask
        if op == "/": return (l // r) & mask if r != 0 else None
        if op == "%": return (l % r) & mask if r != 0 else None
        if op == "&": return (l & r) & mask
        if op == "|": return (l | r) & mask
        if op == "^": return (l ^ r) & mask
        if op == "<<": return (l << (r & (width - 1))) & mask
        if op in (">>", ">>_u"): return (l >> (r & (width - 1))) & mask
        if op == "==": return l == r
        if op == "!=": return l != r
        if op == "<": return l < r
        if op == "<=": return l <= r
        if op == ">": return l > r
        if op == ">=": return l >= r
        if op == "&&": return bool(l and r)
        if op == "||": return bool(l or r)
        return None

    def visit_CCastExpr(self, node: CCastExpr) -> CExpr:
        node.expr = self.visit(node.expr)

        if isinstance(node.expr, CCastExpr) and node.expr.ctype.name == node.ctype.name:
            self.modified = True
            return node.expr

        lit_val = self._unwrap_int_literal(node.expr)
        if lit_val == 0:
            self.modified = True
            return CLiteralExpr(0, node.ctype)

        return node

    def visit_CTernaryExpr(self, node: CTernaryExpr) -> CExpr:
        node.cond = self.visit(node.cond)
        node.true_expr = self.visit(node.true_expr)
        node.false_expr = self.visit(node.false_expr)

        cond_val = self._unwrap_int_literal(node.cond)
        if cond_val is not None:
            self.modified = True
            return node.true_expr if cond_val != 0 else node.false_expr

        if self._are_same_expr(node.true_expr, node.false_expr):
            self.modified = True
            return node.true_expr

        return node

    def visit_CBinaryExpr(self, node: CBinaryExpr) -> CExpr:
        node.lhs = self.visit(node.lhs)
        node.rhs = self.visit(node.rhs)

        val_l = self._unwrap_int_literal(node.lhs)
        val_r = self._unwrap_int_literal(node.rhs)

        if val_l is not None and val_r is not None:
            res = self._eval_const_binary(node.op, val_l, val_r, node.ctype)
            if res is not None:
                self.modified = True
                return CLiteralExpr(res, node.ctype)

        if node.op == "+":
            if val_r == 0:
                self.modified = True
                return node.lhs
            if val_l == 0:
                self.modified = True
                return node.rhs
        elif node.op == "-":
            if val_r == 0:
                self.modified = True
                return node.lhs
            if self._are_same_expr(node.lhs, node.rhs):
                self.modified = True
                return CLiteralExpr(0, node.ctype)

        elif node.op == "*":
            if val_r == 0 or val_l == 0:
                self.modified = True
                return CLiteralExpr(0, node.ctype)
            if val_r == 1:
                self.modified = True
                return node.lhs
            if val_l == 1:
                self.modified = True
                return node.rhs
        elif node.op in ("/", ">>", ">>_u", ">>a", "<<"):
            if val_r == 0 and node.op in ("<<", ">>", ">>_u", ">>a"):
                self.modified = True
                return node.lhs
            if val_r == 1 and node.op == "/":
                self.modified = True
                return node.lhs

        elif node.op == "&":
            if val_r == 0 or val_l == 0:
                self.modified = True
                return CLiteralExpr(0, node.ctype)
            if self._are_same_expr(node.lhs, node.rhs):
                self.modified = True
                return node.lhs
        elif node.op == "|":
            if val_r == 0:
                self.modified = True
                return node.lhs
            if val_l == 0:
                self.modified = True
                return node.rhs
            if self._are_same_expr(node.lhs, node.rhs):
                self.modified = True
                return node.lhs
        elif node.op == "^":
            if val_r == 0:
                self.modified = True
                return node.lhs
            if val_l == 0:
                self.modified = True
                return node.rhs
            if self._are_same_expr(node.lhs, node.rhs):
                self.modified = True
                return CLiteralExpr(0, node.ctype)

        if node.op in ("==", "<=", ">=") and self._are_same_expr(node.lhs, node.rhs):
            self.modified = True
            return CLiteralExpr(True, CType("bool", bit_width=1))
        if node.op in ("!=", "<", ">") and self._are_same_expr(node.lhs, node.rhs):
            self.modified = True
            return CLiteralExpr(False, CType("bool", bit_width=1))

        if isinstance(node.rhs, CLiteralExpr) and isinstance(node.rhs.val, int):
            c2 = node.rhs.val
            if isinstance(node.lhs, CBinaryExpr) and isinstance(node.lhs.rhs, CLiteralExpr) and isinstance(node.lhs.rhs.val, int):
                c1 = node.lhs.rhs.val
                base_x = node.lhs.lhs

                if node.op == "+":
                    if node.lhs.op == "+":
                        new_c = c1 + c2
                        self.modified = True
                        if new_c == 0: return base_x
                        return CBinaryExpr("+", base_x, CLiteralExpr(new_c, node.rhs.ctype), node.ctype)
                    elif node.lhs.op == "-":
                        diff = c2 - c1
                        self.modified = True
                        if diff == 0: return base_x
                        op = "+" if diff > 0 else "-"
                        return CBinaryExpr(op, base_x, CLiteralExpr(abs(diff), node.rhs.ctype), node.ctype)

                elif node.op == "-":
                    if node.lhs.op == "+":
                        diff = c1 - c2
                        self.modified = True
                        if diff == 0: return base_x
                        op = "+" if diff > 0 else "-"
                        return CBinaryExpr(op, base_x, CLiteralExpr(abs(diff), node.rhs.ctype), node.ctype)
                    elif node.lhs.op == "-":
                        total = c1 + c2
                        self.modified = True
                        if total == 0: return base_x
                        return CBinaryExpr("-", base_x, CLiteralExpr(total, node.rhs.ctype), node.ctype)

        return node


class ExpressionSimplifierPass(Pass):
    """AST Pass: associates and folds binary/ternary expressions and arithmetic identities."""
    __slots__ = ()

    def run(self, scope: ASTScope) -> bool:
        simplifier = ExpressionSimplifier()
        simplifier.visit(scope.cfunc)
        return simplifier.modified