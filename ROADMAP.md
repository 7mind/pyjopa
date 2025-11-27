# pyjopa - Java 8 Compiler Roadmap

## Current Status

**Lines of Code:** ~13,700 (parser, codegen, classfile, types)
**Tests:** 35/35 integration tests passing (100%)
**Target:** Java 8 bytecode (class version 52.0)
**Current Phase:** Phase 7 - Core Java Completeness

## Development Timeline

### ✅ Phase 6: Critical Bug Fixes (COMPLETE)
**Duration:** 1-2 days
**Target:** 100% pass rate on initial test suite
**Status:** ✅ COMPLETE - 35/35 tests (100%)

### 🔄 Phase 7: Core Java Completeness (IN PROGRESS)
**Duration:** 1 week
**Target:** 65 tests passing
**Current:** 35/65 tests (54%)
**Remaining:** 30 new tests needed

### 📋 Phase 8: Lambdas & Method References
**Duration:** 1-2 weeks
**Target:** 90 tests passing
**Increment:** +25 tests from Phase 7

### 📋 Phase 9: Standard Library Integration
**Duration:** 1 week
**Target:** 110 tests passing
**Increment:** +20 tests from Phase 8

### 📋 Phase 10: Advanced Features
**Duration:** 2 weeks
**Target:** 140 tests passing
**Increment:** +30 tests from Phase 9

### 📋 Phase 11: Stream API & Full Java 8
**Duration:** 2 weeks
**Target:** 160 tests passing (Full Java 8)
**Increment:** +20 tests from Phase 10

### Working Features

| Category | Feature | Status |
|----------|---------|--------|
| **Types** | Primitives (int, long, float, double, boolean, char, byte, short) | Done |
| | Class types | Done |
| | Array types | Done |
| | Generics (type parameters, signatures) | Done |
| **Operators** | Arithmetic (+, -, *, /, %) | Done |
| | Comparison (<, <=, >, >=, ==, !=) | Done |
| | Logical (&&, \|\|, !) | Done |
| | Bitwise (&, \|, ^, ~, <<, >>, >>>) | Done |
| | Assignment (=, +=, -=, etc.) | Done |
| | Increment/Decrement (++, --) | Done |
| | Ternary (?:) | Done |
| **Control Flow** | if/else | Done |
| | while, do-while | Done |
| | for, enhanced for | Done |
| | switch/case | Done |
| | break, continue, return | Done |
| | labeled statements | Partial |
| **OOP Basics** | Class declarations | Done |
| | Static/instance methods | Done |
| | Static/instance fields | Done |
| | Constructors | Done |
| | Object instantiation (new) | Done |
| | Method calls | Done |
| | Field access | Done |
| **Methods** | Varargs | Done |
| | Overloading | Done |
| | Parameter names (reflection) | Done |
| **Exceptions** | try/catch/finally | Done |
| | throw | Done |
| **Arrays** | Creation, access, .length | Done |
| | Array initializers | Done |
| **Strings** | Concatenation (via StringBuilder) | Done |
| | String literals | Done |
| **Boxing** | Autoboxing/unboxing | Done |
| **Casts** | Primitive casts | Done |
| | Reference casts | Done |
| | instanceof | Done |
| **Annotations** | Class/method/field annotations | Done |
| | Parameter annotations | Done |
| | RuntimeVisibleAnnotations | Done |
| **Other** | package-info.java | Done |
| | Multi-file compilation | Basic |

---

## Phase 1: Core Language Completeness

**Goal:** Support standard Java class hierarchies and interfaces

### 1.1 Inheritance (`extends`)
- [ ] Parse superclass in ClassDeclaration (parser done)
- [ ] Store superclass in ClassFile instead of hardcoded `java/lang/Object`
- [ ] Call correct super constructor
- [ ] Support super() with arguments
- [ ] Resolve inherited methods
- [ ] Resolve inherited fields
- **Test:** Class extending another class, calling super methods

### 1.2 Interfaces
- [ ] Compile InterfaceDeclaration to bytecode
- [ ] ACC_INTERFACE + ACC_ABSTRACT flags
- [ ] Interface method declarations (abstract)
- [ ] Interface constant fields (public static final)
- [ ] `implements` clause in classes
- [ ] Generate interface method table
- [ ] invokeinterface bytecode
- **Test:** Class implementing interface, calling through interface reference

