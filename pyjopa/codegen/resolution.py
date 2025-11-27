"""
Type and method resolution for the bytecode generator.
"""

from typing import Optional
from .. import ast
from ..types import (
    JType, PrimitiveJType, ClassJType, ArrayJType, MethodType,
    VOID, BOOLEAN, BYTE, CHAR, SHORT, INT, LONG, FLOAT, DOUBLE,
    PRIMITIVE_TYPES,
)
from ..classreader import ClassPath, ClassInfo as ReadClassInfo
from ..classfile import AccessFlags
from .types import (
    CompileError, ResolvedMethod, ResolvedField, LocalMethodInfo, JAVA_LANG_CLASSES,
)


class ResolutionMixin:
    """Mixin providing type and method resolution capabilities."""
    
    # These attributes are defined in CodeGenerator
    class_name: str
    classpath: Optional["ClassPath"]
    _class_cache: dict
    _local_methods: dict
    _local_fields: dict
    
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
                # Exact match
                if len(local_method.param_types) == len(arg_types):
                    return ResolvedMethod(
                        owner=self.class_name,
                        name=method_name,
                        descriptor=local_method.descriptor,
                        is_static=local_method.is_static,
                        is_interface=False,
                        return_type=local_method.return_type,
                        param_types=local_method.param_types,
                        is_varargs=local_method.is_varargs,
                    )
                # Varargs match: n args can match method with m params if m >= 1 and n >= m - 1
                if local_method.is_varargs and local_method.param_types:
                    num_regular_params = len(local_method.param_types) - 1
                    if len(arg_types) >= num_regular_params:
                        # Check regular params
                        regular_match = True
                        for i in range(num_regular_params):
                            if not self._type_assignable(arg_types[i], local_method.param_types[i]):
                                regular_match = False
                                break
                        if regular_match:
                            # Check varargs elements against array element type
                            varargs_param = local_method.param_types[-1]
                            if isinstance(varargs_param, ArrayJType):
                                elem_type = varargs_param.element_type
                                varargs_match = True
                                for i in range(num_regular_params, len(arg_types)):
                                    if not self._type_assignable(arg_types[i], elem_type):
                                        varargs_match = False
                                        break
                                if varargs_match:
                                    return ResolvedMethod(
                                        owner=self.class_name,
                                        name=method_name,
                                        descriptor=local_method.descriptor,
                                        is_static=local_method.is_static,
                                        is_interface=False,
                                        return_type=local_method.return_type,
                                        param_types=local_method.param_types,
                                        is_varargs=True,
                                    )

        if class_name == self.class_name and getattr(self, "super_class_name", None):
            if self.super_class_name != self.class_name:
                inherited = self._find_method(self.super_class_name, method_name, arg_types)
                if inherited:
                    return inherited

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
            if self._is_subclass(from_type.internal_name(), to_type.internal_name()):
                return True

        return False

    def _is_subclass(self, subclass_name: str, superclass_name: str) -> bool:
        """Check if subclass_name extends superclass_name using available class metadata."""
        current = subclass_name
        visited = set()
        while current and current not in visited:
            visited.add(current)
            if current == superclass_name:
                return True

            next_super = None
            if current == self.class_name and getattr(self, "super_class_name", None):
                next_super = self.super_class_name
            else:
                cls = self._lookup_class(current)
                if cls:
                    next_super = cls.super_class

            if not next_super:
                return False
            if next_super == superclass_name:
                return True
            current = next_super
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

    def _find_field(self, class_name: str, field_name: str) -> Optional[ResolvedField]:
        """Find a field in a class or its superclasses."""
        if class_name == self.class_name and hasattr(self, '_local_fields'):
            if field_name in self._local_fields:
                field = self._local_fields[field_name]
                return ResolvedField(
                    owner=self.class_name,
                    descriptor=field.descriptor,
                    type=field.jtype,
                    is_static=field.is_static,
                )

        if class_name == self.class_name and getattr(self, "super_class_name", None):
            if self.super_class_name != self.class_name:
                inherited_field = self._find_field(self.super_class_name, field_name)
                if inherited_field:
                    return inherited_field
            # Search implemented interfaces
            if getattr(self, "class_file", None):
                iface_result = self._find_field_in_interfaces(field_name, getattr(self.class_file, "interfaces", []))
                if iface_result:
                    return iface_result

        cls = self._lookup_class(class_name)
        if not cls:
            return None

        current = cls
        while current:
            for fld in current.fields:
                if fld.name == field_name:
                    jtype = self._descriptor_to_type(fld.descriptor)
                    is_static = (fld.access_flags & AccessFlags.STATIC) != 0
                    return ResolvedField(
                        owner=current.name,
                        descriptor=fld.descriptor,
                        type=jtype,
                        is_static=is_static,
                    )
            if current.super_class:
                current = self._lookup_class(current.super_class)
            else:
                break
        # Search interfaces recursively
        iface_result = self._find_field_in_interfaces(field_name, cls.interfaces if cls else ())
        if iface_result:
            return iface_result
        return None

    def _find_field_in_interfaces(self, field_name: str, interfaces: tuple[str, ...] | list[str]) -> Optional[ResolvedField]:
        for iface_name in interfaces:
            iface = self._lookup_class(iface_name)
            if not iface:
                continue
            for fld in iface.fields:
                if fld.name == field_name:
                    jtype = self._descriptor_to_type(fld.descriptor)
                    is_static = (fld.access_flags & AccessFlags.STATIC) != 0
                    return ResolvedField(
                        owner=iface.name,
                        descriptor=fld.descriptor,
                        type=jtype,
                        is_static=is_static,
                    )
            nested = self._find_field_in_interfaces(field_name, iface.interfaces)
            if nested:
                return nested
        return None

    def _find_constructor(self, class_name: str, arg_types: list[JType]) -> Optional[ResolvedMethod]:
        """Find a constructor in the given class matching the argument types."""
        cls = self._lookup_class(class_name)
        if not cls:
            return None

        candidates = []
        is_interface = (cls.access_flags & AccessFlags.INTERFACE) != 0

        for method in cls.methods:
            if method.name != "<init>":
                continue
            return_type, param_types = self._parse_method_descriptor(method.descriptor)
            if len(param_types) == len(arg_types):
                if self._args_compatible(arg_types, param_types):
                    candidates.append(ResolvedMethod(
                        owner=cls.name,
                        name="<init>",
                        descriptor=method.descriptor,
                        is_static=False,
                        is_interface=is_interface,
                        return_type=return_type,
                        param_types=param_types,
                    ))
            elif (method.access_flags & AccessFlags.VARARGS) and param_types:
                num_regular = len(param_types) - 1
                if len(arg_types) >= num_regular:
                    regular_match = all(
                        self._type_assignable(arg_types[i], param_types[i])
                        for i in range(num_regular)
                    )
                    if regular_match:
                        varargs_param = param_types[-1]
                        if isinstance(varargs_param, ArrayJType):
                            elem_type = varargs_param.element_type
                            varargs_match = all(
                                self._type_assignable(arg_types[i], elem_type)
                                for i in range(num_regular, len(arg_types))
                            )
                            if varargs_match:
                                candidates.append(ResolvedMethod(
                                    owner=cls.name,
                                    name="<init>",
                                    descriptor=method.descriptor,
                                    is_static=False,
                                    is_interface=is_interface,
                                    return_type=return_type,
                                    param_types=param_types,
                                    is_varargs=True,
                                ))

        if candidates:
            return self._most_specific_method(candidates, arg_types)
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
