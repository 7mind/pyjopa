#!/usr/bin/env python3
"""Generate comprehensive test files for Java 8 features."""

from pathlib import Path
from typing import List, Tuple

# Test definitions: (filename, main_class, java_code, expected_output)
TESTS: List[Tuple[str, str, str, List[str]]] = [
    # Category 1: Basic Types & Literals
    ("cat01_primitives_basic.java", "TestPrimitives", """
public class TestPrimitives {
    public static void main(String[] args) {
        int i = 42;
        long l = 100L;
        float f = 3.14f;
        double d = 2.718;
        boolean b = true;
        char c = 'A';
        byte by = 127;
        short s = 32000;
        System.out.println(i);
        System.out.println(l);
        System.out.println(b);
        System.out.println(c);
    }
}
""", ["42", "100", "true", "A"]),

    ("cat01_string_literals.java", "TestString", """
public class TestString {
    public static void main(String[] args) {
        String s1 = "Hello";
        String s2 = "World";
        System.out.println(s1);
        System.out.println(s2);
        String s3 = s1 + " " + s2;
        System.out.println(s3);
    }
}
""", ["Hello", "World", "Hello World"]),

    ("cat01_null_literal.java", "TestNull", """
public class TestNull {
    public static void main(String[] args) {
        String s = null;
        System.out.println(s == null);
        s = "test";
        System.out.println(s == null);
    }
}
""", ["true", "false"]),

    ("cat01_numeric_literals.java", "TestNumericLiterals", """
public class TestNumericLiterals {
    public static void main(String[] args) {
        int decimal = 100;
        int hex = 0x64;
        int octal = 0144;
        int binary = 0b1100100;
        System.out.println(decimal);
        System.out.println(hex);
        System.out.println(octal);
        System.out.println(binary);
    }
}
""", ["100", "100", "100", "100"]),

    ("cat01_type_casting.java", "TestCasting", """
public class TestCasting {
    public static void main(String[] args) {
        int i = 100;
        long l = i;
        double d = l;
        int i2 = (int)d;
        System.out.println(l);
        System.out.println(i2);
    }
}
""", ["100", "100"]),

    ("cat01_autoboxing.java", "TestAutoboxing", """
public class TestAutoboxing {
    public static void main(String[] args) {
        Integer i = 42;
        int j = i;
        System.out.println(i);
        System.out.println(j);
    }
}
""", ["42", "42"]),

    # Category 2: Operators & Expressions
    ("cat02_arithmetic_ops.java", "TestArithmetic", """
public class TestArithmetic {
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
""", ["13", "7", "30", "3", "1"]),

    ("cat02_comparison_ops.java", "TestComparison", """
public class TestComparison {
    public static void main(String[] args) {
        int a = 10;
        int b = 20;
        System.out.println(a == b);
        System.out.println(a != b);
        System.out.println(a < b);
        System.out.println(a > b);
        System.out.println(a <= b);
        System.out.println(a >= b);
    }
}
""", ["false", "true", "true", "false", "true", "false"]),

    ("cat02_logical_ops.java", "TestLogical", """
public class TestLogical {
    public static void main(String[] args) {
        boolean t = true;
        boolean f = false;
        System.out.println(t && f);
        System.out.println(t || f);
        System.out.println(!t);
        System.out.println(!f);
    }
}
""", ["false", "true", "false", "true"]),

    ("cat02_increment_ops.java", "TestIncrement", """
public class TestIncrement {
    public static void main(String[] args) {
        int i = 10;
        System.out.println(i++);
        System.out.println(i);
        System.out.println(++i);
        System.out.println(i--);
        System.out.println(i);
        System.out.println(--i);
    }
}
""", ["10", "11", "12", "12", "11", "10"]),

    ("cat02_ternary_op.java", "TestTernary", """
public class TestTernary {
    public static void main(String[] args) {
        int a = 10;
        int b = 20;
        int max = (a > b) ? a : b;
        System.out.println(max);
        String result = (a == 10) ? "yes" : "no";
        System.out.println(result);
    }
}
""", ["20", "yes"]),

    ("cat02_instanceof_op.java", "TestInstanceof", """
public class TestInstanceof {
    public static void main(String[] args) {
        String s = "hello";
        System.out.println(s instanceof String);
        System.out.println(s instanceof Object);
    }
}
""", ["true", "true"]),

    # Category 3: Control Flow
    ("cat03_if_else.java", "TestIfElse", """
public class TestIfElse {
    public static void main(String[] args) {
        int x = 10;
        if (x > 5) {
            System.out.println("greater");
        } else {
            System.out.println("smaller");
        }

        if (x == 5) {
            System.out.println("equal");
        } else if (x > 5) {
            System.out.println("greater");
        } else {
            System.out.println("smaller");
        }
    }
}
""", ["greater", "greater"]),

    ("cat03_while_loop.java", "TestWhile", """
public class TestWhile {
    public static void main(String[] args) {
        int i = 0;
        while (i < 3) {
            System.out.println(i);
            i++;
        }
    }
}
""", ["0", "1", "2"]),

    ("cat03_for_loop.java", "TestFor", """
public class TestFor {
    public static void main(String[] args) {
        for (int i = 0; i < 3; i++) {
            System.out.println(i);
        }
    }
}
""", ["0", "1", "2"]),

    ("cat03_enhanced_for.java", "TestEnhancedFor", """
public class TestEnhancedFor {
    public static void main(String[] args) {
        int[] arr = {1, 2, 3};
        for (int x : arr) {
            System.out.println(x);
        }
    }
}
""", ["1", "2", "3"]),

    ("cat03_switch_int.java", "TestSwitchInt", """
public class TestSwitchInt {
    public static void main(String[] args) {
        int x = 2;
        switch (x) {
            case 1:
                System.out.println("one");
                break;
            case 2:
                System.out.println("two");
                break;
            default:
                System.out.println("other");
        }
    }
}
""", ["two"]),

    ("cat03_break_continue.java", "TestBreakContinue", """
public class TestBreakContinue {
    public static void main(String[] args) {
        for (int i = 0; i < 5; i++) {
            if (i == 2) continue;
            if (i == 4) break;
            System.out.println(i);
        }
    }
}
""", ["0", "1", "3"]),

    # Category 4: Classes & Objects
    ("cat04_simple_class.java", "TestSimpleClass", """
class Point {
    int x;
    int y;

    Point(int x, int y) {
        this.x = x;
        this.y = y;
    }

    int getX() {
        return x;
    }
}

public class TestSimpleClass {
    public static void main(String[] args) {
        Point p = new Point(10, 20);
        System.out.println(p.getX());
        System.out.println(p.y);
    }
}
""", ["10", "20"]),

    ("cat04_constructor_overload.java", "TestConstructorOverload", """
class Box {
    int value;

    Box() {
        value = 0;
    }

    Box(int v) {
        value = v;
    }

    int getValue() {
        return value;
    }
}

public class TestConstructorOverload {
    public static void main(String[] args) {
        Box b1 = new Box();
        Box b2 = new Box(42);
        System.out.println(b1.getValue());
        System.out.println(b2.getValue());
    }
}
""", ["0", "42"]),

    ("cat04_static_members.java", "TestStatic", """
class Counter {
    static int count = 0;

    Counter() {
        count++;
    }

    static int getCount() {
        return count;
    }
}

public class TestStatic {
    public static void main(String[] args) {
        Counter c1 = new Counter();
        Counter c2 = new Counter();
        System.out.println(Counter.getCount());
    }
}
""", ["2"]),

    ("cat04_method_overload.java", "TestMethodOverload", """
class Calculator {
    int add(int a, int b) {
        return a + b;
    }

    int add(int a, int b, int c) {
        return a + b + c;
    }
}

public class TestMethodOverload {
    public static void main(String[] args) {
        Calculator calc = new Calculator();
        System.out.println(calc.add(1, 2));
        System.out.println(calc.add(1, 2, 3));
    }
}
""", ["3", "6"]),

    ("cat04_this_reference.java", "TestThis", """
class Person {
    String name;

    Person(String name) {
        this.name = name;
    }

    String getName() {
        return this.name;
    }
}

public class TestThis {
    public static void main(String[] args) {
        Person p = new Person("Alice");
        System.out.println(p.getName());
    }
}
""", ["Alice"]),

    # Category 5: Inheritance
    ("cat05_simple_inheritance.java", "TestInheritance", """
class Animal {
    String name;

    Animal(String name) {
        this.name = name;
    }

    String getName() {
        return name;
    }
}

class Dog extends Animal {
    Dog(String name) {
        super(name);
    }
}

public class TestInheritance {
    public static void main(String[] args) {
        Dog d = new Dog("Buddy");
        System.out.println(d.getName());
    }
}
""", ["Buddy"]),

    ("cat05_method_override.java", "TestOverride", """
class Shape {
    String getType() {
        return "shape";
    }
}

class Circle extends Shape {
    String getType() {
        return "circle";
    }
}

public class TestOverride {
    public static void main(String[] args) {
        Shape s = new Shape();
        Circle c = new Circle();
        System.out.println(s.getType());
        System.out.println(c.getType());
    }
}
""", ["shape", "circle"]),

    ("cat05_super_method.java", "TestSuperMethod", """
class Base {
    String getMessage() {
        return "base";
    }
}

class Derived extends Base {
    String getMessage() {
        return super.getMessage() + "-derived";
    }
}

public class TestSuperMethod {
    public static void main(String[] args) {
        Derived d = new Derived();
        System.out.println(d.getMessage());
    }
}
""", ["base-derived"]),

    ("cat05_instanceof_hierarchy.java", "TestInstanceofHierarchy", """
class Animal {}
class Dog extends Animal {}

public class TestInstanceofHierarchy {
    public static void main(String[] args) {
        Dog d = new Dog();
        System.out.println(d instanceof Dog);
        System.out.println(d instanceof Animal);
        System.out.println(d instanceof Object);
    }
}
""", ["true", "true", "true"]),

    # Category 6: Interfaces
    ("cat06_simple_interface.java", "TestInterface", """
interface Drawable {
    void draw();
}

class Circle implements Drawable {
    public void draw() {
        System.out.println("drawing circle");
    }
}

public class TestInterface {
    public static void main(String[] args) {
        Circle c = new Circle();
        c.draw();
    }
}
""", ["drawing circle"]),

    ("cat06_multiple_interfaces.java", "TestMultipleInterfaces", """
interface A {
    int getValue();
}

interface B {
    String getName();
}

class C implements A, B {
    public int getValue() {
        return 42;
    }

    public String getName() {
        return "test";
    }
}

public class TestMultipleInterfaces {
    public static void main(String[] args) {
        C c = new C();
        System.out.println(c.getValue());
        System.out.println(c.getName());
    }
}
""", ["42", "test"]),

    # Category 9: Enums
    ("cat09_simple_enum.java", "TestEnum", """
enum Color {
    RED, GREEN, BLUE
}

public class TestEnum {
    public static void main(String[] args) {
        Color c = Color.RED;
        System.out.println(c);
        System.out.println(c.ordinal());
    }
}
""", ["RED", "0"]),

    ("cat09_enum_constructor.java", "TestEnumConstructor", """
enum Size {
    SMALL(1),
    MEDIUM(2),
    LARGE(3);

    private int value;

    Size(int v) {
        value = v;
    }

    int getValue() {
        return value;
    }
}

public class TestEnumConstructor {
    public static void main(String[] args) {
        Size s = Size.MEDIUM;
        System.out.println(s.getValue());
    }
}
""", ["2"]),

    # Category 8: Arrays
    ("cat08_array_basic.java", "TestArray", """
public class TestArray {
    public static void main(String[] args) {
        int[] arr = new int[3];
        arr[0] = 10;
        arr[1] = 20;
        arr[2] = 30;
        System.out.println(arr[0]);
        System.out.println(arr[1]);
        System.out.println(arr.length);
    }
}
""", ["10", "20", "3"]),

    ("cat08_array_init.java", "TestArrayInit", """
public class TestArrayInit {
    public static void main(String[] args) {
        int[] arr = {1, 2, 3, 4, 5};
        for (int i = 0; i < arr.length; i++) {
            System.out.println(arr[i]);
        }
    }
}
""", ["1", "2", "3", "4", "5"]),

    # Category 11: Exceptions
    ("cat11_try_catch.java", "TestTryCatch", """
public class TestTryCatch {
    public static void main(String[] args) {
        try {
            int x = 10 / 2;
            System.out.println(x);
        } catch (Exception e) {
            System.out.println("error");
        }
        System.out.println("done");
    }
}
""", ["5", "done"]),

    ("cat11_try_finally.java", "TestFinally", """
public class TestFinally {
    public static void main(String[] args) {
        try {
            System.out.println("try");
        } finally {
            System.out.println("finally");
        }
        System.out.println("end");
    }
}
""", ["try", "finally", "end"]),
]


def main():
    """Generate all test files."""
    test_dir = Path(__file__).parent

    print(f"Generating {len(TESTS)} test files in {test_dir}...")

    for filename, main_class, code, expected in TESTS:
        filepath = test_dir / filename
        filepath.write_text(code.strip() + "\n")
        print(f"  ✓ {filename}")

    print(f"\nGenerated {len(TESTS)} test files successfully!")
    print("\nRun tests with:")
    print("  python tests/integration/run_tests.py")


if __name__ == "__main__":
    main()
