# Abstract Syntax Tree & Codegen (`copdec.ast`)

The AST represents structured high-level source constructs independent of compiler IR.

## AST Nodes

- **Expressions (`CExpr`)**: `CVarExpr`, `CLiteralExpr`, `CBinaryExpr`, `CUnaryExpr`, `CCastExpr`, `CCallExpr`, `CTernaryExpr`, `CMemberExpr`, `CIndexExpr`.
- **Statements (`CStmt`)**: `CBlock`, `CAssignStmt`, `CExprStmt`, `CIfStmt`, `CWhileStmt`, `CDoWhileStmt`, `CForStmt`, `CSwitchStmt`, `CReturnStmt`, `CGotoStmt`.
- **Top-Level**: `CFunction`, `CStructDef`.

---

## AST Transformation Passes (`copdec.ast.passes`)

1. **`ExpressionInlinerPass`**: Inlines single-use temporary variables and cleans up intermediate SSA assignments.
2. **`ExpressionSimplifierPass`**: Simplifies associative math expressions and eliminates redundant binary operations.
3. **`CastNormalizerPass`**: Strips redundant type casts (e.g. `(int64_t)((int64_t)x)` or casting literals).
4. **`LoopRefinerPass`**: Converts `while(true)` loops containing break/continue guards into structured `while(cond)` or `do-while` loops.
5. **`ConditionNormalizerPass`**: Inverts negative if-branches and collapses comparisons like `(x - y == 0)` into `(x == y)`.
6. **`DeadCodePrunerPass`**: Removes unused labels, unreachable code after returns, and empty branches.

---

## Code Printers (`copdec.ast.codegen`)

- **`CPrettyPrinter`**: Emits syntactically valid C source code with customizable indentation and correct pointer dereference syntax.
- **`PythonPrettyPrinter`**: Generates idiomatic Python 3.10+ pseudocode (using `match/case`, eliminating type casts, and emitting memory access helpers).