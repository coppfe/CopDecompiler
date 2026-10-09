from ..const import Arch

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..decoder.base import BaseDecoder
    from ..lir.lifter.base import BaseLifter

    from .abi.base import TargetABI


def get_target_decoder(arch: 'Arch') -> 'BaseDecoder':
    if arch == Arch.ARM64:
        from ..decoder.arm64 import ARM64Decoder
        return ARM64Decoder()
    raise NotImplementedError(f"No decoder implemented for architecture: {arch.name}")

def get_target_abi(arch: 'Arch') -> 'TargetABI':
    """Instantiates the canonical calling convention ABI model for target architecture."""
    if arch == Arch.ARM64:
        from .abi.arm64 import ARM64ABI
        return ARM64ABI()
    raise NotImplementedError(f"No TargetABI implemented for architecture: {arch.name}")


def get_target_lifter(arch: 'Arch') -> type['BaseLifter']:
    """Returns the concrete Lifter class for the target architecture."""
    if arch == Arch.ARM64:
        from ..lir.lifter.arm64 import ARM64LIRLifter
        return ARM64LIRLifter
    raise NotImplementedError(f"No Lifter implemented for architecture: {arch.name}")