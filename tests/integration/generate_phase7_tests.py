#!/usr/bin/env python3
"""Generate 30 new test cases for Phase 7 - Core Java Completeness"""

import os

# Test definitions: (filename, code, expected_output)
TESTS = [
    # Category 1 - Basic Types (4 new tests)
    ("cat01_char_escapes.java", '''public class TestCharEscapes {
    public static void main(String[] args) {
        char newline = '\\n';
        char tab = '\\t';
        char backslash = '\\\\\\\\';
        char quote = '\\'';
        System.out.println((int)newline);
        System.out.println((int)tab);
        System.out.println((int)backslash);
        System.out.println((int)quote);
    }
}''', "10\n9\n92\n39\n"),

    ("cat01_float_double.java", '''public class TestFloatDouble {
    public static void main(String[] args) {
        float f = 3.14f;
        double d = 2.71828;
        System.out.println(f > 3.0f);
        System.out.println(d < 3.0);
        System.out.println((int)(f + d));
    }
}''', "true\ntrue\n5\n"),

    ("cat01_wrapper_classes.java", '''public class TestWrappers {
    public static void main(String[] args) {
        Integer i = 42;
        int x = i;
        System.out.println(x);
        Long l = 100L;
        System.out.println(l);
    }
}''', "42\n100\n"),

    ("cat01_hex_binary_literals.java", '''public class TestLiteralFormats {
    public static void main(String[] args) {
        int hex = 0xFF;
        int binary = 0b1010;
        int octal = 077;
        System.out.println(hex);
        System.out.println(binary);
        System.out.println(octal);
    }
}''', "255\n10\n63\n"),

    # Category 2 - Operators (4 new tests)
    ("cat02_bitwise_ops.java", '''public class TestBitwiseOps {
    public static void main(String[] args) {
        int a = 12;  // 1100
        int b = 10;  // 1010
        System.out.println(a & b);  // 1000 = 8
        System.out.println(a | b);  // 1110 = 14
        System.out.println(a ^ b);  // 0110 = 6
        System.out.println(~a);     // -13
        System.out.println(a << 1); // 24
        System.out.println(a >> 1); // 6
    }
}''', "8\n14\n6\n-13\n24\n6\n"),

    ("cat02_assignment_ops.java", '''public class TestAssignmentOps {
    public static void main(String[] args) {
        int x = 10;
        x += 5;
        System.out.println(x);
        x -= 3;
        System.out.println(x);
        x *= 2;
        System.out.println(x);
        x /= 4;
        System.out.println(x);
    }
}''', "15\n12\n24\n6\n"),

    ("cat02_operator_precedence.java", '''public class TestPrecedence {
    public static void main(String[] args) {
        int result = 2 + 3 * 4;
        System.out.println(result);
        result = (2 + 3) * 4;
        System.out.println(result);
        result = 10 - 4 - 2;
        System.out.println(result);
    }
}''', "14\n20\n4\n"),

    ("cat02_string_concat.java", '''public class TestStringConcat {
    public static void main(String[] args) {
        String s = "Hello" + " " + "World";
        System.out.println(s);
        s = "Number: " + 42;
        System.out.println(s);
        s = 10 + 20 + " items";
        System.out.println(s);
    }
}''', "Hello World\nNumber: 42\n30 items\n"),

    # Category 3 - Control Flow (2 new tests)
    ("cat03_switch_string.java", '''public class TestSwitchString {
    public static void main(String[] args) {
        String day = "Monday";
        switch (day) {
            case "Monday":
                System.out.println(1);
                break;
            case "Tuesday":
                System.out.println(2);
                break;
            default:
                System.out.println(0);
        }
    }
}''', "1\n"),

    ("cat03_do_while.java", '''public class TestDoWhile {
    public static void main(String[] args) {
        int i = 0;
        do {
            System.out.println(i);
            i++;
        } while (i < 3);
    }
}''', "0\n1\n2\n"),

    # Category 4 - Classes & Objects (6 new tests)
    ("cat04_constructor_chaining.java", '''public class TestConstructorChaining {
    private int value;

    public TestConstructorChaining() {
        this(42);
    }

    public TestConstructorChaining(int v) {
        value = v;
    }

    public static void main(String[] args) {
        TestConstructorChaining obj = new TestConstructorChaining();
        System.out.println(obj.value);
    }
}''', "42\n"),

    ("cat04_access_modifiers.java", '''class Helper {
    public int publicField = 1;
    private int privateField = 2;
    protected int protectedField = 3;

    public int getPrivate() {
        return privateField;
    }
}

public class TestAccessModifiers {
    public static void main(String[] args) {
        Helper h = new Helper();
        System.out.println(h.publicField);
        System.out.println(h.getPrivate());
        System.out.println(h.protectedField);
    }
}''', "1\n2\n3\n"),

    ("cat04_final_field.java", '''public class TestFinalField {
    private final int value = 100;

    public static void main(String[] args) {
        TestFinalField obj = new TestFinalField();
        System.out.println(obj.value);
    }
}''', "100\n"),

    ("cat04_final_method.java", '''class Base {
    public final int getValue() {
        return 42;
    }
}

public class TestFinalMethod extends Base {
    public static void main(String[] args) {
        TestFinalMethod obj = new TestFinalMethod();
        System.out.println(obj.getValue());
    }
}''', "42\n"),

    ("cat04_final_class.java", '''final class FinalClass {
    int value = 123;
}

public class TestFinalClass {
    public static void main(String[] args) {
        FinalClass obj = new FinalClass();
        System.out.println(obj.value);
    }
}''', "123\n"),

    ("cat04_multiple_constructors.java", '''class Point {
    int x, y;

    Point() {
        this(0, 0);
    }

    Point(int x) {
        this(x, 0);
    }

    Point(int x, int y) {
        this.x = x;
        this.y = y;
    }
}

public class TestMultipleConstructors {
    public static void main(String[] args) {
        Point p1 = new Point();
        Point p2 = new Point(5);
        Point p3 = new Point(3, 4);
        System.out.println(p1.x + "," + p1.y);
        System.out.println(p2.x + "," + p2.y);
        System.out.println(p3.x + "," + p3.y);
    }
}''', "0,0\n5,0\n3,4\n"),

    # Category 5 - Inheritance (5 new tests)
    ("cat05_super_constructor.java", '''class Animal {
    String name;
    Animal(String n) {
        name = n;
    }
}

class Dog extends Animal {
    Dog(String n) {
        super(n);
    }
}

public class TestSuperConstructor {
    public static void main(String[] args) {
        Dog d = new Dog("Buddy");
        System.out.println(d.name);
    }
}''', "Buddy\n"),

    ("cat05_super_field.java", '''class Parent {
    int value = 10;
}

class Child extends Parent {
    int value = 20;

    void printValues() {
        System.out.println(value);
        System.out.println(super.value);
    }
}

public class TestSuperField {
    public static void main(String[] args) {
        Child c = new Child();
        c.printValues();
    }
}''', "20\n10\n"),

    ("cat05_abstract_class.java", '''abstract class Shape {
    abstract int getArea();
}

class Rectangle extends Shape {
    int width = 4;
    int height = 5;

    int getArea() {
        return width * height;
    }
}

public class TestAbstractClass {
    public static void main(String[] args) {
        Shape s = new Rectangle();
        System.out.println(s.getArea());
    }
}''', "20\n"),

    ("cat05_override_annotation.java", '''class Base {
    int getValue() {
        return 10;
    }
}

class Derived extends Base {
    @Override
    int getValue() {
        return 20;
    }
}

public class TestOverrideAnnotation {
    public static void main(String[] args) {
        Base b = new Derived();
        System.out.println(b.getValue());
    }
}''', "20\n"),

    ("cat05_multilevel_inheritance.java", '''class A {
    int a = 1;
}

class B extends A {
    int b = 2;
}

class C extends B {
    int c = 3;
}

public class TestMultilevelInheritance {
    public static void main(String[] args) {
        C obj = new C();
        System.out.println(obj.a);
        System.out.println(obj.b);
        System.out.println(obj.c);
    }
}''', "1\n2\n3\n"),

    # Category 6 - Interfaces (3 new tests)
    ("cat06_interface_constants.java", '''interface Constants {
    int MAX = 100;
    int MIN = 0;
}

public class TestInterfaceConstants implements Constants {
    public static void main(String[] args) {
        System.out.println(MAX);
        System.out.println(MIN);
        System.out.println(Constants.MAX);
    }
}''', "100\n0\n100\n"),

    ("cat06_interface_extends.java", '''interface A {
    int getA();
}

interface B extends A {
    int getB();
}

class Impl implements B {
    public int getA() { return 1; }
    public int getB() { return 2; }
}

public class TestInterfaceExtends {
    public static void main(String[] args) {
        Impl obj = new Impl();
        System.out.println(obj.getA());
        System.out.println(obj.getB());
    }
}''', "1\n2\n"),

    ("cat06_default_method.java", '''interface Greet {
    default String greet() {
        return "Hello";
    }
}

class Person implements Greet {
}

public class TestDefaultMethod {
    public static void main(String[] args) {
        Person p = new Person();
        System.out.println(p.greet());
    }
}''', "Hello\n"),

    # Category 8 - Arrays (3 new tests)
    ("cat08_multidimensional.java", '''public class TestMultidimensional {
    public static void main(String[] args) {
        int[][] matrix = new int[2][3];
        matrix[0][0] = 1;
        matrix[0][1] = 2;
        matrix[1][2] = 6;
        System.out.println(matrix[0][0]);
        System.out.println(matrix[0][1]);
        System.out.println(matrix[1][2]);
    }
}''', "1\n2\n6\n"),

    ("cat08_varargs.java", '''class VarArgsTest {
    static int sum(int... numbers) {
        int total = 0;
        for (int n : numbers) {
            total += n;
        }
        return total;
    }
}

public class TestVarargs {
    public static void main(String[] args) {
        System.out.println(VarArgsTest.sum(1, 2, 3));
        System.out.println(VarArgsTest.sum(10, 20));
    }
}''', "6\n30\n"),

    ("cat08_array_objects.java", '''public class TestArrayObjects {
    public static void main(String[] args) {
        String[] words = new String[3];
        words[0] = "Hello";
        words[1] = "World";
        words[2] = "!";
        for (String w : words) {
            System.out.println(w);
        }
    }
}''', "Hello\nWorld\n!\n"),

    # Category 11 - Exceptions (3 new tests)
    ("cat11_throw_statement.java", '''public class TestThrow {
    static void checkAge(int age) {
        if (age < 18) {
            throw new RuntimeException("Too young");
        }
        System.out.println("Valid age");
    }

    public static void main(String[] args) {
        try {
            checkAge(20);
            checkAge(15);
        } catch (RuntimeException e) {
            System.out.println("Caught");
        }
    }
}''', "Valid age\nCaught\n"),

    ("cat11_throws_clause.java", '''class Test {
    static void riskyMethod() throws Exception {
        throw new Exception("Error");
    }
}

public class TestThrows {
    public static void main(String[] args) {
        try {
            Test.riskyMethod();
        } catch (Exception e) {
            System.out.println("Handled");
        }
    }
}''', "Handled\n"),

    ("cat11_multiple_catch.java", '''public class TestMultipleCatch {
    public static void main(String[] args) {
        try {
            int[] arr = new int[2];
            arr[5] = 10;
        } catch (ArrayIndexOutOfBoundsException e) {
            System.out.println("Array error");
        } catch (Exception e) {
            System.out.println("Other error");
        }
    }
}''', "Array error\n"),
]

def main():
    """Generate all test files"""
    count = 0
    for filename, code, expected in TESTS:
        filepath = filename

        # Write test file
        with open(filepath, 'w') as f:
            f.write(code)
        count += 1
        print(f"Created {filename}")

    print(f"\nGenerated {count} test files")
    print(f"Total tests: 35 (existing) + {count} (new) = {35 + count}")

if __name__ == '__main__':
    main()
