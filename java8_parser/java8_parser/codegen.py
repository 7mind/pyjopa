"""
Bytecode generator for Java 8 AST.
Generates Java 6 bytecode (version 50.0).
"""

from dataclasses import dataclass, field
from typing import Optional
from . import ast
from .types import (
    JType, PrimitiveJType, ClassJType, ArrayJType, MethodType,
    VOID, BOOLEAN, BYTE, CHAR, SHORT, INT, LONG, FLOAT, DOUBLE,
    OBJECT, STRING, SYSTEM, PRINTSTREAM,
    PRIMITIVE_TYPES, is_numeric, binary_numeric_promotion,
)
from .classfile import (
    ClassFile, MethodInfo, FieldInfo, CodeAttribute, BytecodeBuilder,
    AccessFlags, AnnotationInfo,
)
from .classreader import ClassPath, ClassInfo as ReadClassInfo, MethodInfo as ReadMethodInfo, FieldInfo as ReadFieldInfo


class CompileError(Exception):
    """Error during compilation."""
    pass


@dataclass
class LocalVariable:
    """A local variable in a method."""
    name: str
    type: JType
    slot: int


@dataclass
class MethodContext:
    """Context for compiling a method."""
    class_name: str
    method_name: str
    return_type: JType
    builder: BytecodeBuilder
    locals: dict[str, LocalVariable] = field(default_factory=dict)
    next_slot: int = 0

    def add_local(self, name: str, jtype: JType) -> LocalVariable:
        var = LocalVariable(name, jtype, self.next_slot)
        self.locals[name] = var
        self.next_slot += jtype.size
        self.builder.max_locals = max(self.builder.max_locals, self.next_slot)
        return var

    def get_local(self, name: str) -> LocalVariable:
        if name not in self.locals:
            raise CompileError(f"Undefined variable: {name}")
        return self.locals[name]


@dataclass
class ResolvedMethod:
    """A resolved method from the classpath."""
    owner: str
    name: str
    descriptor: str
    is_static: bool
    is_interface: bool
    return_type: JType
    param_types: tuple[JType, ...]


JAVA_LANG_CLASSES = {
    "Object", "String", "Class", "System", "Thread", "Throwable",
    "Exception", "RuntimeException", "Error",
    "Math", "StrictMath", "Number",
    "Byte", "Short", "Integer", "Long", "Float", "Double", "Character", "Boolean",
    "StringBuilder", "StringBuffer",
    "Comparable", "Cloneable", "Runnable", "Iterable", "AutoCloseable",
    "Enum", "Void",
    # Annotations
    "Deprecated", "Override", "SuppressWarnings", "SafeVarargs", "FunctionalInterface",
}


@dataclass
class LocalMethodInfo:
    """Info about a method defined in the current class."""
    name: str
    descriptor: str
    is_static: bool
    return_type: JType
    param_types: tuple[JType, ...]


