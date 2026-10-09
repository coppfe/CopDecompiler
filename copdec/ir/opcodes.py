

from enum import IntEnum, auto


class IROpcode(IntEnum):
    """
    Orthogonal, architecture-neutral intermediate representation opcodes.
    Modeled after LLVM IR micro-operations.
    """
    # --- Terminators ---
    RET = auto()
    BR = auto()
    BR_COND = auto()
    INDIRECT_BR = auto()
    SWITCH = auto()
    UNREACHABLE = auto()

    # --- Standard Binary ALU ---
    ADD = auto()
    SUB = auto()
    MUL = auto()
    UDIV = auto()
    SDIV = auto()
    UREM = auto()
    SREM = auto()

    # --- Floating-Point Binary ALU ---
    FADD = auto()
    FSUB = auto()
    FMUL = auto()
    FDIV = auto()

    # --- Bitwise Binary ---
    SHL = auto()
    LSHR = auto()
    ASHR = auto()
    AND = auto()
    OR = auto()
    XOR = auto()

    # --- Unary ALU ---
    NEG = auto()
    NOT = auto()
    FNEG = auto()
    FABS = auto()

    # --- Memory Operations ---
    ALLOCA = auto()
    LOAD = auto()
    STORE = auto()

    # --- Comparisons ---
    ICMP = auto()
    FCMP = auto()

    # --- Type Casts / Conversions ---
    TRUNC = auto()
    ZEXT = auto()
    SEXT = auto()
    FPTRUNC = auto()
    FPEXT = auto()
    FPTOSI = auto()
    FPTOUI = auto()
    SITOFP = auto()
    UITOFP = auto()
    BITCAST = auto()
    PTRTOINT = auto()
    INTTOPTR = auto()

    # --- SSA & Control Specials ---
    PHI = auto()
    SELECT = auto()
    CALL = auto()
    SYSCALL = auto()
    INTRINSIC = auto()


class CmpPredicate(IntEnum):
    """Relational comparison predicates for ICmpInst and FCmpInst."""
    EQ = auto()   # Equal
    NE = auto()   # Not Equal
    UGT = auto()  # Unsigned / Unordered Greater Than
    UGE = auto()  # Unsigned / Unordered Greater or Equal
    ULT = auto()  # Unsigned / Unordered Less Than
    ULE = auto()  # Unsigned / Unordered Less or Equal
    SGT = auto()  # Signed / Ordered Greater Than
    SGE = auto()  # Signed / Ordered Greater or Equal
    SLT = auto()  # Signed / Ordered Less Than
    SLE = auto()  # Signed / Ordered Less or Equal
    OEQ = auto()  # Ordered and Equal
    OGT = auto()  # Ordered and Greater Than
    OGE = auto()  # Ordered and Greater or Equal
    OLT = auto()  # Ordered and Less Than
    OLE = auto()  # Ordered and Less or Equal
    ONE = auto()  # Ordered and Not Equal
    ORD = auto()  # Ordered (no NaNs)
    UNO = auto()  # Unordered (at least one NaN)

    @property
    def symbol(self) -> str:
        symbols = {
            CmpPredicate.EQ: "==", CmpPredicate.NE: "!=",
            CmpPredicate.UGT: ">_u", CmpPredicate.UGE: ">=_u",
            CmpPredicate.ULT: "<_u", CmpPredicate.ULE: "<=_u",
            CmpPredicate.SGT: ">_s", CmpPredicate.SGE: ">=_s",
            CmpPredicate.SLT: "<_s", CmpPredicate.SLE: "<=_s",
            CmpPredicate.OEQ: "==_o", CmpPredicate.OGT: ">_o",
            CmpPredicate.OGE: ">=_o", CmpPredicate.OLT: "<_o",
            CmpPredicate.OLE: "<=_o", CmpPredicate.ONE: "!=",
            CmpPredicate.ORD: "ord", CmpPredicate.UNO: "uno",
        }
        return symbols.get(self, "??")