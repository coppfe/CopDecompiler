import struct
from abc import ABC, abstractmethod
from bisect import bisect_right
from enum import IntFlag
from typing import Optional, List
from .symbols import SymbolTable, Symbol


class SegmentFlags(IntFlag):
    """Memory protection and access permission flags for binary segments."""
    NONE  = 0
    READ  = 1 << 0
    WRITE = 1 << 1
    EXEC  = 1 << 2

    # Aliases
    R   = READ
    W   = WRITE
    X   = EXEC
    RW  = READ | WRITE
    RX  = READ | EXEC
    RWX = READ | WRITE | EXEC
    RO  = READ


class Segment:
    """Represents a discrete mapped memory region (.text, .rodata, .data, .bss)."""
    __slots__ = ('start', 'end', 'data', 'flags', 'name')

    def __init__(
        self,
        start: int,
        end: int,
        data: bytes,
        flags: SegmentFlags = SegmentFlags.RX,
        name: str = ""
    ):
        assert start < end, f"Invalid segment bounds: [{hex(start)}, {hex(end)})"
        assert len(data) == (end - start), f"Data size ({len(data)}) must match segment size ({end - start})"
        self.start: int = start
        self.end: int = end
        self.data: bytes = data
        self.flags: SegmentFlags = flags
        self.name: str = name

    @property
    def size(self) -> int:
        return self.end - self.start

    @property
    def is_readable(self) -> bool:
        return bool(self.flags & SegmentFlags.READ)

    @property
    def is_readonly(self) -> bool:
        return bool(self.flags & SegmentFlags.READ) and not bool(self.flags & SegmentFlags.WRITE)

    @property
    def is_executable(self) -> bool:
        return bool(self.flags & SegmentFlags.EXEC)

    @property
    def is_writable(self) -> bool:
        return bool(self.flags & SegmentFlags.WRITE)

    def contains(self, addr: int) -> bool:
        return self.start <= addr < self.end

    def contains_range(self, addr: int, size: int) -> bool:
        return self.start <= addr and (addr + size) <= self.end

    def __repr__(self) -> str:
        flags_str = "".join([
            "R" if self.flags & SegmentFlags.READ else "-",
            "W" if self.flags & SegmentFlags.WRITE else "-",
            "X" if self.flags & SegmentFlags.EXEC else "-"
        ])
        name_str = f" '{self.name}'" if self.name else ""
        return f"<Segment{name_str} {hex(self.start)}..{hex(self.end)} [{flags_str}] size={self.size}>"


