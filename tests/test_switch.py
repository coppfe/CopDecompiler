from copdec.ir.core.cfg import Function, BasicBlock
from copdec.ir.core.value import ConstantInt
from copdec.ir.types.integer import Int32
from copdec.ir.instructions.control import SwitchInst, ReturnInst
from copdec.decompiler import Decompiler
from copdec.const import Arch
from copdec.ast.codegen.python_printer import PythonPrettyPrinter

func = Function("test_canonical_switch", Int32)
a0 = func.add_argument(Int32, "a0")

bb_entry = BasicBlock("entry")
bb_case1 = BasicBlock("case_1")
bb_case2 = BasicBlock("case_2")
bb_default = BasicBlock("default_bb")

func.append_block(bb_entry)
func.append_block(bb_case1)
func.append_block(bb_case2)
func.append_block(bb_default)

bb_entry.add_successor(bb_case1)
bb_entry.add_successor(bb_case2)
bb_entry.add_successor(bb_default)
bb_case1.add_predecessor(bb_entry)
bb_case2.add_predecessor(bb_entry)
bb_default.add_predecessor(bb_entry)

cases = [
    (ConstantInt.get(Int32, 1), bb_case1),
    (ConstantInt.get(Int32, 2), bb_case2),
]
switch_inst = SwitchInst(cond=a0, default_block=bb_default, cases=cases)
bb_entry.append_instruction(switch_inst)

bb_case1.append_instruction(ReturnInst(ConstantInt.get(Int32, 100)))
bb_case2.append_instruction(ReturnInst(ConstantInt.get(Int32, 200)))
bb_default.append_instruction(ReturnInst(ConstantInt.get(Int32, 999)))

decomp = Decompiler(arch=Arch.ARM64)
result_c = decomp.pass_manager.run(func)

print("C Switch")
print(decomp.printer.format_function(result_c))

decomp_py = Decompiler(arch=Arch.ARM64, printer=PythonPrettyPrinter(indent_spaces=4))
result_py = decomp_py.pass_manager.run(func)

print("\nPython Match")
print(decomp_py.printer.format_function(result_py))