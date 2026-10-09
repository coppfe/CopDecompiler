from typing import Optional, Tuple, Callable, Set
from ....const import Cond, ShiftType, ExtendType
from ...nodes import (
    LIRExpr, RegVar, Imm, Binary, Cast, Assign, Select, Unary, LIRInsn
)
from ....insn import MCOperand, RegOp, ImmOp, MemOp
from ..base import BaseLifterContext


class ARM64LifterContext(BaseLifterContext):
    """Concrete AArch64 Lifting Context with strict hardware invariant enforcement."""
    __slots__ = ('last_cmp_lhs', 'last_cmp_rhs', 'func_pcs')

    def __init__(self, func_pcs: Optional[Set[int]] = None):
        super().__init__(arch_bits=64)
        self.last_cmp_lhs: Optional[LIRExpr] = None
        self.last_cmp_rhs: Optional[LIRExpr] = None
        self.func_pcs: Set[int] = func_pcs if func_pcs is not None else set()

    def is_internal_address(self, addr: int) -> bool:
        """Checks if a target address belongs to the subroutine currently being lifted."""
        return addr in self.func_pcs

    def read(self, op: MCOperand) -> LIRExpr:
        if isinstance(op, ImmOp):
            val = op.value
            if op.shift_val > 0:
                val = (val << op.shift_val) & ((1 << op.size) - 1)
            return Imm(val, op.size)

        if isinstance(op, RegOp):
            return self._read_reg(op)

        raise TypeError(f"Cannot read from operand type: {type(op).__name__}")

    def write(self, dst: MCOperand, expr: LIRExpr) -> None:
        if isinstance(dst, RegOp):
            self._write_reg(dst, expr)
            return
        raise TypeError(f"Cannot write to non-register destination: {type(dst).__name__}")

    def _read_reg(self, op: RegOp) -> LIRExpr:
        if op.is_zero:
            return Imm(0, op.size)

        if op.is_sp:
            base_reg: LIRExpr = RegVar("sp", 64)
            if op.size == 32:
                base_reg = Cast("trunc", base_reg, 32)
        else:
            base_reg = RegVar(op.canonical_name, 64)
            if op.size == 32:
                base_reg = Cast("trunc", base_reg, 32)

        res: LIRExpr = base_reg

        # Hardware sign/zero extension
        if op.extend_type is not None:
            res = self._apply_extend(res, op.extend_type)

        # Hardware barrel shifter
        if op.shift_val > 0 and op.shift_type is not None:
            res = self._apply_shift(res, op.shift_type, op.shift_val)

        return res

    def _write_reg(self, dst: RegOp, expr: LIRExpr) -> None:
        if dst.is_zero:
            # Writes to zero register are dropped by hardware
            return

        target_name = "sp" if dst.is_sp else dst.canonical_name

        if dst.size == 32:
            # AArch64 Rule: 32-bit register writes implicitly zero-extend upper 32 bits
            val32 = expr if expr.size == 32 else Cast("trunc", expr, 32)
            zext64 = Cast("zext", val32, 64)
            self.emit(Assign(RegVar(target_name, 64), zext64, pc=self.pc))
        else:
            self.emit(Assign(RegVar(target_name, 64), expr, pc=self.pc))

    @staticmethod
    def _apply_shift(val: LIRExpr, shift_type: ShiftType, shift_val: int) -> LIRExpr:
        op_map = {
            ShiftType.LSL: "<<",
            ShiftType.LSR: ">>",
            ShiftType.ASR: ">>a",
            ShiftType.ROR: "ror"
        }
        sym = op_map.get(shift_type, "<<")
        return Binary(sym, val, Imm(shift_val, val.size), size=val.size)

    @staticmethod
    def _apply_extend(val: LIRExpr, ext_type: ExtendType) -> LIRExpr:
        if ext_type == ExtendType.UXTB: return Binary("&", val, Imm(0xFF, val.size), size=val.size)
        if ext_type == ExtendType.UXTH: return Binary("&", val, Imm(0xFFFF, val.size), size=val.size)
        if ext_type == ExtendType.UXTW: return Cast("zext", Cast("trunc", val, 32), 64)
        if ext_type == ExtendType.SXTB: return Cast("sext", Cast("trunc", val, 8), val.size)
        if ext_type == ExtendType.SXTH: return Cast("sext", Cast("trunc", val, 16), val.size)
        if ext_type == ExtendType.SXTW: return Cast("sext", Cast("trunc", val, 32), 64)
        return val

    def lower_mem_address(self, mem: MemOp) -> Tuple[LIRExpr, Optional[Callable[[], None]]]:
        """
        Computes effective address and returns optional post-index writeback callback.
        """
        base_name = mem.base or "xzr"
        if base_name in ("xzr", "wzr"):
            base_expr: LIRExpr = Imm(0, 64)
        elif base_name in ("sp", "wsp"):
            base_expr = RegVar("sp", 64)
        elif base_name in ("fp", "x29", "w29"):
            base_expr = RegVar("x29", 64)
        else:
            base_expr = RegVar(f"x{base_name[1:]}" if base_name.startswith("w") else base_name, 64)

        offset_expr: Optional[LIRExpr] = None

        if mem.index:
            idx_name = mem.index
            idx_reg: LIRExpr = RegVar(f"x{idx_name[1:]}" if idx_name.startswith("w") else idx_name, 64)
            if mem.extend_type:
                idx_reg = self._apply_extend(idx_reg, mem.extend_type)
            if mem.shift_val > 0 and mem.shift_type:
                idx_reg = self._apply_shift(idx_reg, mem.shift_type, mem.shift_val)
            offset_expr = idx_reg
        elif mem.disp != 0:
            offset_expr = Imm(abs(mem.disp), 64)

        if offset_expr is not None:
            op_sym = "-" if mem.disp < 0 else "+"
            eff_addr: LIRExpr = Binary(op_sym, base_expr, offset_expr, size=64)
        else:
            eff_addr = base_expr

        post_callback: Optional[Callable[[], None]] = None

        if mem.pre_indexed and base_name not in ("xzr", "wzr"):
            self.emit(Assign(base_expr, eff_addr, pc=self.pc))
            eff_addr = base_expr

        elif mem.post_indexed and base_name not in ("xzr", "wzr"):
            post_step = abs(mem.disp) if mem.disp != 0 else mem.size // 8
            post_op = "-" if mem.disp < 0 else "+"
            post_addr = Binary(post_op, base_expr, Imm(post_step, 64), size=64)

            def _writeback():
                self.emit(Assign(RegVar(base_name, 64), post_addr, pc=self.pc))

            post_callback = _writeback
            eff_addr = base_expr

        return eff_addr, post_callback

    def emit_flags_update(
        self,
        res: LIRExpr,
        lhs: Optional[LIRExpr] = None,
        rhs: Optional[LIRExpr] = None,
        is_sub: bool = False
    ) -> None:
        self.emit(Assign(RegVar("nzcv_z", 1), Binary("==", res, Imm(0, res.size), size=1), pc=self.pc))
        self.emit(Assign(RegVar("nzcv_n", 1), Binary("<", res, Imm(0, res.size), size=1), pc=self.pc))

        if lhs is not None and rhs is not None:
            if is_sub:
                self.emit(Assign(RegVar("nzcv_c", 1), Binary(">=u", lhs, rhs, size=1), pc=self.pc))
            else:
                self.emit(Assign(RegVar("nzcv_c", 1), Binary("<u", res, lhs, size=1), pc=self.pc))
            self.last_cmp_lhs = lhs
            self.last_cmp_rhs = rhs
        else:
            self.last_cmp_lhs = res
            self.last_cmp_rhs = Imm(0, res.size)

    def eval_condition(self, cond: Cond) -> LIRExpr:
        if self.last_cmp_lhs is not None and self.last_cmp_rhs is not None:
            lhs = self.last_cmp_lhs
            rhs = self.last_cmp_rhs
            cond_map = {
                Cond.EQ: lambda: Binary("==", lhs, rhs, size=1),
                Cond.NE: lambda: Binary("!=", lhs, rhs, size=1),
                Cond.CS: lambda: Binary(">=u", lhs, rhs, size=1),
                Cond.CC: lambda: Binary("<u", lhs, rhs, size=1),
                Cond.HI: lambda: Binary(">u", lhs, rhs, size=1),
                Cond.LS: lambda: Binary("<=u", lhs, rhs, size=1),
                Cond.GE: lambda: Binary(">=", lhs, rhs, size=1),
                Cond.LT: lambda: Binary("<", lhs, rhs, size=1),
                Cond.GT: lambda: Binary(">", lhs, rhs, size=1),
                Cond.LE: lambda: Binary("<=", lhs, rhs, size=1),
            }
            if cond in cond_map:
                return cond_map[cond]()

        if cond == Cond.EQ: return RegVar("nzcv_z", 1)
        if cond == Cond.NE: return Unary("!", RegVar("nzcv_z", 1), size=1)
        if cond == Cond.CS: return RegVar("nzcv_c", 1)
        if cond == Cond.CC: return Unary("!", RegVar("nzcv_c", 1), size=1)
        if cond == Cond.MI: return RegVar("nzcv_n", 1)
        if cond == Cond.PL: return Unary("!", RegVar("nzcv_n", 1), size=1)

        return Imm(1, 1)