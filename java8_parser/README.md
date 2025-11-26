# pyjopa - Python Java Parser and Compiler

A complete Java 8 parser and bytecode compiler written in Python using the Lark parsing library.

## Features

- Full Java 8 grammar support
- Generates Java 6 bytecode (class version 50.0)
- CLI for parsing and compiling Java files
- Reflection metadata (MethodParameters attribute)
- Annotation support (runtime visible annotations)
- Generics signature generation
- Multi-file compilation with dependency resolution
- Package-info.java support

## Installation

### Using Nix

```bash
nix run github:owner/repo -- compile MyClass.java
```

### From source

Requires Python 3.10+ and lark:

```bash
pip install -e .
```

## Usage

### CLI

Parse a Java file to AST (JSON):

```bash
pyjopa parse MyClass.java
```

Compile Java files to bytecode:

```bash
pyjopa compile MyClass.java
pyjopa compile -o output/ MyClass.java OtherClass.java
pyjopa compile -v --no-rt MyClass.java  # verbose, without rt.jar
```

### As a library

```python
from pyjopa.parser import Java8Parser
from pyjopa.codegen import CodeGenerator
from pyjopa.classreader import ClassPath

# Parse Java source
parser = Java8Parser()
ast = parser.parse_file("MyClass.java")

# Or parse from string
ast = parser.parse("""
public class Hello {
    public static void main(String[] args) {
        System.out.println("Hello, world!");
    }
}
""")

# Compile to bytecode
classpath = ClassPath()
classpath.add_rt_jar()  # Optional: for method resolution

gen = CodeGenerator(classpath=classpath)
class_files = gen.compile(ast)  # Returns dict[str, bytes]

# Write class files
for name, bytecode in class_files.items():
    with open(f"{name}.class", "wb") as f:
        f.write(bytecode)

classpath.close()
```

## Supported Features

### Statements

- Variable declarations with initializers
- If/else, switch/case
- While, do-while, for, enhanced for
- Break, continue, return
- Try/catch/finally, throw
- Block statements

### Expressions

- Arithmetic, logical, bitwise operators
- Comparisons, ternary operator
- Method calls (static and instance)
- Field access (static and instance)
- Array creation and access
- Object instantiation
- String concatenation
- Type casts, instanceof
- Pre/post increment/decrement
- Autoboxing/unboxing

### Class Features

- Public/private/protected/static/final modifiers
- Instance and static fields
- Instance and static methods
- Constructors
- Varargs methods
- Annotations (class, method, field, parameter level)
- Generic type parameters and signatures

## Project Structure

```
pyjopa/
  __init__.py       # Package exports
  parser.py         # Java8Parser using Lark
  java8.lark        # Java 8 grammar
  ast.py            # AST node definitions
  types.py          # Java type system
  classfile.py      # Class file writer
  classreader.py    # Class file reader (for rt.jar)
  codegen/          # Bytecode generation
    generator.py    # Main CodeGenerator class
    expressions.py  # Expression compilation
    statements.py   # Statement compilation
    arrays.py       # Array operations
    boxing.py       # Autoboxing
    resolution.py   # Type/method resolution
    signatures.py   # Generic signatures
```

## Development

Using Nix with direnv:

```bash
cd java8_parser
direnv allow
```

Run tests:

```bash
# Parser tests
pytest tests/

# Compiler tests (requires Java 8)
cd test_compiler && python run_tests.py
```

## Limitations

Current limitations that may be addressed in future versions:

- No inner/anonymous classes
- No lambda expressions
- No method references
- No enum types
- No interface default methods
- Single-file compilation (no import resolution across files)

## License

MIT
