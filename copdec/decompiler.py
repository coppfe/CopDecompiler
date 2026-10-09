from typing import List, Optional, Union

from .const import Arch
from .insn import Insn

from .decoder.base import BaseDecoder

from .pipeline.manager import PassManager
from .target.binary.memory import BinaryMemoryView

from .ir.ssa.builder import SSABuilder

from .ast.nodes import CFunction
from .ast.codegen.base_printer import BaseSourcePrinter
from .ast.codegen.c_printer import CPrettyPrinter

from .target.factory import get_target_abi, get_target_decoder, get_target_lifter

class Decompiler:
    """
    Top-Level Architecture-Aware Decompiler Facade.
    Orchestrates decoding, LIR lifting, SSA construction, modular pipeline execution,
    and target language source generation (C / Python).
    """
    __slots__ = ('_arch', '_decoder', '_lifter', '_abi', '_pass_manager', '_printer')

    def __init__(
        self,
        arch: Arch = Arch.ARM64,
        pass_manager: Optional['PassManager'] = None,
        printer: Optional['BaseSourcePrinter'] = None
    ):
        self._arch: 'Arch' = arch
        self._decoder: 'BaseDecoder' = get_target_decoder(arch)
        self._lifter = get_target_lifter(arch)
        self._abi = get_target_abi(arch)
        self._pass_manager: 'PassManager' = pass_manager if pass_manager is not None else PassManager.standard()
        self._printer: 'BaseSourcePrinter' = printer if printer is not None else CPrettyPrinter(indent_spaces=4)

    @property
    def pass_manager(self) -> 'PassManager':
        return self._pass_manager

    @pass_manager.setter
    def pass_manager(self, pm: 'PassManager') -> None:
        self._pass_manager = pm

    @property
    def printer(self) -> 'BaseSourcePrinter':
        return self._printer

    @printer.setter
    def printer(self, printer: 'BaseSourcePrinter') -> None:
        self._printer = printer

    @staticmethod
    def _func_name_gen(addr: int): return f"fun_{addr:02x}"

    def decompile_bytes(
        self,
        raw_bytes: Union[bytes, bytearray],
        base_pc: int = 0,
        func_name: Optional[str] = None,
        memory: Optional['BinaryMemoryView'] = None
    ) -> str:
        if func_name is None:
            func_name = self._func_name_gen(base_pc)
        insns = self._decoder.decode_stream(raw_bytes, base_pc=base_pc)
        return self.decompile_instructions(insns, func_name=func_name, memory=memory)

    def decompile_instructions(
        self,
        insns: List['Insn'],
        func_name: str,
        memory: Optional['BinaryMemoryView'] = None
    ) -> str:
        lir_func = self._lifter.lift(insns, func_name=func_name)

        ir_func = SSABuilder(lir_func, memory=memory, abi=self._abi).build()

        # IR Opts -> AST Bridge -> AST Opts
        result = self._pass_manager.run(ir_func, memory=memory)

        if isinstance(result, CFunction):
            return self._printer.format_function(result)

        return f"// Decompilation finished: No AST produced for @{func_name}"