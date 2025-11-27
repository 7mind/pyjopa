# Roadmap Progress Log

## Session Summary

**Phase 1: Core Language Completeness - COMPLETE**
- Superclass support: classes now honor real superclasses, resolve inherited fields/methods, and call correct super constructors (including varargs). Instantiation of interfaces/abstract classes is blocked when metadata is available.
- Constructor handling: explicit `super(...)`/`this(...)` calls parsed and executed; compiled classes are cached for intra-run resolution.
- Initializers: static/instance field initializers and initializer blocks are sequenced into `<clinit>` and constructors; field literals emit ConstantValue attributes compatible with the class reader.
- Interface support: `implements` parsed; interfaces compile with ACC_INTERFACE/ABSTRACT and inherited interfaces recorded; interface constants resolve across hierarchies; `invokeinterface` emitted for interface dispatch. Default/static interface methods are currently rejected for Java 6 target.
- Abstract classes: ACC_ABSTRACT flag on classes and methods; abstract methods have no code; instantiation prevented at compile-time when metadata is available.
- Labeled statements: break/continue with labels now fully supported; parser workaround for grammar ambiguity where "break label;" was misparsed as variable declaration.
- Parser fixes: `super` becomes `SuperExpression`; enum constants and bodies populate correctly; break/continue with labels handled.
- Tests: added `InheritanceSuper`, `SuperKeyword`, `InterfaceBasic`

**Phase 2: Advanced OOP - Enums COMPLETE, Static Nested Classes COMPLETE**
- Enum support: EnumDeclaration compiles to class extending java.lang.Enum with ACC_ENUM flag; enum constants as public static final fields; synthetic values() and valueOf(String) methods generated; private constructor with (String, int) signature.
- Static initializer (<clinit>) creates enum constants and $VALUES array.
- Generic signature: Enum<EnumName> correctly generated.
- Qualified name resolution: static field access via ClassName.FIELD now works (e.g., Color.RED).
- Bytecode builder additions: checkcast and ldc_class instructions implemented.
- CLI improvement: output directory added to classpath for multi-file compilation.
- Test: added `EnumBasic`; full suite passing (`python test_compiler/run_tests.py`: 52/52).

**Static Nested Classes - COMPLETE:**
- AST hierarchy: TypeDeclaration now extends ClassBodyDeclaration to allow nested classes in class bodies.
- Parser: class_body() and class_declaration() accept TypeDeclaration; nested classes parsed correctly.
- Compilation: compile_class() returns dict[str, bytes] for multiple class files; nested classes compiled first, then outer class; state (class_name, class_file, super_class_name) saved and restored correctly.
- Naming: nested classes use Outer$Inner convention; fully qualified references like Outer.Inner and simple references like Inner both resolve correctly.
- Resolution: _resolve_class_name() checks if simple name is nested class of current outer class; supports both qualified (Outer.Inner) and unqualified (Inner) references.
- InnerClasses attribute: Added InnerClassInfo dataclass; classfile.py writes InnerClasses attribute with proper format; outer class lists all nested classes, nested class lists itself; verified with javap.
- Test: added `NestedStatic`; full suite passing (`python test_compiler/run_tests.py`: 53/53).

**Inner Classes (Non-static) - ~80% COMPLETE:**
- Infrastructure: this$0 synthetic field added to inner classes with ACC_FINAL | ACC_SYNTHETIC flags.
- Constructor modification: Inner class constructors accept outer instance as first parameter; outer instance stored in this$0 field after super() call.
- Qualified allocation parser: class_instance_creation_expression transformer handles qualifier for `outer.new Inner()` syntax.
- Expression compiler: compile_new_instance detects inner classes (via this$0 field); evaluates qualifier and passes to constructor; unqualified allocation uses 'this' as outer instance.
- Field resolution: Identifier resolution checks outer class fields via this$0 when in inner class.
- ConstantValue fix: Only emit ConstantValue attribute for static final fields, not instance fields.
- State isolation fix: Save and restore _static_init_sequence, _instance_init_sequence, _local_methods, _local_fields when compiling nested classes to prevent pollution.
- Known bug: Field resolution from inner to outer class doesn't work in all cases; outer class fields registered before nested compilation but _find_field doesn't access them correctly during inner class compilation.
- Test status: test_inner.java (OuterClass/InnerClass) compiles and runs successfully; test_inner_basic.java (TestInner/Inner) fails with field resolution error.
- Remaining work: Fix field resolution bug, implement synthetic accessor methods for private member access.
