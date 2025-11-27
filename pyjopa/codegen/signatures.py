"""
Signature and annotation generation for the bytecode generator.
"""

from typing import Optional
from .. import ast
from ..classfile import AnnotationInfo
from .types import CompileError, JAVA_LANG_CLASSES


class SignatureMixin:
    """Mixin providing signature and annotation generation."""
    
    # These methods are expected from other mixins
    _resolve_class_name: callable
    resolve_type: callable
    parse_int_literal: callable
    parse_long_literal: callable
    parse_escape: callable
    parse_string_literal: callable
    
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
        if isinstance(ta, ast.TypeArgument):
            if ta.wildcard == "extends" and ta.type:
                return "+" + self._generate_type_signature(ta.type)
            elif ta.wildcard == "super" and ta.type:
                return "-" + self._generate_type_signature(ta.type)
            elif ta.wildcard and not ta.type:
                return "*"  # Unbounded wildcard
            else:
                # Regular type argument
                return self._generate_type_signature(ta.type) if ta.type else "*"
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

    def _generate_interface_signature(self, iface: ast.InterfaceDeclaration) -> Optional[str]:
        """Generate interface signature if it has type parameters."""
        if not iface.type_parameters and not iface.extends:
            return None
        self._type_param_names = {tp.name for tp in iface.type_parameters}
        sig = ""
        if iface.type_parameters:
            sig += self._generate_type_params_signature(iface.type_parameters)
        if iface.extends:
            for ext in iface.extends:
                sig += self._generate_type_signature(ext)
        else:
            sig += "Ljava/lang/Object;"
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
        elif isinstance(type_node, ast.TypeArgument):
            # Wildcards always require signature generation
            return True
        return False
