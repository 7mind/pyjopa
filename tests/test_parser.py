"""Tests for the Java 8 parser."""

import json
import pytest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from pyjopa import Java8Parser
from pyjopa.ast import (
    CompilationUnit, ClassDeclaration, MethodDeclaration, FieldDeclaration,
    PrimitiveType, ClassType, Literal, Identifier
)


@pytest.fixture
def parser():
    return Java8Parser()


class TestBasicParsing:
    def test_empty_class(self, parser):
        source = "class Foo {}"
        result = parser.parse(source)
        assert isinstance(result, CompilationUnit)
        assert len(result.types) == 1
        assert isinstance(result.types[0], ClassDeclaration)
        assert result.types[0].name == "Foo"

    def test_package_declaration(self, parser):
        source = "package com.example; class Foo {}"
        result = parser.parse(source)
        assert result.package is not None
        assert result.package.name == "com.example"

    def test_imports(self, parser):
        source = """
        import java.util.List;
        import java.util.*;
        import static java.lang.Math.PI;
        class Foo {}
        """
        result = parser.parse(source)
        assert len(result.imports) == 3
        assert result.imports[0].name == "java.util.List"
        assert not result.imports[0].is_wildcard
        assert result.imports[1].is_wildcard
        assert result.imports[2].is_static

    def test_method_declaration(self, parser):
        source = """
        class Foo {
            public static void main(String[] args) {
                System.out.println("Hello");
            }
        }
        """
        result = parser.parse(source)
        cls = result.types[0]
        assert isinstance(cls, ClassDeclaration)
        assert len(cls.body) == 1
        method = cls.body[0]
        assert isinstance(method, MethodDeclaration)
        assert method.name == "main"

    def test_field_declaration(self, parser):
        source = """
        class Foo {
            private int x = 42;
            public String name;
        }
        """
        result = parser.parse(source)
        cls = result.types[0]
        assert len(cls.body) == 2
        assert isinstance(cls.body[0], FieldDeclaration)
        assert isinstance(cls.body[1], FieldDeclaration)

    def test_interface(self, parser):
        source = """
        interface Bar {
            void doSomething();
        }
        """
        result = parser.parse(source)
        assert len(result.types) == 1

    def test_enum(self, parser):
        source = """
        enum Color {
            RED, GREEN, BLUE
        }
        """
        result = parser.parse(source)
        assert len(result.types) == 1

    def test_annotation_type(self, parser):
        source = """
        @interface MyAnnotation {
            String value();
        }
        """
        result = parser.parse(source)
        assert len(result.types) == 1


class TestGenerics:
    def test_generic_class(self, parser):
        source = "class Box<T> {}"
        result = parser.parse(source)
        cls = result.types[0]
        assert len(cls.type_parameters) == 1
        assert cls.type_parameters[0].name == "T"

    def test_bounded_type_parameter(self, parser):
        source = "class NumberBox<T extends Number> {}"
        result = parser.parse(source)
        cls = result.types[0]
        assert len(cls.type_parameters) == 1
        assert len(cls.type_parameters[0].bounds) == 1

    def test_generic_method(self, parser):
        source = """
        class Foo {
            public <T> T identity(T value) { return value; }
        }
        """
        result = parser.parse(source)


class TestExpressions:
    def test_literals(self, parser):
        source = """
        class Foo {
            int i = 42;
            long l = 42L;
            double d = 3.14;
            float f = 3.14f;
            boolean b = true;
            char c = 'x';
            String s = "hello";
            Object o = null;
        }
        """
        result = parser.parse(source)
        assert len(result.types[0].body) == 8

    def test_lambda(self, parser):
        source = """
        class Foo {
            Runnable r = () -> System.out.println("hi");
        }
        """
        result = parser.parse(source)

    def test_method_reference(self, parser):
        source = """
        class Foo {
            Function<String, Integer> f = String::length;
        }
        """
        result = parser.parse(source)


class TestStatements:
    def test_if_else(self, parser):
        source = """
        class Foo {
            void test() {
                if (true) {
                    System.out.println("yes");
                } else {
                    System.out.println("no");
                }
            }
        }
        """
        result = parser.parse(source)

    def test_for_loop(self, parser):
        source = """
        class Foo {
            void test() {
                for (int i = 0; i < 10; i++) {
                    System.out.println(i);
                }
            }
        }
        """
        result = parser.parse(source)

    def test_enhanced_for(self, parser):
        source = """
        class Foo {
            void test(int[] arr) {
                for (int x : arr) {
                    System.out.println(x);
                }
            }
        }
        """
        result = parser.parse(source)

    def test_try_catch_finally(self, parser):
        source = """
        class Foo {
            void test() {
                try {
                    riskyOperation();
                } catch (Exception e) {
                    handleError(e);
                } finally {
                    cleanup();
                }
            }
        }
        """
        result = parser.parse(source)

    def test_try_with_resources(self, parser):
        source = """
        class Foo {
            void test() throws Exception {
                try (InputStream is = new FileInputStream("file")) {
                    read(is);
                }
            }
        }
        """
        result = parser.parse(source)

    def test_switch(self, parser):
        source = """
        class Foo {
            void test(int x) {
                switch (x) {
                    case 1:
                        doOne();
                        break;
                    case 2:
                        doTwo();
                        break;
                    default:
                        doDefault();
                }
            }
        }
        """
        result = parser.parse(source)


class TestJsonSerialization:
    def test_basic_serialization(self, parser):
        source = "class Foo {}"
        result = parser.parse(source)
        json_str = result.to_json()
        data = json.loads(json_str)
        assert data["_type"] == "CompilationUnit"
        assert len(data["types"]) == 1
        assert data["types"][0]["_type"] == "ClassDeclaration"
        assert data["types"][0]["name"] == "Foo"

    def test_complex_serialization(self, parser):
        source = """
        package com.example;
        import java.util.List;
        public class Foo<T> extends Bar implements Baz {
            private int x = 42;
            public void method() {}
        }
        """
        result = parser.parse(source)
        json_str = result.to_json()
        data = json.loads(json_str)
        assert data["package"]["name"] == "com.example"
        assert len(data["imports"]) == 1


class TestUnicodeSupport:
    def test_unicode_escape(self, parser):
        source = r'class Foo { String s = "\u0048\u0065\u006c\u006c\u006f"; }'
        result = parser.parse(source)
        assert len(result.types) == 1


class TestWhitelistFiles:
    """Test parsing files from the whitelist."""

    @pytest.fixture
    def whitelist_files(self):
        whitelist_path = Path(__file__).parent.parent / "whitelist.txt"
        if not whitelist_path.exists():
            pytest.skip("whitelist.txt not found")
        with open(whitelist_path) as f:
            files = [line.strip() for line in f if line.strip()]
        excluded = {"DeepStringConcat.java"}
        return [f for f in files if Path(f).name not in excluded]

    def test_whitelist_sample(self, parser, whitelist_files):
        """Test a sample of whitelist files."""
        sample = whitelist_files[:100]
        for file_path in sample:
            if Path(file_path).exists():
                result = parser.parse_file(file_path)
                assert isinstance(result, CompilationUnit)
                json_str = result.to_json()
                assert json.loads(json_str) is not None
