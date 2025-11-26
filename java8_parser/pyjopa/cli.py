#!/usr/bin/env python3
"""
Command-line interface for pyjopa - Python Java Parser and Compiler.
"""

import argparse
import sys
from pathlib import Path


def parse_command(args):
    """Parse a Java file and output AST as JSON."""
    from .parser import Java8Parser

    parser = Java8Parser()

    for source_file in args.files:
        path = Path(source_file)
        if not path.exists():
            print(f"Error: File not found: {source_file}", file=sys.stderr)
            sys.exit(1)

        try:
            ast = parser.parse_file(str(path))
            print(ast.to_json())
        except Exception as e:
            print(f"Error parsing {source_file}: {e}", file=sys.stderr)
            sys.exit(1)


def compile_command(args):
    """Compile Java files to .class bytecode."""
    from .parser import Java8Parser
    from .codegen import CodeGenerator
    from .classreader import ClassPath

    parser = Java8Parser()

    classpath = None
    if not args.no_rt:
        try:
            classpath = ClassPath()
            classpath.add_rt_jar()
        except FileNotFoundError:
            print("Warning: rt.jar not found, method resolution may be limited", file=sys.stderr)

    output_dir = Path(args.output) if args.output else Path(".")
    output_dir.mkdir(parents=True, exist_ok=True)

    total_classes = 0
    for source_file in args.files:
        path = Path(source_file)
        if not path.exists():
            print(f"Error: File not found: {source_file}", file=sys.stderr)
            sys.exit(1)

        try:
            ast = parser.parse_file(str(path))
            codegen = CodeGenerator(classpath=classpath)
            class_files = codegen.compile(ast)

            for name, bytecode in class_files.items():
                class_path = output_dir / f"{name}.class"
                with open(class_path, "wb") as f:
                    f.write(bytecode)
                if args.verbose:
                    print(f"Wrote {class_path}")
                total_classes += 1

        except Exception as e:
            print(f"Error compiling {source_file}: {e}", file=sys.stderr)
            sys.exit(1)

    if classpath:
        classpath.close()

    if not args.quiet:
        print(f"Compiled {len(args.files)} file(s) to {total_classes} class(es)")


def main():
    """Main entry point for pyjopa CLI."""
    parser = argparse.ArgumentParser(
        prog="pyjopa",
        description="Python Java Parser - Parse and compile Java 8 source files",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Parse command
    parse_parser = subparsers.add_parser(
        "parse",
        help="Parse Java files and output AST as JSON",
    )
    parse_parser.add_argument(
        "files",
        nargs="+",
        help="Java source files to parse",
    )
    parse_parser.set_defaults(func=parse_command)

    # Compile command
    compile_parser = subparsers.add_parser(
        "compile",
        help="Compile Java files to .class bytecode",
    )
    compile_parser.add_argument(
        "files",
        nargs="+",
        help="Java source files to compile",
    )
    compile_parser.add_argument(
        "-o", "--output",
        help="Output directory for .class files (default: current directory)",
    )
    compile_parser.add_argument(
        "--no-rt",
        action="store_true",
        help="Don't use rt.jar for method resolution",
    )
    compile_parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Print each generated class file",
    )
    compile_parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Suppress summary output",
    )
    compile_parser.set_defaults(func=compile_command)

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
