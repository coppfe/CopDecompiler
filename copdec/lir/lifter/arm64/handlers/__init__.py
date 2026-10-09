from typing import Dict, Callable
from .....insn import Insn
from ..context import ARM64LifterContext

from .alu import lift_binary_alu, lift_neg, lift_umull, lift_smull
from .compare import lift_cmp
from .bitwise import lift_bitwise, lift_mvn
from .mov import lift_mov, lift_movk, lift_adr
from .memory import lift_memory_single, lift_memory_pair
from .branch import lift_branch, lift_cbz, lift_tbz, lift_call, lift_return
from .select import lift_select
from .sysreg import lift_mrs, lift_msr
from .bitfield import lift_ubfx, lift_sbfx, lift_rev, lift_sxtw, lift_uxtw

Handler = Callable[[ARM64LifterContext, Insn], None]

HANDLER_MAP: Dict[str, Handler] = {
    # ALU
    "add": lift_binary_alu, "adds": lift_binary_alu,
    "sub": lift_binary_alu, "subs": lift_binary_alu,
    "mul": lift_binary_alu, "madd": lift_binary_alu, "msub": lift_binary_alu,
    "sdiv": lift_binary_alu, "udiv": lift_binary_alu,
    "neg": lift_neg, "negs": lift_neg,
    "umull": lift_umull, "smull": lift_smull,

    # Compare
    "cmp": lift_cmp, "cmn": lift_cmp, "tst": lift_cmp,

    # Bitwise
    "and": lift_bitwise, "ands": lift_bitwise,
    "orr": lift_bitwise, "eor": lift_bitwise,
    "bic": lift_bitwise, "bics": lift_bitwise,
    "orn": lift_bitwise, "eon": lift_bitwise,
    "lsl": lift_bitwise, "lsr": lift_bitwise,
    "asr": lift_bitwise, "ror": lift_bitwise,
    "mvn": lift_mvn,

    # Moves
    "mov": lift_mov, "movz": lift_mov, "movn": lift_mov,
    "movk": lift_movk,
    "adr": lift_adr, "adrp": lift_adr,

    # Memory
    "ldr": lift_memory_single, "ldrb": lift_memory_single, "ldrh": lift_memory_single,
    "ldrsb": lift_memory_single, "ldrsh": lift_memory_single, "ldur": lift_memory_single,
    "str": lift_memory_single, "strb": lift_memory_single, "strh": lift_memory_single, "stur": lift_memory_single,
    "ldp": lift_memory_pair, "stp": lift_memory_pair,
    "ldar": lift_memory_single, "ldarb": lift_memory_single, "ldarh": lift_memory_single,
    "stlr": lift_memory_single, "stlrb": lift_memory_single, "stlrh": lift_memory_single,

    # Branches & Calls
    "b": lift_branch, "br": lift_branch,
    "cbz": lift_cbz, "cbnz": lift_cbz,
    "tbz": lift_tbz, "tbnz": lift_tbz,
    "bl": lift_call, "blr": lift_call,
    "ret": lift_return,

    # Selects
    "csel": lift_select, "csinc": lift_select,
    "csinv": lift_select, "csneg": lift_select,
    "cset": lift_select,

    # System registers
    "mrs": lift_mrs, "msr": lift_msr,

    "ubfx": lift_ubfx,
    "sbfx": lift_sbfx,
    "rev": lift_rev,    # 64-bit / 32-bit full byte-swap
    "rev16": lift_rev,  # Swap bytes within halfwords
    "rev32": lift_rev,  # Swap bytes within words in GPR
    "sxtw": lift_sxtw,
    "uxtw": lift_uxtw, #  zext
}

for cond_suffix in ("eq", "ne", "cs", "cc", "mi", "pl", "vs", "vc", "hi", "ls", "ge", "lt", "gt", "le"):
    HANDLER_MAP[f"b.{cond_suffix}"] = lift_branch