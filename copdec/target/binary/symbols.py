from enum import IntEnum, auto
from dataclasses import dataclass
from typing import Dict, Optional, List, Tuple
from bisect import bisect_right, bisect_left


class SymbolType(IntEnum):
    """Discriminator for symbol classifications."""
    FUNCTION = auto()
    IMPORT   = auto()
    OBJECT   = auto()
    LABEL    = auto()


@dataclass(frozen=True, slots=True)
class Symbol:
    """Represents a symbolic identifier at a specific virtual address."""
    addr: int
    name: str
    sym_type: SymbolType = SymbolType.FUNCTION
    size: int = 0
    num_args: Optional[int] = None

    @property
    def is_function(self) -> bool:
        return self.sym_type in (SymbolType.FUNCTION, SymbolType.IMPORT)

    @property
    def is_import(self) -> bool:
        return self.sym_type == SymbolType.IMPORT

    def __repr__(self) -> str:
        return f"<Symbol @{hex(self.addr)} '{self.name}' type={self.sym_type.name} args={self.num_args}>"


class SymbolTable:
    """
    High-performance sorted symbol repository with O(1) exact address lookup
    and O(log N) interval resolution. Architecture-agnostic.
    """
    __slots__ = ('_by_addr', '_sorted_addrs')

    def __init__(self):
        self._by_addr: Dict[int, Symbol] = {}
        self._sorted_addrs: List[int] = []

    def add_symbol(
        self,
        addr: int,
        name: str,
        sym_type: SymbolType = SymbolType.FUNCTION,
        size: int = 0,
        num_args: Optional[int] = None
    ) -> Symbol:
        """Registers a symbol at the given virtual address with explicit metadata."""
        sym = Symbol(
            addr=addr,
            name=name,
            sym_type=sym_type,
            size=size,
            num_args=num_args
        )
        if addr not in self._by_addr:
            idx = bisect_right(self._sorted_addrs, addr)
            self._sorted_addrs.insert(idx, addr)
        self._by_addr[addr] = sym
        return sym

    def get_symbol(self, addr: int) -> Optional[Symbol]:
        """Returns the exact symbol located at virtual address `addr`."""
        return self._by_addr.get(addr)

    def get_symbol_name(self, addr: int) -> Optional[str]:
        """Returns the name of the symbol at `addr`, or None."""
        sym = self.get_symbol(addr)
        return sym.name if sym is not None else None

    def get_symbol_by_name(self, name: str) -> Optional[Symbol]:
        for sym in self._by_addr.values():
            if sym.name == name:
                return sym
        return None

    def get_symbol_arity(self, addr: int) -> Optional[int]:
        """Returns the user-defined argument count for symbol at `addr`, or None."""
        sym = self.get_symbol(addr)
        return sym.num_args if sym is not None else None
    
    def get_symbol_arity_by_name(self, name: str) -> Optional[int]:
           sym = self.get_symbol_by_name(name)
           return sym.num_args if sym is not None else None
   
    def has_symbol(self, addr: int) -> bool:
        return addr in self._by_addr

    def get_symbol_at_or_before(self, addr: int) -> Optional[Tuple[Symbol, int]]:
        if not self._sorted_addrs or addr < self._sorted_addrs[0]:
            return None

        idx = bisect_right(self._sorted_addrs, addr) - 1
        if idx >= 0:
            sym_addr = self._sorted_addrs[idx]
            sym = self._by_addr[sym_addr]
            offset = addr - sym_addr
            if sym.size > 0 and offset < sym.size:
                return sym, offset
            if sym.size == 0:
                return sym, offset
        return None

    def get_symbols_in_range(self, start_addr: int, end_addr: int) -> List[Symbol]:
        if start_addr >= end_addr or not self._sorted_addrs:
            return []

        start_idx = bisect_left(self._sorted_addrs, start_addr)
        end_idx = bisect_left(self._sorted_addrs, end_addr)
        return [self._by_addr[self._sorted_addrs[i]] for i in range(start_idx, end_idx)]