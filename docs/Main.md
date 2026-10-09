# copdec Architecture & Design Overview

**copdec** is a modular binary analysis and decompilation framework currently targeting AArch64 (ARM64).

Unlike naive pattern-matching decompilers, `copdec` adopts a modern multi-tier compiler pipeline modeled after modern optimizing compilers (such as LLVM) and academic SSA reconstruction algorithms.

---

## High-Level Pipeline Architecture
```
[ Machine Code (Bytes) ]
│
▼ (capstone-engine wrapper)
[ Decoded Insn Stream ] ───────── copdec.decoder
│
▼ (Semantic Lifting)
[ Low-Level IR (LIR) ] ────────── copdec.lir
│
▼ (Braun SSA Construction)
[ Static Single Assignment (IR) ] copdec.ir
│
▼ (Optimization Pipeline: GVN, InstCombine, ADCE, CFGSimplify)
[ Optimized SSA IR ] ──────────── copdec.ir.passes
│
▼ (Hammock SESE Structurizer & HighVariable DSU)
[ AST Bridge ] ────────────────── copdec.bridge.ast
│
▼ (AST Passes: Inlining, Loop Refiner, Dead Code)
[ High-Level C AST ] ──────────── copdec.ast
│
├──────────────────────────┐
▼ ▼
[ Strict C Output ] [ Python 3.10+ Pseudocode ]
```

---

## Core Layers

1. **`Decoder`**: Machine instruction decoding into immutable, architecture-normalized operand primitives (`RegOp`, `ImmOp`, `MemOp`).
2. **`LIR` (Low-Level Micro-IR)**: Decomposes complex CISC/RISC hardware instructions into explicit primitives, evaluates condition codes, and handles memory addressing modes.
3. **`IR` (SSA Intermediate Representation)**: Strongly typed, control-flow graph based SSA form with intrusive doubly-linked instructions, Def-Use chains, and interning flyweights.
4. **`Passes`**: Modular optimization passes that run on both IR and AST levels using a configurable `PassManager`.
5. **`Bridge`**: Connects low-level graph representations with high-level structural semantics (CFG to structured loops/if- hammocks, and SSA values into scoped C variables).
6. **`AST`**: Expression and Statement trees capable of generating idiomatic C or Python 3.10+ pseudocode.
7. **`Target`**: Architecture-specific details, calling conventions (AAPCS64), virtual memory mapping, and symbol tables.

---

## Future Roadmap: AOT Binary Translation

The intermediate representations (`LIR` and SSA `IR`) are decoupled from high-level C AST emission. This enables `copdec` to be repurposed as an **Ahead-of-Time (AOT) Binary Translator**:
- **LIR-to-LLVM / IR-to-LLVM Backend**: Translate SSA blocks directly to LLVM IR module definitions.
- **Runtime Emulation Hooks**: Bridge system registers (`tpidr_el0`, timer registers) and syscalls directly into a runtime library.