"""
Dataclasses and constants for the bytecode generator.
"""

from dataclasses import dataclass, field
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..classfile import BytecodeBuilder
    from ..types import JType


class CompileError(Exception):
    """Error during compilation."""
    pass


@dataclass
class LocalVariable:
    """A local variable in a method."""
    name: str
    type: "JType"
    slot: int


@dataclass
class LoopContext:
    """Context for a loop (for break/continue)."""
    break_label: str
    continue_label: str


@dataclass
class MethodContext:
    """Context for compiling a method."""
    class_name: str
    method_name: str
    return_type: "JType"
    builder: "BytecodeBuilder"
    locals: dict[str, LocalVariable] = field(default_factory=dict)
    next_slot: int = 0
    loop_stack: list[LoopContext] = field(default_factory=list)
    switch_break_label: Optional[str] = None
    label_map: dict[str, tuple[str, Optional[str]]] = field(default_factory=dict)  # label -> (break_label, continue_label or None)

    def push_loop(self, break_label: str, continue_label: str):
        self.loop_stack.append(LoopContext(break_label, continue_label))

    def pop_loop(self):
        self.loop_stack.pop()

    def register_label(self, label: str, break_label: str, continue_label: Optional[str] = None):
        """Register a labeled statement."""
        self.label_map[label] = (break_label, continue_label)

    def unregister_label(self, label: str):
        """Remove a label from the map."""
        if label in self.label_map:
            del self.label_map[label]

    def get_break_label(self, label: Optional[str] = None) -> str:
        if label:
            if label not in self.label_map:
                raise CompileError(f"Label not found: {label}")
            return self.label_map[label][0]
        if self.switch_break_label:
            return self.switch_break_label
        if not self.loop_stack:
            raise CompileError("break outside of loop or switch")
        return self.loop_stack[-1].break_label

    def get_continue_label(self, label: Optional[str] = None) -> str:
        if label:
            if label not in self.label_map:
                raise CompileError(f"Label not found: {label}")
            continue_label = self.label_map[label][1]
            if continue_label is None:
                raise CompileError(f"Cannot continue to non-loop label: {label}")
            return continue_label
        if not self.loop_stack:
            raise CompileError("continue outside of loop")
        return self.loop_stack[-1].continue_label

    def add_local(self, name: str, jtype: "JType") -> LocalVariable:
        var = LocalVariable(name, jtype, self.next_slot)
        self.locals[name] = var
        self.next_slot += jtype.size
        self.builder.max_locals = max(self.builder.max_locals, self.next_slot)
        return var

    def get_local(self, name: str) -> LocalVariable:
        if name not in self.locals:
            raise CompileError(f"Undefined variable: {name}")
        return self.locals[name]


@dataclass
class ResolvedMethod:
    """A resolved method from the classpath."""
    owner: str
    name: str
    descriptor: str
    is_static: bool
    is_interface: bool
    return_type: "JType"
    param_types: tuple["JType", ...]
    is_varargs: bool = False


@dataclass
class ResolvedField:
    """A resolved field from the classpath or current class."""
    owner: str
    descriptor: str
    type: "JType"
    is_static: bool


@dataclass
class LocalMethodInfo:
    """Info about a method defined in the current class."""
    name: str
    descriptor: str
    is_static: bool
    return_type: "JType"
    param_types: tuple["JType", ...]
    is_varargs: bool = False


@dataclass
class LocalFieldInfo:
    """Info about a field defined in the current class."""
    name: str
    jtype: "JType"
    descriptor: str
    is_static: bool


JAVA_LANG_CLASSES = {
    "Object", "String", "Class", "System", "Thread", "Throwable",
    "Exception", "RuntimeException", "Error",
    # Common exceptions
    "ArithmeticException", "ArrayIndexOutOfBoundsException", "ArrayStoreException",
    "ClassCastException", "ClassNotFoundException", "CloneNotSupportedException",
    "IllegalAccessException", "IllegalArgumentException", "IllegalMonitorStateException",
    "IllegalStateException", "IllegalThreadStateException", "IndexOutOfBoundsException",
    "InstantiationException", "InterruptedException", "NegativeArraySizeException",
    "NoSuchFieldException", "NoSuchMethodException", "NullPointerException",
    "NumberFormatException", "ReflectiveOperationException", "SecurityException",
    "StringIndexOutOfBoundsException", "TypeNotPresentException",
    "UnsupportedOperationException",
    # Errors
    "AssertionError", "LinkageError", "VirtualMachineError", "OutOfMemoryError",
    "StackOverflowError", "NoClassDefFoundError", "ExceptionInInitializerError",
    "Math", "StrictMath", "Number",
    "Byte", "Short", "Integer", "Long", "Float", "Double", "Character", "Boolean",
    "StringBuilder", "StringBuffer",
    "Comparable", "Cloneable", "Runnable", "Iterable", "AutoCloseable",
    "Enum", "Void",
    # Annotations
    "Deprecated", "Override", "SuppressWarnings", "SafeVarargs", "FunctionalInterface",
}

# Autoboxing/unboxing mappings: primitive_descriptor -> (wrapper_class, valueOf_desc, unbox_method, unbox_desc)
BOXING_MAP = {
    'I': ('java/lang/Integer', '(I)Ljava/lang/Integer;', 'intValue', '()I'),
    'J': ('java/lang/Long', '(J)Ljava/lang/Long;', 'longValue', '()J'),
    'F': ('java/lang/Float', '(F)Ljava/lang/Float;', 'floatValue', '()F'),
    'D': ('java/lang/Double', '(D)Ljava/lang/Double;', 'doubleValue', '()D'),
    'Z': ('java/lang/Boolean', '(Z)Ljava/lang/Boolean;', 'booleanValue', '()Z'),
    'C': ('java/lang/Character', '(C)Ljava/lang/Character;', 'charValue', '()C'),
    'B': ('java/lang/Byte', '(B)Ljava/lang/Byte;', 'byteValue', '()B'),
    'S': ('java/lang/Short', '(S)Ljava/lang/Short;', 'shortValue', '()S'),
}

# Reverse mapping: wrapper class internal name -> primitive descriptor
UNBOXING_MAP = {v[0]: k for k, v in BOXING_MAP.items()}
