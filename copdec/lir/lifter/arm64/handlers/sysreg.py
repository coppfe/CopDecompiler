from ....nodes import Assign
from .....insn import Insn, RegOp
from ..context import ARM64LifterContext


def lift_mrs(ctx: ARM64LifterContext, insn: Insn) -> None:
    dst: RegOp = insn.reg(0)
    sysreg: RegOp = insn.reg(1)
    ctx.write(dst, ctx.read(sysreg))


def lift_msr(ctx: ARM64LifterContext, insn: Insn) -> None:
    sysreg: RegOp = insn.reg(0)
    val = ctx.read(insn.op(1))
    ctx.emit(Assign(ctx.read(sysreg), val, pc=ctx.pc))