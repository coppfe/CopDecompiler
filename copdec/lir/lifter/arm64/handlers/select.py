from ....nodes import Select, Binary, Unary, Imm
from .....insn import Insn, RegOp
from ..context import ARM64LifterContext


def lift_select(ctx: ARM64LifterContext, insn: Insn) -> None:
    dst: RegOp = insn.reg(0)
    cond = insn.cond
    cond_expr = ctx.eval_condition(cond) if cond else Imm(1, 1)

    if insn.mnemonic == "cset":
        t_val = Imm(1, dst.size)
        f_val = Imm(0, dst.size)
    else:
        rn_val = ctx.read(insn.op(1))
        rm_val = ctx.read(insn.op(2))

        if insn.mnemonic == "csel":
            t_val, f_val = rn_val, rm_val
        elif insn.mnemonic == "csinc":
            t_val = rn_val
            f_val = Binary("+", rm_val, Imm(1, dst.size), size=dst.size)
        elif insn.mnemonic == "csinv":
            t_val = rn_val
            f_val = Unary("~", rm_val, size=dst.size)
        elif insn.mnemonic == "csneg":
            t_val = rn_val
            f_val = Binary("-", Imm(0, dst.size), rm_val, size=dst.size)
        else:
            t_val, f_val = rn_val, rm_val

    sel = Select(cond_expr, t_val, f_val, size=dst.size)
    ctx.write(dst, sel)