### 1.3 Abstract Classes
- [ ] ACC_ABSTRACT on class
- [ ] Abstract method declarations (no body)
- [ ] Prevent instantiation of abstract classes
- **Test:** Abstract base class with concrete subclass

### 1.4 Static & Instance Initializers
- [ ] `static { }` blocks → `<clinit>` method
- [ ] `{ }` instance initializer blocks → merge into constructors
- [ ] Field initializers (non-constant)
- [ ] Initialization order (static first, then instance)
- **Test:** Class with static and instance initializers

### 1.5 `super` Keyword
- [ ] super.method() calls → invokespecial
- [ ] super.field access
- [ ] super() constructor calls with arguments
- **Test:** Subclass calling super methods and constructor

**Estimated complexity:** Medium
**Dependencies:** None
**Unlocks:** Phase 2 (OOP)

---

## Phase 2: Advanced OOP

**Goal:** Support nested classes, enums, and Java's full OOP model

### 2.1 Static Nested Classes
- [ ] Parse nested class declarations
- [ ] Generate separate .class files (Outer$Inner.class)
- [ ] InnerClasses attribute
- [ ] Access outer class static members
- [ ] Outer.Inner instantiation syntax
- **Test:** Static nested class accessing outer static fields

### 2.2 Inner Classes (Non-static)
- [ ] Synthetic `this$0` field for outer reference
- [ ] Pass outer instance to constructor
- [ ] Access outer instance members
- [ ] Outer.this syntax
- [ ] Synthetic accessor methods for private members
- **Test:** Inner class accessing outer instance fields

### 2.3 Anonymous Classes
- [ ] Parse anonymous class syntax
- [ ] Generate Outer$1, Outer$2, etc.
- [ ] Capture local variables (final or effectively final)
- [ ] Synthetic fields for captured variables
- **Test:** Anonymous Runnable implementation

### 2.4 Local Classes
- [ ] Classes declared inside methods
- [ ] Capture enclosing method's variables
- [ ] Limited visibility scope
- **Test:** Local class inside method

### 2.5 Enums
- [ ] EnumDeclaration → class extending java.lang.Enum
- [ ] Enum constants as static final fields
- [ ] Synthetic values() and valueOf() methods
- [ ] Enum constructor (private)
- [ ] Enum with fields and methods
- [ ] Switch on enum (tableswitch with ordinal)
- **Test:** Enum with values, switch on enum

**Estimated complexity:** High
**Dependencies:** Phase 1
**Unlocks:** Many real-world Java programs

---

## Phase 3: Generics Completion

**Goal:** Full generic type support including erasure, bridges, and inference

### 3.1 Type Erasure
- [ ] Erase type parameters in method descriptors
- [ ] Generate checkcast for generic return types
- [ ] Handle generic field access
- **Test:** Generic class with type parameter used in method

### 3.2 Bridge Methods
- [ ] Detect when bridge method needed (override with different erasure)
- [ ] Generate bridge method calling real method
- [ ] ACC_BRIDGE + ACC_SYNTHETIC flags
- **Test:** Class overriding generic method with concrete type

### 3.3 Wildcard Types
- [ ] `? extends T` upper bounds
- [ ] `? super T` lower bounds
- [ ] Unbounded `?`
- [ ] Signature generation for wildcards
- **Test:** Method accepting List<? extends Number>

### 3.4 Generic Method Invocation
- [ ] Infer type arguments from method arguments
- [ ] Explicit type arguments: `obj.<String>method()`
- [ ] Diamond operator: `new ArrayList<>()`
- **Test:** Generic method call with inference

### 3.5 Bounded Type Parameters
- [ ] `<T extends Comparable<T>>`
- [ ] Multiple bounds: `<T extends A & B>`
- [ ] Use bounds for method resolution
- **Test:** Bounded type parameter

**Estimated complexity:** High
**Dependencies:** Phase 1
**Unlocks:** Collections API usage

---

## Phase 4: Java 8 Features

**Goal:** Lambda expressions, method references, default methods

