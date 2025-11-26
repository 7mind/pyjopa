"""
JVM generic signature parser.

Parses Signature attributes from class files to extract generic type information.
See JVM Spec §4.7.9.1 for the signature grammar.
"""

from dataclasses import dataclass, field
from typing import Optional, Sequence
from abc import ABC


class TypeSignature(ABC):
    """Base class for type signatures."""
    pass


@dataclass(frozen=True)
class BaseTypeSignature(TypeSignature):
    """Primitive type signature (B, C, D, F, I, J, S, Z, V)."""
    descriptor: str

    @property
    def name(self) -> str:
        names = {
            "B": "byte", "C": "char", "D": "double", "F": "float",
            "I": "int", "J": "long", "S": "short", "Z": "boolean", "V": "void"
        }
        return names[self.descriptor]


@dataclass(frozen=True)
class TypeVariableSignature(TypeSignature):
    """Type variable reference (T<name>;)."""
    name: str


@dataclass(frozen=True)
class ArrayTypeSignature(TypeSignature):
    """Array type signature ([<element>)."""
    element: TypeSignature
    dimensions: int = 1


@dataclass(frozen=True)
class TypeArgument:
    """A type argument in a parameterized type."""
    wildcard: Optional[str]  # None, '+' (extends), '-' (super), or '*' (unbounded)
    signature: Optional[TypeSignature]  # None for unbounded wildcard '*'


@dataclass(frozen=True)
class SimpleClassTypeSignature:
    """A simple class type with optional type arguments."""
    name: str
    type_arguments: tuple[TypeArgument, ...] = ()


@dataclass(frozen=True)
class ClassTypeSignature(TypeSignature):
    """Class type signature (L<package>/<name><type_args>;)."""
    package: str  # e.g., "java/lang"
    simple_type: SimpleClassTypeSignature
    inner_types: tuple[SimpleClassTypeSignature, ...] = ()

    @property
    def full_name(self) -> str:
        """Return the full class name without type arguments."""
        base = f"{self.package}/{self.simple_type.name}" if self.package else self.simple_type.name
        for inner in self.inner_types:
            base = f"{base}${inner.name}"
        return base


@dataclass(frozen=True)
class TypeParameter:
    """A type parameter declaration (e.g., T extends Object)."""
    name: str
    class_bound: Optional[TypeSignature]  # may be None
    interface_bounds: tuple[TypeSignature, ...] = ()


@dataclass(frozen=True)
class ClassSignature:
    """A class signature with type parameters and superclass/interfaces."""
    type_parameters: tuple[TypeParameter, ...]
    superclass: ClassTypeSignature
    interfaces: tuple[ClassTypeSignature, ...]


@dataclass(frozen=True)
class ThrowsSignature:
    """A throws clause in a method signature."""
    exception_type: TypeSignature  # ClassTypeSignature or TypeVariableSignature


@dataclass(frozen=True)
class MethodSignature:
    """A method signature with type parameters, params, return type, and throws."""
    type_parameters: tuple[TypeParameter, ...]
    parameter_types: tuple[TypeSignature, ...]
    return_type: TypeSignature
    throws: tuple[ThrowsSignature, ...]


