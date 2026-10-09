from ....nodes import Jump, JumpCond, JumpIndirect, Call, Return, Assign, RegVar, Imm, Binary
from .....insn import Insn, RegOp
from ..context import ARM64LifterContext


def lift_branch(ctx: ARM64LifterContext, insn: Insn) -> None:
    if insn.is_conditional and insn.cond is not None:
        target = insn.imm(0)
        cond_expr = ctx.eval_condition(insn.cond)
        ctx.emit(JumpCond(cond_expr, true_target=target, false_target=ctx.pc + 4, pc=ctx.pc))
    else:
        if insn.op_count > 0 and isinstance(insn.op(0), RegOp):
            target_reg = ctx.read(insn.reg(0))
            ctx.emit(JumpIndirect(target_reg, pc=ctx.pc))
        else:
            target = insn.imm(0)
            if ctx.func_pcs and not ctx.is_internal_address(target):
                args = [RegVar(f"x{i}", 64) for i in range(8)]
                ctx.emit(Call(Imm(target, 64), args, ret_reg=RegVar("x0", 64), pc=ctx.pc))
                ctx.emit(Return(RegVar("x0", 64), pc=ctx.pc))
            else:
                ctx.emit(Jump(target, pc=ctx.pc))


def lift_cbz(ctx: ARM64LifterContext, insn: Insn) -> None:
    reg_val = ctx.read(insn.reg(0))
    target = insn.imm(1)
    sym = "==" if insn.mnemonic == "cbz" else "!="
    cond_expr = Binary(sym, reg_val, Imm(0, reg_val.size), size=1)
    ctx.emit(JumpCond(cond_expr, true_target=target, false_target=ctx.pc + 4, pc=ctx.pc))


def lift_tbz(ctx: ARM64LifterContext, insn: Insn) -> None:
    reg_val = ctx.read(insn.reg(0))
    bit_pos = insn.imm(1)
    target = insn.imm(2)

    mask = Imm(1 << bit_pos, reg_val.size)
    tst = Binary("&", reg_val, mask, size=reg_val.size)
    sym = "==" if insn.mnemonic == "tbz" else "!="
    cond_expr = Binary(sym, tst, Imm(0, reg_val.size), size=1)
    ctx.emit(JumpCond(cond_expr, true_target=target, false_target=ctx.pc + 4, pc=ctx.pc))


def lift_call(ctx: ARM64LifterContext, insn: Insn) -> None:
    callee = ctx.read(insn.op(0))
    ctx.emit(Assign(RegVar("x30", 64), Imm(ctx.pc + 4, 64), pc=ctx.pc))
    args = [RegVar(f"x{i}", 64) for i in range(8)]
    ctx.emit(Call(callee, args, ret_reg=RegVar("x0", 64), pc=ctx.pc))


def lift_return(ctx: ARM64LifterContext, insn: Insn) -> None:
    ctx.emit(Return(RegVar("x0", 64), pc=ctx.pc))