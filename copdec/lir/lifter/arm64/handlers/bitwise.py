from ....nodes import Binary, Unary
from .....insn import Insn, RegOp
from ..context import ARM64LifterContext

_BITWISE_OPS = {
    "and": "&", "ands": "&",
    "orr": "|",
    "eor": "^",
    "bic": "&", "bics": "&",
    "orn": "|",
    "eon": "^",
    "lsl": "<<", "lsr": ">>", "asr": ">>a", "ror": "ror"
}


def lift_bitwise(ctx: ARM64LifterContext, insn: Insn) -> None:
    dst: RegOp = insn.reg(0)
    lhs = ctx.read(insn.op(1))
    rhs = ctx.read(insn.op(2))

    if insn.mnemonic in ("bic", "bics", "orn", "eon"):
        rhs = Unary("~", rhs, size=rhs.size)

    op_sym = _BITWISE_OPS.get(insn.mnemonic, "&")
    res = Binary(op_sym, lhs, rhs, size=dst.size)

    ctx.write(dst, res)

    if insn.mnemonic.endswith("s"):
        ctx.emit_flags_update(res)


def lift_mvn(ctx: ARM64LifterContext, insn: Insn) -> None:
    dst: RegOp = insn.reg(0)
    src = ctx.read(insn.op(1))
    ctx.write(dst, Unary("~", src, size=dst.size))