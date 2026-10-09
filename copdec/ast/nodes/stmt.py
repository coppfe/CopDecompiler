from typing import List, Optional, Union
from .base import CASTNode
from .expr import CExpr


class CStmt(CASTNode):
    """Abstract base class for all Control Flow statements and side-effects."""
    __slots__ = ()


class CBlock(CStmt):
    """Sequential sequence of C statements enclosed in braces { ... }."""
    __slots__ = ('stmts',)

    def __init__(self, stmts: Optional[List[CStmt]] = None):
        self.stmts: List[CStmt] = stmts if stmts is not None else []

    def append(self, stmt: CStmt) -> None:
        self.stmts.append(stmt)


class CAssignStmt(CStmt):
    """Assignment statement: [type] lhs [= expr];"""
    __slots__ = ('lhs', 'expr', 'is_declaration')

    def __init__(self, lhs: CExpr, expr: Optional[CExpr] = None, is_declaration: bool = False):
        self.lhs: CExpr = lhs
        self.expr: Optional[CExpr] = expr
        self.is_declaration: bool = is_declaration


class CExprStmt(CStmt):
    """Standalone expression statement (e.g. function call side-effect): expr;"""
    __slots__ = ('expr',)

    def __init__(self, expr: CExpr):
        self.expr: CExpr = expr


class CIfStmt(CStmt):
    """Conditional branching statement: if (cond) { then } else { else }."""
    __slots__ = ('cond', 'then_block', 'else_block')

    def __init__(self, cond: CExpr, then_block: CBlock, else_block: Optional[CBlock] = None):
        self.cond: CExpr = cond
        self.then_block: CBlock = then_block
        self.else_block: Optional[CBlock] = else_block


class CWhileStmt(CStmt):
    """Pre-tested loop statement: while (cond) { body }."""
    __slots__ = ('cond', 'body')

    def __init__(self, cond: CExpr, body: CBlock):
        self.cond: CExpr = cond
        self.body: CBlock = body


class CDoWhileStmt(CStmt):
    """Post-tested loop statement: do { body } while (cond);"""
    __slots__ = ('cond', 'body')

    def __init__(self, cond: CExpr, body: CBlock):
        self.cond: CExpr = cond
        self.body: CBlock = body


class CForStmt(CStmt):
    """Counter-based loop statement: for (init; cond; step) { body }."""
    __slots__ = ('init', 'cond', 'step', 'body')

    def __init__(self, init: Optional[CStmt], cond: Optional[CExpr], step: Optional[CStmt], body: CBlock):
        self.init: Optional[CStmt] = init
        self.cond: Optional[CExpr] = cond
        self.step: Optional[CStmt] = step
        self.body: CBlock = body


class CCaseStmt(CStmt):
    """Switch case branch: case val: { body } or default: { body }."""
    __slots__ = ('val', 'body', 'is_default')

    def __init__(self, val: Optional[CExpr], body: CBlock, is_default: bool = False):
        self.val: Optional[CExpr] = val
        self.body: CBlock = body
        self.is_default: bool = is_default


class CSwitchStmt(CStmt):
    """Multi-way branch switch statement: switch (cond) { case ... }."""
    __slots__ = ('cond', 'cases', 'default_case')

    def __init__(self, cond: CExpr, cases: List[CCaseStmt], default_case: Optional[CCaseStmt] = None):
        self.cond: CExpr = cond
        self.cases: List[CCaseStmt] = cases
        self.default_case: Optional[CCaseStmt] = default_case


class CReturnStmt(CStmt):
    """Function return statement: return expr; or return;"""
    __slots__ = ('val',)

    def __init__(self, val: Optional[CExpr] = None):
        self.val: Optional[CExpr] = val


class CBreakStmt(CStmt):
    """Loop/switch break statement: break;"""
    __slots__ = ()


class CContinueStmt(CStmt):
    """Loop continue statement: continue;"""
    __slots__ = ()


class CGotoStmt(CStmt):
    """Unstructured control flow jump: goto label; or goto *expr;"""
    __slots__ = ('label',)

    def __init__(self, label: Union[str, CExpr]):
        self.label: Union[str, CExpr] = label


class CLabelStmt(CStmt):
    """Label declaration target: label:"""
    __slots__ = ('label',)

    def __init__(self, label: str):
        self.label: str = label