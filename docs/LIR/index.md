# Low-Level Intermediate Representation (`copdec.lir`)

`LIR` represents machine instructions broken down into simple, explicit micro-operations. It acts as an abstraction barrier between hardware-specific peculiarities and SSA construction.

## Goals

1. **Eliminate complex memory side-effects**: Pre-indexed and post-indexed addressing modes are lowered into explicit address computations and register write-backs.
2. **Explicit Zero-Register & Extension Semantics**: Register writes to 32-bit registers (`wN`) explicitly emit zero-extension to 64 bits (`xN`).
3. **Explicit Flag Handling**: Condition updates (`ADDS`, `SUBS`, `CMP`) emit micro-operations setting virtual condition flags (`nzcv_z`, `nzcv_n`, `nzcv_c`).

## LIR Nodes (`copdec.lir.nodes`)

### Expressions (`LIRExpr`)
- `RegVar`: Architecture or temporary register reference (`name`, `size`).
- `Imm`: Constant integer values with strict bit-width truncation.
- `Binary` / `Unary`: Arithmetic, bitwise, and relational operations.
- `Cast`: Explicit `zext`, `sext`, `trunc`, `bitcast`.
- `Select`: Ternary expressions `(cond ? true_val : false_val)`.

### Instructions (`LIRInsn`)
- `Assign`: Register assignment (`dst = src`).
- `Load` / `Store`: Direct memory accesses by explicit size and address.
- `Jump` / `JumpCond` / `JumpIndirect`: Control flow branch instructions.
- `Call` / `Return`: Subroutine invocations and exits.
- `Syscall` / `Intrinsic`: System calls and hardware-specific barriers (`dmb`, `isb`).