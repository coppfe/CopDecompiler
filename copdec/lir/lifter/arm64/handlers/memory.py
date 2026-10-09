from ....nodes import Load, Store, Cast, Binary, Imm, RegVar
from .....insn import Insn, RegOp, MemOp
from ..context import ARM64LifterContext


def lift_memory_single(ctx: ARM64LifterContext, insn: Insn) -> None:
    reg: RegOp = insn.reg(0)
    mem: MemOp = insn.mem(1)

    eff_addr, post_cb = ctx.lower_mem_address(mem)
    elem_bytes = max(1, mem.size // 8)
    is_load = insn.mnemonic.startswith("ld")
    sign_extend = "s" in insn.mnemonic[2:]

    if is_load:
        dst_var = RegVar(reg.canonical_name, 64)
        
        ctx.emit(Load(dst_var, eff_addr, size=elem_bytes, sign_extend=sign_extend, pc=ctx.pc))
    else:
        src_val = ctx.read(reg)
        if src_val.size > mem.size:
            src_val = Cast("trunc", src_val, mem.size)
        ctx.emit(Store(eff_addr, src_val, size=elem_bytes, pc=ctx.pc))

    if post_cb:
        post_cb()

def lift_memory_pair(ctx: ARM64LifterContext, insn: Insn) -> None:
    r1: RegOp = insn.reg(0)
    r2: RegOp = insn.reg(1)
    mem: MemOp = insn.mem(2)

    eff_addr, post_cb = ctx.lower_mem_address(mem)
    elem_bytes = 8 if r1.size == 64 else 4
    addr2 = Binary("+", eff_addr, Imm(elem_bytes, 64), size=64)
    is_ldp = insn.mnemonic == "ldp"

    if is_ldp:
        t1 = RegVar(r1.canonical_name, 64)
        t2 = RegVar(r2.canonical_name, 64)
        ctx.emit(Load(t1, eff_addr, size=elem_bytes, pc=ctx.pc))
        ctx.emit(Load(t2, addr2, size=elem_bytes, pc=ctx.pc))
    else:
        v1 = ctx.read(r1)
        v2 = ctx.read(r2)
        ctx.emit(Store(eff_addr, v1, size=elem_bytes, pc=ctx.pc))
        ctx.emit(Store(addr2, v2, size=elem_bytes, pc=ctx.pc))

    if post_cb:
        post_cb()