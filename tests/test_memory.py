# test.py

from copdec.const import Arch
from copdec.target.binary.memory import SectionMappedMemoryView, SegmentFlags
from copdec.target.binary.symbols import SymbolTable, SymbolType
from copdec.pipeline.manager import PassManager
from copdec.decompiler import Decompiler


def test_memory_string_lifting() -> None:
    RODATA_ADDR: int = 0x40160000
    CODE_ADDR: int = 0x40156000
    PUTS_ADDR: int = 0x40156020

    # 1. Initialize Symbol Table and explicitly define symbol arity (num_args=1)
    sym_table = SymbolTable()
    sym_table.add_symbol(
        addr=PUTS_ADDR,
        name="puts",
        sym_type=SymbolType.IMPORT,
        num_args=1
    )

    # 2. Setup Memory with .rodata section
    mem = SectionMappedMemoryView(symbols=sym_table)
    mem.map_section(
        base_addr=RODATA_ADDR,
        data=b"Hello, World!\x00",
        flags=SegmentFlags.RO,
        name=".rodata"
    )

    # 0x40156000: push {r7, lr}          (2 bytes)
    # 0x40156002: movw r1, #0x0000       (4 bytes)
    # 0x40156006: movt r1, #0x4016       (4 bytes)
    # 0x4015600a: str  r1, [r0]          (2 bytes)
    # 0x4015600c: mov  r0, r1            (2 bytes)
    # 0x4015600e: bl   0x40156020        (4 bytes)
    # 0x40156012: pop  {r7, pc}          (2 bytes)
    raw_code = bytes([
        0x80, 0xb5,              # push {r7, lr}
        0x40, 0xf2, 0x00, 0x01,  # movw r1, #0x0000
        0xc4, 0xf2, 0x16, 0x01,  # movt r1, #0x4016
        0x01, 0x60,              # str  r1, [r0]
        0x08, 0x46,              # mov  r0, r1
        0x00, 0xf0, 0x07, 0xf8,  # bl   puts (0x40156020)
        0x80, 0xbd,              # pop  {r7, pc}
    ])

    decompiler = Decompiler(
        arch=Arch.ARM32_THUMB,
        pass_manager=PassManager.standard()
    )

    print("=" * 80)
    print("[*] Decompiling with active MemoryView & SymbolTable...")
    print("=" * 80)

    c_code = decompiler.decompile_bytes(
        raw_bytes=raw_code,
        base_pc=CODE_ADDR,
        func_name="write_and_print_string",
        memory=mem
    )

    print(c_code)
    print("=" * 80)

    assert '"Hello, World!"' in c_code, "Failed: String literal was not lifted from .rodata"
    assert "puts(\"Hello, World!\")" in c_code, "Failed: Explicit arity puts call was not rendered correctly"

    print("[+] Test PASSED: Pure abstract symbol resolution and memory access verified!")


if __name__ == "__main__":
    test_memory_string_lifting()