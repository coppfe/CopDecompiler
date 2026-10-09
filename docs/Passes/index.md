# Optimization Passes (`copdec.ir.passes` & `copdec.pipeline`)

Passes in `copdec` are executed across distinct layers managed by `PassManager`. Layers support both single-pass (`ONCE`) and iterative convergence (`FIXPOINT`) policies.

---

## Middle-End IR Passes

### 1. `InstCombinePass` (`copdec.ir.passes.instcombine`)
Peephole algebraic simplifications and store-to-load forwarding:
- Algebraic identities: $x + 0 \to x$, $x \land x \to x$, $x \oplus x \to 0$, $x \times 0 \to 0$.
- Store-to-Load Forwarding: Reads following a dominating `StoreInst` to the same local `alloca` within the same basic block are replaced with the stored value.

### 2. `GVNPass` (Global Value Numbering)
Eliminates redundant computations across distinct basic blocks using dominance congruence. Uses allocation-free tuple keys (`ExpressionKey`).

### 3. `ADCEPass` (Aggressive Dead Code Elimination)
Identifies critical root instructions (memory stores, branches, returns, external calls) and sweeps unreferenced SSA values backwards.

### 4. `CFGSimplifyPass`
- Folds constant branches (`br i1 true/false`).
- Prunes unreachable basic blocks.
- Merges linear block chains ($A \to B$ where $A$ has 1 successor and $B$ has 1 predecessor).
- Synchronizes Phi-nodes across deleted CFG edges.

### 5. `CallingConventionCleanupPass`
- Prunes dummy tail arguments injected by generic calling convention lifters.
- Strips unused formal parameters from the function prototype.
- Infers `void` return types.

### 6. `StackFramePromotionPass`
- Identifies accesses relative to `sp_base`.
- Verifies slot boundaries to prevent overlapping aliasing.
- Promotes isolated stack slots into first-class `AllocaInst` variables.