class BinaryMemoryView(ABC):
    """
    Abstract segmented memory interface providing virtual memory access,
    string lifting, typed integer/float readers, and symbol resolution.
    """

    @abstractmethod
    def read_bytes(self, addr: int, size: int) -> Optional[bytes]:
        pass

    @abstractmethod
    def is_readable(self, addr: int, size: int = 1) -> bool:
        pass

    @abstractmethod
    def is_readonly(self, addr: int, size: int = 1) -> bool:
        pass

    @abstractmethod
    def is_writable(self, addr: int, size: int = 1) -> bool:
        pass

    @abstractmethod
    def is_executable(self, addr: int, size: int = 1) -> bool:
        pass

    @abstractmethod
    def is_mapped(self, addr: int, size: int = 1) -> bool:
        pass

    @abstractmethod
    def get_segment(self, addr: int) -> Optional[Segment]:
        pass

    def get_symbol(self, addr: int) -> Optional[Symbol]:
        """Resolves Symbol for address `addr` if available."""
        return None

    def get_symbol_name(self, addr: int) -> Optional[str]:
        """Resolves symbol name for address `addr` if available."""
        sym = self.get_symbol(addr)
        return sym.name if sym is not None else None

    def get_symbol_arity(self, addr: int) -> Optional[int]:
        """Resolves symbol arity for address `addr` if available."""
        sym = self.get_symbol(addr)
        return sym.num_args if sym is not None else None

    def read_cstring(self, addr: int, max_len: int = 1024, encoding: str = 'utf-8') -> Optional[str]:
        seg = self.get_segment(addr)
        if seg is None or not seg.is_readable:
            return None

        offset_in_seg = addr - seg.start
        available_bytes = min(max_len, seg.size - offset_in_seg)
        if available_bytes <= 0:
            return None

        raw_slice = seg.data[offset_in_seg:offset_in_seg + available_bytes]
        null_idx = raw_slice.find(b'\x00')
        if null_idx == -1 or null_idx <= 0:
            return None

        string_bytes = raw_slice[:null_idx]
        try:
            decoded = string_bytes.decode(encoding)
            if all(c.isprintable() or c in '\n\r\t' for c in decoded):
                return decoded
            return None
        except UnicodeDecodeError:
            return None

    # =========================================================================
    # Typed Integer Readers
    # =========================================================================
    def read_u8(self, addr: int) -> Optional[int]:
        raw = self.read_bytes(addr, 1)
        return raw[0] if raw is not None else None

    def read_i8(self, addr: int) -> Optional[int]:
        raw = self.read_bytes(addr, 1)
        return struct.unpack("<b", raw)[0] if raw is not None else None

    def read_u16(self, addr: int, big_endian: bool = False) -> Optional[int]:
        raw = self.read_bytes(addr, 2)
        if raw is None: return None
        fmt = ">H" if big_endian else "<H"
        return struct.unpack(fmt, raw)[0]

    def read_i16(self, addr: int, big_endian: bool = False) -> Optional[int]:
        raw = self.read_bytes(addr, 2)
        if raw is None: return None
        fmt = ">h" if big_endian else "<h"
        return struct.unpack(fmt, raw)[0]

    def read_u32(self, addr: int, big_endian: bool = False) -> Optional[int]:
        raw = self.read_bytes(addr, 4)
        if raw is None: return None
        fmt = ">I" if big_endian else "<I"
        return struct.unpack(fmt, raw)[0]

    def read_i32(self, addr: int, big_endian: bool = False) -> Optional[int]:
        raw = self.read_bytes(addr, 4)
        if raw is None: return None
        fmt = ">i" if big_endian else "<i"
        return struct.unpack(fmt, raw)[0]

    def read_u64(self, addr: int, big_endian: bool = False) -> Optional[int]:
        raw = self.read_bytes(addr, 8)
        if raw is None: return None
        fmt = ">Q" if big_endian else "<Q"
        return struct.unpack(fmt, raw)[0]

    def read_i64(self, addr: int, big_endian: bool = False) -> Optional[int]:
        raw = self.read_bytes(addr, 8)
        if raw is None: return None
        fmt = ">q" if big_endian else "<q"
        return struct.unpack(fmt, raw)[0]

    def read_pointer(self, addr: int, bit_width: int = 64, big_endian: bool = False) -> Optional[int]:
        """Reads an architectural pointer (32-bit or 64-bit address)."""
        if bit_width == 64:
            return self.read_u64(addr, big_endian=big_endian)
        return self.read_u32(addr, big_endian=big_endian)

    # =========================================================================
    # Typed Floating-Point Readers
    # =========================================================================
    def read_f16(self, addr: int, big_endian: bool = False) -> Optional[float]:
        raw = self.read_bytes(addr, 2)
        if raw is None: return None
        fmt = ">e" if big_endian else "<e"
        return struct.unpack(fmt, raw)[0]

    def read_f32(self, addr: int, big_endian: bool = False) -> Optional[float]:
        raw = self.read_bytes(addr, 4)
        if raw is None: return None
        fmt = ">f" if big_endian else "<f"
        return struct.unpack(fmt, raw)[0]

    def read_f64(self, addr: int, big_endian: bool = False) -> Optional[float]:
        raw = self.read_bytes(addr, 8)
        if raw is None: return None
        fmt = ">d" if big_endian else "<d"
        return struct.unpack(fmt, raw)[0]


