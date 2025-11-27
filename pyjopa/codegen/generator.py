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
    ClassFileVersion,
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
        self._single_type_imports: dict[str, str] = {}  # short name -> full name
        self._wildcard_imports: list[str] = []  # list of package prefixes
        self._current_package: str = ""  # current package as internal name (e.g., "com/example")

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

        # Set up method type parameters for type erasure
        saved_type_params = self._type_params.copy() if hasattr(self, '_type_params') else {}
        if not hasattr(self, '_type_params'):
            self._type_params = {}
        for tp in method.type_parameters:
            self._type_params[tp.name] = tp

        # Now resolve types with erasure
        return_type = self.resolve_type(method.return_type)
        param_types = tuple(self._resolve_parameter_type(p) for p in method.parameters)
        descriptor = MethodType(return_type, param_types).descriptor()
        is_varargs = bool(method.parameters and method.parameters[-1].varargs)

        # Restore type parameters
        self._type_params = saved_type_params

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

    def _process_imports(self, imports: tuple[ast.ImportDeclaration, ...]):
        """Process import declarations for name resolution."""
        for imp in imports:
            if imp.is_static:
                # TODO: Handle static imports
                continue

            if imp.is_wildcard:
                # Wildcard import: import java.util.*;
                self._wildcard_imports.append(imp.name.replace(".", "/"))
            else:
                # Single-type import: import java.util.List;
                full_name = imp.name.replace(".", "/")
                short_name = full_name.split("/")[-1]
                self._single_type_imports[short_name] = full_name

    def compile(self, unit: ast.CompilationUnit) -> dict[str, bytes]:
        """Compile a compilation unit to class files."""
        results = {}

        # Process imports for name resolution
        self._process_imports(unit.imports)

        # Store package prefix for class naming
        package_prefix = ""
        if unit.package:
            package_prefix = unit.package.name.replace(".", "/") + "/"
            self._current_package = package_prefix.rstrip("/")
        else:
            self._current_package = ""

        # Handle package-info.java (no types, but has package with annotations)
        if not unit.types and unit.package and unit.package.annotations:
            class_bytes = self._compile_package_info(unit.package)
            package_path = unit.package.name.replace(".", "/")
            results[f"{package_path}/package-info"] = class_bytes

        for type_decl in unit.types:
            # Prepend package to type name for bytecode generation
            if isinstance(type_decl, ast.ClassDeclaration):
                # Temporarily modify the class name to include package
                original_name = type_decl.name
                if package_prefix:
                    # Pass package prefix (with trailing /) so it's distinguished from nested class
                    class_files = self.compile_class(type_decl, outer_class=package_prefix)
                else:
                    class_files = self.compile_class(type_decl)
                for name, bytecode in class_files.items():
                    results[name] = bytecode
                    self._cache_compiled_class(name, bytecode)
            elif isinstance(type_decl, ast.InterfaceDeclaration):
                if package_prefix:
                    class_bytes = self.compile_interface(type_decl, outer_class=package_prefix)
                else:
                    class_bytes = self.compile_interface(type_decl)
                # Get the actual name from the compiled class
                reader = ClassReader(class_bytes)
                info = reader.read()
                results[info.name] = class_bytes
                self._cache_compiled_class(info.name, class_bytes)
            elif isinstance(type_decl, ast.EnumDeclaration):
                if package_prefix:
                    class_bytes = self.compile_enum(type_decl, outer_class=package_prefix)
                else:
                    class_bytes = self.compile_enum(type_decl)
                # Get the actual name from the compiled class
                reader = ClassReader(class_bytes)
                info = reader.read()
                results[info.name] = class_bytes
                self._cache_compiled_class(info.name, class_bytes)
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

    def compile_interface(self, iface: ast.InterfaceDeclaration, outer_class: Optional[str] = None) -> bytes:
        """Compile an interface declaration.
        If outer_class contains '/', it's treated as a package prefix, otherwise as a nested class."""
        if outer_class:
            if "/" in outer_class:
                # Package prefix (may have trailing /)
                package = outer_class.rstrip("/")
                self.class_name = f"{package}/{iface.name}"
            else:
                # Nested class
                self.class_name = f"{outer_class}${iface.name}"
        else:
            self.class_name = iface.name
        self.super_class_name = "java/lang/Object"

        # Check if we need Java 8 for default/static methods
        needs_java8 = any(
            isinstance(member, ast.MethodDeclaration) and member.body is not None
            for member in iface.body
        )
        version = ClassFileVersion.JAVA_8 if needs_java8 else ClassFileVersion.JAVA_6

        self.class_file = ClassFile(self.class_name, super_class=self.super_class_name, version=version)
        self.class_file.access_flags = AccessFlags.INTERFACE | AccessFlags.ABSTRACT

        # Check for @FunctionalInterface annotation
        has_functional_annotation = False
        for mod in iface.modifiers:
            if mod.keyword == "public":
                self.class_file.access_flags |= AccessFlags.PUBLIC
            elif mod.keyword == "abstract":
                self.class_file.access_flags |= AccessFlags.ABSTRACT
            elif isinstance(mod, ast.Annotation) and mod.name == "FunctionalInterface":
                has_functional_annotation = True

        # Validate @FunctionalInterface if present
        if has_functional_annotation:
            abstract_methods = []
            for member in iface.body:
                if isinstance(member, ast.MethodDeclaration):
                    is_abstract = True
                    is_static = False
                    has_default = False
                    for m in member.modifiers:
                        if m.keyword == "static":
                            is_static = True
                        elif m.keyword == "default":
                            has_default = True
                    if member.body is not None:
                        is_abstract = False
                    if is_abstract and not is_static and not has_default:
                        abstract_methods.append(member.name)

            if len(abstract_methods) != 1:
                raise CompileError(f"@FunctionalInterface {iface.name} must have exactly one abstract method, found {len(abstract_methods)}: {', '.join(abstract_methods) if abstract_methods else 'none'}")

        for mod in iface.modifiers:
            pass  # Already processed above

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

    def compile_enum(self, enum: ast.EnumDeclaration, outer_class: Optional[str] = None) -> bytes:
        """Compile an enum declaration as a class extending java.lang.Enum.
        If outer_class contains '/', it's treated as a package prefix, otherwise as a nested class."""
        if outer_class:
            if "/" in outer_class:
                # Package prefix (may have trailing /)
                package = outer_class.rstrip("/")
                self.class_name = f"{package}/{enum.name}"
            else:
                # Nested class
                self.class_name = f"{outer_class}${enum.name}"
        else:
            self.class_name = enum.name
        self.super_class_name = "java/lang/Enum"
        self.class_file = ClassFile(self.class_name, super_class=self.super_class_name)

        # Enums are final classes with ENUM flag
        flags = AccessFlags.SUPER | AccessFlags.FINAL | AccessFlags.ENUM
        for mod in enum.modifiers:
            if mod.keyword == "public":
                flags |= AccessFlags.PUBLIC
            elif mod.keyword == "private":
                flags |= AccessFlags.PRIVATE
            elif mod.keyword == "protected":
                flags |= AccessFlags.PROTECTED
        self.class_file.access_flags = flags

        # Implement interfaces
        iface_names = []
        for iface_type in enum.implements:
            resolved = self.resolve_type(iface_type)
            if isinstance(resolved, ClassJType):
                iface_names.append(resolved.internal_name())
            else:
                iface_names.append(str(resolved))
        self.class_file.interfaces = iface_names

        # Generate generic signature: Enum<EnumName>
        self.class_file.signature = f"Ljava/lang/Enum<L{enum.name};>;"

        self._class_type_params = set()
        self._local_methods = {}
        self._local_fields = {}
        self._static_init_sequence = []
        self._instance_init_sequence = []

        # Register enum constants as fields
        for const in enum.constants:
            self._local_fields[const.name] = LocalFieldInfo(
                name=const.name,
                jtype=ClassJType(enum.name),
                descriptor=f"L{enum.name};",
                is_static=True,
            )

        # Register methods from body
        for member in enum.body:
            if isinstance(member, ast.MethodDeclaration):
                self._register_local_method(member)
            elif isinstance(member, ast.FieldDeclaration):
                self._register_local_field(member)

        # Add enum constant fields
        for const in enum.constants:
            field_info = FieldInfo(
                access_flags=AccessFlags.PUBLIC | AccessFlags.STATIC | AccessFlags.FINAL | AccessFlags.ENUM,
                name=const.name,
                descriptor=f"L{enum.name};",
                annotations=self._convert_annotations(const.annotations),
            )
            self.class_file.add_field(field_info)

        # Add synthetic $VALUES array field
        values_field = FieldInfo(
            access_flags=AccessFlags.PRIVATE | AccessFlags.STATIC | AccessFlags.FINAL | AccessFlags.SYNTHETIC,
            name="$VALUES",
            descriptor=f"[L{enum.name};",
        )
        self.class_file.add_field(values_field)

        # Compile methods from body (except constructors - we handle those specially)
        user_constructor = None
        for member in enum.body:
            if isinstance(member, ast.ConstructorDeclaration):
                user_constructor = member
            elif isinstance(member, ast.MethodDeclaration):
                self.compile_method(member)
            elif isinstance(member, ast.FieldDeclaration):
                self.compile_field(member)

        # Generate constructor with user parameters if provided
        self._generate_enum_constructor(enum, user_constructor)

        # Generate static initializer that creates enum constants
        self._generate_enum_static_initializer(enum)

        # Generate values() method
        self._generate_enum_values_method(enum)

        # Generate valueOf(String) method
        self._generate_enum_valueof_method(enum)

        return self.class_file.to_bytes()

    def _generate_enum_constructor(self, enum: ast.EnumDeclaration, user_constructor: Optional[ast.MethodDeclaration] = None):
        """Generate private constructor for enum with user parameters if provided."""
        builder = BytecodeBuilder(self.class_file.cp)
        ctx = MethodContext(
            class_name=self.class_name,
            method_name="<init>",
            return_type=VOID,
            builder=builder,
        )

        # this, name, ordinal (always present)
        ctx.add_local("this", ClassJType(self.class_name))
        ctx.add_local("name", ClassJType("java/lang/String"))
        ctx.add_local("ordinal", INT)

        # Build descriptor with user parameters
        descriptor_parts = ["Ljava/lang/String;", "I"]
        if user_constructor:
            # Add user parameters to context and descriptor
            for param in user_constructor.parameters:
                param_type = self.resolve_type(param.type)
                ctx.add_local(param.name, param_type)
                descriptor_parts.append(param_type.descriptor())

        descriptor = f"({''.join(descriptor_parts)})V"

        # Call super(String, int)
        builder.aload(0)  # this
        builder.aload(1)  # name
        builder.iload(2)  # ordinal
        builder.invokespecial("java/lang/Enum", "<init>", "(Ljava/lang/String;I)V", 3, 0)

        # Compile user constructor body if provided
        if user_constructor and user_constructor.body:
            for stmt in user_constructor.body.statements:
                self.compile_statement(stmt, ctx)

        builder.return_()

        method_info = MethodInfo(
            access_flags=AccessFlags.PRIVATE,
            name="<init>",
            descriptor=descriptor,
            code=builder.build(),
        )
        self.class_file.add_method(method_info)

    def _generate_enum_static_initializer(self, enum: ast.EnumDeclaration):
        """Generate <clinit> that initializes enum constants."""
        builder = BytecodeBuilder(self.class_file.cp)
        ctx = MethodContext(
            class_name=self.class_name,
            method_name="<clinit>",
            return_type=VOID,
            builder=builder,
        )

        # Create each enum constant
        for ordinal, const in enumerate(enum.constants):
            # new EnumName("CONST_NAME", ordinal, ...user_args)
            builder.new(self.class_name)
            builder.dup()
            builder.ldc_string(const.name)
            builder.iconst(ordinal)

            # Compile user arguments
            descriptor_parts = ["Ljava/lang/String;", "I"]
            args_slots = 3  # this + name + ordinal
            for arg in const.arguments:
                arg_type = self.compile_expression(arg, ctx)
                descriptor_parts.append(arg_type.descriptor())
                args_slots += arg_type.size

            descriptor = f"({''.join(descriptor_parts)})V"
            builder.invokespecial(self.class_name, "<init>", descriptor, args_slots, 0)
            # Store in static field
            builder.putstatic(self.class_name, const.name, f"L{self.class_name};")

        # Create $VALUES array
        builder.iconst(len(enum.constants))
        builder.anewarray(self.class_name)

        # Fill array
        for ordinal, const in enumerate(enum.constants):
            builder.dup()
            builder.iconst(ordinal)
            builder.getstatic(self.class_name, const.name, f"L{self.class_name};")
            builder.aastore()

        # Store in $VALUES
        builder.putstatic(self.class_name, "$VALUES", f"[L{self.class_name};")

        builder.return_()

        method_info = MethodInfo(
            access_flags=AccessFlags.STATIC,
            name="<clinit>",
            descriptor="()V",
            code=builder.build(),
        )
        self.class_file.add_method(method_info)

    def _generate_enum_values_method(self, enum: ast.EnumDeclaration):
        """Generate public static values() method."""
        builder = BytecodeBuilder(self.class_file.cp)
        ctx = MethodContext(
            class_name=self.class_name,
            method_name="values",
            return_type=ArrayJType(ClassJType(self.class_name), 1),
            builder=builder,
        )

        # return $VALUES.clone()
        builder.getstatic(self.class_name, "$VALUES", f"[L{self.class_name};")
        builder.invokevirtual(f"[L{self.class_name};", "clone", "()Ljava/lang/Object;", 0, 1)
        builder.checkcast(f"[L{self.class_name};")
        builder.areturn()

        method_info = MethodInfo(
            access_flags=AccessFlags.PUBLIC | AccessFlags.STATIC,
            name="values",
            descriptor=f"()[L{self.class_name};",
            code=builder.build(),
        )
        self.class_file.add_method(method_info)

    def _generate_enum_valueof_method(self, enum: ast.EnumDeclaration):
        """Generate public static valueOf(String) method."""
        builder = BytecodeBuilder(self.class_file.cp)
        ctx = MethodContext(
            class_name=self.class_name,
            method_name="valueOf",
            return_type=ClassJType(self.class_name),
            builder=builder,
        )
        ctx.add_local("name", ClassJType("java/lang/String"))

        # return Enum.valueOf(EnumName.class, name)
        builder.ldc_class(self.class_name)
        builder.aload(0)  # name parameter
        builder.invokestatic("java/lang/Enum", "valueOf", "(Ljava/lang/Class;Ljava/lang/String;)Ljava/lang/Enum;", 2, 1)
        builder.checkcast(self.class_name)
        builder.areturn()

        method_info = MethodInfo(
            access_flags=AccessFlags.PUBLIC | AccessFlags.STATIC,
            name="valueOf",
            descriptor=f"(Ljava/lang/String;)L{self.class_name};",
            code=builder.build(),
        )
        self.class_file.add_method(method_info)

    def compile_class(self, cls: ast.ClassDeclaration, outer_class: Optional[str] = None) -> dict[str, bytes]:
        """Compile a class declaration. Returns dict of class_name -> bytecode.
        For nested classes, includes both outer and inner class files.
        If outer_class contains '/', it's treated as a package prefix, otherwise as a nested class."""
        # Determine the full class name (Outer$Inner for nested classes, package/Class for packages)
        if outer_class:
            if "/" in outer_class:
                # Package prefix (may have trailing /)
                package = outer_class.rstrip("/")
                self.class_name = f"{package}/{cls.name}"
            else:
                # Nested class
                self.class_name = f"{outer_class}${cls.name}"
        else:
            self.class_name = cls.name
        self.super_class_name = "java/lang/Object"
        if cls.extends:
            super_type = self.resolve_type(cls.extends)
            if not isinstance(super_type, ClassJType):
                raise CompileError("Superclass must be a class type")
            self.super_class_name = super_type.internal_name()
        self.class_file = ClassFile(self.class_name, super_class=self.super_class_name)
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

        # Set up type parameters for type erasure
        self._type_params = {tp.name: tp for tp in cls.type_parameters}

        # Store class type parameters for method signature generation
        self.current_class_type_params = cls.type_parameters

        # First pass: collect field and method signatures for forward references
        self._local_methods = {}
        self._local_fields = {}
        self._static_init_sequence = []
        self._instance_init_sequence = []

        # Register outer class fields and methods BEFORE compiling nested classes
        # (so nested classes can access them)
        for member in cls.body:
            if isinstance(member, ast.MethodDeclaration):
                self._register_local_method(member)
            elif isinstance(member, ast.FieldDeclaration):
                self._register_local_field(member)

        # First pass: compile nested classes (they need to be available for lookup)
        # Save current state before compiling nested classes
        saved_class_name = self.class_name
        saved_class_file = self.class_file
        saved_super_class = self.super_class_name
        saved_static_init_sequence = list(self._static_init_sequence)  # Make a copy
        saved_instance_init_sequence = list(self._instance_init_sequence)  # Make a copy
        saved_local_methods = dict(self._local_methods)  # Make a copy
        saved_local_fields = dict(self._local_fields)  # Make a copy

        nested_classes = {}
        for member in cls.body:
            if isinstance(member, ast.ClassDeclaration):
                nested_results = self.compile_class(member, outer_class=saved_class_name)
                nested_classes.update(nested_results)
                # Cache the nested classes immediately
                for name, bytecode in nested_results.items():
                    self._cache_compiled_class(name, bytecode)
            elif isinstance(member, ast.InterfaceDeclaration):
                nested_bytecode = self.compile_interface(member, outer_class=saved_class_name)
                nested_name = f"{saved_class_name}${member.name}"
                nested_classes[nested_name] = nested_bytecode
                self._cache_compiled_class(nested_name, nested_bytecode)
            elif isinstance(member, ast.EnumDeclaration):
                nested_bytecode = self.compile_enum(member, outer_class=saved_class_name)
                nested_name = f"{saved_class_name}${member.name}"
                nested_classes[nested_name] = nested_bytecode
                self._cache_compiled_class(nested_name, nested_bytecode)

        # Restore state after compiling nested classes
        self.class_name = saved_class_name
        self.class_file = saved_class_file
        self.super_class_name = saved_super_class
        self._static_init_sequence = saved_static_init_sequence
        self._instance_init_sequence = saved_instance_init_sequence
        self._local_methods = saved_local_methods
        self._local_fields = saved_local_fields

        # Check if this is a non-static inner class
        # (outer_class with "/" is a package prefix, not an outer class)
        is_static = any(mod.keyword == "static" for mod in cls.modifiers)
        is_package = outer_class and "/" in outer_class
        self.is_inner_class = outer_class is not None and not is_static and not is_package
        self.outer_class_name = outer_class if self.is_inner_class else None

        # For non-static inner classes, add synthetic this$0 field
        if self.is_inner_class:
            this0_field = FieldInfo(
                name="this$0",
                descriptor=f"L{outer_class};",
                access_flags=AccessFlags.FINAL | AccessFlags.SYNTHETIC
            )
            self.class_file.add_field(this0_field)
            # Register in _local_fields for method resolution
            self._local_fields["this$0"] = ClassJType(outer_class)

        # Second pass: collect field initializers and initializer blocks
        for member in cls.body:
            if isinstance(member, ast.FieldDeclaration):
                self._collect_field_initializers(member)
            elif isinstance(member, ast.StaticInitializer):
                self._static_init_sequence.append(("block", member.body))
            elif isinstance(member, ast.InstanceInitializer):
                self._instance_init_sequence.append(("block", member.body))

        # Third pass: compile members
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

        # Add InnerClasses attribute entries
        from ..classfile import InnerClassInfo
        if outer_class:
            # This is a nested class - add entry for itself
            # Determine access flags from class modifiers
            inner_flags = 0
            for mod in cls.modifiers:
                if mod.keyword == "public":
                    inner_flags |= AccessFlags.PUBLIC
                elif mod.keyword == "private":
                    inner_flags |= AccessFlags.PRIVATE
                elif mod.keyword == "protected":
                    inner_flags |= AccessFlags.PROTECTED
                elif mod.keyword == "static":
                    inner_flags |= AccessFlags.STATIC
                elif mod.keyword == "final":
                    inner_flags |= AccessFlags.FINAL
                elif mod.keyword == "abstract":
                    inner_flags |= AccessFlags.ABSTRACT
            self.class_file.inner_classes.append(
                InnerClassInfo(
                    inner_class=self.class_name,  # e.g., "Outer$Inner"
                    outer_class=outer_class,      # e.g., "Outer"
                    inner_name=cls.name,          # e.g., "Inner"
                    access_flags=inner_flags
                )
            )
        else:
            # This is an outer class - add entries for all nested classes
            for member in cls.body:
                if isinstance(member, ast.ClassDeclaration):
                    nested_name = f"{self.class_name}${member.name}"
                    # Determine access flags from nested class modifiers
                    inner_flags = 0
                    for mod in member.modifiers:
                        if mod.keyword == "public":
                            inner_flags |= AccessFlags.PUBLIC
                        elif mod.keyword == "private":
                            inner_flags |= AccessFlags.PRIVATE
                        elif mod.keyword == "protected":
                            inner_flags |= AccessFlags.PROTECTED
                        elif mod.keyword == "static":
                            inner_flags |= AccessFlags.STATIC
                        elif mod.keyword == "final":
                            inner_flags |= AccessFlags.FINAL
                        elif mod.keyword == "abstract":
                            inner_flags |= AccessFlags.ABSTRACT
                    self.class_file.inner_classes.append(
                        InnerClassInfo(
                            inner_class=nested_name,     # e.g., "Outer$Inner"
                            outer_class=self.class_name, # e.g., "Outer"
                            inner_name=member.name,      # e.g., "Inner"
                            access_flags=inner_flags
                        )
                    )

        # Return all class files (this class + nested classes)
        result = {self.class_name: self.class_file.to_bytes()}
        result.update(nested_classes)
        return result

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
            # ConstantValue attribute only for static final fields
            is_static = flags & AccessFlags.STATIC
            is_final = flags & AccessFlags.FINAL
            const_value = None
            if is_static and is_final and decl.initializer:
                const_value = self._constant_value_attribute(jtype, decl.initializer)
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

        # For inner classes, add outer instance parameter
        if self.is_inner_class:
            ctx.add_local("this$0", ClassJType(self.outer_class_name))
            descriptor = f"(L{self.outer_class_name};)V"
        else:
            descriptor = "()V"

        self._invoke_super_constructor((), ctx)

        # For inner classes, store outer instance in this$0 field
        if self.is_inner_class:
            builder.aload(0)  # load this
            builder.aload(1)  # load outer instance
            builder.putfield(self.class_name, "this$0", f"L{self.outer_class_name};")

        self._emit_instance_initializers(ctx)
        builder.return_()

        code_attr = builder.build()
        method_info = MethodInfo(
            access_flags=AccessFlags.PUBLIC,
            name="<init>",
            descriptor=descriptor,
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

        # For inner classes, prepend outer instance to descriptor
        if self.is_inner_class:
            descriptor = f"(L{self.outer_class_name};{''.join(t.descriptor() for t in param_types)})V"
        else:
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

        # For inner classes, add outer instance as first parameter
        if self.is_inner_class:
            ctx.add_local("this$0", ClassJType(self.outer_class_name))

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

        # For inner classes, store outer instance in this$0 field
        if self.is_inner_class:
            builder.aload(0)  # load this
            builder.aload(1)  # load outer instance (first parameter after this)
            builder.putfield(self.class_name, "this$0", f"L{self.outer_class_name};")

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
            # ConstantValue attribute only for static final fields
            is_static = flags & AccessFlags.STATIC
            is_final = flags & AccessFlags.FINAL
            const_value = None
            if is_static and is_final and decl.initializer:
                const_value = self._constant_value_attribute(jtype, decl.initializer)
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

        # Save class-level type params and add method type params for erasure
        saved_type_params = self._type_params.copy() if hasattr(self, '_type_params') else {}
        if not hasattr(self, '_type_params'):
            self._type_params = {}
        for tp in method.type_parameters:
            self._type_params[tp.name] = tp

        # Build method descriptor (with type erasure)
        param_types = [self._resolve_parameter_type(p) for p in method.parameters]
        return_type = self.resolve_type(method.return_type)
        descriptor = MethodType(return_type, tuple(param_types)).descriptor()

        # Generate method signature for generics
        class_type_params = {tp.name for tp in getattr(self, 'current_class_type_params', [])}
        method_signature = self._generate_method_signature(method, class_type_params)

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
                signature=method_signature,
                annotations=annotations,
                exceptions=throws_list,
                parameter_names=parameter_names,
                parameter_annotations=parameter_annotations,
            )
            self.class_file.add_method(method_info)
            # Restore class-level type params
            self._type_params = saved_type_params
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
            signature=method_signature,
            annotations=annotations,
            exceptions=throws_list,
            parameter_names=parameter_names,
            parameter_annotations=parameter_annotations,
        )
        self.class_file.add_method(method_info)

        # Generate bridge method if needed
        if not is_static and not method.name.startswith("<"):
            self._generate_bridge_method_if_needed(method, descriptor, return_type, param_types)

        # Restore class-level type params
        self._type_params = saved_type_params

    def _generate_bridge_method_if_needed(self, method: ast.MethodDeclaration,
                                          child_descriptor: str,
                                          child_return_type: JType,
                                          child_param_types: list[JType]):
        """Generate a bridge method if the child method has a different descriptor than the parent."""
        # Only for classes with a superclass
        if not hasattr(self, 'super_class_name') or not self.super_class_name:
            return

        # Look for a method with the same name in the superclass
        parent_method = self._find_method(self.super_class_name, method.name, child_param_types)
        if not parent_method:
            return

        # If descriptors are the same, no bridge needed
        if parent_method.descriptor == child_descriptor:
            return

        # Generate bridge method with parent's descriptor
        builder = BytecodeBuilder(self.class_file.cp)

        # Load 'this'
        builder.aload(0)

        # Load and convert arguments
        slot = 1  # Slot 0 is 'this'
        for i, parent_param_type in enumerate(parent_method.param_types):
            # Load argument
            if parent_param_type == LONG or parent_param_type == DOUBLE:
                if parent_param_type == LONG:
                    builder.lload(slot)
                else:
                    builder.dload(slot)
                slot += 2
            elif parent_param_type.is_reference:
                builder.aload(slot)
                # Cast to child parameter type if needed
                if i < len(child_param_types):
                    child_param_type = child_param_types[i]
                    if child_param_type != parent_param_type:
                        builder.checkcast(child_param_type.internal_name())
                slot += 1
            else:  # int, float, boolean, etc.
                if parent_param_type == FLOAT:
                    builder.fload(slot)
                else:
                    builder.iload(slot)
                slot += 1

        # Call the real method
        builder.invokevirtual(
            self.class_name,
            method.name,
            child_descriptor,
            sum(t.size for t in child_param_types) + 1,  # +1 for 'this'
            0 if child_return_type == VOID else child_return_type.size
        )

        # Return
        if child_return_type == VOID:
            builder.return_()
        elif child_return_type == LONG:
            builder.lreturn()
        elif child_return_type == DOUBLE:
            builder.dreturn()
        elif child_return_type == FLOAT:
            builder.freturn()
        elif child_return_type.is_reference:
            builder.areturn()
        else:
            builder.ireturn()

        # Set max_locals: 1 (this) + sum of parameter sizes
        builder.max_locals = 1 + sum(t.size for t in parent_method.param_types)

        # Create bridge method info
        bridge_method = MethodInfo(
            access_flags=AccessFlags.PUBLIC | AccessFlags.BRIDGE | AccessFlags.SYNTHETIC,
            name=method.name,
            descriptor=parent_method.descriptor,
            code=builder.build(),
            annotations=[],
            exceptions=[],
            parameter_names=[],
            parameter_annotations=[],
        )
        self.class_file.add_method(bridge_method)


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
        # Create package directories if needed
        class_path.parent.mkdir(parents=True, exist_ok=True)
        with open(class_path, "wb") as f:
            f.write(bytecode)
        print(f"Wrote {class_path}")

    # Clean up classpath resources
    if classpath:
        classpath.close()

    return class_files
