#!/usr/bin/env python3
"""Demo script showing the Java 8 parser in action."""

from java8_parser import Java8Parser
import json

SAMPLE_CODE = '''
package com.example;

import java.util.List;
import java.util.Map;

/**
 * A sample class demonstrating Java 8 features.
 */
@SuppressWarnings("unchecked")
public class Sample<T extends Comparable<T>> {

    private final List<T> items;
    private static int counter = 0;

    public Sample(List<T> items) {
        this.items = items;
    }

    public T getFirst() {
        return items.isEmpty() ? null : items.get(0);
    }

    public void forEach(Consumer<T> action) {
        for (T item : items) {
            action.accept(item);
        }
    }

    public static void main(String[] args) {
        List<String> names = Arrays.asList("Alice", "Bob", "Charlie");
        Sample<String> sample = new Sample<>(names);

        sample.forEach(name -> System.out.println("Hello, " + name));

        sample.forEach(System.out::println);

        try (InputStream is = new FileInputStream("test.txt")) {
            int data = is.read();
        } catch (IOException | RuntimeException e) {
            e.printStackTrace();
        }
    }
}
'''


def main():
    parser = Java8Parser()

    print("=" * 60)
    print("Java 8 Parser Demo")
    print("=" * 60)
    print()
    print("Input Java code:")
    print("-" * 60)
    print(SAMPLE_CODE)
    print("-" * 60)
    print()

    ast = parser.parse(SAMPLE_CODE)

    print("Parsed AST (JSON):")
    print("-" * 60)
    json_output = ast.to_json(indent=2)
    print(json_output[:3000])
    if len(json_output) > 3000:
        print("... (truncated)")
    print("-" * 60)
    print()

    print("Summary:")
    print(f"  Package: {ast.package.name if ast.package else 'None'}")
    print(f"  Imports: {len(ast.imports)}")
    print(f"  Types: {len(ast.types)}")

    for type_decl in ast.types:
        print(f"    - {type_decl.__class__.__name__}: {type_decl.name}")
        if hasattr(type_decl, 'body'):
            for member in type_decl.body:
                member_name = getattr(member, 'name', 'unnamed')
                print(f"        {member.__class__.__name__}: {member_name}")


if __name__ == "__main__":
    main()
