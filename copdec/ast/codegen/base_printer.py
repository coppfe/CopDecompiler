from ..visitor import ASTVisitor
from ..nodes import CFunction, CLiteralExpr


class BaseSourcePrinter(ASTVisitor):
    """
    Abstract Source Code Pretty Printer.
    Manages indentation levels, nested blocks, and common literal rendering.
    """
    __slots__ = ('_indent_level', '_indent_str')

    def __init__(self, indent_spaces: int = 4):
        self._indent_level: int = 0
        self._indent_str: str = " " * indent_spaces

    def indent(self) -> str:
        return self._indent_str * self._indent_level

    def format_function(self, func: CFunction) -> str:
        raise NotImplementedError

    def format_literal(self, expr: CLiteralExpr, is_python: bool = False) -> str:
        if isinstance(expr.val, bool):
            if is_python:
                return "True" if expr.val else "False"
            return "true" if expr.val else "false"
    
        if isinstance(expr.val, int):
            val = expr.val
            if expr.ctype.is_pointer or val > 9 or val < -9:
                return f"0x{val:x}" if val >= 0 else f"-0x{-val:x}"
            return str(val)
    
        return str(expr.val)