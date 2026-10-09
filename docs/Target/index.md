# Target Layer (`copdec.target`)

Contains target-specific machine models, binary memory representations, and symbol metadata.

---

## ABI Model (`copdec.target.abi`)

The `TargetABI` abstraction models calling conventions:
- **`ARM64ABI`**:
  - Arguments: `x0`-`x7` (`w0`-`w7`, `d0`-`d7`, `v0`-`v7`).
  - Returns: `x0`-`x7`.
  - Callee-Saved: `x19`-`x28`, `x29` (`fp`), `x30` (`lr`), `d8`-`d15`.
  - Stack Pointer: `sp`.
  - System Registers: `tpidr_el0`.

---

## Segmented Memory Model (`copdec.target.binary.memory`)

`SectionMappedMemoryView` provides virtual memory simulation with binary search ($O(\log N)$) lookup over sorted segments:
- Segment permissions: `READ`, `WRITE`, `EXEC` (`SegmentFlags`).
- Resolves constant string literals (`read_cstring`).
- Typed numeric and floating-point readers (`read_u32`, `read_i64`, `read_f32`, etc.).

---

## Symbol Management (`copdec.target.binary.symbols`)

- **`SymbolTable`**: Maintains address-to-name and address-to-symbol lookups.
- Supports symbol arity hints (`num_args`) used by `CallingConventionCleanupPass` to prune call-site arguments accurately.