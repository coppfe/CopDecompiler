from enum import IntEnum, auto


class LIROpcode(IntEnum):
    """Discriminator for Low-Level Micro-IR instruction kinds."""
    ASSIGN        = auto()
    LOAD          = auto()
    STORE         = auto()
    JUMP          = auto()
    JUMP_COND     = auto()
    JUMP_INDIRECT = auto()
    CALL          = auto()
    RETURN        = auto()
    SYSCALL       = auto()
    INTRINSIC     = auto()
    NOP           = auto()


class BinaryOp:
    """Canonical string symbols for LIR binary operators."""
    # Arithmetic
    ADD    = "+"
    SUB    = "-"
    MUL    = "*"
    SDIV   = "/"
    UDIV   = "/u"
    SREM   = "%"
    UREM   = "%u"

    # Bitwise
    AND    = "&"
    OR     = "|"
    XOR    = "^"
    SHL    = "<<"
    LSHR   = ">>"
    ASHR   = ">>a"
    ROR    = "ror"
    ROL    = "rol"

    # Comparisons (produce 1-bit boolean)
    EQ     = "=="
    NE     = "!="
    SLT    = "<"
    SLE    = "<="
    SGT    = ">"
    SGE    = ">="
    ULT    = "<u"
    ULE    = "<=u"
    UGT    = ">u"
    UGE    = ">=u"


class UnaryOp:
    """Canonical string symbols for LIR unary operators."""
    NOT    = "~"   # Bitwise NOT
    NEG    = "-"   # Arithmetic two's complement negation
    LNOT   = "!"   # Logical boolean NOT


class CastOp:
    """Canonical string symbols for LIR casting operations."""
    ZEXT    = "zext"
    SEXT    = "sext"
    TRUNC   = "trunc"
    BITCAST = "bitcast"