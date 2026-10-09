

import struct
from typing import List, Optional, Dict, Tuple, TYPE_CHECKING
from ..types.base import Type, TypeKind
from ..types.integer import IntegerType, Int1
from ..types.composite import FloatType, PointerType

if TYPE_CHECKING:
    from .cfg import BasicBlock, Function


class Value:
    """
    Fundamental base class for all compute entities in the IR graph.
    Every Value produces a typed result and maintains an intrusive list of its readers (Uses).
    Supports transparent canonical forwarding resolution.
    """
    __slots__ = ('_type', '_id', '_name', '_uses', '_forwarded_to')
    _global_id_counter: int = 0

    def __init__(self, val_type: Type, name: str = ""):
        assert isinstance(val_type, Type), f"Expected Type instance, got: {type(val_type)}"
        Value._global_id_counter += 1
        self._id: int = Value._global_id_counter
        self._type: Type = val_type
        self._name: str = name if name else f"v{self._id}"
        self._uses: List['Use'] = []
        self._forwarded_to: Optional['Value'] = None

    def resolve(self) -> 'Value':
        if isinstance(self, Constant):
            return self
        if self._forwarded_to is None:
            return self

        curr = self._forwarded_to
        while not isinstance(curr, Constant) and curr._forwarded_to is not None:
            curr = curr._forwarded_to

        self._forwarded_to = curr
        return curr

    @property
    def id(self) -> int:
        return self._id

    @property
    def type(self) -> Type:
        return self._type

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, new_name: str) -> None:
        self._name = new_name

    @property
    def uses(self) -> List['Use']:
        return self._uses

    def has_users(self) -> bool:
        return len(self._uses) > 0

    def num_users(self) -> int:
        return len(self._uses)

    def add_use(self, use: 'Use') -> None:
        self._uses.append(use)

    def remove_use(self, use: 'Use') -> None:
        self._uses.remove(use)

    def replace_all_uses_with(self, new_val: 'Value') -> None:
        assert isinstance(new_val, Value), f"RAUW target must be a Value, got: {type(new_val)}"
        assert self is not new_val, "Cannot replace a Value with itself"

        resolved_target = new_val.resolve()
        self._forwarded_to = resolved_target

        for use in list(self._uses):
            use.set_value(resolved_target)

    def __repr__(self) -> str:
        return f"%{self._name}"


class Use:
    """
    Represents a directed data-flow graph edge connecting a consumer (User)
    to a data source (Value) at a specific operand position.
    """
    __slots__ = ('_user', '_value', '_operand_index')

    def __init__(self, user: 'User', value: Value, operand_index: int):
        self._user: 'User' = user
        self._value: Value = value
        self._operand_index: int = operand_index
        self._value.add_use(self)

    @property
    def user(self) -> 'User':
        return self._user

    @property
    def value(self) -> Value:
        return self._value

    @property
    def operand_index(self) -> int:
        return self._operand_index

    def set_value(self, new_val: Value) -> None:
        if self._value is new_val:
            return
        self._value.remove_use(self)
        self._value = new_val
        self._value.add_use(self)


class User(Value):
    """Base class for any Value that consumes other Values as operands."""
    __slots__ = ('_operands',)

    def __init__(self, val_type: Type, name: str = ""):
        super().__init__(val_type, name)
        self._operands: List[Use] = []

    @property
    def num_operands(self) -> int:
        return len(self._operands)

    def get_operand(self, index: int) -> Value:
        return self._operands[index].value

    def get_use(self, index: int) -> Use:
        return self._operands[index]

    def set_operand(self, index: int, val: Value) -> None:
        assert 0 <= index < len(self._operands), f"Operand index out of bounds: {index}"
        self._operands[index].set_value(val)

    def add_operand(self, val: Value) -> None:
        assert isinstance(val, Value), f"Operand must be an instance of Value, got: {type(val)}"
        idx = len(self._operands)
        use = Use(user=self, value=val, operand_index=idx)
        self._operands.append(use)

    def remove_operand(self, index: int) -> None:
        """Removes operand at index and cleans up the Def-Use edge."""
        assert 0 <= index < len(self._operands), f"Operand index out of bounds: {index}"
        use = self._operands[index]
        use.value.remove_use(use)
        del self._operands[index]
        for i, u in enumerate(self._operands):
            u._operand_index = i

    def replace_uses_of_with(self, from_val: Value, to_val: Value) -> None:
        """Replaces all operand occurrences of from_val with to_val."""
        for use in self._operands:
            if use.value is from_val:
                use.set_value(to_val)

    def drop_all_references(self) -> None:
        for use in self._operands:
            use.value.remove_use(use)
        self._operands.clear()


