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


def _get_file_dependencies(source_file: Path, parser) -> tuple[str, set[str]]:
    """Extract package and imported types from a source file.
    Returns: (package_name, set_of_imported_types)"""
    ast = parser.parse_file(str(source_file))

    package = ast.package.name if ast.package else ""
    imported_types = set()

    # Collect imported types (simple names only, from same or imported packages)
    for imp in ast.imports:
        if not imp.is_static and not imp.is_wildcard:
            # Single-type import: java.util.List -> List
            simple_name = imp.name.split(".")[-1]
            imported_types.add(simple_name)

    return package, imported_types


def _topological_sort(files: list[Path], parser) -> list[Path]:
    """Sort files in dependency order using topological sort.
    Files that define types used by other files come first."""
    from collections import defaultdict, deque

    # Map: package.TypeName -> source file
    type_to_file = {}
    # Map: source file -> set of types it depends on
    file_deps = {}

    # First pass: identify what types each file defines
    for f in files:
        ast = parser.parse_file(str(f))
        package = ast.package.name if ast.package else ""

        for type_decl in ast.types:
            type_name = type_decl.name
            full_name = f"{package}.{type_name}" if package else type_name
            type_to_file[full_name] = f

    # Second pass: identify dependencies
    for f in files:
        ast = parser.parse_file(str(f))
        package = ast.package.name if ast.package else ""
        deps = set()

        # Add dependencies from imports
        for imp in ast.imports:
            if not imp.is_static and not imp.is_wildcard:
                # Check if this import is for a type in our compilation set
                imported_type = imp.name
                if imported_type in type_to_file:
                    deps.add(imported_type)
                else:
                    deps.add(imp.name)

        # For same-package dependencies, check if type names appear in source
        # This is a heuristic for detecting usage without full semantic analysis
        source_text = f.read_text()
        for full_type_name, type_file in type_to_file.items():
            if type_file != f:  # Don't depend on ourselves
                simple_name = full_type_name.split(".")[-1]
                # Check if type name appears in source (crude but effective)
                if package:
                    # Same package?
                    type_package = ".".join(full_type_name.split(".")[:-1])
                    if type_package == package and simple_name in source_text:
                        deps.add(full_type_name)

        # Check if types defined in this file extend/implement types in other files
        for type_decl in ast.types:
            from pyjopa.ast import ClassDeclaration, InterfaceDeclaration, EnumDeclaration

            # Get superclass and interfaces
            if isinstance(type_decl, ClassDeclaration) and type_decl.extends:
                # extends Type -> might be in same package
                super_name = type_decl.extends.name if hasattr(type_decl.extends, 'name') else str(type_decl.extends)
                # Try same package first
                if package:
                    candidate = f"{package}.{super_name}"
                    if candidate in type_to_file:
                        deps.add(candidate)
                else:
                    if super_name in type_to_file:
                        deps.add(super_name)

            if isinstance(type_decl, (ClassDeclaration, EnumDeclaration)):
                for iface in type_decl.implements:
                    iface_name = iface.name if hasattr(iface, 'name') else str(iface)
                    if package:
                        candidate = f"{package}.{iface_name}"
                        if candidate in type_to_file:
                            deps.add(candidate)
                    else:
                        if iface_name in type_to_file:
                            deps.add(iface_name)

        file_deps[f] = deps

    # Build adjacency list: file -> files that depend on it
    in_degree = {f: 0 for f in files}
    adj = defaultdict(list)

    for file, deps in file_deps.items():
        for dep in deps:
            if dep in type_to_file:
                dep_file = type_to_file[dep]
                if dep_file != file:  # Skip self-dependencies
                    adj[dep_file].append(file)
                    in_degree[file] += 1

    # Topological sort using Kahn's algorithm
    queue = deque([f for f in files if in_degree[f] == 0])
    result = []

    while queue:
        current = queue.popleft()
        result.append(current)

        for neighbor in adj[current]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    # Check for cycles
    if len(result) != len(files):
        # Circular dependency detected - return original order
        return files

    return result


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
    else:
        classpath = ClassPath()

    output_dir = Path(args.output) if args.output else Path(".")

    # Create output directory first
    output_dir.mkdir(parents=True, exist_ok=True)

    # Add custom classpath entries
    if args.classpath:
        import os
        for entry in args.classpath.split(os.pathsep):
            if entry:
                classpath.add_path(entry)

    # Add output directory to classpath so previously compiled classes can be found
    if classpath:
        classpath.add_path(str(output_dir.absolute()))

    # Sort files in dependency order if multiple files
    file_paths = [Path(f) for f in args.files]
    if len(file_paths) > 1:
        file_paths = _topological_sort(file_paths, parser)
        if args.verbose:
            print(f"Compilation order: {[str(f) for f in file_paths]}")

    total_classes = 0
    for path in file_paths:
        if not path.exists():
            print(f"Error: File not found: {path}", file=sys.stderr)
            sys.exit(1)

        try:
            ast = parser.parse_file(str(path))
            codegen = CodeGenerator(classpath=classpath)
            class_files = codegen.compile(ast)

            for name, bytecode in class_files.items():
                class_path = output_dir / f"{name}.class"
                class_path.parent.mkdir(parents=True, exist_ok=True)
                with open(class_path, "wb") as f:
                    f.write(bytecode)
                if args.verbose:
                    print(f"Wrote {class_path}")
                total_classes += 1

        except Exception as e:
            print(f"Error compiling {path}: {e}", file=sys.stderr)
            sys.exit(1)

    if classpath:
        classpath.close()

    if not args.quiet:
        print(f"Compiled {len(file_paths)} file(s) to {total_classes} class(es)")


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
        "-cp", "--classpath",
        help="Additional classpath entries (colon-separated paths to .jar files or directories)",
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