class CodeGenerator:
    """Generates bytecode from AST."""

    def __init__(self, classpath: Optional[ClassPath] = None):
        self.class_file: Optional[ClassFile] = None
        self.class_name: str = ""
        self._label_counter = 0
        self.classpath = classpath
        self._class_cache: dict[str, ReadClassInfo] = {}
        self._local_methods: dict[str, list[LocalMethodInfo]] = {}  # method_name -> list of overloads

    def _resolve_class_name(self, name: str) -> str:
        """Resolve a simple class name to its full internal name."""
        # Already qualified
        if "/" in name or "." in name:
            return name.replace(".", "/")
        # Check if it's a java.lang class
        if name in JAVA_LANG_CLASSES:
            return f"java/lang/{name}"
        # Check if it's the current class
        if name == self.class_name or name == self.class_name.split("/")[-1]:
            return self.class_name
        # Otherwise assume it's in the default package or same package
        return name

    def new_label(self, prefix: str = "L") -> str:
        self._label_counter += 1
        return f"{prefix}{self._label_counter}"

    def _lookup_class(self, name: str) -> Optional[ReadClassInfo]:
        """Look up a class from the classpath."""
        if name in self._class_cache:
            return self._class_cache[name]
        if self.classpath:
            cls = self.classpath.find_class(name)
            if cls:
                self._class_cache[name] = cls
            return cls
        return None

    def _find_method(self, class_name: str, method_name: str,
                     arg_types: list[JType]) -> Optional[ResolvedMethod]:
        """Find a method in a class that matches the given name and argument types."""
        # Check if looking in the current class being compiled
        if class_name == self.class_name and method_name in self._local_methods:
            for local_method in self._local_methods[method_name]:
                if len(local_method.param_types) == len(arg_types):
                    return ResolvedMethod(
                        owner=self.class_name,
                        name=method_name,
                        descriptor=local_method.descriptor,
                        is_static=local_method.is_static,
                        is_interface=False,
                        return_type=local_method.return_type,
                        param_types=local_method.param_types,
                    )

        cls = self._lookup_class(class_name)
        if not cls:
            return None

        # Check if it's an interface
        is_interface = (cls.access_flags & AccessFlags.INTERFACE) != 0

        # Collect all matching methods
        candidates = []
        current = cls
        while current:
            for method in current.methods:
                if method.name != method_name:
                    continue
                return_type, param_types = self._parse_method_descriptor(method.descriptor)
                if len(param_types) != len(arg_types):
                    continue
                # Check type compatibility
                if self._args_compatible(arg_types, param_types):
                    is_static = (method.access_flags & AccessFlags.STATIC) != 0
                    candidates.append(ResolvedMethod(
                        owner=current.name,
                        name=method_name,
                        descriptor=method.descriptor,
                        is_static=is_static,
                        is_interface=is_interface,
                        return_type=return_type,
                        param_types=param_types,
                    ))
            if current.super_class:
                current = self._lookup_class(current.super_class)
            else:
                break

        # Pick the most specific method
        if candidates:
            return self._most_specific_method(candidates, arg_types)

        # Check interfaces for default methods
        if cls.interfaces:
            for iface_name in cls.interfaces:
                result = self._find_method(iface_name, method_name, arg_types)
                if result:
                    return result

        return None

    def _args_compatible(self, arg_types: list[JType], param_types: tuple[JType, ...]) -> bool:
        """Check if argument types are compatible with parameter types."""
        for arg, param in zip(arg_types, param_types):
            if not self._type_assignable(arg, param):
                return False
        return True

    def _type_assignable(self, from_type: JType, to_type: JType) -> bool:
        """Check if from_type can be assigned to to_type."""
        # Same type is always assignable
        if from_type == to_type:
            return True

        # Integer widening: byte -> short -> int -> long
        # Also: byte/short/char -> int
        integer_types = {BYTE, SHORT, CHAR, INT, LONG}
        if from_type in integer_types and to_type in integer_types:
            widening_order = [BYTE, SHORT, CHAR, INT, LONG]
            from_idx = widening_order.index(from_type) if from_type in widening_order else -1
            to_idx = widening_order.index(to_type) if to_type in widening_order else -1
            # char is a bit special, but for simplicity treat byte/short/char as convertible to int
            if from_type in {BYTE, SHORT, CHAR} and to_type == INT:
                return True
            if from_idx <= to_idx and from_idx >= 0:
                return True

        # Float widening: float -> double
        if from_type == FLOAT and to_type == DOUBLE:
            return True

        # Int to float/double (widening)
        if from_type in {BYTE, SHORT, CHAR, INT} and to_type in {FLOAT, DOUBLE}:
            return True
        if from_type == LONG and to_type in {FLOAT, DOUBLE}:
            return True

        # Object is assignable from any reference type
        if isinstance(to_type, ClassJType) and to_type.internal_name() == "java/lang/Object":
            if isinstance(from_type, (ClassJType, ArrayJType)):
                return True

        # Subtyping for reference types (simplified - just check if same or Object)
        if isinstance(from_type, ClassJType) and isinstance(to_type, ClassJType):
            if from_type.internal_name() == to_type.internal_name():
                return True

        return False

    def _most_specific_method(self, candidates: list[ResolvedMethod], arg_types: list[JType]) -> ResolvedMethod:
        """Select the most specific method from candidates."""
        if len(candidates) == 1:
            return candidates[0]

        # Prefer methods with primitive parameters over Object parameters
        # This handles println(int) vs println(Object) for byte/short args
        best = candidates[0]
        for candidate in candidates[1:]:
            if self._method_more_specific(candidate, best, arg_types):
                best = candidate
        return best

    def _method_more_specific(self, m1: ResolvedMethod, m2: ResolvedMethod, arg_types: list[JType]) -> bool:
        """Check if m1 is more specific than m2 for the given argument types."""
        # A method is more specific if its parameter types are more specific
        for p1, p2, arg in zip(m1.param_types, m2.param_types, arg_types):
            if p1 == p2:
                continue
            # Primitive is more specific than Object
            if isinstance(p2, ClassJType) and p2.internal_name() == "java/lang/Object":
                if isinstance(p1, PrimitiveJType) or (isinstance(p1, ClassJType) and p1.internal_name() != "java/lang/Object"):
                    return True
            # Narrower primitive is more specific
            if isinstance(p1, PrimitiveJType) and isinstance(p2, PrimitiveJType):
                widening = [BYTE, SHORT, CHAR, INT, LONG, FLOAT, DOUBLE]
                if p1 in widening and p2 in widening:
                    if widening.index(p1) < widening.index(p2):
                        return True
        return False

    def _find_field(self, class_name: str, field_name: str) -> Optional[tuple[str, str, JType]]:
        """Find a field in a class. Returns (owner, descriptor, type)."""
        cls = self._lookup_class(class_name)
        if not cls:
            return None

        current = cls
        while current:
            for fld in current.fields:
                if fld.name == field_name:
                    jtype = self._descriptor_to_type(fld.descriptor)
                    return (current.name, fld.descriptor, jtype)
            if current.super_class:
                current = self._lookup_class(current.super_class)
            else:
                break
        return None

    def _parse_method_descriptor(self, descriptor: str) -> tuple[JType, tuple[JType, ...]]:
        """Parse a method descriptor into return type and parameter types."""
        params = []
        i = 1  # Skip '('
        while descriptor[i] != ')':
            jtype, consumed = self._parse_type_from_descriptor(descriptor, i)
            params.append(jtype)
            i += consumed
        i += 1  # Skip ')'
        return_type, _ = self._parse_type_from_descriptor(descriptor, i)
        return return_type, tuple(params)

    def _parse_type_from_descriptor(self, desc: str, pos: int) -> tuple[JType, int]:
        """Parse a single type from a descriptor at the given position."""
        ch = desc[pos]
        if ch == 'B':
            return BYTE, 1
        elif ch == 'C':
            return CHAR, 1
        elif ch == 'D':
            return DOUBLE, 1
        elif ch == 'F':
            return FLOAT, 1
        elif ch == 'I':
            return INT, 1
        elif ch == 'J':
            return LONG, 1
        elif ch == 'S':
            return SHORT, 1
        elif ch == 'Z':
            return BOOLEAN, 1
        elif ch == 'V':
            return VOID, 1
        elif ch == 'L':
            end = desc.index(';', pos)
            class_name = desc[pos + 1:end]
            return ClassJType(class_name), end - pos + 1
        elif ch == '[':
            elem_type, consumed = self._parse_type_from_descriptor(desc, pos + 1)
            if isinstance(elem_type, ArrayJType):
                return ArrayJType(elem_type.element_type, elem_type.dimensions + 1), consumed + 1
            return ArrayJType(elem_type, 1), consumed + 1
        else:
            raise CompileError(f"Unknown descriptor char: {ch}")

    def _descriptor_to_type(self, desc: str) -> JType:
        """Convert a full descriptor to a JType."""
        jtype, _ = self._parse_type_from_descriptor(desc, 0)
        return jtype

    def _register_local_method(self, method: ast.MethodDeclaration):
        """Register a method for forward reference resolution."""
        is_static = any(m.keyword == "static" for m in method.modifiers)
        return_type = self.resolve_type(method.return_type)
        param_types = tuple(self.resolve_type(p.type) for p in method.parameters)
        descriptor = MethodType(return_type, param_types).descriptor()

        info = LocalMethodInfo(
            name=method.name,
            descriptor=descriptor,
            is_static=is_static,
            return_type=return_type,
            param_types=param_types,
        )

        if method.name not in self._local_methods:
            self._local_methods[method.name] = []
        self._local_methods[method.name].append(info)

    def _convert_annotations(self, modifiers: tuple) -> list[AnnotationInfo]:
        """Convert AST annotations from modifiers to AnnotationInfo list."""
        annotations = []
        for mod in modifiers:
            if mod.annotation:
                ann = self._convert_annotation(mod.annotation)
                annotations.append(ann)
        return annotations

    def _convert_annotation(self, ann: ast.Annotation) -> AnnotationInfo:
        """Convert an AST Annotation to AnnotationInfo."""
        # Resolve annotation type name to descriptor
        type_name = self._resolve_class_name(ann.name)
        type_desc = f"L{type_name};"

        elements = {}
        for arg in ann.arguments:
            name = arg.name if arg.name else "value"
            tag, value = self._convert_annotation_value(arg.value)
            elements[name] = (tag, value)

        return AnnotationInfo(type_descriptor=type_desc, elements=elements)

    def _convert_annotation_value(self, expr: ast.Expression) -> tuple[str, any]:
        """Convert an annotation element value to (tag, value)."""
        if isinstance(expr, ast.Literal):
            if expr.kind == "int":
                return ('I', self.parse_int_literal(expr.value))
            elif expr.kind == "long":
                return ('J', self.parse_long_literal(expr.value))
            elif expr.kind == "float":
                return ('F', float(expr.value.rstrip("fF")))
            elif expr.kind == "double":
                return ('D', float(expr.value.rstrip("dD")))
            elif expr.kind == "boolean":
                return ('Z', 1 if expr.value == "true" else 0)
            elif expr.kind == "char":
                s = expr.value[1:-1]
                if s.startswith("\\"):
                    return ('C', self.parse_escape(s))
                return ('C', ord(s))
            elif expr.kind == "string":
                return ('s', self.parse_string_literal(expr.value))
        elif isinstance(expr, ast.ClassLiteral):
            jtype = self.resolve_type(expr.type)
            return ('c', jtype.descriptor())
        elif isinstance(expr, ast.FieldAccess):
            # Enum constant: SomeEnum.VALUE
            if isinstance(expr.target, ast.Identifier):
                enum_type = self._resolve_class_name(expr.target.name)
                return ('e', (f"L{enum_type};", expr.field))
            elif isinstance(expr.target, ast.QualifiedName):
                enum_type = "/".join(expr.target.parts)
                return ('e', (f"L{enum_type};", expr.field))
        elif isinstance(expr, ast.ArrayInitializer):
            # Array of values
            values = [self._convert_annotation_value(e) for e in expr.elements]
            return ('[', values)
        elif isinstance(expr, ast.Annotation):
            # Nested annotation
            return ('@', self._convert_annotation(expr))
        elif isinstance(expr, ast.Identifier):
            # Could be an enum constant in the same context
            return ('s', expr.name)

        raise CompileError(f"Unsupported annotation value: {type(expr).__name__}")

    def _generate_type_param_signature(self, tp: ast.TypeParameter) -> str:
        """Generate signature for a type parameter declaration."""
        sig = tp.name + ":"
        if tp.bounds:
            for i, bound in enumerate(tp.bounds):
                if i > 0:
                    sig += ":"
                sig += self._generate_type_signature(bound)
        else:
            sig += "Ljava/lang/Object;"
        return sig

    def _generate_type_params_signature(self, type_params: tuple) -> str:
        """Generate signature for type parameters."""
        if not type_params:
            return ""
        sigs = [self._generate_type_param_signature(tp) for tp in type_params]
        return "<" + "".join(sigs) + ">"

    def _generate_type_signature(self, type_node) -> str:
        """Generate signature for a type reference."""
        if isinstance(type_node, ast.ClassType):
            name = type_node.name
            if name in ("int", "byte", "short", "long", "float", "double", "boolean", "char", "void"):
                descriptors = {
                    "int": "I", "byte": "B", "short": "S", "long": "J",
                    "float": "F", "double": "D", "boolean": "Z", "char": "C", "void": "V"
                }
                return descriptors[name]
            if hasattr(self, '_type_param_names') and name in self._type_param_names:
                return f"T{name};"
            full_name = self._resolve_class_name(name)
            sig = f"L{full_name}"
            if type_node.type_arguments:
                sig += "<"
                for ta in type_node.type_arguments:
                    sig += self._generate_type_argument_signature(ta)
                sig += ">"
            sig += ";"
            return sig
        elif isinstance(type_node, ast.ArrayType):
            return "[" * type_node.dimensions + self._generate_type_signature(type_node.element_type)
        elif isinstance(type_node, ast.PrimitiveType):
            descriptors = {
                "int": "I", "byte": "B", "short": "S", "long": "J",
                "float": "F", "double": "D", "boolean": "Z", "char": "C", "void": "V"
            }
            return descriptors[type_node.name]
        else:
            return "Ljava/lang/Object;"

    def _generate_type_argument_signature(self, ta) -> str:
        """Generate signature for a type argument."""
        if isinstance(ta, ast.WildcardType):
            if ta.extends:
                return "+" + self._generate_type_signature(ta.extends)
            elif ta.super_:
                return "-" + self._generate_type_signature(ta.super_)
            else:
                return "*"
        else:
            return self._generate_type_signature(ta)

    def _generate_class_signature(self, cls: ast.ClassDeclaration) -> Optional[str]:
        """Generate class signature if class has type parameters."""
        if not cls.type_parameters:
            return None
        self._type_param_names = {tp.name for tp in cls.type_parameters}
        sig = self._generate_type_params_signature(cls.type_parameters)
        if cls.extends:
            sig += self._generate_type_signature(cls.extends)
        else:
            sig += "Ljava/lang/Object;"
        for iface in cls.implements:
            sig += self._generate_type_signature(iface)
        return sig

    def _generate_method_signature(self, method: ast.MethodDeclaration, class_type_params: set[str]) -> Optional[str]:
        """Generate method signature if method uses generics."""
        self._type_param_names = class_type_params.copy()
        for tp in method.type_parameters:
            self._type_param_names.add(tp.name)

        has_generics = bool(method.type_parameters)
        if not has_generics:
            if self._type_uses_generics(method.return_type, self._type_param_names):
                has_generics = True
            else:
                for param in method.parameters:
                    if self._type_uses_generics(param.type, self._type_param_names):
                        has_generics = True
                        break

        if not has_generics:
            return None

        sig = self._generate_type_params_signature(method.type_parameters)
        sig += "("
        for param in method.parameters:
            sig += self._generate_type_signature(param.type)
        sig += ")"
        sig += self._generate_type_signature(method.return_type)
        return sig

    def _type_uses_generics(self, type_node, type_params: set[str]) -> bool:
        """Check if a type uses any type parameters."""
        if isinstance(type_node, ast.ClassType):
            if type_node.name in type_params:
                return True
            for ta in type_node.type_arguments:
                if self._type_uses_generics(ta, type_params):
                    return True
            return False
        elif isinstance(type_node, ast.ArrayType):
            return self._type_uses_generics(type_node.element_type, type_params)
        elif isinstance(type_node, ast.WildcardType):
            if type_node.extends and self._type_uses_generics(type_node.extends, type_params):
                return True
            if type_node.super_ and self._type_uses_generics(type_node.super_, type_params):
                return True
            return False
        return False

    def compile(self, unit: ast.CompilationUnit) -> dict[str, bytes]:
        """Compile a compilation unit to class files."""
        results = {}
        for type_decl in unit.types:
            if isinstance(type_decl, ast.ClassDeclaration):
                class_bytes = self.compile_class(type_decl)
                results[type_decl.name] = class_bytes
        return results

    def compile_class(self, cls: ast.ClassDeclaration) -> bytes:
        """Compile a class declaration."""
        self.class_name = cls.name
        self.class_file = ClassFile(cls.name)

        # Store class type parameters for method signature generation
        self._class_type_params = {tp.name for tp in cls.type_parameters}

        # Set access flags
        flags = AccessFlags.SUPER
        for mod in cls.modifiers:
            if mod.keyword == "public":
                flags |= AccessFlags.PUBLIC
            elif mod.keyword == "private":
                flags |= AccessFlags.PRIVATE
            elif mod.keyword == "protected":
                flags |= AccessFlags.PROTECTED
            elif mod.keyword == "final":
                flags |= AccessFlags.FINAL
            elif mod.keyword == "abstract":
                flags |= AccessFlags.ABSTRACT
        self.class_file.access_flags = flags

        # Add class annotations
        self.class_file.annotations = self._convert_annotations(cls.modifiers)

        # Generate class signature for generics
        self.class_file.signature = self._generate_class_signature(cls)

        # First pass: collect method signatures for forward references
        self._local_methods = {}
        for member in cls.body:
            if isinstance(member, ast.MethodDeclaration):
                self._register_local_method(member)

        # Second pass: compile members
        for member in cls.body:
            if isinstance(member, ast.MethodDeclaration):
                self.compile_method(member)
            elif isinstance(member, ast.FieldDeclaration):
                self.compile_field(member)
            elif isinstance(member, ast.ConstructorDeclaration):
                self.compile_constructor(member)

        return self.class_file.to_bytes()

    def compile_field(self, fld: ast.FieldDeclaration):
        """Compile a field declaration."""
        flags = 0
        for mod in fld.modifiers:
            if mod.keyword == "public":
                flags |= AccessFlags.PUBLIC
            elif mod.keyword == "private":
                flags |= AccessFlags.PRIVATE
            elif mod.keyword == "protected":
                flags |= AccessFlags.PROTECTED
            elif mod.keyword == "static":
                flags |= AccessFlags.STATIC
            elif mod.keyword == "final":
                flags |= AccessFlags.FINAL

        jtype = self.resolve_type(fld.type)
        annotations = self._convert_annotations(fld.modifiers)
        for decl in fld.declarators:
            field_info = FieldInfo(
                access_flags=flags,
                name=decl.name,
                descriptor=jtype.descriptor(),
                annotations=annotations
            )
            self.class_file.add_field(field_info)

    def compile_constructor(self, ctor: ast.ConstructorDeclaration):
        """Compile a constructor."""
        flags = 0
        for mod in ctor.modifiers:
            if mod.keyword == "public":
                flags |= AccessFlags.PUBLIC
            elif mod.keyword == "private":
                flags |= AccessFlags.PRIVATE
            elif mod.keyword == "protected":
                flags |= AccessFlags.PROTECTED

        # Build method descriptor
        param_types = [self.resolve_type(p.type) for p in ctor.parameters]
        descriptor = "(" + "".join(t.descriptor() for t in param_types) + ")V"

        builder = BytecodeBuilder(self.class_file.cp)
        ctx = MethodContext(
            class_name=self.class_name,
            method_name="<init>",
            return_type=VOID,
            builder=builder,
        )

        # 'this' is slot 0
        ctx.add_local("this", ClassJType(self.class_name))

        # Add parameters
        for param, jtype in zip(ctor.parameters, param_types):
            ctx.add_local(param.name, jtype)

        # Call super constructor
        builder.aload(0)
        builder.invokespecial("java/lang/Object", "<init>", "()V", 0, 0)

        # Compile body
        self.compile_block(ctor.body, ctx)

        # Add return
        builder.return_()

        method_info = MethodInfo(
            access_flags=flags,
            name="<init>",
            descriptor=descriptor,
            code=builder.build()
        )
        self.class_file.add_method(method_info)

    def compile_method(self, method: ast.MethodDeclaration):
        """Compile a method declaration."""
        flags = 0
        is_static = False
        for mod in method.modifiers:
            if mod.keyword == "public":
                flags |= AccessFlags.PUBLIC
            elif mod.keyword == "private":
                flags |= AccessFlags.PRIVATE
            elif mod.keyword == "protected":
                flags |= AccessFlags.PROTECTED
            elif mod.keyword == "static":
                flags |= AccessFlags.STATIC
                is_static = True
            elif mod.keyword == "final":
                flags |= AccessFlags.FINAL
            elif mod.keyword == "native":
                flags |= AccessFlags.NATIVE
            elif mod.keyword == "abstract":
                flags |= AccessFlags.ABSTRACT

        # Build method descriptor
        param_types = [self.resolve_type(p.type) for p in method.parameters]
        return_type = self.resolve_type(method.return_type)
        descriptor = MethodType(return_type, tuple(param_types)).descriptor()

        # Collect annotations
        annotations = self._convert_annotations(method.modifiers)

        # Collect throws as internal names
        throws_list = [self._resolve_class_name(t.name) if isinstance(t, ast.ClassType) else str(t)
                       for t in method.throws]

        # Abstract/native methods have no code
        if method.body is None:
            method_info = MethodInfo(
                access_flags=flags,
                name=method.name,
                descriptor=descriptor,
                code=None,
                annotations=annotations,
                exceptions=throws_list
            )
            self.class_file.add_method(method_info)
            return

        builder = BytecodeBuilder(self.class_file.cp)
        ctx = MethodContext(
            class_name=self.class_name,
            method_name=method.name,
            return_type=return_type,
            builder=builder,
        )

        # Add 'this' for instance methods
        if not is_static:
            ctx.add_local("this", ClassJType(self.class_name))

        # Add parameters
        for param, jtype in zip(method.parameters, param_types):
            ctx.add_local(param.name, jtype)

        # Compile body
        self.compile_block(method.body, ctx)

        # Add implicit return for void methods
        if return_type == VOID:
            builder.return_()

        method_info = MethodInfo(
            access_flags=flags,
            name=method.name,
            descriptor=descriptor,
            code=builder.build(),
            annotations=annotations,
            exceptions=throws_list
        )
        self.class_file.add_method(method_info)

    def compile_block(self, block: ast.Block, ctx: MethodContext):
        """Compile a block of statements."""
        for stmt in block.statements:
            self.compile_statement(stmt, ctx)

    def compile_statement(self, stmt: ast.Statement, ctx: MethodContext):
        """Compile a statement."""
        builder = ctx.builder

        if isinstance(stmt, ast.Block):
            self.compile_block(stmt, ctx)

        elif isinstance(stmt, ast.LocalVariableDeclaration):
            jtype = self.resolve_type(stmt.type)
            for decl in stmt.declarators:
                var = ctx.add_local(decl.name, jtype)
                if decl.initializer:
                    self.compile_expression(decl.initializer, ctx)
                    self.store_local(var, builder)

        elif isinstance(stmt, ast.ExpressionStatement):
            expr_type = self.compile_expression(stmt.expression, ctx)
            # Pop result if not void
            if expr_type != VOID:
                if expr_type.size == 2:
                    builder._emit(0x58)  # pop2
                    builder._pop(2)
                else:
                    builder.pop()

        elif isinstance(stmt, ast.ReturnStatement):
            if stmt.expression:
                self.compile_expression(stmt.expression, ctx)
                if ctx.return_type == VOID:
                    builder.return_()
                elif ctx.return_type == INT or ctx.return_type == BOOLEAN:
                    builder.ireturn()
                elif ctx.return_type == LONG:
                    builder.lreturn()
                elif ctx.return_type == FLOAT:
                    builder.freturn()
                elif ctx.return_type == DOUBLE:
                    builder.dreturn()
                elif ctx.return_type.is_reference:
                    builder.areturn()
                else:
                    builder.ireturn()
            else:
                builder.return_()

        elif isinstance(stmt, ast.IfStatement):
            else_label = self.new_label("else")
            end_label = self.new_label("endif")

            # Compile condition
            self.compile_condition(stmt.condition, ctx, else_label, False)

            # Then branch
            self.compile_statement(stmt.then_branch, ctx)

            if stmt.else_branch:
                builder.goto(end_label)
                builder.label(else_label)
                self.compile_statement(stmt.else_branch, ctx)
                builder.label(end_label)
            else:
                builder.label(else_label)

        elif isinstance(stmt, ast.WhileStatement):
            loop_label = self.new_label("while")
            end_label = self.new_label("endwhile")

            builder.label(loop_label)
            self.compile_condition(stmt.condition, ctx, end_label, False)
            self.compile_statement(stmt.body, ctx)
            builder.goto(loop_label)
            builder.label(end_label)

        elif isinstance(stmt, ast.DoWhileStatement):
            loop_label = self.new_label("do")

            builder.label(loop_label)
            self.compile_statement(stmt.body, ctx)
            self.compile_condition(stmt.condition, ctx, loop_label, True)

        elif isinstance(stmt, ast.ForStatement):
            loop_label = self.new_label("for")
            end_label = self.new_label("endfor")
            update_label = self.new_label("update")

            # Init
            if stmt.init:
                if isinstance(stmt.init, ast.LocalVariableDeclaration):
                    self.compile_statement(stmt.init, ctx)
                else:
                    for expr in stmt.init:
                        expr_type = self.compile_expression(expr, ctx)
                        if expr_type != VOID:
                            builder.pop()

            builder.label(loop_label)

            # Condition
            if stmt.condition:
                self.compile_condition(stmt.condition, ctx, end_label, False)

            # Body
            self.compile_statement(stmt.body, ctx)

            builder.label(update_label)

            # Update
            for expr in stmt.update:
                expr_type = self.compile_expression(expr, ctx)
                if expr_type != VOID:
                    builder.pop()

            builder.goto(loop_label)
            builder.label(end_label)

        elif isinstance(stmt, ast.EmptyStatement):
            pass

        else:
            raise CompileError(f"Unsupported statement type: {type(stmt).__name__}")

    def compile_condition(self, expr: ast.Expression, ctx: MethodContext,
                          target: str, jump_if_true: bool):
        """Compile a boolean expression as a condition for branching."""
        builder = ctx.builder

        if isinstance(expr, ast.BinaryExpression):
            op = expr.operator
            if op in ("==", "!=", "<", ">=", ">", "<="):
                left_type = self.compile_expression(expr.left, ctx)
                right_type = self.compile_expression(expr.right, ctx)

                if left_type == INT and right_type == INT:
                    if jump_if_true:
                        if op == "==":
                            builder.if_icmpeq(target)
                        elif op == "!=":
                            builder.if_icmpne(target)
                        elif op == "<":
                            builder.if_icmplt(target)
                        elif op == ">=":
                            builder.if_icmpge(target)
                        elif op == ">":
                            builder.if_icmpgt(target)
                        elif op == "<=":
                            builder.if_icmple(target)
                    else:
                        # Jump if false (inverted)
                        if op == "==":
                            builder.if_icmpne(target)
                        elif op == "!=":
                            builder.if_icmpeq(target)
                        elif op == "<":
                            builder.if_icmpge(target)
                        elif op == ">=":
                            builder.if_icmplt(target)
                        elif op == ">":
                            builder.if_icmple(target)
                        elif op == "<=":
                            builder.if_icmpgt(target)
                    return

            elif op == "&&":
                if jump_if_true:
                    next_label = self.new_label("and")
                    self.compile_condition(expr.left, ctx, next_label, False)
                    self.compile_condition(expr.right, ctx, target, True)
                    builder.label(next_label)
                else:
                    self.compile_condition(expr.left, ctx, target, False)
                    self.compile_condition(expr.right, ctx, target, False)
                return

            elif op == "||":
                if jump_if_true:
                    self.compile_condition(expr.left, ctx, target, True)
                    self.compile_condition(expr.right, ctx, target, True)
                else:
                    next_label = self.new_label("or")
                    self.compile_condition(expr.left, ctx, next_label, True)
                    self.compile_condition(expr.right, ctx, target, False)
                    builder.label(next_label)
                return

        elif isinstance(expr, ast.UnaryExpression) and expr.operator == "!":
            self.compile_condition(expr.operand, ctx, target, not jump_if_true)
            return

        # Default: evaluate as boolean and branch
        self.compile_expression(expr, ctx)
        if jump_if_true:
            builder.ifne(target)
        else:
            builder.ifeq(target)

    def compile_expression(self, expr: ast.Expression, ctx: MethodContext) -> JType:
        """Compile an expression and return its type."""
        builder = ctx.builder

        if isinstance(expr, ast.Literal):
            return self.compile_literal(expr, ctx)

        elif isinstance(expr, ast.Identifier):
            var = ctx.get_local(expr.name)
            self.load_local(var, builder)
            return var.type

        elif isinstance(expr, ast.ParenthesizedExpression):
            return self.compile_expression(expr.expression, ctx)

        elif isinstance(expr, ast.BinaryExpression):
            return self.compile_binary(expr, ctx)

        elif isinstance(expr, ast.UnaryExpression):
            return self.compile_unary(expr, ctx)

        elif isinstance(expr, ast.Assignment):
            return self.compile_assignment(expr, ctx)

        elif isinstance(expr, ast.MethodInvocation):
            return self.compile_method_call(expr, ctx)

        elif isinstance(expr, ast.ConditionalExpression):
            return self.compile_ternary(expr, ctx)

        elif isinstance(expr, ast.CastExpression):
            return self.compile_cast(expr, ctx)

        else:
            raise CompileError(f"Unsupported expression type: {type(expr).__name__}")

    def _estimate_expression_type(self, expr, ctx: MethodContext) -> JType:
        """Estimate the type of an expression without generating code."""
        if isinstance(expr, ast.Literal):
            if expr.kind == "int":
                return INT
            elif expr.kind == "long":
                return LONG
            elif expr.kind == "float":
                return FLOAT
            elif expr.kind == "double":
                return DOUBLE
            elif expr.kind == "boolean":
                return BOOLEAN
            elif expr.kind == "char":
                return CHAR
            elif expr.kind == "string":
                return STRING
            elif expr.kind == "null":
                return ClassJType("java/lang/Object")
        elif isinstance(expr, ast.Identifier):
            if expr.name in ctx.locals:
                return ctx.get_local(expr.name).type
            return ClassJType("java/lang/Object")
        elif isinstance(expr, ast.BinaryExpression):
            left_type = self._estimate_expression_type(expr.left, ctx)
            right_type = self._estimate_expression_type(expr.right, ctx)
            if left_type == LONG or right_type == LONG:
                return LONG
            if left_type == DOUBLE or right_type == DOUBLE:
                return DOUBLE
            if left_type == FLOAT or right_type == FLOAT:
                return FLOAT
            return INT
        elif isinstance(expr, ast.UnaryExpression):
            return self._estimate_expression_type(expr.operand, ctx)
        elif isinstance(expr, ast.ParenthesizedExpression):
            return self._estimate_expression_type(expr.expression, ctx)
        return ClassJType("java/lang/Object")

    def compile_literal(self, lit: ast.Literal, ctx: MethodContext) -> JType:
        builder = ctx.builder

        if lit.kind == "int":
            value = self.parse_int_literal(lit.value)
            builder.iconst(value)
            return INT

        elif lit.kind == "long":
            value = self.parse_long_literal(lit.value)
            builder.lconst(value)
            return LONG

        elif lit.kind == "float":
            value = float(lit.value.rstrip("fF"))
            builder.fconst(value)
            return FLOAT

        elif lit.kind == "double":
            value = float(lit.value.rstrip("dD"))
            builder.dconst(value)
            return DOUBLE

        elif lit.kind == "boolean":
            builder.iconst(1 if lit.value == "true" else 0)
            return BOOLEAN

        elif lit.kind == "char":
            # Parse character literal
            s = lit.value[1:-1]  # Remove quotes
            if s.startswith("\\"):
                ch = self.parse_escape(s)
            else:
                ch = ord(s)
            builder.iconst(ch)
            return CHAR

        elif lit.kind == "string":
            # Remove quotes and parse escapes
            s = self.parse_string_literal(lit.value)
            builder.ldc_string(s)
            return STRING

        elif lit.kind == "null":
            builder.aconst_null()
            return ClassJType("java/lang/Object")

        else:
            raise CompileError(f"Unknown literal kind: {lit.kind}")

    def parse_int_literal(self, s: str) -> int:
        s = s.replace("_", "")
        if s.startswith("0x") or s.startswith("0X"):
            return int(s, 16)
        elif s.startswith("0b") or s.startswith("0B"):
            return int(s, 2)
        elif s.startswith("0") and len(s) > 1 and s[1].isdigit():
            return int(s, 8)
        return int(s)

    def parse_long_literal(self, s: str) -> int:
        return self.parse_int_literal(s.rstrip("lL"))

    def parse_escape(self, s: str) -> int:
        escapes = {"n": 10, "r": 13, "t": 9, "b": 8, "f": 12, "\\": 92, "'": 39, '"': 34}
        if s[1] in escapes:
            return escapes[s[1]]
        elif s[1] == "u":
            return int(s[2:6], 16)
        elif s[1].isdigit():
            return int(s[1:], 8)
        return ord(s[1])

    def parse_string_literal(self, s: str) -> str:
        result = []
        s = s[1:-1]  # Remove quotes
        i = 0
        while i < len(s):
            if s[i] == "\\" and i + 1 < len(s):
                if s[i + 1] == "n":
                    result.append("\n")
                    i += 2
                elif s[i + 1] == "r":
                    result.append("\r")
                    i += 2
                elif s[i + 1] == "t":
                    result.append("\t")
                    i += 2
                elif s[i + 1] == "\\":
                    result.append("\\")
                    i += 2
                elif s[i + 1] == '"':
                    result.append('"')
                    i += 2
                elif s[i + 1] == "u":
                    result.append(chr(int(s[i + 2:i + 6], 16)))
                    i += 6
                else:
                    result.append(s[i + 1])
                    i += 2
            else:
                result.append(s[i])
                i += 1
        return "".join(result)

    def compile_binary(self, expr: ast.BinaryExpression, ctx: MethodContext) -> JType:
        builder = ctx.builder
        op = expr.operator

        # Special handling for string concatenation
        # For now, just handle numeric operations

        left_type = self.compile_expression(expr.left, ctx)
        right_type = self.compile_expression(expr.right, ctx)

        # Numeric promotion
        result_type = binary_numeric_promotion(left_type, right_type)

        if op == "+":
            if result_type == INT:
                builder.iadd()
            elif result_type == LONG:
                builder.ladd()
            elif result_type == FLOAT:
                builder.fadd()
            elif result_type == DOUBLE:
                builder.dadd()
        elif op == "-":
            if result_type == INT:
                builder.isub()
            elif result_type == LONG:
                builder.lsub()
            elif result_type == FLOAT:
                builder.fsub()
            elif result_type == DOUBLE:
                builder.dsub()
        elif op == "*":
            if result_type == INT:
                builder.imul()
            elif result_type == LONG:
                builder.lmul()
            elif result_type == FLOAT:
                builder.fmul()
            elif result_type == DOUBLE:
                builder.dmul()
        elif op == "/":
            if result_type == INT:
                builder.idiv()
            elif result_type == LONG:
                builder.ldiv()
            elif result_type == FLOAT:
                builder.fdiv()
            elif result_type == DOUBLE:
                builder.ddiv()
        elif op == "%":
            if result_type == INT:
                builder.irem()
            elif result_type == LONG:
                builder.lrem()
        elif op == "<<":
            if result_type == INT:
                builder.ishl()
            elif result_type == LONG:
                builder.lshl()
        elif op == ">>":
            if result_type == INT:
                builder.ishr()
            elif result_type == LONG:
                builder.lshr()
        elif op == ">>>":
            if result_type == INT:
                builder.iushr()
            elif result_type == LONG:
                builder.lushr()
        elif op == "&":
            if result_type == INT:
                builder.iand()
            elif result_type == LONG:
                builder.land()
        elif op == "|":
            if result_type == INT:
                builder.ior()
            elif result_type == LONG:
                builder.lor()
        elif op == "^":
            if result_type == INT:
                builder.ixor()
            elif result_type == LONG:
                builder.lxor()
        elif op in ("==", "!=", "<", ">=", ">", "<="):
            # Comparison - result is boolean (int)
            true_label = self.new_label("true")
            end_label = self.new_label("end")

            if left_type == INT and right_type == INT:
                if op == "==":
                    builder.if_icmpeq(true_label)
                elif op == "!=":
                    builder.if_icmpne(true_label)
                elif op == "<":
                    builder.if_icmplt(true_label)
                elif op == ">=":
                    builder.if_icmpge(true_label)
                elif op == ">":
                    builder.if_icmpgt(true_label)
                elif op == "<=":
                    builder.if_icmple(true_label)

            builder.iconst(0)
            builder.goto(end_label)
            builder.label(true_label)
            builder.iconst(1)
            builder.label(end_label)
            return BOOLEAN
        else:
            raise CompileError(f"Unsupported binary operator: {op}")

        return result_type

    def compile_unary(self, expr: ast.UnaryExpression, ctx: MethodContext) -> JType:
        builder = ctx.builder
        op = expr.operator

        if op == "-" and expr.prefix:
            operand_type = self.compile_expression(expr.operand, ctx)
            if operand_type == INT:
                builder.ineg()
            elif operand_type == LONG:
                builder.lneg()
            elif operand_type == FLOAT:
                builder.fneg()
            elif operand_type == DOUBLE:
                builder.dneg()
            return operand_type

        elif op == "+" and expr.prefix:
            return self.compile_expression(expr.operand, ctx)

        elif op == "!" and expr.prefix:
            # Boolean negation
            true_label = self.new_label("true")
            end_label = self.new_label("end")
            self.compile_expression(expr.operand, ctx)
            builder.ifeq(true_label)
            builder.iconst(0)
            builder.goto(end_label)
            builder.label(true_label)
            builder.iconst(1)
            builder.label(end_label)
            return BOOLEAN

        elif op == "~" and expr.prefix:
            operand_type = self.compile_expression(expr.operand, ctx)
            if operand_type == INT:
                builder.iconst(-1)
                builder.ixor()
            elif operand_type == LONG:
                builder.lconst(-1)
                builder.lxor()
            return operand_type

        elif op == "++" or op == "--":
            if not isinstance(expr.operand, ast.Identifier):
                raise CompileError("Increment/decrement requires variable")
            var = ctx.get_local(expr.operand.name)
            if var.type != INT:
                raise CompileError("Increment/decrement only supported for int")

            if expr.prefix:
                builder.iinc(var.slot, 1 if op == "++" else -1)
                builder.iload(var.slot)
            else:
                builder.iload(var.slot)
                builder.iinc(var.slot, 1 if op == "++" else -1)
            return INT

        else:
            raise CompileError(f"Unsupported unary operator: {op}")

    def compile_assignment(self, expr: ast.Assignment, ctx: MethodContext) -> JType:
        builder = ctx.builder

        if not isinstance(expr.target, ast.Identifier):
            raise CompileError("Only simple variable assignment supported")

        var = ctx.get_local(expr.target.name)

        if expr.operator == "=":
            self.compile_expression(expr.value, ctx)
        else:
            # Compound assignment: +=, -=, etc.
            self.load_local(var, builder)
            self.compile_expression(expr.value, ctx)

            base_op = expr.operator[:-1]
            if var.type == INT:
                if base_op == "+":
                    builder.iadd()
                elif base_op == "-":
                    builder.isub()
                elif base_op == "*":
                    builder.imul()
                elif base_op == "/":
                    builder.idiv()
                elif base_op == "%":
                    builder.irem()
                elif base_op == "&":
                    builder.iand()
                elif base_op == "|":
                    builder.ior()
                elif base_op == "^":
                    builder.ixor()
                elif base_op == "<<":
                    builder.ishl()
                elif base_op == ">>":
                    builder.ishr()
                elif base_op == ">>>":
                    builder.iushr()

        # Duplicate value for expression result, then store
        builder.dup()
        self.store_local(var, builder)
        return var.type

    def compile_method_call(self, expr: ast.MethodInvocation, ctx: MethodContext) -> JType:
        builder = ctx.builder

        # Check for System.out.println/print (hardcoded common case)
        is_system_out = False
        if isinstance(expr.target, ast.FieldAccess):
            if (isinstance(expr.target.target, ast.Identifier) and
                    expr.target.target.name == "System" and
                    expr.target.field == "out"):
                is_system_out = True
        elif isinstance(expr.target, ast.QualifiedName):
            if expr.target.parts == ("System", "out"):
                is_system_out = True

        if is_system_out:
            if expr.method == "println":
                builder.getstatic("java/lang/System", "out", "Ljava/io/PrintStream;")
                if expr.arguments:
                    arg_type = self.compile_expression(expr.arguments[0], ctx)
                    if arg_type in {INT, BYTE, SHORT}:
                        builder.invokevirtual("java/io/PrintStream", "println", "(I)V", 1, 0)
                    elif arg_type == LONG:
                        builder.invokevirtual("java/io/PrintStream", "println", "(J)V", 2, 0)
                    elif arg_type == FLOAT:
                        builder.invokevirtual("java/io/PrintStream", "println", "(F)V", 1, 0)
                    elif arg_type == DOUBLE:
                        builder.invokevirtual("java/io/PrintStream", "println", "(D)V", 2, 0)
                    elif arg_type == BOOLEAN:
                        builder.invokevirtual("java/io/PrintStream", "println", "(Z)V", 1, 0)
                    elif arg_type == CHAR:
                        builder.invokevirtual("java/io/PrintStream", "println", "(C)V", 1, 0)
                    elif arg_type == STRING:
                        builder.invokevirtual("java/io/PrintStream", "println",
                                              "(Ljava/lang/String;)V", 1, 0)
                    else:
                        builder.invokevirtual("java/io/PrintStream", "println",
                                              "(Ljava/lang/Object;)V", 1, 0)
                else:
                    builder.invokevirtual("java/io/PrintStream", "println", "()V", 0, 0)
                return VOID

            elif expr.method == "print":
                builder.getstatic("java/lang/System", "out", "Ljava/io/PrintStream;")
                if expr.arguments:
                    arg_type = self.compile_expression(expr.arguments[0], ctx)
                    if arg_type in {INT, BYTE, SHORT}:
                        builder.invokevirtual("java/io/PrintStream", "print", "(I)V", 1, 0)
                    elif arg_type == CHAR:
                        builder.invokevirtual("java/io/PrintStream", "print", "(C)V", 1, 0)
                    elif arg_type == STRING:
                        builder.invokevirtual("java/io/PrintStream", "print",
                                              "(Ljava/lang/String;)V", 1, 0)
                    else:
                        builder.invokevirtual("java/io/PrintStream", "print",
                                              "(Ljava/lang/Object;)V", 1, 0)
                return VOID

        # Try to resolve using classpath
        return self._compile_general_method_call(expr, ctx)

    def _compile_general_method_call(self, expr: ast.MethodInvocation, ctx: MethodContext) -> JType:
        """Compile a general method call using classpath resolution."""
        builder = ctx.builder

        # Determine the target type (but don't load it yet - need to check if static first)
        target_type = None
        is_static_call = False
        needs_this_load = False  # Will be set if we need to load 'this' later

        if expr.target is None:
            # Method call on this (or static call to same class - need to check later)
            target_type = ClassJType(self.class_name)
            needs_this_load = True  # Tentatively - will skip if method is static
        elif isinstance(expr.target, ast.Identifier):
            # Could be a local variable or a class name
            if expr.target.name in ctx.locals:
                var = ctx.get_local(expr.target.name)
                self.load_local(var, builder)
                target_type = var.type
            else:
                # Assume it's a class name (static call)
                is_static_call = True
                resolved_name = self._resolve_class_name(expr.target.name)
                target_type = ClassJType(resolved_name)
        elif isinstance(expr.target, ast.QualifiedName):
            # e.g., java.lang.Math.abs() or Math.abs() - class name for static call
            is_static_call = True
            if len(expr.target.parts) == 1:
                # Single name like "Math" - resolve it
                resolved_name = self._resolve_class_name(expr.target.parts[0])
                target_type = ClassJType(resolved_name)
            else:
                # Qualified name like "java.lang.Math"
                class_name = "/".join(expr.target.parts)
                target_type = ClassJType(class_name)
        elif isinstance(expr.target, ast.FieldAccess):
            # e.g., obj.field.method()
            target_type = self._compile_field_access_for_call(expr.target, ctx)
        else:
            # Some other expression - compile it
            target_type = self.compile_expression(expr.target, ctx)

        if not isinstance(target_type, ClassJType):
            raise CompileError(f"Cannot call method on type: {target_type}")

        # First, determine argument types without compiling them yet
        # We need to resolve the method first to know if it's static
        class_internal_name = target_type.internal_name()

        # Estimate arg types for method resolution
        # Note: This is a simplified approach - we compile args once after knowing the method
        arg_types_estimate = []
        for arg in expr.arguments:
            arg_type = self._estimate_expression_type(arg, ctx)
            arg_types_estimate.append(arg_type)

        # Try to resolve the method
        resolved = self._find_method(class_internal_name, expr.method, arg_types_estimate)

        if not resolved:
            raise CompileError(f"Cannot resolve method: {class_internal_name}.{expr.method}")

        # Now we know if the method is static - load 'this' if needed
        if needs_this_load and not resolved.is_static:
            builder.aload(0)  # load 'this'

        # Compile arguments
        for arg in expr.arguments:
            self.compile_expression(arg, ctx)

        # Calculate stack effect
        args_slots = sum(t.size for t in resolved.param_types)
        return_slots = 0 if resolved.return_type == VOID else resolved.return_type.size

        # Emit the call
        if is_static_call or resolved.is_static:
            builder.invokestatic(resolved.owner, resolved.name, resolved.descriptor, args_slots, return_slots)
        elif resolved.is_interface:
            builder.invokeinterface(resolved.owner, resolved.name, resolved.descriptor,
                                    args_slots + 1, return_slots)
        else:
            builder.invokevirtual(resolved.owner, resolved.name, resolved.descriptor,
                                  args_slots + 1, return_slots)

        return resolved.return_type

    def _compile_field_access_for_call(self, fa: ast.FieldAccess, ctx: MethodContext) -> JType:
        """Compile a field access and return its type (for method calls)."""
        builder = ctx.builder

        # First compile the target
        if isinstance(fa.target, ast.Identifier):
            if fa.target.name in ctx.locals:
                var = ctx.get_local(fa.target.name)
                self.load_local(var, builder)
                target_type = var.type
            else:
                # Class name - static field access
                target_type = ClassJType(fa.target.name)
                # Look up the field
                field_info = self._find_field(target_type.internal_name(), fa.field)
                if field_info:
                    owner, desc, ftype = field_info
                    builder.getstatic(owner, fa.field, desc)
                    return ftype
                raise CompileError(f"Cannot find field: {fa.target.name}.{fa.field}")
        else:
            target_type = self.compile_expression(fa.target, ctx)

        if not isinstance(target_type, ClassJType):
            raise CompileError(f"Cannot access field on type: {target_type}")

        # Look up the field in the class
        field_info = self._find_field(target_type.internal_name(), fa.field)
        if field_info:
            owner, desc, ftype = field_info
            builder.getfield(owner, fa.field, desc)
            return ftype

        raise CompileError(f"Cannot find field: {target_type.internal_name()}.{fa.field}")

    def compile_ternary(self, expr: ast.ConditionalExpression, ctx: MethodContext) -> JType:
        builder = ctx.builder
        else_label = self.new_label("else")
        end_label = self.new_label("end")

        self.compile_condition(expr.condition, ctx, else_label, False)
        then_type = self.compile_expression(expr.then_expr, ctx)
        builder.goto(end_label)
        builder.label(else_label)
        else_type = self.compile_expression(expr.else_expr, ctx)
        builder.label(end_label)

        return then_type  # Simplified - should compute common type

    def compile_cast(self, expr: ast.CastExpression, ctx: MethodContext) -> JType:
        builder = ctx.builder
        source_type = self.compile_expression(expr.expression, ctx)
        target_type = self.resolve_type(expr.type)

        # Numeric conversions
        if source_type == INT:
            if target_type == LONG:
                builder.i2l()
            elif target_type == FLOAT:
                builder.i2f()
            elif target_type == DOUBLE:
                builder.i2d()
            elif target_type == BYTE:
                builder._emit(0x91)  # i2b
            elif target_type == CHAR:
                builder._emit(0x92)  # i2c
            elif target_type == SHORT:
                builder._emit(0x93)  # i2s
        elif source_type == LONG:
            if target_type == INT:
                builder.l2i()
            elif target_type == FLOAT:
                builder.l2f()
            elif target_type == DOUBLE:
                builder.l2d()
        elif source_type == FLOAT:
            if target_type == INT:
                builder.f2i()
            elif target_type == LONG:
                builder.f2l()
            elif target_type == DOUBLE:
                builder.f2d()
        elif source_type == DOUBLE:
            if target_type == INT:
                builder.d2i()
            elif target_type == LONG:
                builder.d2l()
            elif target_type == FLOAT:
                builder.d2f()

        return target_type

    def load_local(self, var: LocalVariable, builder: BytecodeBuilder):
        if var.type == INT or var.type == BOOLEAN or var.type == BYTE or var.type == CHAR or var.type == SHORT:
            builder.iload(var.slot)
        elif var.type == LONG:
            builder.lload(var.slot)
        elif var.type == FLOAT:
            builder.fload(var.slot)
        elif var.type == DOUBLE:
            builder.dload(var.slot)
        elif var.type.is_reference:
            builder.aload(var.slot)

    def store_local(self, var: LocalVariable, builder: BytecodeBuilder):
        if var.type == INT or var.type == BOOLEAN or var.type == BYTE or var.type == CHAR or var.type == SHORT:
            builder.istore(var.slot)
        elif var.type == LONG:
            builder.lstore(var.slot)
        elif var.type == FLOAT:
            builder.fstore(var.slot)
        elif var.type == DOUBLE:
            builder.dstore(var.slot)
        elif var.type.is_reference:
            builder.astore(var.slot)

    def resolve_type(self, t: ast.Type) -> JType:
        """Resolve an AST type to a JType."""
        if isinstance(t, ast.PrimitiveType):
            if t.name in PRIMITIVE_TYPES:
                return PRIMITIVE_TYPES[t.name]
            raise CompileError(f"Unknown primitive type: {t.name}")

        elif isinstance(t, ast.ClassType):
            # Handle void (may come through as ClassType in some cases)
            if t.name == "void":
                return VOID
            # Resolve class name (handles java.lang.* auto-import)
            resolved_name = self._resolve_class_name(t.name)
            return ClassJType(resolved_name)

        elif isinstance(t, ast.ArrayType):
            elem = self.resolve_type(t.element_type)
            return ArrayJType(elem, t.dimensions)

        else:
            raise CompileError(f"Unsupported type: {type(t).__name__}")


def compile_file(source_path: str, output_dir: str = ".", use_rt_jar: bool = True):
    """Compile a Java source file to class file(s)."""
    from .parser import Java8Parser
    from pathlib import Path

    parser = Java8Parser()
    unit = parser.parse_file(source_path)

    # Set up classpath with rt.jar for method resolution
    classpath = None
    if use_rt_jar:
        try:
            classpath = ClassPath()
            classpath.add_rt_jar()
        except FileNotFoundError:
            print("Warning: rt.jar not found, method resolution may be limited")
            classpath = None

    codegen = CodeGenerator(classpath=classpath)
    class_files = codegen.compile(unit)

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    for name, bytecode in class_files.items():
        class_path = output_path / f"{name}.class"
        with open(class_path, "wb") as f:
            f.write(bytecode)
        print(f"Wrote {class_path}")

    # Clean up classpath resources
    if classpath:
        classpath.close()

    return class_files