# =============================================================================
# Interned Constants (Flyweight Pattern)
# =============================================================================

class Constant(Value):
    """
    Base class for all immutable compile-time constants.
    Guarantees leaf-node semantics in the Def-Use graph.
    """
    __slots__ = ()

    def resolve(self) -> 'Value':
        return self


class ConstantInt(Constant):
    """
    Interned, immutable compile-time integer constant.
    Instances are unique per (type, truncated_value) tuple.
    """
    __slots__ = ('_raw_value',)
    _cache: Dict[Tuple[Type, int], 'ConstantInt'] = {}

    def __new__(cls, int_type: Type, value: int) -> 'ConstantInt':
        if not int_type.is_integer:
            raise TypeError(f"ConstantInt requires IntegerType, got: {int_type}")

        raw_val = int_type.truncate(value)
        key = (int_type, raw_val)
        cached = cls._cache.get(key)
        if cached is not None:
            return cached

        instance = super(ConstantInt, cls).__new__(cls)
        Value._global_id_counter += 1
        instance._id = Value._global_id_counter
        instance._type = int_type
        instance._name = ""
        instance._uses = []
        instance._forwarded_to = None
        instance._raw_value = raw_val

        cls._cache[key] = instance
        return instance

    def __init__(self, int_type: Type, value: int) -> None:
        pass

    @classmethod
    def get(cls, int_type: Type, value: int) -> 'ConstantInt':
        return cls(int_type, value)

    @classmethod
    def get_true(cls) -> 'ConstantInt':
        return cls(Int1, 1)

    @classmethod
    def get_false(cls) -> 'ConstantInt':
        return cls(Int1, 0)

    @classmethod
    def get_all_ones(cls, int_type: Type) -> 'ConstantInt':
        assert int_type.is_integer, f"Expected IntegerType, got: {int_type}"
        return cls(int_type, int_type.mask)  # type: ignore

    @property
    def value(self) -> int:
        return self._raw_value

    @property
    def signed_value(self) -> int:
        if self.type.bit_width == 1:
            return self._raw_value
        return self.type.sign_extend(self._raw_value)  # type: ignore

    def __repr__(self) -> str:
        return f"ConstantInt<{self._type}>({self._raw_value})"

    def __eq__(self, other: object) -> bool:
        if self is other:
            return True
        return (isinstance(other, ConstantInt) and
                self.type is other.type and
                self._raw_value == other._raw_value)

    def __hash__(self) -> int:
        return hash((self.type, self._raw_value))


class ConstantFP(Constant):
    """
    Interned, immutable compile-time IEEE-754 floating point constant.
    """
    __slots__ = ('_float_value',)
    _cache: Dict[Tuple[Type, bytes], 'ConstantFP'] = {}

    def __new__(cls, fp_type: Type, value: float) -> 'ConstantFP':
        if not fp_type.is_float:
            raise TypeError(f"ConstantFP requires FloatType, got: {fp_type}")

        # Canonical IEEE-754 binary representation for exact bitwise hashing (handles -0.0, NaNs)
        fmt = "d" if fp_type.bit_width == 64 else ("f" if fp_type.bit_width == 32 else "e")
        raw_bytes = struct.pack(f"<{fmt}", value)

        key = (fp_type, raw_bytes)
        cached = cls._cache.get(key)
        if cached is not None:
            return cached

        instance = super(ConstantFP, cls).__new__(cls)
        Value._global_id_counter += 1
        instance._id = Value._global_id_counter
        instance._type = fp_type
        instance._name = ""
        instance._uses = []
        instance._forwarded_to = None
        instance._float_value = float(value)

        cls._cache[key] = instance
        return instance

    def __init__(self, fp_type: Type, value: float) -> None:
        pass

    @classmethod
    def get(cls, fp_type: Type, value: float) -> 'ConstantFP':
        return cls(fp_type, value)

    @property
    def value(self) -> float:
        return self._float_value

    def __repr__(self) -> str:
        return f"{self._type} {self._float_value}"

    def __eq__(self, other: object) -> bool:
        if self is other:
            return True
        return (isinstance(other, ConstantFP) and
                self.type is other.type and
                self._float_value == other._float_value)

    def __hash__(self) -> int:
        return hash((self.type, self._float_value))


