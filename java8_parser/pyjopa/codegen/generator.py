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
    AccessFlags, AnnotationInfo, ExceptionTableEntry,
)
from ..classreader import ClassPath, ClassInfo as ReadClassInfo

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
        self._label_counter = 0
        self.classpath = classpath
        self._class_cache: dict[str, ReadClassInfo] = {}
        self._local_methods: dict[str, list[LocalMethodInfo]] = {}  # method_name -> list of overloads

    def new_label(self, prefix: str = "L") -> str:
        self._label_counter += 1
        return f"{prefix}{self._label_counter}"

    def _resolve_parameter_type(self, param: ast.FormalParameter) -> JType:
        """Resolve parameter type, handling varargs (T... becomes T[])."""
        base_type = self.resolve_type(param.type)
        if param.varargs:
            return ArrayJType(base_type, 1)
        return base_type

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

    def _register_local_field(self, field: ast.FieldDeclaration):
        """Register a field for name resolution."""
        is_static = any(m.keyword == "static" for m in field.modifiers)
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

        # First pass: collect field and method signatures for forward references
        self._local_methods = {}
        self._local_fields = {}
        for member in cls.body:
            if isinstance(member, ast.MethodDeclaration):
                self._register_local_method(member)
            elif isinstance(member, ast.FieldDeclaration):
                self._register_local_field(member)

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

    def _generate_default_constructor(self):
        """Generate a default no-arg constructor that calls super()."""
        builder = BytecodeBuilder(self.class_file.cp)
        builder.max_locals = 1  # slot 0 for 'this'

        # aload_0 (load this)
        builder.aload(0)
        # invokespecial java/lang/Object.<init>()V
        builder.invokespecial("java/lang/Object", "<init>", "()V", 0, 0)
        # return
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
            code=builder.build(),
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
