"""
Java type system for the compiler.
"""

from dataclasses import dataclass
from typing import Optional, Sequence
from abc import ABC, abstractmethod


class JType(ABC):
    """Base class for all Java types."""

    @abstractmethod
    def descriptor(self) -> str:
        """Return the JVM type descriptor."""
        pass

    @abstractmethod
    def internal_name(self) -> str:
        """Return the JVM internal name (for class types)."""
        pass

    @property
    @abstractmethod
    def is_primitive(self) -> bool:
        pass

    @property
    @abstractmethod
    def is_reference(self) -> bool:
        pass

    @property
    def size(self) -> int:
        """Stack slots used by this type (1 or 2)."""
        return 1


@dataclass(frozen=True)
class PrimitiveJType(JType):
    """Primitive Java types."""
    name: str
    _descriptor: str
    _size: int = 1

    def descriptor(self) -> str:
        return self._descriptor

    def internal_name(self) -> str:
        return self.name

    @property
    def is_primitive(self) -> bool:
        return True

    @property
    def is_reference(self) -> bool:
        return False

    @property
    def size(self) -> int:
        return self._size


VOID = PrimitiveJType("void", "V")
BOOLEAN = PrimitiveJType("boolean", "Z")
BYTE = PrimitiveJType("byte", "B")
CHAR = PrimitiveJType("char", "C")
SHORT = PrimitiveJType("short", "S")
INT = PrimitiveJType("int", "I")
LONG = PrimitiveJType("long", "J", 2)
FLOAT = PrimitiveJType("float", "F")
DOUBLE = PrimitiveJType("double", "D", 2)

PRIMITIVE_TYPES = {
    "void": VOID,
    "boolean": BOOLEAN,
    "byte": BYTE,
    "char": CHAR,
    "short": SHORT,
    "int": INT,
    "long": LONG,
    "float": FLOAT,
    "double": DOUBLE,
}


@dataclass(frozen=True)
class ClassJType(JType):
    """Class or interface type."""
    name: str  # Fully qualified: java.lang.String or java/lang/String

    def descriptor(self) -> str:
        return f"L{self.internal_name()};"

    def internal_name(self) -> str:
        return self.name.replace(".", "/")

    @property
    def is_primitive(self) -> bool:
        return False

    @property
    def is_reference(self) -> bool:
        return True


OBJECT = ClassJType("java/lang/Object")
STRING = ClassJType("java/lang/String")
SYSTEM = ClassJType("java/lang/System")
PRINTSTREAM = ClassJType("java/io/PrintStream")


@dataclass(frozen=True)
class ArrayJType(JType):
    """Array type."""
    element_type: JType
    dimensions: int = 1

    def descriptor(self) -> str:
        return "[" * self.dimensions + self.element_type.descriptor()

    def internal_name(self) -> str:
        return self.descriptor()

    @property
    def is_primitive(self) -> bool:
        return False

    @property
    def is_reference(self) -> bool:
        return True


@dataclass(frozen=True)
class MethodType:
    """Method signature type."""
    return_type: JType
    parameter_types: tuple[JType, ...]

    def descriptor(self) -> str:
        params = "".join(p.descriptor() for p in self.parameter_types)
        return f"({params}){self.return_type.descriptor()}"


class NullType(JType):
    """The null type - assignable to any reference type."""

    def descriptor(self) -> str:
        return "Ljava/lang/Object;"

    def internal_name(self) -> str:
        return "java/lang/Object"

    @property
    def is_primitive(self) -> bool:
        return False

    @property
    def is_reference(self) -> bool:
        return True


NULL_TYPE = NullType()


def is_numeric(t: JType) -> bool:
    """Check if type is numeric (for arithmetic operations)."""
    return t in (BYTE, SHORT, CHAR, INT, LONG, FLOAT, DOUBLE)


def is_integral(t: JType) -> bool:
    """Check if type is integral."""
    return t in (BYTE, SHORT, CHAR, INT, LONG)


def is_assignable(target: JType, source: JType) -> bool:
    """Check if source type is assignable to target type."""
    if target == source:
        return True

    if isinstance(source, type) and source == NullType:
        return target.is_reference

    if source == NULL_TYPE:
        return target.is_reference

    # Primitive widening
    if target.is_primitive and source.is_primitive:
        widening = {
            BYTE: {INT, LONG, FLOAT, DOUBLE, SHORT},
            SHORT: {INT, LONG, FLOAT, DOUBLE},
            CHAR: {INT, LONG, FLOAT, DOUBLE},
            INT: {LONG, FLOAT, DOUBLE},
            LONG: {FLOAT, DOUBLE},
            FLOAT: {DOUBLE},
        }
        return target in widening.get(source, set())

    # Reference types - simplified for now
    if target.is_reference and source.is_reference:
        if target == OBJECT:
            return True

    return False


def binary_numeric_promotion(left: JType, right: JType) -> JType:
    """Apply binary numeric promotion rules."""
    if left == DOUBLE or right == DOUBLE:
        return DOUBLE
    if left == FLOAT or right == FLOAT:
        return FLOAT
    if left == LONG or right == LONG:
        return LONG
    return INT


def unary_numeric_promotion(t: JType) -> JType:
    """Apply unary numeric promotion rules."""
    if t in (BYTE, SHORT, CHAR):
        return INT
    return t
