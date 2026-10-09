from typing import List, Optional
from .opcodes import LIROpcode, BinaryOp


# =============================================================================
# LIR Expressions (LIRExpr)
# =============================================================================

class LIRExpr:
    """Abstract base class for all Low-Level Micro-IR expressions."""
    __slots__ = ('size',)

    def __init__(self, size: int = 32):
        assert size > 0, f"Expression bit-width must be strictly positive, got: {size}"
        self.size: int = size  # Bit-width: 1 (bool), 8, 16, 32, 64, 128


class RegVar(LIRExpr):
    """
    Architectural or temporary register identifier.
    Completely architecture-agnostic (e.g. 'r0', 'sp', 'x0', 'flags', 'temp_0').
    """
    __slots__ = ('name',)

    def __init__(self, name: str, size: int = 32):
        super().__init__(size)
        self.name: str = name

    def __repr__(self) -> str:
        return f"{self.name}:{self.size}"

    def __str__(self) -> str:
        return f"{self.name}:{self.size}"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, RegVar) and self.name == other.name and self.size == other.size

    def __hash__(self) -> int:
        return hash((self.name, self.size))


class Imm(LIRExpr):
    """Literal integer constant value with strict bit-width masking."""
    __slots__ = ('val',)

    def __init__(self, val: int, size: int = 32):
        super().__init__(size)
        mask = (1 << size) - 1 if size < 128 else (1 << 128) - 1
        self.val: int = val & mask

    @property
    def signed_value(self) -> int:
        """Returns the two's complement signed interpretation of this immediate."""
        sign_bit = 1 << (self.size - 1)
        if self.val & sign_bit:
            return self.val - (1 << self.size)
        return self.val

    def __repr__(self) -> str:
        if self.val > 0xFFF or self.val < -0xFFF:
            return f"0x{self.val:x}:{self.size}"
        return f"{self.val}:{self.size}"

    def __str__(self) -> str:
        return self.__repr__()

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Imm) and self.val == other.val and self.size == other.size

    def __hash__(self) -> int:
        return hash((self.val, self.size))


class Unary(LIRExpr):
    """Unary operation: ~, -, !"""
    __slots__ = ('op', 'val')

    def __init__(self, op: str, val: LIRExpr, size: Optional[int] = None):
        super().__init__(size if size is not None else val.size)
        self.op: str = op
        self.val: LIRExpr = val

    def __repr__(self) -> str:
        return f"({self.op}{self.val})"

    def __str__(self) -> str:
        return self.__repr__()

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Unary) and self.op == other.op and self.val == other.val and self.size == other.size

    def __hash__(self) -> int:
        return hash((self.op, self.val, self.size))


class Binary(LIRExpr):
    """Binary operation: +, -, *, /, &, |, ^, <<, >>, ==, !=, <, etc."""
    __slots__ = ('op', 'lhs', 'rhs')

    def __init__(self, op: str, lhs: LIRExpr, rhs: LIRExpr, size: Optional[int] = None):
        is_cmp = op in (
            BinaryOp.EQ, BinaryOp.NE, BinaryOp.SLT, BinaryOp.SLE,
            BinaryOp.SGT, BinaryOp.SGE, BinaryOp.ULT, BinaryOp.ULE,
            BinaryOp.UGT, BinaryOp.UGE
        )
        res_size = size if size is not None else (1 if is_cmp else lhs.size)
        super().__init__(res_size)
        self.op: str = op
        self.lhs: LIRExpr = lhs
        self.rhs: LIRExpr = rhs

    def __repr__(self) -> str:
        return f"({self.lhs} {self.op} {self.rhs})"

    def __str__(self) -> str:
        return self.__repr__()

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, Binary) and
            self.op == other.op and
            self.lhs == other.lhs and
            self.rhs == other.rhs and
            self.size == other.size
        )

    def __hash__(self) -> int:
        return hash((self.op, self.lhs, self.rhs, self.size))


