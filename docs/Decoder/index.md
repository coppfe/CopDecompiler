# Decoder Layer (`copdec.decoder`)

The decoder layer translates raw binary byte buffers into architecture-agnostic instruction instances.

## Architecture

- **`BaseDecoder` (`copdec.decoder.base`)**: Abstract base class specifying the `decode_stream(raw_bytes, base_pc)` interface.
- **`ARM64Decoder` (`copdec.decoder.arm64`)**: Capstone-based implementation tailored for AArch64.

## Key Abstractions (`copdec.insn`)

All instructions are converted to `Insn` instances holding structured operand primitives:

| Class | Description |
| :--- | :--- |
| `Insn` | Machine instruction representation (`address`, `mnemonic`, `operands`, `cond`, `raw`). |
| `RegOp` | Register operand with size, canonical physical mapping (e.g. `w0` $\to$ `x0`), barrel shift, and extension info. |
| `ImmOp` | Immediate scalar values normalized to 64-bit integer masks. |
| `MemOp` | Universal memory operand supporting base, index, displacement, pre-index (`[Rn, #imm]!`), and post-index (`[Rn], #imm`). |

```python
from copdec.decoder.arm64 import ARM64Decoder

decoder = ARM64Decoder()
insns = decoder.decode_stream(b"\x20\x00\x80\xd2\xc0\x03\x5f\xd6", base_pc=0x1000)
# Yields:
# <0x1000: mov x0, #1>
# <0x1004: ret x30>
```
---