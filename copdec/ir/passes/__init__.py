from .cfg_simplify import CFGSimplifyPass
from .dce import ADCEPass
from .gvn import GVNPass
from .instcombine import InstCombinePass
from .abi_cleanup import CallingConventionCleanupPass
from .stack_frame import StackFramePromotionPass

__all__ = [
    "CFGSimplifyPass",
    "ADCEPass",
    "GVNPass",
    "InstCombinePass",
    "CallingConventionCleanupPass",
    "StackFramePromotionPass",
]