class Select(LIRExpr):
    """Conditional select / ternary expression: (cond ? true_val : false_val)"""
    __slots__ = ('cond', 'true_val', 'false_val')

    def __init__(self, cond: LIRExpr, true_val: LIRExpr, false_val: LIRExpr, size: Optional[int] = None):
        super().__init__(size if size is not None else true_val.size)
        self.cond: LIRExpr = cond
        self.true_val: LIRExpr = true_val
        self.false_val: LIRExpr = false_val

    def __repr__(self) -> str:
        return f"({self.cond} ? {self.true_val} : {self.false_val})"

    def __str__(self) -> str:
        return self.__repr__()

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, Select) and
            self.cond == other.cond and
            self.true_val == other.true_val and
            self.false_val == other.false_val and
            self.size == other.size
        )

    def __hash__(self) -> int:
        return hash((self.cond, self.true_val, self.false_val, self.size))


class Cast(LIRExpr):
    """Explicit bit-width conversion: zext, sext, trunc, bitcast."""
    __slots__ = ('op', 'val')

    def __init__(self, op: str, val: LIRExpr, target_size: int):
        super().__init__(target_size)
        self.op: str = op
        self.val: LIRExpr = val

    def __repr__(self) -> str:
        return f"{self.op}({self.val} to {self.size})"

    def __str__(self) -> str:
        return self.__repr__()

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Cast) and self.op == other.op and self.val == other.val and self.size == other.size

    def __hash__(self) -> int:
        return hash((self.op, self.val, self.size))


# =============================================================================
# LIR Instructions (LIRInsn)
# =============================================================================

class LIRInsn:
    """Abstract base class for all linear Low-Level micro-instructions."""
    __slots__ = ('pc',)

    def __init__(self, pc: int = 0):
        self.pc: int = pc

    @property
    def opcode(self) -> LIROpcode:
        raise NotImplementedError

    @property
    def is_terminator(self) -> bool:
        return False

    def __repr__(self) -> str:
        raise NotImplementedError


class Assign(LIRInsn):
    """dst = expr (register assignment)"""
    __slots__ = ('dst', 'src')

    def __init__(self, dst: RegVar, src: LIRExpr, pc: int = 0):
        super().__init__(pc)
        self.dst: RegVar = dst
        self.src: LIRExpr = src

    @property
    def opcode(self) -> LIROpcode:
        return LIROpcode.ASSIGN

    def __repr__(self) -> str:
        return f"{self.dst} = {self.src}"


class Load(LIRInsn):
    """dst = [sext] load.size[addr] (memory read)"""
    __slots__ = ('dst', 'addr', 'size', 'sign_extend')

    def __init__(self, dst: RegVar, addr: LIRExpr, size: int = 4, sign_extend: bool = False, pc: int = 0):
        super().__init__(pc)
        self.dst: RegVar = dst
        self.addr: LIRExpr = addr
        self.size: int = size
        self.sign_extend: bool = sign_extend

    @property
    def opcode(self) -> LIROpcode:
        return LIROpcode.LOAD

    def __repr__(self) -> str:
        ext = "sext " if self.sign_extend else ""
        return f"{self.dst} = {ext}load.{self.size * 8}[{self.addr}]"


class Store(LIRInsn):
    """store.size[addr] = val (memory write)"""
    __slots__ = ('addr', 'val', 'size')

    def __init__(self, addr: LIRExpr, val: LIRExpr, size: int = 4, pc: int = 0):
        super().__init__(pc)
        self.addr: LIRExpr = addr
        self.val: LIRExpr = val
        self.size: int = size

    @property
    def opcode(self) -> LIROpcode:
        return LIROpcode.STORE

    def __repr__(self) -> str:
        return f"store.{self.size * 8}[{self.addr}] = {self.val}"


class Jump(LIRInsn):
    """Unconditional direct jump: goto target"""
    __slots__ = ('target',)

    def __init__(self, target: int, pc: int = 0):
        super().__init__(pc)
        self.target: int = target

    @property
    def opcode(self) -> LIROpcode:
        return LIROpcode.JUMP

    @property
    def is_terminator(self) -> bool:
        return True

    def __repr__(self) -> str:
        return f"goto 0x{self.target:x}"


