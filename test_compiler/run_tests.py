#!/usr/bin/env python3
"""
Comprehensive test runner for Java 6 bytecode compiler.

Test flow:
1. Compile with our compiler
2. Validate with javap (checks class file format)
3. Run with real JVM WITHOUT -noverify (full bytecode verification)
"""

import os
import sys
import subprocess
import tempfile
from pathlib import Path
from dataclasses import dataclass

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from pyjopa.parser import Java8Parser
from pyjopa.codegen import CodeGenerator
from pyjopa.classreader import ClassPath


@dataclass
class TestCase:
    name: str
    source: str
    expected_output: str
    main_class: str = None

    def __post_init__(self):
        if self.main_class is None:
            self.main_class = self.name


@dataclass
class MultiFileTestCase:
    """Test case with multiple source files."""
    name: str
    sources: dict[str, str]  # filename -> source
    expected_output: str
    main_class: str


@dataclass
class PackageInfoTestCase:
    """Test case for package-info.java files."""
    name: str
    source: str  # package-info.java content
    expected_annotations: list[str]  # list of expected annotation descriptors


JAVA6_TESTS = [
    # Basic tests
    TestCase(
        name="HelloWorld",
        source='''
public class HelloWorld {
    public static void main(String[] args) {
        System.out.println("Hello, World!");
    }
}
''',
        expected_output="Hello, World!\n"
    ),

    # Arithmetic operations
    TestCase(
        name="Arithmetic",
        source='''
public class Arithmetic {
    public static void main(String[] args) {
        int a = 10;
        int b = 3;
        System.out.println(a + b);
        System.out.println(a - b);
        System.out.println(a * b);
        System.out.println(a / b);
        System.out.println(a % b);
    }
}
''',
        expected_output="13\n7\n30\n3\n1\n"
    ),

    # Comparison operators
    TestCase(
        name="Comparisons",
        source='''
public class Comparisons {
    public static void main(String[] args) {
        int x = 5;
        int y = 10;
        if (x < y) {
            System.out.println("less");
        }
        if (x <= y) {
            System.out.println("less or equal");
        }
        if (y > x) {
            System.out.println("greater");
        }
        if (y >= x) {
            System.out.println("greater or equal");
        }
        if (x == 5) {
            System.out.println("equal");
        }
        if (x != y) {
            System.out.println("not equal");
        }
    }
}
''',
        expected_output="less\nless or equal\ngreater\ngreater or equal\nequal\nnot equal\n"
    ),

    # Loops
    TestCase(
        name="WhileLoop",
        source='''
public class WhileLoop {
    public static void main(String[] args) {
        int i = 0;
        while (i < 5) {
            System.out.println(i);
            i = i + 1;
        }
    }
}
''',
        expected_output="0\n1\n2\n3\n4\n"
    ),

    TestCase(
        name="ForLoop",
        source='''
public class ForLoop {
    public static void main(String[] args) {
        for (int i = 0; i < 5; i++) {
            System.out.println(i);
        }
    }
}
''',
        expected_output="0\n1\n2\n3\n4\n"
    ),

    # Static methods and fields
    TestCase(
        name="StaticMethod",
        source='''
public class StaticMethod {
    public static int add(int a, int b) {
        return a + b;
    }

    public static void main(String[] args) {
        int result = add(3, 4);
        System.out.println(result);
    }
}
''',
        expected_output="7\n"
    ),

    # Method with multiple parameters
    TestCase(
        name="MultipleParams",
        source='''
public class MultipleParams {
    public static int sum(int a, int b, int c, int d) {
        return a + b + c + d;
    }

    public static void main(String[] args) {
        System.out.println(sum(1, 2, 3, 4));
    }
}
''',
        expected_output="10\n"
    ),

    # If-else
    TestCase(
        name="IfElse",
        source='''
public class IfElse {
    public static void main(String[] args) {
        int x = 5;
        if (x > 3) {
            System.out.println("greater");
        } else {
            System.out.println("not greater");
        }

        int y = 1;
        if (y > 3) {
            System.out.println("greater");
        } else {
            System.out.println("not greater");
        }
    }
}
''',
        expected_output="greater\nnot greater\n"
    ),

    # Long arithmetic
    TestCase(
        name="LongArithmetic",
        source='''
public class LongArithmetic {
    public static void main(String[] args) {
        long a = 10000000000L;
        long b = 20000000000L;
        System.out.println(a + b);
    }
}
''',
        expected_output="30000000000\n"
    ),

    # Boolean operations
    TestCase(
        name="BooleanOps",
        source='''
public class BooleanOps {
    public static void main(String[] args) {
        boolean t = true;
        boolean f = false;
        if (t) {
            System.out.println("true");
        }
        if (!f) {
            System.out.println("not false");
        }
    }
}
''',
        expected_output="true\nnot false\n"
    ),

    # Static method from rt.jar
    TestCase(
        name="MathMethods",
        source='''
public class MathMethods {
    public static void main(String[] args) {
        int x = -42;
        System.out.println(Math.abs(x));
        System.out.println(Math.max(10, 20));
        System.out.println(Math.min(10, 20));
    }
}
''',
        expected_output="42\n20\n10\n"
    ),

    # Annotations
    TestCase(
        name="Annotations",
        source='''
@Deprecated
public class Annotations {
    @Deprecated
    public static void main(String[] args) {
        System.out.println("Annotations work!");
    }
}
''',
        expected_output="Annotations work!\n"
    ),

    # Generics (class-level)
    TestCase(
        name="Generics",
        source='''
public class Generics<T> {
    public static void main(String[] args) {
        System.out.println("Generics work!");
    }
}
''',
        expected_output="Generics work!\n"
    ),

    # Combined generics and annotations
    TestCase(
        name="GenericsAndAnnotations",
        source='''
@Deprecated
public class GenericsAndAnnotations<T, U> {
    @Deprecated
    public static void main(String[] args) {
        System.out.println("Both work!");
    }
}
''',
        expected_output="Both work!\n"
    ),

    # Unary operators
    TestCase(
        name="UnaryOps",
        source='''
public class UnaryOps {
    public static void main(String[] args) {
        int x = 5;
        System.out.println(-x);
        int y = -10;
        System.out.println(-y);
    }
}
''',
        expected_output="-5\n10\n"
    ),

    # String literals
    TestCase(
        name="StringLiterals",
        source='''
public class StringLiterals {
    public static void main(String[] args) {
        System.out.println("Hello");
        System.out.println("World");
        System.out.println("Line1\\nLine2");
    }
}
''',
        expected_output="Hello\nWorld\nLine1\nLine2\n"
    ),

    # Integer types
    TestCase(
        name="IntegerTypes",
        source='''
public class IntegerTypes {
    public static void main(String[] args) {
        byte b = 127;
        short s = 32767;
        int i = 2147483647;
        System.out.println(b);
        System.out.println(s);
        System.out.println(i);
    }
}
''',
        expected_output="127\n32767\n2147483647\n"
    ),

    # Recursive method
    TestCase(
        name="Recursion",
        source='''
public class Recursion {
    public static int factorial(int n) {
        if (n <= 1) {
            return 1;
        }
        return n * factorial(n - 1);
    }

    public static void main(String[] args) {
        System.out.println(factorial(5));
    }
}
''',
        expected_output="120\n"
    ),

    # Nested if statements
    TestCase(
        name="NestedIf",
        source='''
public class NestedIf {
    public static void main(String[] args) {
        int x = 10;
        int y = 20;
        if (x > 5) {
            if (y > 15) {
                System.out.println("both true");
            }
        }
    }
}
''',
        expected_output="both true\n"
    ),

    # Multiple classes compilation (main class only)
    TestCase(
        name="MultiReturn",
        source='''
public class MultiReturn {
    public static int sign(int x) {
        if (x > 0) {
            return 1;
        }
        if (x < 0) {
            return -1;
        }
        return 0;
    }

    public static void main(String[] args) {
        System.out.println(sign(10));
        System.out.println(sign(-5));
        System.out.println(sign(0));
    }
}
''',
        expected_output="1\n-1\n0\n"
    ),

    # ==================== CONTROL FLOW ====================

    # Do-while loop
    TestCase(
        name="DoWhile",
        source='''
public class DoWhile {
    public static void main(String[] args) {
        int i = 0;
        do {
            System.out.println(i);
            i++;
        } while (i < 3);
    }
}
''',
        expected_output="0\n1\n2\n"
    ),

    # Switch statement
    TestCase(
        name="SwitchCase",
        source='''
public class SwitchCase {
    public static void main(String[] args) {
        int x = 2;
        switch (x) {
            case 1:
                System.out.println("one");
                break;
            case 2:
                System.out.println("two");
                break;
            case 3:
                System.out.println("three");
                break;
            default:
                System.out.println("other");
        }
    }
}
''',
        expected_output="two\n"
    ),

    # Break and continue
    TestCase(
        name="BreakContinue",
        source='''
public class BreakContinue {
    public static void main(String[] args) {
        for (int i = 0; i < 10; i++) {
            if (i == 3) {
                continue;
            }
            if (i == 6) {
                break;
            }
            System.out.println(i);
        }
    }
}
''',
        expected_output="0\n1\n2\n4\n5\n"
    ),

    # Else-if chain
    TestCase(
        name="ElseIf",
        source='''
public class ElseIf {
    public static void main(String[] args) {
        int x = 5;
        if (x < 0) {
            System.out.println("negative");
        } else if (x == 0) {
            System.out.println("zero");
        } else if (x < 10) {
            System.out.println("small");
        } else {
            System.out.println("large");
        }
    }
}
''',
        expected_output="small\n"
    ),

    # ==================== OPERATORS ====================

    # Compound assignment operators
    TestCase(
        name="CompoundAssign",
        source='''
public class CompoundAssign {
    public static void main(String[] args) {
        int a = 10;
        a += 5;
        System.out.println(a);
        a -= 3;
        System.out.println(a);
        a *= 2;
        System.out.println(a);
        a /= 4;
        System.out.println(a);
        a %= 3;
        System.out.println(a);
    }
}
''',
        expected_output="15\n12\n24\n6\n0\n"
    ),

    # Bitwise operators
    TestCase(
        name="BitwiseOps",
        source='''
public class BitwiseOps {
    public static void main(String[] args) {
        int a = 5;
        int b = 3;
        System.out.println(a & b);
        System.out.println(a | b);
        System.out.println(a ^ b);
        System.out.println(~a);
        System.out.println(a << 1);
        System.out.println(a >> 1);
    }
}
''',
        expected_output="1\n7\n6\n-6\n10\n2\n"
    ),

    # Logical operators with short-circuit
    TestCase(
        name="LogicalOps",
        source='''
public class LogicalOps {
    public static void main(String[] args) {
        boolean t = true;
        boolean f = false;
        if (t && t) {
            System.out.println("and1");
        }
        if (t && f) {
            System.out.println("and2");
        }
        if (f || t) {
            System.out.println("or1");
        }
        if (f || f) {
            System.out.println("or2");
        }
    }
}
''',
        expected_output="and1\nor1\n"
    ),

    # Ternary operator
    TestCase(
        name="Ternary",
        source='''
public class Ternary {
    public static void main(String[] args) {
        int x = 5;
        int y = x > 3 ? 10 : 20;
        System.out.println(y);
        int z = x < 3 ? 10 : 20;
        System.out.println(z);
    }
}
''',
        expected_output="10\n20\n"
    ),

    # Pre-increment and pre-decrement
    TestCase(
        name="PreIncDec",
        source='''
public class PreIncDec {
    public static void main(String[] args) {
        int a = 5;
        System.out.println(++a);
        System.out.println(a);
        System.out.println(--a);
        System.out.println(a);
    }
}
''',
        expected_output="6\n6\n5\n5\n"
    ),

    # String concatenation
    TestCase(
        name="StringConcat",
        source='''
public class StringConcat {
    public static void main(String[] args) {
        String s = "Hello" + " " + "World";
        System.out.println(s);
        String t = "Value: " + 42;
        System.out.println(t);
    }
}
''',
        expected_output="Hello World\nValue: 42\n"
    ),

    # ==================== TYPES ====================

    # Float and double
    TestCase(
        name="FloatDouble",
        source='''
public class FloatDouble {
    public static void main(String[] args) {
        float f = 3.14f;
        double d = 2.718;
        System.out.println(f > 3.0f);
        System.out.println(d < 3.0);
    }
}
''',
        expected_output="true\ntrue\n"
    ),

    # Char type
    TestCase(
        name="CharType",
        source='''
public class CharType {
    public static void main(String[] args) {
        char c = 'A';
        System.out.println(c);
        char d = 66;
        System.out.println(d);
    }
}
''',
        expected_output="A\nB\n"
    ),

    # Arrays
    TestCase(
        name="Arrays",
        source='''
public class Arrays {
    public static void main(String[] args) {
        int[] arr = new int[3];
        arr[0] = 10;
        arr[1] = 20;
        arr[2] = 30;
        System.out.println(arr[0]);
        System.out.println(arr[1]);
        System.out.println(arr[2]);
        System.out.println(arr.length);
    }
}
''',
        expected_output="10\n20\n30\n3\n"
    ),

    # Array initializer
    TestCase(
        name="ArrayInit",
        source='''
public class ArrayInit {
    public static void main(String[] args) {
        int[] arr = {1, 2, 3, 4, 5};
        System.out.println(arr[0]);
        System.out.println(arr[4]);
        System.out.println(arr.length);
    }
}
''',
        expected_output="1\n5\n5\n"
    ),

    # Enhanced for loop (for-each)
    TestCase(
        name="ForEach",
        source='''
public class ForEach {
    public static void main(String[] args) {
        int[] arr = {1, 2, 3};
        for (int x : arr) {
            System.out.println(x);
        }
    }
}
''',
        expected_output="1\n2\n3\n"
    ),

    # ==================== OOP ====================

    # Instance fields and methods
    TestCase(
        name="InstanceMembers",
        source='''
public class InstanceMembers {
    int value;

    int getValue() {
        return value;
    }

    void setValue(int v) {
        value = v;
    }

    public static void main(String[] args) {
        InstanceMembers obj = new InstanceMembers();
        obj.setValue(42);
        System.out.println(obj.getValue());
        System.out.println(obj.value);
    }
}
''',
        expected_output="42\n42\n"
    ),

    # Constructors
    TestCase(
        name="Constructor",
        source='''
public class Constructor {
    int x;
    int y;

    public Constructor(int a, int b) {
        x = a;
        y = b;
    }

    public static void main(String[] args) {
        Constructor c = new Constructor(10, 20);
        System.out.println(c.x);
        System.out.println(c.y);
    }
}
''',
        expected_output="10\n20\n"
    ),

    # This keyword
    TestCase(
        name="ThisKeyword",
        source='''
public class ThisKeyword {
    int x;

    void setX(int x) {
        this.x = x;
    }

    int getX() {
        return this.x;
    }

    public static void main(String[] args) {
        ThisKeyword obj = new ThisKeyword();
        obj.setX(100);
        System.out.println(obj.getX());
    }
}
''',
        expected_output="100\n"
    ),

    # Static fields
    TestCase(
        name="StaticFields",
        source='''
public class StaticFields {
    static int count = 0;

    static void increment() {
        count++;
    }

    public static void main(String[] args) {
        System.out.println(count);
        increment();
        System.out.println(count);
        increment();
        System.out.println(count);
    }
}
''',
        expected_output="0\n1\n2\n"
    ),

    # Null handling
    TestCase(
        name="NullHandling",
        source='''
public class NullHandling {
    public static void main(String[] args) {
        String s = null;
        if (s == null) {
            System.out.println("is null");
        }
        s = "hello";
        if (s != null) {
            System.out.println("not null");
        }
    }
}
''',
        expected_output="is null\nnot null\n"
    ),

    # instanceof operator
    TestCase(
        name="InstanceOf",
        source='''
public class InstanceOf {
    public static void main(String[] args) {
        String s = "hello";
        if (s instanceof String) {
            System.out.println("is String");
        }
        Object o = s;
        if (o instanceof String) {
            System.out.println("also String");
        }
    }
}
''',
        expected_output="is String\nalso String\n"
    ),

    # ==================== EXCEPTIONS ====================

    # Try-catch
    TestCase(
        name="TryCatch",
        source='''
public class TryCatch {
    public static void main(String[] args) {
        try {
            int x = 10 / 0;
            System.out.println("no exception");
        } catch (ArithmeticException e) {
            System.out.println("caught");
        }
        System.out.println("done");
    }
}
''',
        expected_output="caught\ndone\n"
    ),

    # Try-catch-finally
    TestCase(
        name="TryFinally",
        source='''
public class TryFinally {
    public static void main(String[] args) {
        try {
            System.out.println("try");
        } finally {
            System.out.println("finally");
        }
        System.out.println("done");
    }
}
''',
        expected_output="try\nfinally\ndone\n"
    ),

    # Throw statement
    TestCase(
        name="ThrowStmt",
        source='''
public class ThrowStmt {
    static void test(int x) {
        if (x < 0) {
            throw new IllegalArgumentException();
        }
        System.out.println("ok");
    }

    public static void main(String[] args) {
        try {
            test(5);
            test(-1);
        } catch (IllegalArgumentException e) {
            System.out.println("caught");
        }
    }
}
''',
        expected_output="ok\ncaught\n"
    ),

    # ==================== JAVA 5 FEATURES ====================

    # Autoboxing
    TestCase(
        name="Autoboxing",
        source='''
public class Autoboxing {
    public static void main(String[] args) {
        Integer i = 42;
        int x = i;
        System.out.println(x);
        System.out.println(i.intValue());
    }
}
''',
        expected_output="42\n42\n"
    ),

    # Varargs
    TestCase(
        name="Varargs",
        source='''
public class Varargs {
    static int sum(int... nums) {
        int total = 0;
        for (int n : nums) {
            total += n;
        }
        return total;
    }

    public static void main(String[] args) {
        System.out.println(sum(1, 2, 3));
        System.out.println(sum(10, 20));
    }
}
''',
        expected_output="6\n30\n"
    ),
]

