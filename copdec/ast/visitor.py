

from typing import Any, Optional, List
from .nodes import (
    CASTNode, CExpr, CStmt,
    CLiteralExpr, CVarExpr, CBinaryExpr, CUnaryExpr, CCastExpr, CCallExpr, CTernaryExpr,
    CMemberExpr, CIndexExpr,
    CBlock, CAssignStmt, CExprStmt, CIfStmt, CWhileStmt, CDoWhileStmt, CForStmt,
    CSwitchStmt, CCaseStmt, CReturnStmt, CBreakStmt, CContinueStmt, CGotoStmt, CLabelStmt,
    CFunction
)


class ASTVisitor:
    """
    Complete AST Visitor Dispatcher.
    Provides standard double-dispatch traversal for all AST nodes.
    """
    __slots__ = ()

    def visit(self, node: Optional[CASTNode]) -> Any:
        if node is None:
            return None
        method_name = f"visit_{node.__class__.__name__}"
        visitor = getattr(self, method_name, self.generic_visit)
        return visitor(node)

    def generic_visit(self, node: CASTNode) -> Any:
        return None

    # --- Data Flow (CExpr) ---
    def visit_CLiteralExpr(self, node: CLiteralExpr) -> Any:
        return self.generic_visit(node)

    def visit_CVarExpr(self, node: CVarExpr) -> Any:
        return self.generic_visit(node)

    def visit_CBinaryExpr(self, node: CBinaryExpr) -> Any:
        self.visit(node.lhs)
        self.visit(node.rhs)
        return None

    def visit_CUnaryExpr(self, node: CUnaryExpr) -> Any:
        self.visit(node.operand)
        return None

    def visit_CCastExpr(self, node: CCastExpr) -> Any:
        self.visit(node.expr)
        return None

    def visit_CCallExpr(self, node: CCallExpr) -> Any:
        if isinstance(node.callee, CASTNode):
            self.visit(node.callee)
        for arg in node.args:
            self.visit(arg)
        return None

    def visit_CTernaryExpr(self, node: CTernaryExpr) -> Any:
        self.visit(node.cond)
        self.visit(node.true_expr)
        self.visit(node.false_expr)
        return None

    # --- Control Flow (CStmt) ---
    def visit_CBlock(self, node: CBlock) -> Any:
        for stmt in node.stmts:
            self.visit(stmt)
        return None

    def visit_CAssignStmt(self, node: CAssignStmt) -> Any:
        self.visit(node.lhs)
        self.visit(node.expr)
        return None

    def visit_CExprStmt(self, node: CExprStmt) -> Any:
        self.visit(node.expr)
        return None

    def visit_CIfStmt(self, node: CIfStmt) -> Any:
        self.visit(node.cond)
        self.visit(node.then_block)
        if node.else_block:
            self.visit(node.else_block)
        return None

    def visit_CWhileStmt(self, node: CWhileStmt) -> Any:
        self.visit(node.cond)
        self.visit(node.body)
        return None

    def visit_CDoWhileStmt(self, node: CDoWhileStmt) -> Any:
        self.visit(node.body)
        self.visit(node.cond)
        return None

    def visit_CForStmt(self, node: CForStmt) -> Any:
        if node.init:
            self.visit(node.init)
        if node.cond:
            self.visit(node.cond)
        if node.step:
            self.visit(node.step)
        self.visit(node.body)
        return None

    def visit_CSwitchStmt(self, node: CSwitchStmt) -> Any:
        self.visit(node.cond)
        for case in node.cases:
            self.visit(case)
        if node.default_case:
            self.visit(node.default_case)
        return None

    def visit_CCaseStmt(self, node: CCaseStmt) -> Any:
        if node.val:
            self.visit(node.val)
        self.visit(node.body)
        return None

    def visit_CReturnStmt(self, node: CReturnStmt) -> Any:
        if node.val:
            self.visit(node.val)
        return None

    def visit_CBreakStmt(self, node: CBreakStmt) -> Any:
        return None

    def visit_CContinueStmt(self, node: CContinueStmt) -> Any:
        return None

    def visit_CGotoStmt(self, node: CGotoStmt) -> Any:
        if isinstance(node.label, CASTNode):
            self.visit(node.label)
        return None

    def visit_CLabelStmt(self, node: CLabelStmt) -> Any:
        return None

    def visit_CFunction(self, node: CFunction) -> Any:
        self.visit(node.body)
        return None

    def visit_CMemberExpr(self, node: CMemberExpr) -> Any:
        self.visit(node.base)
        return None

    def visit_CIndexExpr(self, node: CIndexExpr) -> Any:
        self.visit(node.base)
        self.visit(node.index)
        return None

