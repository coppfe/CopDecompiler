from enum import IntEnum, auto
from dataclasses import dataclass
from typing import Optional, Tuple
from ..core.value import Value, ConstantInt, ConstantSymbol
from ..core.cfg import Function
from ..instructions.memory import AllocaInst
from ..instructions.cast import CastInst
from ..instructions.alu import BinaryOperator
from ..opcodes import IROpcode
from ...target.binary.memory import BinaryMemoryView
from ...pipeline.scope import BaseScope


class AliasResult(IntEnum):
    NO_ALIAS   = 0
    MAY_ALIAS  = 1
    MUST_ALIAS = 2


class LocationKind(IntEnum):
    ALLOCA = auto()
    RODATA = auto()
    GLOBAL = auto()
    HEAP   = auto()
    UNKNOWN= auto()


@dataclass(frozen=True, slots=True)
class MemoryLocation:
    base_object: Value
    offset: int = 0
    size: Optional[int] = None
    kind: LocationKind = LocationKind.UNKNOWN


class BasicAliasAnalysis:
    """Type-based and allocation-based Alias Analysis Engine."""
    __slots__ = ('_func', '_memory')

    def __init__(self, scope: BaseScope):
        self._func: Function = scope.artifact
        self._memory: Optional[BinaryMemoryView] = scope.memory

    def get_underlying_object(self, ptr: Value) -> Tuple[Value, int]:
        curr = ptr
        accum_offset = 0

        while True:
            if isinstance(curr, CastInst):
                curr = curr.src
                continue

            if isinstance(curr, BinaryOperator):
                if curr.opcode == IROpcode.ADD:
                    if isinstance(curr.rhs, ConstantInt):
                        accum_offset += curr.rhs.value
                        curr = curr.lhs
                        continue
                    elif isinstance(curr.lhs, ConstantInt):
                        accum_offset += curr.lhs.value
                        curr = curr.rhs
                        continue
                elif curr.opcode == IROpcode.SUB:
                    if isinstance(curr.rhs, ConstantInt):
                        accum_offset -= curr.rhs.value
                        curr = curr.lhs
                        continue

            break

        return curr, accum_offset

    def get_location(self, ptr: Value, size: Optional[int] = None) -> MemoryLocation:
        base_obj, offset = self.get_underlying_object(ptr)
        kind = LocationKind.UNKNOWN

        if isinstance(base_obj, AllocaInst):
            kind = LocationKind.ALLOCA
        elif isinstance(base_obj, ConstantSymbol):
            kind = LocationKind.GLOBAL
        elif isinstance(base_obj, ConstantInt):
            if self._memory is not None and self._memory.is_readonly(base_obj.value):
                kind = LocationKind.RODATA
            else:
                kind = LocationKind.GLOBAL

        return MemoryLocation(base_object=base_obj, offset=offset, size=size, kind=kind)

    def alias(self, locA: MemoryLocation, locB: MemoryLocation) -> AliasResult:
        if locA.kind == LocationKind.ALLOCA and locB.kind == LocationKind.ALLOCA:
            if locA.base_object is not locB.base_object:
                return AliasResult.NO_ALIAS

        if (locA.kind == LocationKind.ALLOCA and locB.kind == LocationKind.RODATA) or \
           (locA.kind == LocationKind.RODATA and locB.kind == LocationKind.ALLOCA):
            return AliasResult.NO_ALIAS

        if locA.kind == LocationKind.RODATA and locB.kind == LocationKind.RODATA:
            if locA.base_object == locB.base_object and locA.offset == locB.offset:
                return AliasResult.MUST_ALIAS
            return AliasResult.NO_ALIAS

        if locA.base_object == locB.base_object:
            if locA.offset == locB.offset:
                return AliasResult.MUST_ALIAS

            if locA.size is not None and locB.size is not None:
                if locA.offset + locA.size <= locB.offset or locB.offset + locB.size <= locA.offset:
                    return AliasResult.NO_ALIAS

            return AliasResult.MAY_ALIAS

        return AliasResult.MAY_ALIAS

    def alias_pointers(self, ptrA: Value, ptrB: Value) -> AliasResult:
        locA = self.get_location(ptrA)
        locB = self.get_location(ptrB)
        return self.alias(locA, locB)