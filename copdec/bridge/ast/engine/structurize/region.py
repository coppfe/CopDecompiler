from typing import List, Optional
from .....ir.core.cfg import BasicBlock
from .....ir.core.value import Value


class ControlRegion:
    __slots__ = ()


class BlockRegion(ControlRegion):
    __slots__ = ('bb',)

    def __init__(self, bb: BasicBlock):
        self.bb: BasicBlock = bb


class SeqRegion(ControlRegion):
    __slots__ = ('regions',)

    def __init__(self, regions: Optional[List[ControlRegion]] = None):
        self.regions: List[ControlRegion] = regions if regions is not None else []

    def append(self, r: ControlRegion) -> None:
        self.regions.append(r)


class IfRegion(ControlRegion):
    """cond, then_body, else_body."""
    __slots__ = ('cond', 'then_body', 'else_body', 'is_inverted')

    def __init__(
        self,
        cond: Value,
        then_body: SeqRegion,
        else_body: Optional[SeqRegion] = None,
        is_inverted: bool = False
    ):
        self.cond: Value = cond
        self.then_body: SeqRegion = then_body
        self.else_body: Optional[SeqRegion] = else_body
        self.is_inverted: bool = is_inverted



class LoopRegion(ControlRegion):
    """(while / do-while)."""
    __slots__ = ('cond', 'body', 'is_do_while', 'header_bb', 'is_inverted')

    def __init__(
        self,
        cond: Optional[Value],
        body: SeqRegion,
        is_do_while: bool = False,
        header_bb: Optional[BasicBlock] = None,
        is_inverted: bool = False
    ):
        self.cond: Optional[Value] = cond
        self.body: SeqRegion = body
        self.is_do_while: bool = is_do_while
        self.header_bb: Optional[BasicBlock] = header_bb
        self.is_inverted: bool = is_inverted


class BreakRegion(ControlRegion):
    __slots__ = ()


class ContinueRegion(ControlRegion):
    __slots__ = ()


class GotoRegion(ControlRegion):
    __slots__ = ('target_name',)

    def __init__(self, target_name: str):
        self.target_name: str = target_name

class CaseRegion(ControlRegion):
    __slots__ = ('val', 'body', 'is_default')

    def __init__(self, val: Optional[Value], body: SeqRegion, is_default: bool = False):
        self.val: Optional[Value] = val
        self.body: SeqRegion = body
        self.is_default: bool = is_default


class SwitchRegion(ControlRegion):
    __slots__ = ('cond', 'cases', 'default_case')

    def __init__(
        self,
        cond: Value,
        cases: List[CaseRegion],
        default_case: Optional[CaseRegion] = None
    ):
        self.cond: Value = cond
        self.cases: List[CaseRegion] = cases
        self.default_case: Optional[CaseRegion] = default_case