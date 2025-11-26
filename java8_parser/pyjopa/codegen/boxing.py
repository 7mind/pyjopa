"""
Boxing/unboxing and type conversion for the bytecode generator.
"""

from ..types import (
    JType, PrimitiveJType, ClassJType,
    BOOLEAN, BYTE, CHAR, SHORT, INT, LONG, FLOAT, DOUBLE,
    PRIMITIVE_BY_DESCRIPTOR,
)
from ..classfile import BytecodeBuilder
from .types import CompileError, LocalVariable, BOXING_MAP, UNBOXING_MAP


class BoxingMixin:
    """Mixin providing boxing/unboxing and type conversion."""
    
    def load_local(self, var: LocalVariable, builder: BytecodeBuilder):
        if var.type == INT or var.type == BOOLEAN or var.type == BYTE or var.type == CHAR or var.type == SHORT:
            builder.iload(var.slot)
        elif var.type == LONG:
            builder.lload(var.slot)
        elif var.type == FLOAT:
            builder.fload(var.slot)
        elif var.type == DOUBLE:
            builder.dload(var.slot)
        elif var.type.is_reference:
            builder.aload(var.slot)

    def store_local(self, var: LocalVariable, builder: BytecodeBuilder):
        if var.type == INT or var.type == BOOLEAN or var.type == BYTE or var.type == CHAR or var.type == SHORT:
            builder.istore(var.slot)
        elif var.type == LONG:
            builder.lstore(var.slot)
        elif var.type == FLOAT:
            builder.fstore(var.slot)
        elif var.type == DOUBLE:
            builder.dstore(var.slot)
        elif var.type.is_reference:
            builder.astore(var.slot)

    def emit_boxing(self, primitive_type: JType, builder: BytecodeBuilder) -> ClassJType:
        """Box a primitive value on the stack to its wrapper type."""
        desc = primitive_type.descriptor()
        if desc not in BOXING_MAP:
            raise CompileError(f"Cannot box type: {primitive_type}")
        wrapper_class, valueof_desc, _, _ = BOXING_MAP[desc]
        builder.invokestatic(wrapper_class, "valueOf", valueof_desc, primitive_type.size, 1)
        return ClassJType(wrapper_class)

    def emit_unboxing(self, wrapper_type: ClassJType, builder: BytecodeBuilder) -> JType:
        """Unbox a wrapper value on the stack to its primitive type."""
        internal_name = wrapper_type.internal_name()
        if internal_name not in UNBOXING_MAP:
            raise CompileError(f"Cannot unbox type: {wrapper_type}")
        prim_desc = UNBOXING_MAP[internal_name]
        wrapper_class, _, unbox_method, unbox_desc = BOXING_MAP[prim_desc]
        prim_type = PRIMITIVE_BY_DESCRIPTOR[prim_desc]
        builder.invokevirtual(wrapper_class, unbox_method, unbox_desc, 0, prim_type.size)
        return prim_type

    def needs_boxing(self, source_type: JType, target_type: JType) -> bool:
        """Check if we need to box source_type to target_type."""
        if not isinstance(source_type, PrimitiveJType):
            return False
        if not isinstance(target_type, ClassJType):
            return False
        prim_desc = source_type.descriptor()
        if prim_desc not in BOXING_MAP:
            return False
        wrapper_class = BOXING_MAP[prim_desc][0]
        return target_type.internal_name() == wrapper_class

    def needs_unboxing(self, source_type: JType, target_type: JType) -> bool:
        """Check if we need to unbox source_type to target_type."""
        if not isinstance(source_type, ClassJType):
            return False
        if not isinstance(target_type, PrimitiveJType):
            return False
        internal_name = source_type.internal_name()
        if internal_name not in UNBOXING_MAP:
            return False
        prim_desc = UNBOXING_MAP[internal_name]
        return target_type.descriptor() == prim_desc

    def emit_conversion(self, source_type: JType, target_type: JType, builder: BytecodeBuilder) -> JType:
        """Emit code to convert source_type to target_type if needed."""
        if self.needs_boxing(source_type, target_type):
            return self.emit_boxing(source_type, builder)
        elif self.needs_unboxing(source_type, target_type):
            return self.emit_unboxing(source_type, builder)
        return source_type