class ASTTransformer(ASTVisitor):
    """
    In-Place AST Node Transformer Engine (modeled after Python's ast.NodeTransformer).
    Preserves all unhandled nodes by default and supports in-place list replacement.
    """
    __slots__ = ()

    def generic_visit(self, node: CASTNode) -> Any:
        """Default fallback: preserve node untouched."""
        return node

    # --- Data Flow Leaf Nodes ---
    def visit_CLiteralExpr(self, node: CLiteralExpr) -> CExpr:
        return node

    def visit_CVarExpr(self, node: CVarExpr) -> CExpr:
        return node

    # --- Data Flow Composite Expressions ---
    def visit_CBinaryExpr(self, node: CBinaryExpr) -> CExpr:
        node.lhs = self.visit(node.lhs)
        node.rhs = self.visit(node.rhs)
        return node

    def visit_CUnaryExpr(self, node: CUnaryExpr) -> CExpr:
        node.operand = self.visit(node.operand)
        return node

    def visit_CCastExpr(self, node: CCastExpr) -> CExpr:
        node.expr = self.visit(node.expr)
        return node

    def visit_CCallExpr(self, node: CCallExpr) -> CExpr:
        if isinstance(node.callee, CASTNode):
            node.callee = self.visit(node.callee)
        node.args = [self.visit(a) for a in node.args]
        return node

    def visit_CTernaryExpr(self, node: CTernaryExpr) -> CExpr:
        node.cond = self.visit(node.cond)
        node.true_expr = self.visit(node.true_expr)
        node.false_expr = self.visit(node.false_expr)
        return node

    # --- Control Flow Statements ---
    def visit_CBlock(self, node: CBlock) -> CBlock:
        new_stmts: List[CStmt] = []
        for stmt in node.stmts:
            res = self.visit(stmt)
            if res is None:
                continue
            elif isinstance(res, list):
                new_stmts.extend(res)
            else:
                new_stmts.append(res)
        node.stmts = new_stmts
        return node

    def visit_CAssignStmt(self, node: CAssignStmt) -> Optional[CStmt]:
        node.lhs = self.visit(node.lhs)
        node.expr = self.visit(node.expr)
        return node

    def visit_CExprStmt(self, node: CExprStmt) -> Optional[CStmt]:
        node.expr = self.visit(node.expr)
        return node

    def visit_CIfStmt(self, node: CIfStmt) -> Optional[CStmt]:
        node.cond = self.visit(node.cond)
        node.then_block = self.visit(node.then_block)
        if node.else_block:
            node.else_block = self.visit(node.else_block)
        return node

    def visit_CWhileStmt(self, node: CWhileStmt) -> Optional[CStmt]:
        node.cond = self.visit(node.cond)
        node.body = self.visit(node.body)
        return node

    def visit_CDoWhileStmt(self, node: CDoWhileStmt) -> Optional[CStmt]:
        node.body = self.visit(node.body)
        node.cond = self.visit(node.cond)
        return node

    def visit_CForStmt(self, node: CForStmt) -> Optional[CStmt]:
        if node.init:
            node.init = self.visit(node.init)
        if node.cond:
            node.cond = self.visit(node.cond)
        if node.step:
            node.step = self.visit(node.step)
        node.body = self.visit(node.body)
        return node

    def visit_CSwitchStmt(self, node: CSwitchStmt) -> Optional[CStmt]:
        node.cond = self.visit(node.cond)
        for case in node.cases:
            self.visit(case)
        if node.default_case:
            self.visit(node.default_case)
        return node

    def visit_CCaseStmt(self, node: CCaseStmt) -> Optional[CStmt]:
        if node.val:
            node.val = self.visit(node.val)
        node.body = self.visit(node.body)
        return node

    def visit_CReturnStmt(self, node: CReturnStmt) -> Optional[CStmt]:
        if node.val:
            node.val = self.visit(node.val)
        return node

    def visit_CBreakStmt(self, node: CBreakStmt) -> Optional[CStmt]:
        return node

    def visit_CContinueStmt(self, node: CContinueStmt) -> Optional[CStmt]:
        return node

    def visit_CGotoStmt(self, node: CGotoStmt) -> Optional[CStmt]:
        if isinstance(node.label, CASTNode):
            node.label = self.visit(node.label)
        return node

    def visit_CLabelStmt(self, node: CLabelStmt) -> Optional[CStmt]:
        return node

    def visit_CFunction(self, node: CFunction) -> CFunction:
        node.body = self.visit(node.body)
        return node

    def visit_CMemberExpr(self, node: CMemberExpr) -> CExpr:
        node.base = self.visit(node.base)
        return node

    def visit_CIndexExpr(self, node: CIndexExpr) -> CExpr:
        node.base = self.visit(node.base)
        node.index = self.visit(node.index)
        return node