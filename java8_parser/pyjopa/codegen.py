"""
Bytecode generator for Java 8 AST.
Generates Java 6 bytecode (version 50.0).

This module re-exports from the codegen package for backwards compatibility.
"""

from .codegen import (
    CompileError,
    CodeGenerator,
    compile_file,
    LocalVariable,
    MethodContext,
    ResolvedMethod,
    LocalMethodInfo,
    LocalFieldInfo,
    JAVA_LANG_CLASSES,
    BOXING_MAP,
    UNBOXING_MAP,
)

__all__ = [
    'CompileError',
    'CodeGenerator',
    'compile_file',
    'LocalVariable',
    'MethodContext',
    'ResolvedMethod',
    'LocalMethodInfo',
    'LocalFieldInfo',
    'JAVA_LANG_CLASSES',
    'BOXING_MAP',
    'UNBOXING_MAP',
]
