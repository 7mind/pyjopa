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
    # Test the failing lambda function test instead
    ast = parser.parse_file('tests/integration/cat12_lambda_function.java')
    codegen = CodeGenerator(classpath=classpath)

    # Compile using the correct method
    class_files = codegen.compile(ast)

    # Write bytecode
    for internal_name, bytecode in class_files.items():
        filename = f"{internal_name.replace('/', '_')}.class"
        with open(filename, 'wb') as f:
            f.write(bytecode)
        print(f"Wrote {len(bytecode)} bytes to {filename}")

except Exception as e:
    print(f"Error: {e}")
    traceback.print_exc()
    sys.exit(1)