class SignatureParser:
    """Parses JVM generic signatures."""

    def __init__(self, signature: str):
        self.sig = signature
        self.pos = 0

    def _peek(self) -> str:
        if self.pos >= len(self.sig):
            return ""
        return self.sig[self.pos]

    def _read(self) -> str:
        ch = self._peek()
        self.pos += 1
        return ch

    def _expect(self, expected: str):
        ch = self._read()
        if ch != expected:
            raise ValueError(f"Expected '{expected}' at pos {self.pos-1}, got '{ch}' in '{self.sig}'")

    def _read_identifier(self) -> str:
        """Read an identifier (ends at /;.<>:)."""
        start = self.pos
        while self.pos < len(self.sig) and self.sig[self.pos] not in "/;.<>:":
            self.pos += 1
        return self.sig[start:self.pos]

    def parse_class_signature(self) -> ClassSignature:
        """Parse a class signature."""
        type_params = self._parse_type_parameters()
        superclass = self._parse_class_type_signature()
        interfaces = []
        while self.pos < len(self.sig):
            interfaces.append(self._parse_class_type_signature())
        return ClassSignature(
            type_parameters=tuple(type_params),
            superclass=superclass,
            interfaces=tuple(interfaces),
        )

    def parse_method_signature(self) -> MethodSignature:
        """Parse a method signature."""
        type_params = self._parse_type_parameters()
        self._expect("(")
        params = []
        while self._peek() != ")":
            params.append(self._parse_type_signature())
        self._expect(")")
        return_type = self._parse_return_type()
        throws = []
        while self._peek() == "^":
            self._read()  # consume '^'
            if self._peek() == "T":
                throws.append(ThrowsSignature(self._parse_type_variable_signature()))
            else:
                throws.append(ThrowsSignature(self._parse_class_type_signature()))
        return MethodSignature(
            type_parameters=tuple(type_params),
            parameter_types=tuple(params),
            return_type=return_type,
            throws=tuple(throws),
        )

    def parse_field_signature(self) -> TypeSignature:
        """Parse a field type signature."""
        return self._parse_field_type_signature()

    def _parse_type_parameters(self) -> list[TypeParameter]:
        """Parse optional type parameters (<T:..>)."""
        if self._peek() != "<":
            return []
        self._read()  # consume '<'
        params = []
        while self._peek() != ">":
            params.append(self._parse_type_parameter())
        self._read()  # consume '>'
        return params

    def _parse_type_parameter(self) -> TypeParameter:
        """Parse a single type parameter."""
        name = self._read_identifier()
        self._expect(":")
        # Class bound (optional - may be empty before first ':')
        class_bound = None
        if self._peek() not in ":>":
            class_bound = self._parse_field_type_signature()
        # Interface bounds
        interface_bounds = []
        while self._peek() == ":":
            self._read()  # consume ':'
            interface_bounds.append(self._parse_field_type_signature())
        return TypeParameter(
            name=name,
            class_bound=class_bound,
            interface_bounds=tuple(interface_bounds),
        )

    def _parse_type_signature(self) -> TypeSignature:
        """Parse a type signature (base type or field type)."""
        ch = self._peek()
        if ch in "BCDFIJSZV":
            return self._parse_base_type()
        return self._parse_field_type_signature()

    def _parse_return_type(self) -> TypeSignature:
        """Parse return type (type signature or V)."""
        if self._peek() == "V":
            self._read()
            return BaseTypeSignature("V")
        return self._parse_type_signature()

    def _parse_base_type(self) -> BaseTypeSignature:
        """Parse a base (primitive) type."""
        return BaseTypeSignature(self._read())

    def _parse_field_type_signature(self) -> TypeSignature:
        """Parse a field type signature (class, array, or type variable)."""
        ch = self._peek()
        if ch == "L":
            return self._parse_class_type_signature()
        elif ch == "[":
            return self._parse_array_type_signature()
        elif ch == "T":
            return self._parse_type_variable_signature()
        else:
            raise ValueError(f"Unexpected char '{ch}' at pos {self.pos} in field type signature")

    def _parse_class_type_signature(self) -> ClassTypeSignature:
        """Parse a class type signature (L...;)."""
        self._expect("L")
        # Read package and class name
        parts = []
        while True:
            part = self._read_identifier()
            parts.append(part)
            if self._peek() == "/":
                self._read()  # consume '/'
            else:
                break

        # Package is all but last part
        if len(parts) > 1:
            package = "/".join(parts[:-1])
            class_name = parts[-1]
        else:
            package = ""
            class_name = parts[0]

        # Type arguments
        type_args = self._parse_type_arguments()
        simple_type = SimpleClassTypeSignature(name=class_name, type_arguments=tuple(type_args))

        # Inner classes
        inner_types = []
        while self._peek() == ".":
            self._read()  # consume '.'
            inner_name = self._read_identifier()
            inner_args = self._parse_type_arguments()
            inner_types.append(SimpleClassTypeSignature(name=inner_name, type_arguments=tuple(inner_args)))

        self._expect(";")
        return ClassTypeSignature(
            package=package,
            simple_type=simple_type,
            inner_types=tuple(inner_types),
        )

    def _parse_type_arguments(self) -> list[TypeArgument]:
        """Parse optional type arguments (<...>)."""
        if self._peek() != "<":
            return []
        self._read()  # consume '<'
        args = []
        while self._peek() != ">":
            args.append(self._parse_type_argument())
        self._read()  # consume '>'
        return args

    def _parse_type_argument(self) -> TypeArgument:
        """Parse a single type argument."""
        ch = self._peek()
        if ch == "*":
            self._read()
            return TypeArgument(wildcard="*", signature=None)
        elif ch == "+":
            self._read()
            return TypeArgument(wildcard="+", signature=self._parse_field_type_signature())
        elif ch == "-":
            self._read()
            return TypeArgument(wildcard="-", signature=self._parse_field_type_signature())
        else:
            return TypeArgument(wildcard=None, signature=self._parse_field_type_signature())

    def _parse_array_type_signature(self) -> ArrayTypeSignature:
        """Parse an array type signature ([...)."""
        dimensions = 0
        while self._peek() == "[":
            self._read()
            dimensions += 1
        element = self._parse_type_signature()
        return ArrayTypeSignature(element=element, dimensions=dimensions)

    def _parse_type_variable_signature(self) -> TypeVariableSignature:
        """Parse a type variable signature (T<name>;)."""
        self._expect("T")
        name = self._read_identifier()
        self._expect(";")
        return TypeVariableSignature(name=name)


def parse_class_signature(signature: str) -> ClassSignature:
    """Parse a class signature string."""
    return SignatureParser(signature).parse_class_signature()


def parse_method_signature(signature: str) -> MethodSignature:
    """Parse a method signature string."""
    return SignatureParser(signature).parse_method_signature()


def parse_field_signature(signature: str) -> TypeSignature:
    """Parse a field type signature string."""
    return SignatureParser(signature).parse_field_signature()


def signature_to_descriptor(sig: TypeSignature) -> str:
    """Convert a type signature to a simple descriptor (erasing generics)."""
    if isinstance(sig, BaseTypeSignature):
        return sig.descriptor
    elif isinstance(sig, TypeVariableSignature):
        return "Ljava/lang/Object;"  # Type variables erase to Object
    elif isinstance(sig, ArrayTypeSignature):
        return "[" * sig.dimensions + signature_to_descriptor(sig.element)
    elif isinstance(sig, ClassTypeSignature):
        return f"L{sig.full_name};"
    else:
        raise ValueError(f"Unknown signature type: {type(sig)}")
