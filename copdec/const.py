"""
Core Architecture Constants.
Defines supported targets and hardware semantic attributes.
"""

from enum import IntEnum, auto


class Arch(IntEnum):
    """Target processor architecture."""
    ARM64 = auto()


class Cond(IntEnum):
    """ARM condition codes (NZCV condition flags evaluation)."""
    EQ = 0x0  # Equal (Z == 1)
    NE = 0x1  # Not Equal (Z == 0)
    CS = 0x2  # Carry Set / Unsigned Higher or Same (C == 1)
    CC = 0x3  # Carry Clear / Unsigned Lower (C == 0)
    MI = 0x4  # Minus / Negative (N == 1)
    PL = 0x5  # Plus / Positive or Zero (N == 0)
    VS = 0x6  # Overflow (V == 1)
    VC = 0x7  # No Overflow (V == 0)
    HI = 0x8  # Unsigned Higher (C == 1 and Z == 0)
    LS = 0x9  # Unsigned Lower or Same (C == 0 or Z == 1)
    GE = 0xA  # Signed Greater Than or Equal (N == V)
    LT = 0xB  # Signed Less Than (N != V)
    GT = 0xC  # Signed Greater Than (Z == 0 and N == V)
    LE = 0xD  # Signed Less Than or Equal (Z == 1 or N != V)
    AL = 0xE  # Always
    NV = 0xF  # Never


class ShiftType(IntEnum):
    """Hardware barrel shifter types."""
    LSL = 0  # Logical Shift Left
    LSR = 1  # Logical Shift Right
    ASR = 2  # Arithmetic Shift Right
    ROR = 3  # Rotate Right


class ExtendType(IntEnum):
    """Hardware register sign/zero extension modes."""
    UXTB = 0
    UXTH = 1
    UXTW = 2
    UXTX = 3
    SXTB = 4
    SXTH = 5
    SXTW = 6
    SXTX = 7