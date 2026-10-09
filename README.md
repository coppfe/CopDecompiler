# Why copdec?

I wrote this tool with one specific goal in mind: **as an answer to the current state of decompilers.**

I hate the fact that for almost any decent decompiler today you have to pay a fortune to use it. Ghidra is free, but writing custom optimization passes over P-Code is an absolute pain. 

So, together with Gemini, I wrote this project in 1 month. The architecture is heavily inspired by [**LLVM**](https://github.com/llvm/llvm-project):
- Declarative Pass Manager system
- Explicit Scope classes
- Robust binary memory & symbol resolving
- Clean, modular multi-tier IR

---

## The Pipeline

```
LIR ──► LIRTranslator / Step-IR ──► SSABuilder ──► SSA IR ──► Optimizers ──► AST Bridge ──► AST ──► Pretty-Printer
```

---

## Architecture Breakdown

* **`lir/` (Micro-IR)**  
  Low-level representation. Hardware quirks, flags, and complex memory addressing modes are lowered into explicit micro-operations. It is still low-level, but no longer raw machine assembly.

* **`abi/` (Target ABI)**  
  Calling convention specifications (registers, args, returns, callee-saved, sysregs). Used by the SSA Engine for accurate parameter and stack base resolution.

* **`ir/` (SSA Mid-level IR)**  
  Typed SSA nodes (Values, Users, Instructions, Phis) with intrusive doubly-linked blocks, Def-Use chains, and utility engines like pattern matchers (`matcher`) and compile-time arithmetic evaluators (`eval`).

* **`ir/analysis/` (Lazy Analysis)**  
  Analysis passes (Dominance, Post-Dominance, CDG, LoopInfo, Alias Analysis) managed by the pipeline. Executed lazily on-demand and cached per scope.

* **`bridge/` (Pipeline Scopes & Structurization)**  
  Connects different representation domains for the Pass Manager. **Every pass operates on its own scope context defined here:**
  - `bridge/ir/`: Sets up execution scopes and layers for IR passes.
  - `bridge/ast/`: Handles control-flow structurization (Hammock/SESE analysis) and lowers IR nodes into AST nodes.

* **`pipeline/` (Pass Manager & Passes)**  
  Pure optimization passes running over IR and AST. Every single pass is modular and can be toggled on or off at will.

* **`ast/` (High-Level AST & Codegen)**  
  High-level C AST nodes, AST-level refinement passes (inlining, simplifiers, loop refiners), and Pretty-Printers (emitting strict C or clean Python 3.10+ pseudocode).