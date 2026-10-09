from .base_printer import BaseSourcePrinter
from ..nodes import (
    CFunction, CBlock, CAssignStmt, CExprStmt, CIfStmt,
    CWhileStmt, CDoWhileStmt, CForStmt, CSwitchStmt,
    CReturnStmt, CBreakStmt, CContinueStmt,
    CVarExpr, CLiteralExpr, CBinaryExpr, CUnaryExpr,
    CCastExpr, CCallExpr, CTernaryExpr, CMemberExpr, CIndexExpr
)


class PythonPrettyPrinter(BaseSourcePrinter):
    """
    Renders structured AST into clean, idiomatic Python 3.10+ pseudocode.
    Completely eliminates type casting noise and formats memory accesses.
    """
    __slots__ = ()

    def format_function(self, func: CFunction) -> str:
        params_str = ", ".join(name for name, _ in func.params)
        lines = [f"def {func.name}({params_str}):"]

        self._indent_level += 1
        body_str = self.visit_CBlock(func.body)
        if body_str:
            lines.append(body_str)
        else:
            lines.append(f"{self.indent()}pass")
        self._indent_level -= 1

        return "\n".join(lines)

    def visit_CBlock(self, node: CBlock) -> str:
        lines = []
        for stmt in node.stmts:
            rendered = self.visit(stmt)
            if rendered:
                lines.append(rendered)
        return "\n".join(lines) if lines else f"{self.indent()}pass"

    def visit_CAssignStmt(self, node: CAssignStmt) -> str:
        if node.expr is None:
            return ""

        lhs_str = self.visit(node.lhs)
        expr_str = self.visit(node.expr)

        if isinstance(node.lhs, CUnaryExpr) and node.lhs.op == "*":
            ptr_str = self.visit(node.lhs.operand)
            return f"{self.indent()}write_mem({ptr_str}, {expr_str})"

        return f"{self.indent()}{lhs_str} = {expr_str}"

    def visit_CExprStmt(self, node: CExprStmt) -> str:
        return f"{self.indent()}{self.visit(node.expr)}"

    def visit_CReturnStmt(self, node: CReturnStmt) -> str:
        if node.val is not None:
            return f"{self.indent()}return {self.visit(node.val)}"
        return f"{self.indent()}return"

    def visit_CBreakStmt(self, node: CBreakStmt) -> str:
        return f"{self.indent()}break"

    def visit_CContinueStmt(self, node: CContinueStmt) -> str:
        return f"{self.indent()}continue"

    def visit_CIfStmt(self, node: CIfStmt) -> str:
        ind = self.indent()
        cond_str = self.visit(node.cond)
        lines = [f"{ind}if {cond_str}:"]

        self._indent_level += 1
        then_str = self.visit_CBlock(node.then_block)
        lines.append(then_str if then_str else f"{self.indent()}pass")
        self._indent_level -= 1

        if node.else_block and node.else_block.stmts:
            lines.append(f"{ind}else:")
            self._indent_level += 1
            else_str = self.visit_CBlock(node.else_block)
            lines.append(else_str if else_str else f"{self.indent()}pass")
            self._indent_level -= 1

        return "\n".join(lines)

    def visit_CWhileStmt(self, node: CWhileStmt) -> str:
        ind = self.indent()
        cond_str = self.visit(node.cond)
        lines = [f"{ind}while {cond_str}:"]
        self._indent_level += 1
        body_str = self.visit_CBlock(node.body)
        lines.append(body_str if body_str else f"{self.indent()}pass")
        self._indent_level -= 1
        return "\n".join(lines)

    def visit_CDoWhileStmt(self, node: CDoWhileStmt) -> str:
        ind = self.indent()
        lines = [f"{ind}while True:"]
        self._indent_level += 1
        body_str = self.visit_CBlock(node.body)
        if body_str:
            lines.append(body_str)
        cond_str = self.visit(node.cond)
        lines.append(f"{self.indent()}if not ({cond_str}):")
        lines.append(f"{self.indent()}    break")
        self._indent_level -= 1
        return "\n".join(lines)

    def visit_CForStmt(self, node: CForStmt) -> str:
        lines = []
        if node.init:
            init_str = self.visit(node.init)
            if init_str:
                lines.append(init_str)
        
        cond_str = self.visit(node.cond) if node.cond else "True"
        lines.append(f"{self.indent()}while {cond_str}:")
        self._indent_level += 1
        body_str = self.visit_CBlock(node.body)
        if body_str:
            lines.append(body_str)
        if node.step:
            step_str = self.visit(node.step)
            if step_str:
                lines.append(step_str)
        self._indent_level -= 1
        return "\n".join(lines)

    def visit_CSwitchStmt(self, node: CSwitchStmt) -> str:
        ind = self.indent()
        cond_str = self.visit(node.cond)
        lines = [f"{ind}match {cond_str}:"]
        self._indent_level += 1

        for case in node.cases:
            case_val_str = self.visit(case.val)
            lines.append(f"{self.indent()}case {case_val_str}:")
            self._indent_level += 1
            body_str = self.visit_CBlock(case.body)
            lines.append(body_str if body_str else f"{self.indent()}pass")
            self._indent_level -= 1

        if node.default_case:
            lines.append(f"{self.indent()}case _:")
            self._indent_level += 1
            def_str = self.visit_CBlock(node.default_case.body)
            lines.append(def_str if def_str else f"{self.indent()}pass")
            self._indent_level -= 1

        self._indent_level -= 1
        return "\n".join(lines)

    # --- Expressions ---
    def visit_CLiteralExpr(self, node: CLiteralExpr) -> str:
        return self.format_literal(node, is_python=True)

    def visit_CVarExpr(self, node: CVarExpr) -> str:
        return node.name

    def visit_CBinaryExpr(self, node: CBinaryExpr) -> str:
        lhs_str = self.visit(node.lhs)
        rhs_str = self.visit(node.rhs)
        op = node.op
        if op == "&&":
            op = "and"
        elif op == "||":
            op = "or"
        return f"({lhs_str} {op} {rhs_str})"

    def visit_CUnaryExpr(self, node: CUnaryExpr) -> str:
        operand_str = self.visit(node.operand)
        if node.op == "!":
            return f"(not {operand_str})"
        if node.op == "*":
            return f"read_mem({operand_str})"
        if node.op == "&":
            return operand_str
        return f"{node.op}{operand_str}"

    def visit_CCastExpr(self, node: CCastExpr) -> str:
        return self.visit(node.expr)

    def visit_CTernaryExpr(self, node: CTernaryExpr) -> str:
        c = self.visit(node.cond)
        t = self.visit(node.true_expr)
        f = self.visit(node.false_expr)
        return f"({t} if {c} else {f})"

    def visit_CCallExpr(self, node: CCallExpr) -> str:
        args_str = ", ".join(self.visit(a) for a in node.args)
        callee_str = self.visit(node.callee) if hasattr(node.callee, 'ctype') else str(node.callee)
        return f"{callee_str}({args_str})"

    def visit_CMemberExpr(self, node: CMemberExpr) -> str:
        base_str = self.visit(node.base)
        return f"{base_str}.{node.field_name}"

    def visit_CIndexExpr(self, node: CIndexExpr) -> str:
        base_str = self.visit(node.base)
        idx_str = self.visit(node.index)
        return f"{base_str}[{idx_str}]"