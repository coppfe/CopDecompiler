from abc import ABC, abstractmethod
from typing import List, Union
from ..insn import Insn


class BaseDecoder(ABC):
    """Abstract Target Instruction Stream Decoder."""
    __slots__ = ()

    @abstractmethod
    def decode_stream(self, raw_bytes: Union[bytes, bytearray], base_pc: int = 0) -> List[Insn]:
        """Decodes a contiguous byte stream into a list of generic Insn objects."""
        pass