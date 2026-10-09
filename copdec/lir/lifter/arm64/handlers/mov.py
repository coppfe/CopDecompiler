from ....nodes import Binary, Imm, Cast
from .....insn import Insn, RegOp, ImmOp
from ..context import ARM64LifterContext


def lift_mov(ctx: ARM64LifterContext, insn: Insn) -> None:
    dst: RegOp = insn.reg(0)
    src = ctx.read(insn.op(1))
    ctx.write(dst, src)


def lift_movk(ctx: ARM64LifterContext, insn: Insn) -> None:
    dst: RegOp = insn.reg(0)
    imm_op: ImmOp = insn.op(1)

    shift = imm_op.shift_val
    imm_val = imm_op.value & 0xFFFF
    mask = ~((0xFFFF) << shift) & ((1 << dst.size) - 1)

    curr_val = ctx.read(dst)
    cleared = Binary("&", curr_val, Imm(mask, dst.size), size=dst.size)
    res = Binary("|", cleared, Imm(imm_val << shift, dst.size), size=dst.size)

    ctx.write(dst, res)


def lift_adr(ctx: ARM64LifterContext, insn: Insn) -> None:
    dst: RegOp = insn.reg(0)
    target = insn.imm(1)
    ctx.write(dst, Imm(target, 64))