### 4.1 Functional Interfaces
- [ ] Detect functional interfaces (single abstract method)
- [ ] @FunctionalInterface validation
- **Test:** Custom functional interface

### 4.2 Lambda Expressions
- [ ] Parse lambda syntax (already in grammar)
- [ ] Generate invokedynamic instruction
- [ ] Create bootstrap method (LambdaMetafactory)
- [ ] Generate synthetic method for lambda body
- [ ] Capture local variables
- [ ] Capture `this` for instance lambdas
- **Test:** Lambda with Runnable, Consumer, Function

### 4.3 Method References
- [ ] Static method reference: `Math::abs`
- [ ] Instance method reference: `str::length`
- [ ] Constructor reference: `ArrayList::new`
- [ ] Arbitrary object method: `String::toLowerCase`
- **Test:** All four method reference types

### 4.4 Default Interface Methods
- [ ] Parse default methods in interfaces
- [ ] ACC_PUBLIC (not ACC_ABSTRACT)
- [ ] Code attribute for default method body
- [ ] Conflict resolution when implementing multiple interfaces
- **Test:** Interface with default method, class overriding it

### 4.5 Static Interface Methods
- [ ] Parse static methods in interfaces
- [ ] ACC_STATIC flag
- [ ] invokestatic for interface static methods
- **Test:** Interface with static utility method

**Estimated complexity:** Very High
**Dependencies:** Phase 1, Phase 2 (for captures)
**Unlocks:** Modern Java idioms

---

## Phase 5: Import & Multi-file Compilation

**Goal:** Proper import resolution and project compilation

### 5.1 Import Resolution
- [ ] Single-type imports: `import java.util.List;`
- [ ] On-demand imports: `import java.util.*;`
- [ ] Static imports: `import static Math.PI;`
- [ ] Static on-demand: `import static Math.*;`
- [ ] Resolve short names to fully qualified
- **Test:** Class using imported types

### 5.2 Package Resolution
- [ ] Source path scanning
- [ ] Match package to directory structure
- [ ] Resolve classes in same package
- **Test:** Multiple classes in same package

### 5.3 Multi-file Compilation
- [ ] Build dependency graph from imports
- [ ] Topological sort for compilation order
- [ ] Detect circular dependencies
- [ ] Incremental compilation (only changed files)
- **Test:** Project with 10+ interdependent files

### 5.4 Classpath Integration
- [ ] Read class info from compiled .class files
- [ ] Combine source and binary dependencies
- [ ] JAR file support (already partial)
- **Test:** Compile against library JAR

**Estimated complexity:** Medium
**Dependencies:** None (can be done in parallel)
**Unlocks:** Real project compilation

---

## Phase 6: Advanced Features

**Goal:** Complete Java SE feature support

### 6.1 Try-with-resources
- [ ] Parse try (Resource r = ...) syntax
- [ ] Generate try/finally with close() calls
- [ ] Handle suppressed exceptions
- [ ] Multiple resources
- **Test:** Try-with-resources with InputStream

### 6.2 Multi-catch
- [ ] Parse `catch (A | B e)`
- [ ] Single exception handler for multiple types
- [ ] Exception table with multiple entries
- **Test:** Multi-catch with IOException | SQLException

### 6.3 Assert Statements
- [ ] Parse `assert condition;` and `assert condition : message;`
- [ ] Generate $assertionsDisabled field
- [ ] Check assertions only when enabled
- **Test:** Assert with and without message

### 6.4 Synchronized
- [ ] `synchronized (obj) { }` blocks
- [ ] monitorenter/monitorexit instructions
- [ ] Exception handler to ensure monitorexit
- [ ] `synchronized` method modifier
- **Test:** Synchronized block and method

### 6.5 Class Literals
- [ ] `MyClass.class` expression
- [ ] `int.class`, `void.class` for primitives
- [ ] ldc instruction with class constant
- **Test:** Reflection using class literal

### 6.6 Annotation Processing
- [ ] Read annotations at compile time
- [ ] Annotation with array values
- [ ] Annotation with nested annotations
- [ ] Repeatable annotations
- **Test:** Complex annotation with all value types

**Estimated complexity:** Medium each
**Dependencies:** Phase 1
**Unlocks:** Enterprise Java patterns

