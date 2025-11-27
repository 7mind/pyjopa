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

    # Compile but don't cache (to avoid the caching error)
    codegen.compile_ast(ast)

    # Get the raw bytecode
    bytecode = codegen.class_file.to_bytes()

    # Write it to a file
    with open('TestLambdaRunnable.class', 'wb') as f:
        f.write(bytecode)

    print(f"Wrote {len(bytecode)} bytes to TestLambdaRunnable.class")

except Exception as e:
    print(f"Error: {e}")
    traceback.print_exc()
    sys.exit(1)
