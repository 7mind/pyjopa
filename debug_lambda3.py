#!/usr/bin/env python3
import traceback
import sys
from pathlib import Path
from pyjopa.parser import Java8Parser
from pyjopa.codegen import CodeGenerator
from pyjopa.classreader import ClassPath

parser = Java8Parser()
classpath = ClassPath()

try:
    classpath.add_rt_jar()
except FileNotFoundError:
    print("Warning: rt.jar not found")

try:
    ast = parser.parse_file('tests/integration/cat12_lambda_runnable.java')
    codegen = CodeGenerator(classpath=classpath)

    # Monkeypatch _cache_compiled_class to dump bytecode before attempting to cache
    original_cache = codegen._cache_compiled_class

    def dump_and_cache(internal_name, bytecode):
        # Write bytecode to file before caching
        with open(f'{internal_name}.class', 'wb') as f:
            f.write(bytecode)
        print(f"Wrote {len(bytecode)} bytes to {internal_name}.class")

        # Now try the original caching
        return original_cache(internal_name, bytecode)

    codegen._cache_compiled_class = dump_and_cache

    # Compile
    class_files = codegen.compile(ast)
    print(f"Success! Generated {len(class_files)} class files")

except Exception as e:
    print(f"Error: {e}")
    traceback.print_exc()