class JumpCond(LIRInsn):
    """Conditional branch: if (cond) goto true_target else goto false_target"""
    __slots__ = ('cond', 'true_target', 'false_target')

    def __init__(self, cond: LIRExpr, true_target: int, false_target: int, pc: int = 0):
        super().__init__(pc)
        self.cond: LIRExpr = cond
        self.true_target: int = true_target
        self.false_target: int = false_target

    @property
    def opcode(self) -> LIROpcode:
        return LIROpcode.JUMP_COND

    @property
    def is_terminator(self) -> bool:
        return True

    def __repr__(self) -> str:
        return f"if ({self.cond}) goto 0x{self.true_target:x} else goto 0x{self.false_target:x}"

class JumpIndirect(LIRInsn):
    """Indirect control flow jump: goto *target_expr"""
    __slots__ = ('target',)

    def __init__(self, target: LIRExpr, pc: int = 0):
        super().__init__(pc)
        self.target: LIRExpr = target

    @property
    def opcode(self) -> LIROpcode:
        return LIROpcode.JUMP_INDIRECT

    @property
    def is_terminator(self) -> bool:
        return True

    def __repr__(self) -> str:
        return f"goto *{self.target}"

class Call(LIRInsn):
    """Subroutine invocation: [ret_reg =] call callee(args...)"""
    __slots__ = ('callee', 'args', 'ret_reg')

    def __init__(self, callee: LIRExpr, args: List[LIRExpr], ret_reg: Optional[RegVar] = None, pc: int = 0):
        super().__init__(pc)
        self.callee: LIRExpr = callee
        self.args: List[LIRExpr] = args
        self.ret_reg: Optional[RegVar] = ret_reg

    @property
    def opcode(self) -> LIROpcode:
        return LIROpcode.CALL

    def __repr__(self) -> str:
        args_str = ", ".join(str(a) for a in self.args)
        ret_str = f"{self.ret_reg} = " if self.ret_reg else ""
        return f"{ret_str}call {self.callee}({args_str})"


class Return(LIRInsn):
    """Function return: ret [val]"""
    __slots__ = ('val',)

    def __init__(self, val: Optional[LIRExpr] = None, pc: int = 0):
        super().__init__(pc)
        self.val: Optional[LIRExpr] = val

    @property
    def opcode(self) -> LIROpcode:
        return LIROpcode.RETURN

    @property
    def is_terminator(self) -> bool:
        return True

    def __repr__(self) -> str:
        return f"ret {self.val}" if self.val else "ret"


class Syscall(LIRInsn):
    """Supervisor / System call: [ret_reg =] syscall #num(args...)"""
    __slots__ = ('num', 'args', 'ret_reg')

    def __init__(self, num: LIRExpr, args: List[LIRExpr], ret_reg: Optional[RegVar] = None, pc: int = 0):
        super().__init__(pc)
        self.num: LIRExpr = num
        self.args: List[LIRExpr] = args
        self.ret_reg: Optional[RegVar] = ret_reg

    @property
    def opcode(self) -> LIROpcode:
        return LIROpcode.SYSCALL

    def __repr__(self) -> str:
        args_str = ", ".join(str(a) for a in self.args)
        ret_str = f"{self.ret_reg} = " if self.ret_reg else ""
        return f"{ret_str}syscall #{self.num}({args_str})"


class Intrinsic(LIRInsn):
    """Special hardware operation (e.g. DMB, ISB, PAC)"""
    __slots__ = ('name', 'args')

    def __init__(self, name: str, args: Optional[List[LIRExpr]] = None, pc: int = 0):
        super().__init__(pc)
        self.name: str = name
        self.args: List[LIRExpr] = args if args is not None else []

    @property
    def opcode(self) -> LIROpcode:
        return LIROpcode.INTRINSIC

    def __repr__(self) -> str:
        args_str = ", ".join(str(a) for a in self.args)
        return f"intrinsic @{self.name}({args_str})"


class Nop(LIRInsn):
    """No-operation instruction placeholder"""
    __slots__ = ()

    @property
    def opcode(self) -> LIROpcode:
        return LIROpcode.NOP

    def __repr__(self) -> str:
        return "nop"