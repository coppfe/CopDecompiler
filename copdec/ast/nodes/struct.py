from typing import List
from .base import CASTNode
from ..types import CStructField


class CStructDef(CASTNode):
    """
    Top-level or local C struct type definition:
      struct Name {
          type1 field1;
          type2 field2[N];
      };
    """
    __slots__ = ('name', 'fields')

    def __init__(self, name: str, fields: List[CStructField]):
        self.name: str = name
        self.fields: List[CStructField] = fields

    def __repr__(self) -> str:
        return f"<CStructDef {self.name} fields={len(self.fields)}>"