MULTI_FILE_TESTS = [
    # Multi-file dependency test (files ordered so dependencies compile first)
    MultiFileTestCase(
        name="MultiFileDep",
        sources={
            "1_Helper.java": '''
public class Helper {
    public static int add(int a, int b) {
        return a + b;
    }
}
''',
            "2_MultiFileDep.java": '''
public class MultiFileDep {
    public static void main(String[] args) {
        System.out.println(Helper.add(10, 20));
    }
}
''',
        },
        expected_output="30\n",
        main_class="MultiFileDep"
    ),
]

PACKAGE_INFO_TESTS = [
    PackageInfoTestCase(
        name="PackageInfoDeprecated",
        source='''
@Deprecated
package testpkg;
''',
        expected_annotations=["Ljava/lang/Deprecated;"]
    ),
]


def run_test(test: TestCase, output_dir: Path, verbose: bool = False) -> tuple[bool, str]:
    """
    Run a single test case.
    Returns (success, error_message)
    """
    source_file = output_dir / f"{test.name}.java"
    class_file = output_dir / f"{test.main_class}.class"

    # Write source
    source_file.write_text(test.source.strip() + "\n")

    # Step 1: Compile with our compiler
    try:
        parser = Java8Parser()
        ast = parser.parse_file(str(source_file))

        classpath = ClassPath()
        classpath.add_rt_jar()

        gen = CodeGenerator(classpath)
        results = gen.compile(ast)

        for name, class_bytes in results.items():
            out_file = output_dir / f"{name}.class"
            out_file.write_bytes(class_bytes)

        if verbose:
            print(f"  Compiled {test.name}: {len(results)} class(es)")

    except Exception as e:
        return False, f"Compilation failed: {e}"

    # Step 2: Validate with javap
    try:
        result = subprocess.run(
            ["javap", "-v", str(class_file)],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode != 0:
            return False, f"javap validation failed: {result.stderr}"
        if verbose:
            print(f"  javap validation passed")
    except subprocess.TimeoutExpired:
        return False, "javap timed out"
    except Exception as e:
        return False, f"javap failed: {e}"

    # Step 3: Run with real JVM (NO -noverify!)
    try:
        result = subprocess.run(
            ["java", "-cp", str(output_dir), test.main_class],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode != 0:
            return False, f"JVM execution failed (exit {result.returncode}):\nstdout: {result.stdout}\nstderr: {result.stderr}"

        actual_output = result.stdout
        if actual_output != test.expected_output:
            return False, f"Output mismatch:\nExpected: {repr(test.expected_output)}\nActual: {repr(actual_output)}"

        if verbose:
            print(f"  JVM execution passed (verified bytecode)")

    except subprocess.TimeoutExpired:
        return False, "JVM execution timed out"
    except Exception as e:
        return False, f"JVM execution failed: {e}"

    return True, ""


def run_multi_file_test(test: MultiFileTestCase, output_dir: Path, verbose: bool = False) -> tuple[bool, str]:
    """
    Run a multi-file test case.
    Returns (success, error_message)
    """
    # Step 1: Write all source files
    for filename, source in test.sources.items():
        source_file = output_dir / filename
        source_file.parent.mkdir(parents=True, exist_ok=True)
        source_file.write_text(source.strip() + "\n")

    # Step 2: Compile all files with our compiler
    try:
        parser = Java8Parser()
        classpath = ClassPath()
        classpath.add_rt_jar()
        # Add output dir so we can find previously compiled classes
        classpath.add_path(str(output_dir))

        # Compile each source file (sorted so dependencies compile first)
        for filename in sorted(test.sources.keys()):
            source_file = output_dir / filename
            ast = parser.parse_file(str(source_file))

            # Use a fresh generator for each file but same classpath
            gen = CodeGenerator(classpath)
            results = gen.compile(ast)

            for name, class_bytes in results.items():
                out_file = output_dir / f"{name}.class"
                out_file.parent.mkdir(parents=True, exist_ok=True)
                out_file.write_bytes(class_bytes)

        if verbose:
            print(f"  Compiled {test.name}: {len(test.sources)} file(s)")

    except Exception as e:
        return False, f"Compilation failed: {e}"

    # Step 3: Run with real JVM
    try:
        result = subprocess.run(
            ["java", "-cp", str(output_dir), test.main_class],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode != 0:
            return False, f"JVM execution failed (exit {result.returncode}):\nstdout: {result.stdout}\nstderr: {result.stderr}"

        actual_output = result.stdout
        if actual_output != test.expected_output:
            return False, f"Output mismatch:\nExpected: {repr(test.expected_output)}\nActual: {repr(actual_output)}"

        if verbose:
            print(f"  JVM execution passed (verified bytecode)")

    except subprocess.TimeoutExpired:
        return False, "JVM execution timed out"
    except Exception as e:
        return False, f"JVM execution failed: {e}"

    return True, ""


def run_package_info_test(test: PackageInfoTestCase, output_dir: Path, verbose: bool = False) -> tuple[bool, str]:
    """
    Run a package-info test case.
    Returns (success, error_message)
    """
    # Step 1: Write source file
    source_file = output_dir / "package-info.java"
    source_file.write_text(test.source.strip() + "\n")

    # Step 2: Compile with our compiler
    try:
        parser = Java8Parser()
        ast = parser.parse_file(str(source_file))

        gen = CodeGenerator()
        results = gen.compile(ast)

        if not results:
            return False, "No class files generated"

        for name, class_bytes in results.items():
            out_file = output_dir / f"{name}.class"
            out_file.parent.mkdir(parents=True, exist_ok=True)
            out_file.write_bytes(class_bytes)

        if verbose:
            print(f"  Compiled {test.name}: {len(results)} class(es)")

    except Exception as e:
        return False, f"Compilation failed: {e}"

    # Step 3: Validate with javap and check for expected annotations
    try:
        # Find the package-info.class file
        class_files = list(output_dir.rglob("package-info.class"))
        if not class_files:
            return False, "package-info.class not found"

        result = subprocess.run(
            ["javap", "-v", str(class_files[0])],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode != 0:
            return False, f"javap validation failed: {result.stderr}"

        javap_output = result.stdout

        # Check for expected flags
        if "ACC_INTERFACE" not in javap_output:
            return False, "package-info.class missing ACC_INTERFACE flag"
        if "ACC_ABSTRACT" not in javap_output:
            return False, "package-info.class missing ACC_ABSTRACT flag"
        if "ACC_SYNTHETIC" not in javap_output:
            return False, "package-info.class missing ACC_SYNTHETIC flag"

        # Check for expected annotations
        for ann_desc in test.expected_annotations:
            if ann_desc not in javap_output:
                return False, f"Expected annotation {ann_desc} not found in bytecode"

        if verbose:
            print(f"  javap validation passed (annotations verified)")

    except subprocess.TimeoutExpired:
        return False, "javap timed out"
    except Exception as e:
        return False, f"javap failed: {e}"

    return True, ""


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Run Java 6 compiler tests")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    parser.add_argument("--test", type=str, help="Run specific test by name")
    parser.add_argument("--list", action="store_true", help="List all tests")
    args = parser.parse_args()

    all_tests = JAVA6_TESTS + MULTI_FILE_TESTS + PACKAGE_INFO_TESTS

    if args.list:
        print("Available tests:")
        for test in all_tests:
            print(f"  {test.name}")
        return

    tests_to_run = all_tests
    if args.test:
        tests_to_run = [t for t in all_tests if t.name == args.test]
        if not tests_to_run:
            print(f"Test '{args.test}' not found")
            sys.exit(1)

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        passed = 0
        failed = 0
        failures = []

        print(f"Running {len(tests_to_run)} tests (bytecode verification ENABLED)...")
        print()

        for test in tests_to_run:
            if args.verbose:
                print(f"Testing {test.name}...")

            if isinstance(test, MultiFileTestCase):
                success, error = run_multi_file_test(test, output_dir, args.verbose)
            elif isinstance(test, PackageInfoTestCase):
                success, error = run_package_info_test(test, output_dir, args.verbose)
            else:
                success, error = run_test(test, output_dir, args.verbose)

            if success:
                passed += 1
                if not args.verbose:
                    print(f"  PASS: {test.name}")
                else:
                    print(f"  PASS")
            else:
                failed += 1
                failures.append((test.name, error))
                if not args.verbose:
                    print(f"  FAIL: {test.name}")
                else:
                    print(f"  FAIL: {error}")

            if args.verbose:
                print()

        print()
        print(f"Results: {passed} passed, {failed} failed")

        if failures:
            print()
            print("Failures:")
            for name, error in failures:
                print(f"  {name}: {error[:100]}...")

        sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
