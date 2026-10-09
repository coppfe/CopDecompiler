from ....nodes import Binary
from .....insn import Insn
from ..context import ARM64LifterContext


def lift_cmp(ctx: ARM64LifterContext, insn: Insn) -> None:
    lhs = ctx.read(insn.op(0))
    rhs = ctx.read(insn.op(1))

    if insn.mnemonic == "cmp":
        diff = Binary("-", lhs, rhs, size=lhs.size)
        ctx.emit_flags_update(diff, lhs, rhs, is_sub=True)
    elif insn.mnemonic == "cmn":
        total = Binary("+", lhs, rhs, size=lhs.size)
        ctx.emit_flags_update(total, lhs, rhs, is_sub=False)
    elif insn.mnemonic == "tst":
        band = Binary("&", lhs, rhs, size=lhs.size)
        ctx.emit_flags_update(band)