class ConstantPointerNull(Constant):
    """
    Represents an immutable null pointer literal for any PointerType.
    Equivalent to LLVM ConstantPointerNull::get(PtrTy).
    """
    __slots__ = ()
    _cache: Dict[PointerType, 'ConstantPointerNull'] = {}

    def __new__(cls, ptr_type: Type) -> 'ConstantPointerNull':
        if not ptr_type.is_pointer:
            raise TypeError(f"ConstantPointerNull requires PointerType, got: {ptr_type}")

        cached = cls._cache.get(ptr_type)  # type: ignore
        if cached is not None:
            return cached

        instance = super(ConstantPointerNull, cls).__new__(cls)
        Value._global_id_counter += 1
        instance._id = Value._global_id_counter
        instance._type = ptr_type
        instance._name = ""
        instance._uses = []
        instance._forwarded_to = None

        cls._cache[ptr_type] = instance  # type: ignore
        return instance

    def __init__(self, ptr_type: Type) -> None:
        pass

    @classmethod
    def get(cls, ptr_type: Type) -> 'ConstantPointerNull':
        return cls(ptr_type)

    def __repr__(self) -> str:
        return f"{self._type} null"

    def __eq__(self, other: object) -> bool:
        if self is other:
            return True
        return isinstance(other, ConstantPointerNull) and self.type is other.type

    def __hash__(self) -> int:
        return hash((self.type, 0))


class UndefValue(Constant):
    """
    Represents an undefined / uninitialized value of a given Type in SSA form.
    Equivalent to LLVM UndefValue::get(Ty).
    """
    __slots__ = ()
    _cache: Dict[Type, 'UndefValue'] = {}

    def __new__(cls, val_type: Type) -> 'UndefValue':
        cached = cls._cache.get(val_type)
        if cached is not None:
            return cached

        instance = super(UndefValue, cls).__new__(cls)
        Value._global_id_counter += 1
        instance._id = Value._global_id_counter
        instance._type = val_type
        instance._name = ""
        instance._uses = []
        instance._forwarded_to = None

        cls._cache[val_type] = instance
        return instance

    def __init__(self, val_type: Type) -> None:
        pass

    @classmethod
    def get(cls, val_type: Type) -> 'UndefValue':
        return cls(val_type)

    def __repr__(self) -> str:
        return f"{self._type} undef"

    def __eq__(self, other: object) -> bool:
        if self is other:
            return True
        return isinstance(other, UndefValue) and self.type is other.type

    def __hash__(self) -> int:
        return hash(self.type)


class ConstantSymbol(Constant):
    """
    Represents an interned named symbolic reference (e.g. imported function name, global object symbol).
    """
    __slots__ = ('_address',)
    _cache: Dict[Tuple[Type, str, int], 'ConstantSymbol'] = {}

    def __new__(cls, sym_type: Type, name: str, address: int = 0) -> 'ConstantSymbol':
        key = (sym_type, name, address)
        cached = cls._cache.get(key)
        if cached is not None:
            return cached

        instance = super(ConstantSymbol, cls).__new__(cls)
        Value._global_id_counter += 1
        instance._id = Value._global_id_counter
        instance._type = sym_type
        instance._name = name
        instance._uses = []
        instance._address = address
        instance._forwarded_to = None

        cls._cache[key] = instance
        return instance

    def __init__(self, sym_type: Type, name: str, address: int = 0) -> None:
        pass

    @classmethod
    def get(cls, sym_type: Type, name: str, address: int = 0) -> 'ConstantSymbol':
        return cls(sym_type, name, address)

    @property
    def address(self) -> int:
        return self._address

    def __repr__(self) -> str:
        return f"@{self._name}"

    def __eq__(self, other: object) -> bool:
        if self is other:
            return True
        return (isinstance(other, ConstantSymbol) and
                self.type is other.type and
                self._name == other._name and
                self._address == other._address)

    def __hash__(self) -> int:
        return hash((self.type, self._name, self._address))

class ExternalValue(Value):
    """
    Represents an upward-exposed architectural register value entering the function.
    Acts as a first-class SSA Value with variable identity (unlike constants).
    """
    __slots__ = ()

    def __repr__(self) -> str:
        return f"%{self.name}"

class Argument(Value):
    """Represents a formal input parameter of a Function."""
    __slots__ = ('_parent', '_arg_index')

    def __init__(self, arg_type: Type, name: str = "", arg_index: int = 0):
        super().__init__(arg_type, name)
        self._parent: Optional['Function'] = None
        self._arg_index: int = arg_index

    @property
    def parent(self) -> Optional['Function']:
        return self._parent

    @property
    def arg_index(self) -> int:
        return self._arg_index

    def _set_parent(self, func: 'Function') -> None:
        self._parent = func