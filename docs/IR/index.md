# SSA Intermediate Representation (`copdec.ir`)

`copdec.ir` is a strongly typed, graph-based Static Single Assignment (SSA) intermediate representation.

## Design Highlights

- **Def-Use & Use-Def Chains**: Every `Value` maintains an intrusive list of all `Use` sites. Replacing or mutating values automatically synchronizes graph users.
- **Flyweight Type System & Interning**:
  - `IntegerType` (`Int1`, `Int8`, `Int16`, `Int32`, `Int64`, `Int128`) are cached singletons.
  - Constants (`ConstantInt`, `ConstantFP`, `ConstantPointerNull`, `UndefValue`, `ConstantSymbol`) are interned and hashed by value.
- **Intrusive CFG**: `BasicBlock` contains an intrusive doubly-linked list of `Instruction` nodes.

## Braun SSA Construction (`copdec.ir.ssa`)

SSA form is constructed directly from the LIR Control Flow Graph using the algorithm described in:
> *Braun et al., "Simple and Efficient Construction of Static Single Assignment Form", CC 2013.*

- **On-the-fly Trivial Phi Elimination**: Redundant Phis (e.g. $\phi(v, v) \to v$) are collapsed dynamically upon block sealing.
- **Sealed Block Guarantee**: Variable lookups across loop headers automatically handle unsealed cyclic dependencies.
- **Entry Resolvers**: Live-on-entry registers are promoted to function formal arguments (`a0`, `a1`...) or ambient base references (`sp_base`).

## Analysis Framework (`copdec.ir.analysis`)

- **`DominanceTree`**: Immediate dominators ($idom$) and Dominance Frontiers ($DF$) computed via Cooper-Harvey-Kennedy. Fast $O(1)$ dominance queries using DFS interval timestamps.
- **`PostDominanceTree`**: Reverse CFG post-dominators with unified exit roots.
- **`ControlDependenceGraph` (CDG)**: Determines conditional control dependencies.
- **`LoopInfo`**: Natural loop detection, latch computation, and loop nesting tree construction.
- **`BasicAliasAnalysis`**: Distinguishes stack slots (`alloca`), rodata, and globals.