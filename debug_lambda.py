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
    class_files = codegen.compile(ast)
    print(f"Success! Generated {len(class_files)} class files")
except Exception as e:
    print(f"Error: {e}")
    traceback.print_exc()
    sys.exit(1)
