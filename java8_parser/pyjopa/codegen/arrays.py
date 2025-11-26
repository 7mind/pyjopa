"""
Array operations for the bytecode generator.
"""

from .. import ast
from ..types import (
    JType, ClassJType, ArrayJType,
    BOOLEAN, BYTE, CHAR, SHORT, INT, LONG, FLOAT, DOUBLE,
)
from ..classfile import BytecodeBuilder
from .types import CompileError, MethodContext


class ArrayCompilerMixin:
    """Mixin providing array compilation operations."""
    
    # These methods are expected from other mixins/base
    compile_expression: callable
    
    def compile_new_array(self, expr: ast.NewArray, ctx: MethodContext) -> JType:
        """Compile array creation: new int[10] or new int[] {1, 2}"""
        builder = ctx.builder

        # Resolve element type
        elem_type = self.resolve_type(expr.type)
        array_type = ArrayJType(elem_type)

        if expr.initializer:
            # Array with initializer: new int[] {1, 2, 3}
            elements = expr.initializer.elements
            size = len(elements)

            # Push array size
            builder.iconst(size)

            # Create array
            self._emit_newarray(elem_type, builder)

            # Fill array with elements
            for i, element in enumerate(elements):
                builder.dup()  # dup array ref
                builder.iconst(i)  # push index
                self.compile_expression(element, ctx)  # push value
                self._emit_array_store(elem_type, builder)

        else:
            # Array with size: new int[10]
            if expr.dimensions and expr.dimensions[0] is not None:
                self.compile_expression(expr.dimensions[0], ctx)
            else:
                raise CompileError("Array creation requires size or initializer")

            self._emit_newarray(elem_type, builder)

        return array_type

    def _emit_newarray(self, elem_type: JType, builder: BytecodeBuilder):
        """Emit newarray or anewarray based on element type."""
        # newarray type codes: T_BOOLEAN=4, T_CHAR=5, T_FLOAT=6, T_DOUBLE=7, T_BYTE=8, T_SHORT=9, T_INT=10, T_LONG=11
        if elem_type == BOOLEAN:
            builder.newarray(4)
        elif elem_type == CHAR:
            builder.newarray(5)
        elif elem_type == FLOAT:
            builder.newarray(6)
        elif elem_type == DOUBLE:
            builder.newarray(7)
        elif elem_type == BYTE:
            builder.newarray(8)
        elif elem_type == SHORT:
            builder.newarray(9)
        elif elem_type == INT:
            builder.newarray(10)
        elif elem_type == LONG:
            builder.newarray(11)
        elif isinstance(elem_type, ClassJType):
            builder.anewarray(elem_type.internal_name())
        elif isinstance(elem_type, ArrayJType):
            builder.anewarray(elem_type.descriptor())
        else:
            raise CompileError(f"Unsupported array element type: {elem_type}")

    def compile_array_access(self, expr: ast.ArrayAccess, ctx: MethodContext) -> JType:
        """Compile array access: arr[index]"""
        builder = ctx.builder

        # Compile array reference
        array_type = self.compile_expression(expr.array, ctx)

        if not isinstance(array_type, ArrayJType):
            raise CompileError(f"Cannot index non-array type: {array_type}")

        # Compile index
        self.compile_expression(expr.index, ctx)

        # Load element
        elem_type = array_type.element_type
        self._emit_array_load(elem_type, builder)

        return elem_type

    def _emit_array_load(self, elem_type: JType, builder: BytecodeBuilder):
        """Emit appropriate array load instruction."""
        if elem_type == INT:
            builder.iaload()
        elif elem_type == LONG:
            builder.laload()
        elif elem_type == FLOAT:
            builder.faload()
        elif elem_type == DOUBLE:
            builder.daload()
        elif elem_type == BYTE or elem_type == BOOLEAN:
            builder.baload()
        elif elem_type == CHAR:
            builder.caload()
        elif elem_type == SHORT:
            builder.saload()
        elif isinstance(elem_type, (ClassJType, ArrayJType)):
            builder.aaload()
        else:
            raise CompileError(f"Unsupported array element type: {elem_type}")

    def _emit_array_store(self, elem_type: JType, builder: BytecodeBuilder):
        """Emit appropriate array store instruction."""
        if elem_type == INT:
            builder.iastore()
        elif elem_type == LONG:
            builder.lastore()
        elif elem_type == FLOAT:
            builder.fastore()
        elif elem_type == DOUBLE:
            builder.dastore()
        elif elem_type == BYTE or elem_type == BOOLEAN:
            builder.bastore()
        elif elem_type == CHAR:
            builder.castore()
        elif elem_type == SHORT:
            builder.sastore()
        elif isinstance(elem_type, (ClassJType, ArrayJType)):
            builder.aastore()
        else:
            raise CompileError(f"Unsupported array element type: {elem_type}")

    def _compile_array_initializer(self, init: ast.ArrayInitializer, array_type: ArrayJType, ctx: MethodContext):
        """Compile an array initializer: {1, 2, 3}"""
        builder = ctx.builder
        elem_type = array_type.element_type
        elements = init.elements
        size = len(elements)

        # Push array size
        builder.iconst(size)

        # Create array
        self._emit_newarray(elem_type, builder)

        # Fill array with elements
        for i, element in enumerate(elements):
            builder.dup()  # dup array ref
            builder.iconst(i)  # push index
            self.compile_expression(element, ctx)  # push value
            self._emit_array_store(elem_type, builder)

