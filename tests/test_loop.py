from copdec.decompiler import Decompiler
from copdec.ast.codegen.python_printer import PythonPrettyPrinter
from copdec.const import Arch

decomp = Decompiler(arch=Arch.ARM64)

code_loop = bytes.fromhex("01008052 3f00006b 6a000054 21080011 fdffff17 e003012a c0035fd6")

print("\nLOOP")
out = decomp.decompile_bytes(code_loop, base_pc=0x2000, func_name="test_loop")
print(out)

decomp.printer = PythonPrettyPrinter()
out2 = decomp.decompile_bytes(code_loop, base_pc=0x2000, func_name="test_loop")
print(out2)