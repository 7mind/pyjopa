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

from java8_parser.parser import Java8Parser
from java8_parser.codegen import CodeGenerator
from java8_parser.classreader import ClassPath


@dataclass
class TestCase:
    name: str
    source: str
    expected_output: str
    main_class: str = None

    def __post_init__(self):
        if self.main_class is None:
            self.main_class = self.name


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


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Run Java 6 compiler tests")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    parser.add_argument("--test", type=str, help="Run specific test by name")
    parser.add_argument("--list", action="store_true", help="List all tests")
    args = parser.parse_args()

    if args.list:
        print("Available tests:")
        for test in JAVA6_TESTS:
            print(f"  {test.name}")
        return

    tests_to_run = JAVA6_TESTS
    if args.test:
        tests_to_run = [t for t in JAVA6_TESTS if t.name == args.test]
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
