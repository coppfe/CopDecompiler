from ....nodes import Binary, Imm, Cast
from .....insn import Insn, RegOp
from ..context import ARM64LifterContext

_ALU_OPS = {
    "add": "+", "adds": "+",
    "sub": "-", "subs": "-",
    "mul": "*", "madd": "*", "msub": "*",
    "sdiv": "/", "udiv": "/u"
}


def lift_binary_alu(ctx: ARM64LifterContext, insn: Insn) -> None:
    dst: RegOp = insn.reg(0)
    lhs = ctx.read(insn.op(1))
    rhs = ctx.read(insn.op(2))

    op_sym = _ALU_OPS.get(insn.mnemonic, "+")

    if insn.mnemonic in ("madd", "msub"):
        ra = ctx.read(insn.op(3))
        mul_res = Binary("*", lhs, rhs, size=dst.size)
        accum_sym = "+" if insn.mnemonic == "madd" else "-"
        res = Binary(accum_sym, ra, mul_res, size=dst.size)
    else:
        res = Binary(op_sym, lhs, rhs, size=dst.size)

    ctx.write(dst, res)

    if insn.mnemonic.endswith("s"):
        ctx.emit_flags_update(res, lhs, rhs, is_sub="sub" in insn.mnemonic)


def lift_neg(ctx: ARM64LifterContext, insn: Insn) -> None:
    dst: RegOp = insn.reg(0)
    src = ctx.read(insn.op(1))
    res = Binary("-", Imm(0, dst.size), src, size=dst.size)
    ctx.write(dst, res)

    if insn.mnemonic == "negs":
        ctx.emit_flags_update(res, Imm(0, dst.size), src, is_sub=True)

def lift_umull(ctx: ARM64LifterContext, insn: Insn) -> None:
    dst: RegOp = insn.reg(0)
    rn = ctx.read(insn.op(1))
    rm = ctx.read(insn.op(2))

    rn_32 = Cast("trunc", rn, 32) if rn.size > 32 else rn
    rm_32 = Cast("trunc", rm, 32) if rm.size > 32 else rm
    
    rn_64 = Cast("zext", rn_32, 64)
    rm_64 = Cast("zext", rm_32, 64)

    res = Binary("*", rn_64, rm_64, size=64)
    ctx.write(dst, res)

def lift_smull(ctx: ARM64LifterContext, insn: Insn) -> None:
    dst: RegOp = insn.reg(0)
    rn = ctx.read(insn.op(1))
    rm = ctx.read(insn.op(2))

    rn_32 = Cast("trunc", rn, 32) if rn.size > 32 else rn
    rm_32 = Cast("trunc", rm, 32) if rm.size > 32 else rm
    
    rn_64 = Cast("sext", rn_32, 64)
    rm_64 = Cast("sext", rm_32, 64)

    res = Binary("*", rn_64, rm_64, size=64)
    ctx.write(dst, res)