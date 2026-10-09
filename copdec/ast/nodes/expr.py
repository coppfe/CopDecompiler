from typing import List, Union
from .base import CASTNode
from ..types import CType


class CExpr(CASTNode):
    """Abstract base class for all Data Flow expressions returning a value."""
    __slots__ = ('ctype',)

    def __init__(self, ctype: CType):
        self.ctype: CType = ctype


class CLiteralExpr(CExpr):
    """Literal constant value (integer, float, string, boolean, NULL)."""
    __slots__ = ('val',)

    def __init__(self, val: Union[int, float, str, bool], ctype: CType):
        super().__init__(ctype)
        self.val: Union[int, float, str, bool] = val


class CVarExpr(CExpr):
    """Named variable identifier in C code."""
    __slots__ = ('name',)

    def __init__(self, name: str, ctype: CType):
        super().__init__(ctype)
        self.name: str = name

    def __str__(self): return self.name


class CBinaryExpr(CExpr):
    """Binary operation expression: (lhs op rhs)."""
    __slots__ = ('op', 'lhs', 'rhs')

    def __init__(self, op: str, lhs: CExpr, rhs: CExpr, ctype: CType):
        super().__init__(ctype)
        self.op: str = op
        self.lhs: CExpr = lhs
        self.rhs: CExpr = rhs


class CUnaryExpr(CExpr):
    """Unary operation expression: (op operand), dereference (*ptr), address-of (&val)."""
    __slots__ = ('op', 'operand')

    def __init__(self, op: str, operand: CExpr, ctype: CType):
        super().__init__(ctype)
        self.op: str = op
        self.operand: CExpr = operand


class CCastExpr(CExpr):
    """Explicit type cast expression: ((target_type) expr)."""
    __slots__ = ('expr',)

    def __init__(self, target_type: CType, expr: CExpr):
        super().__init__(target_type)
        self.expr: CExpr = expr


class CCallExpr(CExpr):
    """Function / Function pointer call expression: callee(args...)."""
    __slots__ = ('callee', 'args')

    def __init__(self, callee: Union[str, CExpr], args: List[CExpr], ctype: CType):
        super().__init__(ctype)
        self.callee: Union[str, CExpr] = callee
        self.args: List[CExpr] = args


class CTernaryExpr(CExpr):
    """Conditional expression: (cond ? true_expr : false_expr)."""
    __slots__ = ('cond', 'true_expr', 'false_expr')

    def __init__(self, cond: CExpr, true_expr: CExpr, false_expr: CExpr, ctype: CType):
        super().__init__(ctype)
        self.cond: CExpr = cond
        self.true_expr: CExpr = true_expr
        self.false_expr: CExpr = false_expr

class CMemberExpr(CExpr):
    """base.field / base->field."""
    __slots__ = ('base', 'field_name', 'is_arrow')

    def __init__(self, base: CExpr, field_name: str, ctype: CType, is_arrow: bool = False):
        super().__init__(ctype)
        self.base: CExpr = base
        self.field_name: str = field_name
        self.is_arrow: bool = is_arrow


class CIndexExpr(CExpr):
    """base[index]."""
    __slots__ = ('base', 'index')

    def __init__(self, base: CExpr, index: CExpr, ctype: CType):
        super().__init__(ctype)
        self.base: CExpr = base
        self.index: CExpr = index