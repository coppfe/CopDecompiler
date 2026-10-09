# Bridge Layer (`copdec.bridge`)

The Bridge layer transforms low-level SSA CFG structures into high-level C Abstract Syntax Trees.

---

## Control Flow Structurization (`copdec.bridge.ast.engine`)

### 1. Hammock & SESE Region Discovery (`HammockAnalyzer`)
Uses the Post-Dominance tree and reachability analysis to identify Single-Entry Single-Exit (SESE) hammocks:
- Pure If-Then ($A \to B \to C$ and $A \to C$).
- If-Then-Else ($A \to B \to D$ and $A \to C \to D$).
- Loop bodies, break targets, and continue latches.

### 2. Control Region Tree (`ControlTreeBuilder`)
Converts the flat graph into a recursive hierarchy of `ControlRegion` instances:
- `SeqRegion`
- `IfRegion`
- `LoopRegion` (`while`, `do-while`)
- `SwitchRegion`
- `BreakRegion` / `ContinueRegion` / `GotoRegion`

---

## High Variable Management (`HighVariableManager`)

SSA creates new value versions for every assignment. The decompiler reconciles them into high-level variables using a Disjoint Set Union (DSU) structure:
- Merges SSA $\phi$-nodes and their operands into equivalence webs.
- Differentiates between function arguments, stack variables (`alloca`), and function-scoped local variables.
- Generates semantic names (`v1`, `v2`, `b1` for booleans).