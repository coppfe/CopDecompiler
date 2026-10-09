from typing import Set, List
from .....ir.opcodes import IROpcode
from .....ir.core.cfg import BasicBlock
from .....ir.instructions.special import PhiNode
from .....ast.nodes import (
    CBlock, CIfStmt, CWhileStmt, CDoWhileStmt, CSwitchStmt, CCaseStmt,
    CReturnStmt, CBreakStmt, CContinueStmt, CGotoStmt, CLabelStmt,
    CLiteralExpr, CExpr, CBinaryExpr, CUnaryExpr, CVarExpr
)
from .....ast.types import CType
from ..structurize.region import (
    ControlRegion, BlockRegion, SeqRegion, IfRegion, LoopRegion,
    BreakRegion, ContinueRegion, GotoRegion, SwitchRegion, CaseRegion
)
from .instruction_translator import InstructionTranslator

_INVERT_CMP = {
    "==": "!=", "!=": "==",
    "<": ">=", "<=": ">",
    ">": "<=", ">=": "<"
}


class CASTBuilder:
    __slots__ = ('_translator', '_labels_in_use')

    def __init__(self, translator: InstructionTranslator, labels_in_use: Set[str]):
        self._translator = translator
        self._labels_in_use = labels_in_use

    def _invert_expr(self, expr: CExpr) -> CExpr:
        if isinstance(expr, CBinaryExpr) and expr.op in _INVERT_CMP:
            return CBinaryExpr(_INVERT_CMP[expr.op], expr.lhs, expr.rhs, expr.ctype)
        if isinstance(expr, CUnaryExpr) and expr.op == "!":
            return expr.operand
        return CUnaryExpr("!", expr, CType("bool", bit_width=1))

    def _materialize_phi_copies(self, bb: BasicBlock, parent: CBlock) -> None:
        for succ in bb.successors:
            curr = succ.first_instruction
            while isinstance(curr, PhiNode):
                in_val = curr.get_incoming_value_for_block(bb)
                if in_val is not None:
                    phi_cvar = self._translator.get_var(curr)
                    in_expr = self._translator.get_var(in_val)

                    if isinstance(phi_cvar, CVarExpr) and isinstance(in_expr, CVarExpr):
                        if phi_cvar.name == in_expr.name:
                            curr = curr.next_node
                            continue

                    stmt = self._translator.create_assignment(phi_cvar, in_expr)
                    if stmt is not None:
                        parent.append(stmt)
                curr = curr.next_node

    def lower(self, region: ControlRegion, parent: CBlock) -> None:
        if isinstance(region, SeqRegion):
            for r in region.regions:
                self.lower(r, parent)

        elif isinstance(region, BlockRegion):
            bb = region.bb
            if bb.name in self._labels_in_use:
                parent.append(CLabelStmt(bb.name))

            for inst in bb:
                if not inst.is_terminator:
                    self._translator.translate(inst, parent)

            self._materialize_phi_copies(bb, parent)

            term = bb.get_terminator()
            if term is not None and term.opcode == IROpcode.RET:
                ret_val = self._translator.get_var(term.return_value.resolve()) if term.return_value else None
                parent.append(CReturnStmt(ret_val))

        elif isinstance(region, IfRegion):
            cond_expr = self._translator.get_var(region.cond.resolve())
            if region.is_inverted:
                cond_expr = self._invert_expr(cond_expr)

            then_block = CBlock()
            self.lower(region.then_body, then_block)

            else_block = None
            if region.else_body is not None and region.else_body.regions:
                else_block = CBlock()
                self.lower(region.else_body, else_block)

            parent.append(CIfStmt(cond_expr, then_block, else_block))

        elif isinstance(region, LoopRegion):
            body_block = CBlock()
            self.lower(region.body, body_block)

            if body_block.stmts and isinstance(body_block.stmts[-1], CContinueStmt):
                body_block.stmts.pop()

            cond_expr = (
                self._translator.get_var(region.cond.resolve())
                if region.cond is not None
                else CLiteralExpr(True, CType("bool", bit_width=1))
            )
            if region.is_inverted and region.cond is not None:
                cond_expr = self._invert_expr(cond_expr)

            if region.is_do_while:
                parent.append(CDoWhileStmt(cond_expr, body_block))
            else:
                parent.append(CWhileStmt(cond_expr, body_block))

        elif isinstance(region, BreakRegion):
            parent.append(CBreakStmt())

        elif isinstance(region, ContinueRegion):
            parent.append(CContinueStmt())

        elif isinstance(region, GotoRegion):
            parent.append(CGotoStmt(region.target_name))

        elif isinstance(region, SwitchRegion):
            cond_expr = self._translator.get_var(region.cond.resolve())
            c_cases: List[CCaseStmt] = []

            for cr in region.cases:
                case_val = self._translator.get_var(cr.val.resolve()) if cr.val is not None else None
                case_body = CBlock()
                self.lower(cr.body, case_body)
                c_cases.append(CCaseStmt(val=case_val, body=case_body, is_default=False))

            default_case = None
            if region.default_case is not None:
                def_body = CBlock()
                self.lower(region.default_case.body, def_body)
                default_case = CCaseStmt(val=None, body=def_body, is_default=True)

            parent.append(CSwitchStmt(cond=cond_expr, cases=c_cases, default_case=default_case))