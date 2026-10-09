

from typing import Any, Optional
from .core.cfg import Instruction, BasicBlock, Function
from .instructions.alu import BinaryOperator, UnaryOperator, ICmpInst, FCmpInst
from .instructions.cast import CastInst
from .instructions.memory import AllocaInst, LoadInst, StoreInst
from .instructions.control import BranchInst, BranchCondInst, SwitchInst, ReturnInst, UnreachableInst
from .instructions.special import PhiNode, SelectInst, CallInst, SyscallInst, IntrinsicInst


class IRVisitor:
    """
    Compiler IR Instruction & CFG Visitor.
    Enables modular pass implementation and analysis traversal.
    """
    __slots__ = ()

    def visit(self, inst: Optional[Instruction]) -> Any:
        if inst is None:
            return None
        method_name = f"visit_{inst.__class__.__name__}"
        visitor = getattr(self, method_name, self.generic_visit)
        return visitor(inst)

    def generic_visit(self, inst: Instruction) -> Any:
        return None

    def visit_BinaryOperator(self, inst: BinaryOperator) -> Any:
        return self.generic_visit(inst)

    def visit_UnaryOperator(self, inst: UnaryOperator) -> Any:
        return self.generic_visit(inst)

    def visit_ICmpInst(self, inst: ICmpInst) -> Any:
        return self.generic_visit(inst)

    def visit_FCmpInst(self, inst: FCmpInst) -> Any:
        return self.generic_visit(inst)

    def visit_CastInst(self, inst: CastInst) -> Any:
        return self.generic_visit(inst)

    def visit_AllocaInst(self, inst: AllocaInst) -> Any:
        return self.generic_visit(inst)

    def visit_LoadInst(self, inst: LoadInst) -> Any:
        return self.generic_visit(inst)

    def visit_StoreInst(self, inst: StoreInst) -> Any:
        return self.generic_visit(inst)

    def visit_BranchInst(self, inst: BranchInst) -> Any:
        return self.generic_visit(inst)

    def visit_BranchCondInst(self, inst: BranchCondInst) -> Any:
        return self.generic_visit(inst)

    def visit_SwitchInst(self, inst: SwitchInst) -> Any:
        return self.generic_visit(inst)

    def visit_ReturnInst(self, inst: ReturnInst) -> Any:
        return self.generic_visit(inst)

    def visit_UnreachableInst(self, inst: UnreachableInst) -> Any:
        return self.generic_visit(inst)

    def visit_PhiNode(self, inst: PhiNode) -> Any:
        return self.generic_visit(inst)

    def visit_SelectInst(self, inst: SelectInst) -> Any:
        return self.generic_visit(inst)

    def visit_CallInst(self, inst: CallInst) -> Any:
        return self.generic_visit(inst)

    def visit_SyscallInst(self, inst: SyscallInst) -> Any:
        return self.generic_visit(inst)

    def visit_IntrinsicInst(self, inst: IntrinsicInst) -> Any:
        return self.generic_visit(inst)