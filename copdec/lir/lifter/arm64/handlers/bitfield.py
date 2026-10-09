from ....nodes import Binary, Imm, Cast
from .....insn import Insn, RegOp
from ..context import ARM64LifterContext


def lift_ubfx(ctx: ARM64LifterContext, insn: Insn) -> None:
    dst: RegOp = insn.reg(0)
    src = ctx.read(insn.op(1))
    lsb = insn.imm(2)
    width = insn.imm(3)

    shifted = src if lsb == 0 else Binary(">>", src, Imm(lsb, src.size), size=src.size)
    mask_val = (1 << width) - 1
    res = Binary("&", shifted, Imm(mask_val, src.size), size=dst.size)

    ctx.write(dst, res)


def lift_sbfx(ctx: ARM64LifterContext, insn: Insn) -> None:
    dst: RegOp = insn.reg(0)
    src = ctx.read(insn.op(1))
    lsb = insn.imm(2)
    width = insn.imm(3)

    shift_left_amt = src.size - (lsb + width)
    shifted_left = Binary("<<", src, Imm(shift_left_amt, src.size), size=src.size)

    shift_right_amt = src.size - width
    res = Binary(">>a", shifted_left, Imm(shift_right_amt, src.size), size=dst.size)

    ctx.write(dst, res)

def lift_rev(ctx: ARM64LifterContext, insn: Insn) -> None:
    dst: RegOp = insn.reg(0)
    src = ctx.read(insn.op(1))
    mnem = insn.mnemonic
    size = dst.size

    if mnem == "rev" and size == 64:
        b0 = Binary("&", Binary(">>", src, Imm(56, 64), size=64), Imm(0xFF, 64), size=64)
        b1 = Binary("&", Binary(">>", src, Imm(40, 64), size=64), Imm(0xFF00, 64), size=64)
        b2 = Binary("&", Binary(">>", src, Imm(24, 64), size=64), Imm(0xFF0000, 64), size=64)
        b3 = Binary("&", Binary(">>", src, Imm(8,  64), size=64), Imm(0xFF000000, 64), size=64)
        b4 = Binary("&", Binary("<<", src, Imm(8,  64), size=64), Imm(0xFF00000000, 64), size=64)
        b5 = Binary("&", Binary("<<", src, Imm(24, 64), size=64), Imm(0xFF0000000000, 64), size=64)
        b6 = Binary("&", Binary("<<", src, Imm(40, 64), size=64), Imm(0xFF000000000000, 64), size=64)
        b7 = Binary("&", Binary("<<", src, Imm(56, 64), size=64), Imm(0xFF00000000000000, 64), size=64)
        
        res = Binary("|", Binary("|", Binary("|", b0, b1, size=64), Binary("|", b2, b3, size=64), size=64),
                          Binary("|", Binary("|", b4, b5, size=64), Binary("|", b6, b7, size=64), size=64), size=64)
    
    elif mnem in ("rev", "rev32") and size <= 32:
        b0 = Binary("&", Binary(">>", src, Imm(24, 32), size=32), Imm(0xFF, 32), size=32)
        b1 = Binary("&", Binary(">>", src, Imm(8,  32), size=32), Imm(0xFF00, 32), size=32)
        b2 = Binary("&", Binary("<<", src, Imm(8,  32), size=32), Imm(0xFF0000, 32), size=32)
        b3 = Binary("&", Binary("<<", src, Imm(24, 32), size=32), Imm(0xFF000000, 32), size=32)
        
        res = Binary("|", Binary("|", b0, b1, size=32), Binary("|", b2, b3, size=32), size=32)
    
    else:
        res = src

    ctx.write(dst, res)

def lift_sxtw(ctx: ARM64LifterContext, insn: Insn) -> None:
    dst: RegOp = insn.reg(0)
    src = ctx.read(insn.op(1))
    
    w_val = Cast("trunc", src, 32) if src.size > 32 else src
    res = Cast("sext", w_val, 64)
    ctx.write(dst, res)

def lift_uxtw(ctx: ARM64LifterContext, insn: Insn) -> None:
    dst: RegOp = insn.reg(0)
    src = ctx.read(insn.op(1))
    
    w_val = Cast("trunc", src, 32) if src.size > 32 else src
    res = Cast("zext", w_val, 64)
    ctx.write(dst, res)