class SectionMappedMemoryView(BinaryMemoryView):
    """
    High-performance segmented memory view using binary search (O(log N))
    over sorted virtual segments with integrated symbol table.
    """
    __slots__ = ('_segments', '_starts', '_symbols')

    def __init__(self, symbols: Optional[SymbolTable] = None):
        self._segments: List[Segment] = []
        self._starts: List[int] = []
        self._symbols: SymbolTable = symbols if symbols is not None else SymbolTable()

    @property
    def segments(self) -> List[Segment]:
        return self._segments

    @property
    def symbols(self) -> SymbolTable:
        return self._symbols

    @symbols.setter
    def symbols(self, sym_table: SymbolTable) -> None:
        self._symbols = sym_table

    def get_symbol(self, addr: int) -> Optional[Symbol]:
        return self._symbols.get_symbol(addr)

    def map_section(
        self,
        base_addr: int,
        data: bytes | bytearray,
        flags: SegmentFlags = SegmentFlags.RX,
        name: str = ""
    ) -> Segment:
        raw_data = bytes(data)
        if len(raw_data) == 0:
            raise ValueError(f"Cannot map empty memory segment at {hex(base_addr)}")

        start = base_addr
        end = base_addr + len(raw_data)

        idx = bisect_right(self._starts, start)
        if idx > 0:
            prev_seg = self._segments[idx - 1]
            if prev_seg.end > start:
                raise ValueError(
                    f"Segment collision: new segment [{hex(start)}, {hex(end)}) "
                    f"overlaps with existing segment [{hex(prev_seg.start)}, {hex(prev_seg.end)})"
                )
        if idx < len(self._segments):
            next_seg = self._segments[idx]
            if end > next_seg.start:
                raise ValueError(
                    f"Segment collision: new segment [{hex(start)}, {hex(end)}) "
                    f"overlaps with existing segment [{hex(next_seg.start)}, {hex(next_seg.end)})"
                )

        new_segment = Segment(start=start, end=end, data=raw_data, flags=flags, name=name)
        self._segments.insert(idx, new_segment)
        self._starts.insert(idx, start)
        return new_segment

    def _find_segment(self, addr: int) -> Optional[Segment]:
        if not self._starts or addr < self._starts[0]:
            return None
        idx = bisect_right(self._starts, addr) - 1
        if idx >= 0:
            seg = self._segments[idx]
            if seg.contains(addr):
                return seg
        return None

    def get_segment(self, addr: int) -> Optional[Segment]:
        return self._find_segment(addr)

    def get_symbol_name(self, addr: int) -> Optional[str]:
        return self._symbols.get_symbol_name(addr)

    def read_bytes(self, addr: int, size: int) -> Optional[bytes]:
        if size <= 0:
            return b""
        seg = self._find_segment(addr)
        if seg is not None and seg.contains_range(addr, size) and seg.is_readable:
            offset = addr - seg.start
            return seg.data[offset:offset + size]
        return None

    def is_readable(self, addr: int, size: int = 1) -> bool:
        if size <= 0:
            return False
        seg = self._find_segment(addr)
        return seg is not None and seg.contains_range(addr, size) and seg.is_readable

    def is_readonly(self, addr: int, size: int = 1) -> bool:
        if size <= 0:
            return False
        seg = self._find_segment(addr)
        return seg is not None and seg.contains_range(addr, size) and seg.is_readonly

    def is_writable(self, addr: int, size: int = 1) -> bool:
        if size <= 0:
            return False
        seg = self._find_segment(addr)
        return seg is not None and seg.contains_range(addr, size) and seg.is_writable

    def is_executable(self, addr: int, size: int = 1) -> bool:
        if size <= 0:
            return False
        seg = self._find_segment(addr)
        return seg is not None and seg.contains_range(addr, size) and seg.is_executable

    def is_mapped(self, addr: int, size: int = 1) -> bool:
        if size <= 0:
            return False
        seg = self._find_segment(addr)
        return seg is not None and seg.contains_range(addr, size)