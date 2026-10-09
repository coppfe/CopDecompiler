from .base_printer import BaseSourcePrinter
from ..nodes import (
    CFunction, CBlock, CAssignStmt, CExprStmt, CIfStmt,
    CWhileStmt, CDoWhileStmt, CForStmt, CSwitchStmt,
    CReturnStmt, CBreakStmt, CContinueStmt, CGotoStmt, CLabelStmt,
    CVarExpr, CLiteralExpr, CBinaryExpr, CUnaryExpr,
    CCastExpr, CCallExpr, CTernaryExpr, CExpr,
    CMemberExpr, CIndexExpr, CStructDef
)


class CPrettyPrinter(BaseSourcePrinter):
    """Renders structured CFunction AST into syntactically strict C source code."""
    __slots__ = ()

    def format_struct_def(self, struct_def: CStructDef) -> str:
        """
        Renders:
        struct foo_frame_t {
            int64_t arr_m0x60[4];
            int32_t var_0x4;
        };
        """
        lines = [f"{struct_def.name} {{"]
        self._indent_level += 1

        for field in struct_def.fields:
            if field.ctype.is_array and field.ctype.element_type is not None:
                field_line = f"{self.indent()}{field.ctype.element_type} {field.name}[{field.ctype.array_count}];"
            else:
                field_line = f"{self.indent()}{field.ctype} {field.name};"
            lines.append(field_line)

        self._indent_level -= 1
        lines.append("};\n")
        return "\n".join(lines)

    def format_function(self, func: CFunction) -> str:
        lines = []

        params_str = ", ".join(f"{t} {name}" for name, t in func.params) if func.params else ""
        lines.append(f"{func.return_type} {func.name}({params_str}) {{")

        self._indent_level += 1
        body_str = self.visit_CBlock(func.body)
        if body_str:
            lines.append(body_str)
        self._indent_level -= 1

        lines.append("}")
        return "\n".join(lines)

    # --- Statement Renderers ---
    def visit_CBlock(self, node: CBlock) -> str:
        lines = []
        for stmt in node.stmts:
            rendered = self.visit(stmt)
            if rendered:
                lines.append(rendered)
        return "\n".join(lines)

    def visit_CLabelStmt(self, node: CLabelStmt) -> str:
        label_ind = self._indent_str * max(0, self._indent_level - 1)
        return f"\n{label_ind}{node.label}:"

    def visit_CGotoStmt(self, node: CGotoStmt) -> str:
        if isinstance(node.label, CExpr):
            return f"{self.indent()}goto *{self.visit(node.label)};"
        return f"{self.indent()}goto {node.label};"

    def visit_CAssignStmt(self, node: CAssignStmt) -> str:
        lhs_str = self.visit(node.lhs)
        
        if node.expr is None:
            if node.is_declaration:
                return f"{self.indent()}{node.lhs.ctype} {lhs_str};"
            return ""
            
        type_prefix = f"{node.lhs.ctype} " if node.is_declaration else ""
        expr_str = self.visit(node.expr)
        return f"{self.indent()}{type_prefix}{lhs_str} = {expr_str};"

    def visit_CExprStmt(self, node: CExprStmt) -> str:
        return f"{self.indent()}{self.visit(node.expr)};"

    def visit_CReturnStmt(self, node: CReturnStmt) -> str:
        if node.val is not None:
            return f"{self.indent()}return {self.visit(node.val)};"
        return f"{self.indent()}return;"

    def visit_CBreakStmt(self, node: CBreakStmt) -> str:
        return f"{self.indent()}break;"

    def visit_CContinueStmt(self, node: CContinueStmt) -> str:
        return f"{self.indent()}continue;"

    def visit_CIfStmt(self, node: CIfStmt) -> str:
        ind = self.indent()
        cond_str = self.visit(node.cond)
        lines = [f"{ind}if ({cond_str}) {{"]

        self._indent_level += 1
        then_str = self.visit_CBlock(node.then_block)
        if then_str:
            lines.append(then_str)
        self._indent_level -= 1

        if node.else_block and node.else_block.stmts:
            lines.append(f"{ind}}} else {{")
            self._indent_level += 1
            else_str = self.visit_CBlock(node.else_block)
            if else_str:
                lines.append(else_str)
            self._indent_level -= 1

        lines.append(f"{ind}}}")
        return "\n".join(lines)

    def visit_CWhileStmt(self, node: CWhileStmt) -> str:
        ind = self.indent()
        cond_str = self.visit(node.cond)
        lines = [f"{ind}while ({cond_str}) {{"]
        self._indent_level += 1
        body_str = self.visit_CBlock(node.body)
        if body_str:
            lines.append(body_str)
        self._indent_level -= 1
        lines.append(f"{ind}}}")
        return "\n".join(lines)

    def visit_CDoWhileStmt(self, node: CDoWhileStmt) -> str:
        ind = self.indent()
        lines = [f"{ind}do {{"]
        self._indent_level += 1
        body_str = self.visit_CBlock(node.body)
        if body_str:
            lines.append(body_str)
        self._indent_level -= 1
        cond_str = self.visit(node.cond)
        lines.append(f"{ind}}} while ({cond_str});")
        return "\n".join(lines)

    def visit_CForStmt(self, node: CForStmt) -> str:
        ind = self.indent()
        init_str = self.visit(node.init).strip().rstrip(";") if node.init else ""
        cond_str = self.visit(node.cond).strip() if node.cond else ""
        step_str = self.visit(node.step).strip().rstrip(";") if node.step else ""
        lines = [f"{ind}for ({init_str}; {cond_str}; {step_str}) {{"]
        self._indent_level += 1
        body_str = self.visit_CBlock(node.body)
        if body_str:
            lines.append(body_str)
        self._indent_level -= 1
        lines.append(f"{ind}}}")
        return "\n".join(lines)

    def visit_CSwitchStmt(self, node: CSwitchStmt) -> str:
        ind = self.indent()
        cond_str = self.visit(node.cond)
        lines = [f"{ind}switch ({cond_str}) {{"]
        self._indent_level += 1

        for case in node.cases:
            case_val_str = self.visit(case.val)
            lines.append(f"{self.indent()}case {case_val_str}: {{")
            self._indent_level += 1
            body_str = self.visit_CBlock(case.body)
            if body_str:
                lines.append(body_str)
            ends_with_term = case.body.stmts and isinstance(case.body.stmts[-1], (CReturnStmt, CGotoStmt))
            if not ends_with_term:
                lines.append(f"{self.indent()}break;")
            self._indent_level -= 1
            lines.append(f"{self.indent()}}}")

        if node.default_case:
            lines.append(f"{self.indent()}default: {{")
            self._indent_level += 1
            def_body_str = self.visit_CBlock(node.default_case.body)
            if def_body_str:
                lines.append(def_body_str)
            ends_with_term = node.default_case.body.stmts and isinstance(node.default_case.body.stmts[-1], (CReturnStmt, CGotoStmt))
            if not ends_with_term:
                lines.append(f"{self.indent()}break;")
            self._indent_level -= 1
            lines.append(f"{self.indent()}}}")

        self._indent_level -= 1
        lines.append(f"{ind}}}")
        return "\n".join(lines)

    # --- Expression Renderers ---
    def visit_CLiteralExpr(self, node: CLiteralExpr) -> str:
        return self.format_literal(node, is_python=False)

    def visit_CVarExpr(self, node: CVarExpr) -> str:
        return node.name

    def visit_CBinaryExpr(self, node: CBinaryExpr) -> str:
        lhs_str = self.visit(node.lhs)
        rhs_str = self.visit(node.rhs)
        return f"({lhs_str} {node.op} {rhs_str})"

    def visit_CUnaryExpr(self, node: CUnaryExpr) -> str:
        operand_str = self.visit(node.operand)
        
        if isinstance(node.operand, (CBinaryExpr, CTernaryExpr)):
            operand_str = f"({operand_str})"

        if node.op == "*":
            if isinstance(node.operand, CLiteralExpr) and isinstance(node.operand.val, int):
                return f"*(( {node.ctype}* ){operand_str})"
            is_ptr = bool(node.operand and node.operand.ctype.is_pointer)
            return f"*{operand_str}" if is_ptr else f"*(({node.ctype}*){operand_str})"
            
        return f"{node.op}{operand_str}"

    def visit_CCastExpr(self, node: CCastExpr) -> str:
        if node.expr.ctype.name == node.ctype.name and node.expr.ctype.bit_width == node.ctype.bit_width:
            return self.visit(node.expr)

        return f"(({node.ctype}) {self.visit(node.expr)})"

    def visit_CTernaryExpr(self, node: CTernaryExpr) -> str:
        cond_str = self.visit(node.cond)
        t_str = self.visit(node.true_expr)
        f_str = self.visit(node.false_expr)
        return f"({cond_str} ? {t_str} : {f_str})"

    def visit_CCallExpr(self, node: CCallExpr) -> str:
        args_str = ", ".join(self.visit(a) for a in node.args)
        ret_type_str = str(node.ctype) if node.ctype else "void"

        if isinstance(node.callee, str):
            return f"{node.callee}({args_str})"

        elif isinstance(node.callee, CExpr):
            callee_str = self.visit(node.callee)
            return f"(( {ret_type_str} (*)() ){callee_str})({args_str})"

        return f"{node.callee}({args_str})"

    def visit_CMemberExpr(self, node: CMemberExpr) -> str:
        base_str = self.visit(node.base)
        if isinstance(node.base, (CBinaryExpr, CTernaryExpr, CUnaryExpr)):
            base_str = f"({base_str})"
        op = "->" if node.is_arrow else "."
        return f"{base_str}{op}{node.field_name}"

    def visit_CIndexExpr(self, node: CIndexExpr) -> str:
        base_str = self.visit(node.base)
        if isinstance(node.base, (CBinaryExpr, CTernaryExpr, CUnaryExpr)):
            base_str = f"({base_str})"
        idx_str = self.visit(node.index)
        return f"{base_str}[{idx_str}]"