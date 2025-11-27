"""
Main bytecode generator class.
"""

from typing import Optional
from .. import ast
from ..types import (
    JType, PrimitiveJType, ClassJType, ArrayJType, MethodType,
    VOID, BOOLEAN, BYTE, CHAR, SHORT, INT, LONG, FLOAT, DOUBLE,
)
from ..classfile import (
    ClassFile, MethodInfo, FieldInfo, CodeAttribute, BytecodeBuilder,
    AccessFlags, AnnotationInfo, ExceptionTableEntry, ConstantPoolTag,
)
from ..classreader import ClassPath, ClassInfo as ReadClassInfo, ClassReader

from .types import (
    CompileError, LocalVariable, MethodContext, ResolvedMethod,
    LocalMethodInfo, LocalFieldInfo, JAVA_LANG_CLASSES,
)
from .resolution import ResolutionMixin
from .signatures import SignatureMixin
from .statements import StatementCompilerMixin
from .expressions import ExpressionCompilerMixin
from .arrays import ArrayCompilerMixin
from .boxing import BoxingMixin


class CodeGenerator(
    ResolutionMixin,
    SignatureMixin,
    StatementCompilerMixin,
    ExpressionCompilerMixin,
    ArrayCompilerMixin,
    BoxingMixin,
):
    """Generates bytecode from AST."""

    def __init__(self, classpath: Optional[ClassPath] = None):
        self.class_file: Optional[ClassFile] = None
        self.class_name: str = ""
        self.super_class_name: str = "java/lang/Object"
        self._label_counter = 0
        self.classpath = classpath
        self._class_cache: dict[str, ReadClassInfo] = {}
        self._local_methods: dict[str, list[LocalMethodInfo]] = {}  # method_name -> list of overloads
        self._static_init_sequence: list[tuple[str, any]] = []  # ("field", name, expr) or ("block", block)
        self._instance_init_sequence: list[tuple[str, any]] = []  # ("field", name, expr) or ("block", block)

    def new_label(self, prefix: str = "L") -> str:
        self._label_counter += 1
        return f"{prefix}{self._label_counter}"

    def _resolve_parameter_type(self, param: ast.FormalParameter) -> JType:
        """Resolve parameter type, handling varargs (T... becomes T[])."""
        base_type = self.resolve_type(param.type)
        if param.varargs:
            return ArrayJType(base_type, 1)
        return base_type

    def _constant_value_attribute(self, jtype: JType, initializer: ast.Expression) -> Optional[tuple[int, any]]:
        """Return (tag, value) for ConstantValue if initializer is compile-time constant."""
        if initializer is None:
            return None
        if isinstance(initializer, ast.Literal):
            desc = jtype.descriptor()
            if desc in {"I", "B", "S", "C", "Z"} and initializer.kind in {"int", "boolean", "char"}:
                return (ConstantPoolTag.INTEGER, self.parse_int_literal(initializer.value))
            if desc == "J" and initializer.kind in {"int", "long"}:
                val = self.parse_long_literal(initializer.value) if initializer.kind == "long" else self.parse_int_literal(initializer.value)
                return (ConstantPoolTag.LONG, val)
            if desc == "F" and initializer.kind == "float":
                return (ConstantPoolTag.FLOAT, float(initializer.value.rstrip("fF")))
            if desc == "D" and initializer.kind == "double":
                return (ConstantPoolTag.DOUBLE, float(initializer.value.rstrip("dD")))
            if desc == "Ljava/lang/String;" and initializer.kind == "string":
                return (ConstantPoolTag.STRING, self.parse_string_literal(initializer.value))
        return None

    def _register_local_method(self, method: ast.MethodDeclaration):
        """Register a method for forward reference resolution."""
        is_static = any(m.keyword == "static" for m in method.modifiers)
        return_type = self.resolve_type(method.return_type)
        param_types = tuple(self._resolve_parameter_type(p) for p in method.parameters)
        descriptor = MethodType(return_type, param_types).descriptor()
        is_varargs = bool(method.parameters and method.parameters[-1].varargs)

        info = LocalMethodInfo(
            name=method.name,
            descriptor=descriptor,
            is_static=is_static,
            return_type=return_type,
            param_types=param_types,
            is_varargs=is_varargs,
        )

        if method.name not in self._local_methods:
            self._local_methods[method.name] = []
        self._local_methods[method.name].append(info)

    def _register_local_field(self, field: ast.FieldDeclaration, force_static: bool = False):
        """Register a field for name resolution."""
        is_static = force_static or any(m.keyword == "static" for m in field.modifiers)
        jtype = self.resolve_type(field.type)
        descriptor = jtype.descriptor()

        for decl in field.declarators:
            info = LocalFieldInfo(
                name=decl.name,
                jtype=jtype,
                descriptor=descriptor,
                is_static=is_static,
            )
            self._local_fields[decl.name] = info

    def _collect_field_initializers(self, field: ast.FieldDeclaration, force_static: bool = False):
        is_static = force_static or any(m.keyword == "static" for m in field.modifiers)
        for decl in field.declarators:
            if decl.initializer:
                if is_static:
                    self._static_init_sequence.append(("field", decl.name, decl.initializer))
                else:
                    self._instance_init_sequence.append(("field", decl.name, decl.initializer))

    def compile(self, unit: ast.CompilationUnit) -> dict[str, bytes]:
        """Compile a compilation unit to class files."""
        results = {}

        # Handle package-info.java (no types, but has package with annotations)
        if not unit.types and unit.package and unit.package.annotations:
            class_bytes = self._compile_package_info(unit.package)
            package_path = unit.package.name.replace(".", "/")
            results[f"{package_path}/package-info"] = class_bytes

        for type_decl in unit.types:
            if isinstance(type_decl, ast.ClassDeclaration):
                class_bytes = self.compile_class(type_decl)
                results[type_decl.name] = class_bytes
                self._cache_compiled_class(type_decl.name, class_bytes)
            elif isinstance(type_decl, ast.InterfaceDeclaration):
                class_bytes = self.compile_interface(type_decl)
                results[type_decl.name] = class_bytes
                self._cache_compiled_class(type_decl.name, class_bytes)
        return results

    def _compile_package_info(self, pkg: ast.PackageDeclaration) -> bytes:
        """Compile package-info.java into a synthetic interface class."""
        package_path = pkg.name.replace(".", "/")
        class_name = f"{package_path}/package-info"

        cf = ClassFile(class_name)

        # package-info is a synthetic interface
        cf.access_flags = AccessFlags.INTERFACE | AccessFlags.ABSTRACT | AccessFlags.SYNTHETIC

        # Convert package annotations to class annotations
        cf.annotations = []
        for ann in pkg.annotations:
            ann_info = AnnotationInfo(
                type_descriptor=f"L{self._resolve_class_name(ann.name)};",
                elements={}
            )
            cf.annotations.append(ann_info)

        return cf.to_bytes()

    def _cache_compiled_class(self, internal_name: str, class_bytes: bytes):
        """Cache a compiled class for resolution within the same compile pass."""
        try:
            reader = ClassReader(class_bytes)
            info = reader.read()
            self._class_cache[internal_name] = info
        except Exception as exc:
            raise CompileError(f"Failed to cache compiled class {internal_name}: {exc}") from exc

    def compile_interface(self, iface: ast.InterfaceDeclaration) -> bytes:
        """Compile an interface declaration."""
        self.class_name = iface.name
        self.super_class_name = "java/lang/Object"
        self.class_file = ClassFile(iface.name, super_class=self.super_class_name)
        self.class_file.access_flags = AccessFlags.INTERFACE | AccessFlags.ABSTRACT

        for mod in iface.modifiers:
            if mod.keyword == "public":
                self.class_file.access_flags |= AccessFlags.PUBLIC
            elif mod.keyword == "abstract":
                self.class_file.access_flags |= AccessFlags.ABSTRACT

        iface_names = []
        for ext in iface.extends:
            resolved = self.resolve_type(ext)
            if isinstance(resolved, ClassJType):
                iface_names.append(resolved.internal_name())
            else:
                iface_names.append(str(resolved))
        self.class_file.interfaces = iface_names

        self._class_type_params = {tp.name for tp in iface.type_parameters}
        self.class_file.signature = self._generate_interface_signature(iface)
        self._local_methods = {}
        self._local_fields = {}
        self._static_init_sequence = []
        self._instance_init_sequence = []

        for member in iface.body:
            if isinstance(member, ast.FieldDeclaration):
                self._register_local_field(member, force_static=True)
            elif isinstance(member, ast.MethodDeclaration):
                self._register_local_method(member)

        for member in iface.body:
            if isinstance(member, ast.FieldDeclaration):
                self.compile_interface_field(member)
            elif isinstance(member, ast.MethodDeclaration):
                self.compile_interface_method(member)

        self._compile_static_initializers()

        return self.class_file.to_bytes()

    def compile_class(self, cls: ast.ClassDeclaration) -> bytes:
        """Compile a class declaration."""
        self.class_name = cls.name
        self.super_class_name = "java/lang/Object"
        if cls.extends:
            super_type = self.resolve_type(cls.extends)
            if not isinstance(super_type, ClassJType):
                raise CompileError("Superclass must be a class type")
            self.super_class_name = super_type.internal_name()
        self.class_file = ClassFile(cls.name, super_class=self.super_class_name)
        iface_names = []
        for iface_type in cls.implements:
            resolved = self.resolve_type(iface_type)
            if isinstance(resolved, ClassJType):
                iface_names.append(resolved.internal_name())
            else:
                iface_names.append(str(resolved))
        self.class_file.interfaces = iface_names

        # Store class type parameters for method signature generation
        self._class_type_params = {tp.name for tp in cls.type_parameters}
        self._static_field_inits = []
        self._instance_field_inits = []
        self._static_initializers = []
        self._instance_initializers = []

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

        # First pass: collect field and method signatures for forward references
        self._local_methods = {}
        self._local_fields = {}
        self._static_init_sequence = []
        self._instance_init_sequence = []
        for member in cls.body:
            if isinstance(member, ast.MethodDeclaration):
                self._register_local_method(member)
            elif isinstance(member, ast.FieldDeclaration):
                self._register_local_field(member)
                self._collect_field_initializers(member)
            elif isinstance(member, ast.StaticInitializer):
                self._static_init_sequence.append(("block", member.body))
            elif isinstance(member, ast.InstanceInitializer):
                self._instance_init_sequence.append(("block", member.body))

        # Second pass: compile members
        has_constructor = False
        for member in cls.body:
            if isinstance(member, ast.MethodDeclaration):
                self.compile_method(member)
            elif isinstance(member, ast.FieldDeclaration):
                self.compile_field(member)
            elif isinstance(member, ast.ConstructorDeclaration):
                self.compile_constructor(member)
                has_constructor = True

        # Generate default constructor if none exists
        if not has_constructor:
            self._generate_default_constructor()
        # Generate <clinit> if needed
        self._compile_static_initializers()

        # If class has abstract methods and no abstract modifier, flag error early
        if any(m.access_flags & AccessFlags.ABSTRACT for m in self.class_file.methods):
            if not (self.class_file.access_flags & AccessFlags.ABSTRACT):
                raise CompileError(f"Class {cls.name} contains abstract methods but is not abstract")

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
            const_value = self._constant_value_attribute(jtype, decl.initializer) if decl.initializer else None
            field_info = FieldInfo(
                access_flags=flags,
                name=decl.name,
                descriptor=jtype.descriptor(),
                annotations=annotations,
                constant_value=const_value,
            )
            self.class_file.add_field(field_info)

    def _generate_default_constructor(self):
        """Generate a default no-arg constructor that calls super()."""
        builder = BytecodeBuilder(self.class_file.cp)
        ctx = MethodContext(
            class_name=self.class_name,
            method_name="<init>",
            return_type=VOID,
            builder=builder,
        )
        ctx.add_local("this", ClassJType(self.class_name))

        self._invoke_super_constructor((), ctx)
        self._emit_instance_initializers(ctx)
        builder.return_()

        code_attr = builder.build()
        method_info = MethodInfo(
            access_flags=AccessFlags.PUBLIC,
            name="<init>",
            descriptor="()V",
            code=code_attr,
        )
        self.class_file.add_method(method_info)

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
        param_types = [self._resolve_parameter_type(p) for p in ctor.parameters]
        descriptor = "(" + "".join(t.descriptor() for t in param_types) + ")V"

        # Collect parameter names and annotations for reflection
        parameter_names = [p.name for p in ctor.parameters]
        parameter_annotations = [self._convert_annotations(p.modifiers) for p in ctor.parameters]

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

        body_statements = list(ctor.body.statements)
        invocation = self._extract_constructor_invocation(body_statements[0]) if body_statements else None

        if invocation:
            self._compile_constructor_invocation(invocation, ctx)
            body_statements = body_statements[1:]
        else:
            self._invoke_super_constructor((), ctx)

        self._emit_instance_initializers(ctx)

        if body_statements:
            self.compile_block(ast.Block(statements=tuple(body_statements)), ctx)

        # Add return
        builder.return_()

        method_info = MethodInfo(
            access_flags=flags,
            name="<init>",
            descriptor=descriptor,
            code=builder.build(),
            parameter_names=parameter_names,
            parameter_annotations=parameter_annotations,
        )
        self.class_file.add_method(method_info)

    def _extract_constructor_invocation(self, stmt: Optional[ast.Statement]) -> Optional[ast.ExplicitConstructorInvocation]:
        if isinstance(stmt, ast.ExplicitConstructorInvocation):
            return stmt
        if isinstance(stmt, ast.ExpressionStatement):
            expr = stmt.expression
            if isinstance(expr, ast.MethodInvocation) and expr.target is None and expr.method in {"super", "this"}:
                return ast.ExplicitConstructorInvocation(
                    kind=expr.method,
                    arguments=expr.arguments,
                )
            if isinstance(expr, ast.MethodInvocation) and isinstance(expr.target, ast.SuperExpression) and expr.method in {"", "super"}:
                return ast.ExplicitConstructorInvocation(
                    kind="super",
                    arguments=expr.arguments,
                )
        return None

    def _compile_constructor_invocation(self, invocation: ast.ExplicitConstructorInvocation,
                                        ctx: MethodContext):
        if invocation.type_arguments:
            raise CompileError("Constructor invocation type arguments are not supported")
        if invocation.qualifier is not None:
            raise CompileError("Qualified constructor invocations are not supported")
        if invocation.kind == "this":
            raise CompileError("Constructor chaining with this(...) is not supported")
        if invocation.kind != "super":
            raise CompileError(f"Unsupported constructor invocation kind: {invocation.kind}")
        self._invoke_super_constructor(invocation.arguments, ctx)

    def _invoke_super_constructor(self, arguments: tuple[ast.Expression, ...], ctx: MethodContext):
        arg_types = [self._estimate_expression_type(arg, ctx) for arg in arguments]
        resolved = self._find_constructor(self.super_class_name, arg_types)

        if resolved is None:
            if arguments or self.super_class_name != "java/lang/Object":
                raise CompileError(f"Cannot resolve super constructor in {self.super_class_name}")
            target_owner = self.super_class_name
            descriptor = "()V"
            param_types: tuple[JType, ...] = ()
        else:
            target_owner = resolved.owner
            descriptor = resolved.descriptor
            param_types = resolved.param_types

        builder = ctx.builder
        builder.aload(0)

        if resolved and resolved.is_varargs and param_types:
            num_regular = len(param_types) - 1
            varargs_type = param_types[-1]
            for idx in range(num_regular):
                actual_type = self.compile_expression(arguments[idx], ctx)
                self.emit_conversion(actual_type, param_types[idx], builder)

            if not isinstance(varargs_type, ArrayJType):
                raise CompileError(f"Varargs parameter must be array type, got: {varargs_type}")
            elem_type = varargs_type.element_type

            varargs_args = arguments[num_regular:]
            builder.iconst(len(varargs_args))
            self._emit_newarray(elem_type, builder)

            for idx, arg in enumerate(varargs_args):
                builder.dup()
                builder.iconst(idx)
                actual_type = self.compile_expression(arg, ctx)
                self.emit_conversion(actual_type, elem_type, builder)
                self._emit_array_store(elem_type, builder)
        else:
            for arg, target_type in zip(arguments, param_types):
                actual_type = self.compile_expression(arg, ctx)
                self.emit_conversion(actual_type, target_type, builder)

        arg_slots = sum(t.size for t in param_types)
        builder.invokespecial(target_owner, "<init>", descriptor, arg_slots, 0)

    def _emit_instance_initializers(self, ctx: MethodContext):
        builder = ctx.builder
        for entry in self._instance_init_sequence:
            kind = entry[0]
            if kind == "field":
                name, expr = entry[1], entry[2]
                if name not in self._local_fields:
                    raise CompileError(f"Unknown field for initializer: {name}")
                field_info = self._local_fields[name]
                builder.aload(0)
                value_type = self.compile_expression(expr, ctx)
                self.emit_conversion(value_type, field_info.jtype, builder)
                builder.putfield(self.class_name, name, field_info.descriptor)
            elif kind == "block":
                block = entry[1]
                self.compile_block(block, ctx)

    def _compile_static_initializers(self):
        if not self._static_init_sequence:
            return

        builder = BytecodeBuilder(self.class_file.cp)
        ctx = MethodContext(
            class_name=self.class_name,
            method_name="<clinit>",
            return_type=VOID,
            builder=builder,
        )

        for entry in self._static_init_sequence:
            kind = entry[0]
            if kind == "field":
                name, expr = entry[1], entry[2]
                if name not in self._local_fields:
                    raise CompileError(f"Unknown static field for initializer: {name}")
                field_info = self._local_fields[name]
                value_type = self.compile_expression(expr, ctx)
                self.emit_conversion(value_type, field_info.jtype, builder)
                builder.putstatic(self.class_name, name, field_info.descriptor)
            elif kind == "block":
                block = entry[1]
                self.compile_block(block, ctx)

        builder.return_()

        method_info = MethodInfo(
            access_flags=AccessFlags.STATIC,
            name="<clinit>",
            descriptor="()V",
            code=builder.build(),
        )
        self.class_file.add_method(method_info)

    def compile_interface_field(self, fld: ast.FieldDeclaration):
        """Compile an interface field (implicit public static final)."""
        flags = AccessFlags.PUBLIC | AccessFlags.STATIC | AccessFlags.FINAL
        jtype = self.resolve_type(fld.type)
        annotations = self._convert_annotations(fld.modifiers)
        for decl in fld.declarators:
            const_value = self._constant_value_attribute(jtype, decl.initializer) if decl.initializer else None
            field_info = FieldInfo(
                access_flags=flags,
                name=decl.name,
                descriptor=jtype.descriptor(),
                annotations=annotations,
                constant_value=const_value,
            )
            self.class_file.add_field(field_info)

    def compile_interface_method(self, method: ast.MethodDeclaration):
        """Compile an interface method (abstract)."""
        flags = AccessFlags.PUBLIC
        is_static = False
        is_abstract = True
        for mod in method.modifiers:
            if mod.keyword == "public":
                flags |= AccessFlags.PUBLIC
            elif mod.keyword == "private":
                flags |= AccessFlags.PRIVATE
            elif mod.keyword == "protected":
                flags |= AccessFlags.PROTECTED
            elif mod.keyword == "abstract":
                is_abstract = True
            elif mod.keyword == "static":
                is_static = True
                flags |= AccessFlags.STATIC
            elif mod.keyword == "default":
                is_abstract = False

        if method.body is not None:
            is_abstract = False

        if is_abstract and method.body is not None:
            raise CompileError("Abstract interface method cannot have a body")

        # Default/static methods require Java 8 classfile version
        if method.body is not None and self.class_file.version < ClassFileVersion.JAVA_8:
            raise CompileError("Interface methods with bodies require Java 8 bytecode target")

        if not is_abstract and not is_static:
            flags |= AccessFlags.PUBLIC  # ensure public for default method
        if not is_abstract:
            flags |= AccessFlags.SYNCHRONIZED * 0  # placeholder to keep flags computation explicit

        param_types = [self._resolve_parameter_type(p) for p in method.parameters]
        return_type = self.resolve_type(method.return_type)
        descriptor = MethodType(return_type, tuple(param_types)).descriptor()
        annotations = self._convert_annotations(method.modifiers)
        parameter_names = [p.name for p in method.parameters]
        parameter_annotations = [self._convert_annotations(p.modifiers) for p in method.parameters]

        if is_abstract:
            method_info = MethodInfo(
                access_flags=flags | AccessFlags.ABSTRACT,
                name=method.name,
                descriptor=descriptor,
                code=None,
                annotations=annotations,
                parameter_names=parameter_names,
                parameter_annotations=parameter_annotations,
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

        if not is_static:
            ctx.add_local("this", ClassJType(self.class_name))
        for param, jtype in zip(method.parameters, param_types):
            ctx.add_local(param.name, jtype)

        self.compile_block(method.body or ast.Block(statements=()), ctx)
        if return_type == VOID:
            builder.return_()

        method_info = MethodInfo(
            access_flags=flags,
            name=method.name,
            descriptor=descriptor,
            code=builder.build(),
            annotations=annotations,
            parameter_names=parameter_names,
            parameter_annotations=parameter_annotations,
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

        # Check for varargs
        if method.parameters and method.parameters[-1].varargs:
            flags |= AccessFlags.VARARGS

        # Build method descriptor
        param_types = [self._resolve_parameter_type(p) for p in method.parameters]
        return_type = self.resolve_type(method.return_type)
        descriptor = MethodType(return_type, tuple(param_types)).descriptor()

        # Collect annotations
        annotations = self._convert_annotations(method.modifiers)

        # Collect throws as internal names
        throws_list = [self._resolve_class_name(t.name) if isinstance(t, ast.ClassType) else str(t)
                       for t in method.throws]

        # Collect parameter names and annotations for reflection
        parameter_names = [p.name for p in method.parameters]
        parameter_annotations = [self._convert_annotations(p.modifiers) for p in method.parameters]

        # Abstract/native methods have no code
        if method.body is None:
            method_info = MethodInfo(
                access_flags=flags,
                name=method.name,
                descriptor=descriptor,
                code=None,
                annotations=annotations,
                exceptions=throws_list,
                parameter_names=parameter_names,
                parameter_annotations=parameter_annotations,
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
            exceptions=throws_list,
            parameter_names=parameter_names,
            parameter_annotations=parameter_annotations,
        )
        self.class_file.add_method(method_info)



def compile_file(source_path: str, output_dir: str = ".", use_rt_jar: bool = True):
    """Compile a Java source file to class file(s)."""
    from ..parser import Java8Parser
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