---

## Phase 7: Optimization & Debugging

**Goal:** Production-quality bytecode output

### 7.1 Line Number Tables
- [ ] Track source line for each instruction
- [ ] LineNumberTable attribute
- [ ] Map bytecode offset to source line
- **Benefit:** Stack traces show line numbers

### 7.2 Local Variable Tables
- [ ] Track variable names and scopes
- [ ] LocalVariableTable attribute
- [ ] LocalVariableTypeTable for generics
- **Benefit:** Debugger shows variable names

### 7.3 Source File Attribute
- [ ] SourceFile attribute with filename
- **Benefit:** Stack traces show source file

### 7.4 Constant Folding
- [ ] Evaluate constant expressions at compile time
- [ ] `final` primitive constants inline
- [ ] String constant concatenation
- **Benefit:** Smaller, faster code

### 7.5 Stack Map Frames
- [ ] Compute stack/local types at each branch target
- [ ] StackMapTable attribute (Java 6+)
- [ ] Currently works with -noverify, add for full verification
- **Benefit:** Faster class loading

### 7.6 Dead Code Elimination
- [ ] Remove unreachable code after return/throw
- [ ] Remove unused local variables
- [ ] Remove empty blocks
- **Benefit:** Smaller bytecode

**Estimated complexity:** Medium
**Dependencies:** All previous phases
**Unlocks:** Production use

---

## Testing Strategy

### Unit Tests
- Each feature should have dedicated tests
- Test both success and error cases
- Test edge cases (empty, null, boundary values)

### Integration Tests
- Compile real-world Java files from JDK test suite
- Compare output with javac
- Run on multiple JVMs (8, 11, 17, 21)

### Compatibility Tests
- Bytecode verification without -noverify
- javap validation of class file structure
- Mixed compilation (our classes + javac classes)

### Performance Tests
- Compilation speed benchmark
- Compare generated bytecode size with javac
- Runtime performance of generated code

---

## Milestones

### v0.2 - Basic OOP
- [ ] Inheritance (extends)
- [ ] Interfaces (basic)
- [ ] Abstract classes
- [ ] Static initializers

### v0.3 - Complete OOP
- [ ] Inner classes (all types)
- [ ] Enums
- [ ] Full interface support

### v0.4 - Generics
- [ ] Bridge methods
- [ ] Wildcards
- [ ] Type inference

### v0.5 - Java 8
- [ ] Lambda expressions
- [ ] Method references
- [ ] Default methods

### v0.6 - Project Compilation
- [ ] Import resolution
- [ ] Multi-file compilation
- [ ] Incremental compilation

### v1.0 - Production Ready
- [ ] All Phase 6 features
- [ ] Full debugging support
- [ ] Stack map frames
- [ ] 95%+ JDK test suite pass rate

---

## Architecture Notes

### Current Module Structure
```
pyjopa/
├── parser.py          # Lark-based parser (1892 lines)
├── java8.lark         # Grammar definition
├── ast.py             # 60+ AST node classes
├── types.py           # JType hierarchy
├── classfile.py       # Class file writer (900+ lines)
├── classreader.py     # Class file reader (rt.jar)
├── codegen/
│   ├── generator.py   # Main compiler (~400 lines)
│   ├── statements.py  # Statement compilation
│   ├── expressions.py # Expression compilation (~1200 lines)
│   ├── arrays.py      # Array operations
│   ├── boxing.py      # Autoboxing
│   ├── resolution.py  # Type/method resolution
│   └── signatures.py  # Generic signatures
```

### Key Abstractions
- `JType`: Type system (primitive, class, array)
- `MethodContext`: Compilation context (locals, labels, stack)
- `BytecodeBuilder`: Instruction emission
- `ConstantPool`: Class file constant pool

### Extension Points
- Add new expression types in `expressions.py`
- Add new statement types in `statements.py`
- Add new bytecode instructions in `classfile.py`

---

## Contributing

1. Pick a feature from the roadmap
2. Write failing tests first
3. Implement the feature
4. Ensure all existing tests pass
5. Add documentation

Priority order: Phase 1 → Phase 5 → Phase 2 → Phase 3 → Phase 6 → Phase 4 → Phase 7
