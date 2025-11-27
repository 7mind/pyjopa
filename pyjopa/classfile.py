"""
Java class file writer for Java 6 bytecode (version 50.0).
"""

import struct
from dataclasses import dataclass, field
from typing import Optional
from enum import IntEnum, IntFlag


class ClassFileVersion:
    JAVA_6 = (50, 0)
    JAVA_7 = (51, 0)
    JAVA_8 = (52, 0)


class AccessFlags(IntFlag):
    PUBLIC = 0x0001
    PRIVATE = 0x0002
    PROTECTED = 0x0004
    STATIC = 0x0008
    FINAL = 0x0010
    SUPER = 0x0020  # For classes (invokespecial semantics)
    SYNCHRONIZED = 0x0020  # For methods
    VOLATILE = 0x0040
    BRIDGE = 0x0040
    TRANSIENT = 0x0080
    VARARGS = 0x0080
    NATIVE = 0x0100
    INTERFACE = 0x0200
    ABSTRACT = 0x0400
    STRICT = 0x0800
    SYNTHETIC = 0x1000
    ANNOTATION = 0x2000
    ENUM = 0x4000


class Opcode(IntEnum):
    NOP = 0x00
    ACONST_NULL = 0x01
    ICONST_M1 = 0x02
    ICONST_0 = 0x03
    ICONST_1 = 0x04
    ICONST_2 = 0x05
    ICONST_3 = 0x06
    ICONST_4 = 0x07
    ICONST_5 = 0x08
    LCONST_0 = 0x09
    LCONST_1 = 0x0A
    FCONST_0 = 0x0B
    FCONST_1 = 0x0C
    FCONST_2 = 0x0D
    DCONST_0 = 0x0E
    DCONST_1 = 0x0F
    BIPUSH = 0x10
    SIPUSH = 0x11
    LDC = 0x12
    LDC_W = 0x13
    LDC2_W = 0x14
    ILOAD = 0x15
    LLOAD = 0x16
    FLOAD = 0x17
    DLOAD = 0x18
    ALOAD = 0x19
    ILOAD_0 = 0x1A
    ILOAD_1 = 0x1B
    ILOAD_2 = 0x1C
    ILOAD_3 = 0x1D
    LLOAD_0 = 0x1E
    LLOAD_1 = 0x1F
    LLOAD_2 = 0x20
    LLOAD_3 = 0x21
    FLOAD_0 = 0x22
    FLOAD_1 = 0x23
    FLOAD_2 = 0x24
    FLOAD_3 = 0x25
    DLOAD_0 = 0x26
    DLOAD_1 = 0x27
    DLOAD_2 = 0x28
    DLOAD_3 = 0x29
    ALOAD_0 = 0x2A
    ALOAD_1 = 0x2B
    ALOAD_2 = 0x2C
    ALOAD_3 = 0x2D
    IALOAD = 0x2E
    LALOAD = 0x2F
    FALOAD = 0x30
    DALOAD = 0x31
    AALOAD = 0x32
    BALOAD = 0x33
    CALOAD = 0x34
    SALOAD = 0x35
    ISTORE = 0x36
    LSTORE = 0x37
    FSTORE = 0x38
    DSTORE = 0x39
    ASTORE = 0x3A
    ISTORE_0 = 0x3B
    ISTORE_1 = 0x3C
    ISTORE_2 = 0x3D
    ISTORE_3 = 0x3E
    LSTORE_0 = 0x3F
    LSTORE_1 = 0x40
    LSTORE_2 = 0x41
    LSTORE_3 = 0x42
    FSTORE_0 = 0x43
    FSTORE_1 = 0x44
    FSTORE_2 = 0x45
    FSTORE_3 = 0x46
    DSTORE_0 = 0x47
    DSTORE_1 = 0x48
    DSTORE_2 = 0x49
    DSTORE_3 = 0x4A
    ASTORE_0 = 0x4B
    ASTORE_1 = 0x4C
    ASTORE_2 = 0x4D
    ASTORE_3 = 0x4E
    IASTORE = 0x4F
    LASTORE = 0x50
    FASTORE = 0x51
    DASTORE = 0x52
    AASTORE = 0x53
    BASTORE = 0x54
    CASTORE = 0x55
    SASTORE = 0x56
    POP = 0x57
    POP2 = 0x58
    DUP = 0x59
    DUP_X1 = 0x5A
    DUP_X2 = 0x5B
    DUP2 = 0x5C
    DUP2_X1 = 0x5D
    DUP2_X2 = 0x5E
    SWAP = 0x5F
    IADD = 0x60
    LADD = 0x61
    FADD = 0x62
    DADD = 0x63
    ISUB = 0x64
    LSUB = 0x65
    FSUB = 0x66
    DSUB = 0x67
    IMUL = 0x68
    LMUL = 0x69
    FMUL = 0x6A
    DMUL = 0x6B
    IDIV = 0x6C
    LDIV = 0x6D
    FDIV = 0x6E
    DDIV = 0x6F
    IREM = 0x70
    LREM = 0x71
    FREM = 0x72
    DREM = 0x73
    INEG = 0x74
    LNEG = 0x75
    FNEG = 0x76
    DNEG = 0x77
    ISHL = 0x78
    LSHL = 0x79
    ISHR = 0x7A
    LSHR = 0x7B
    IUSHR = 0x7C
    LUSHR = 0x7D
    IAND = 0x7E
    LAND = 0x7F
    IOR = 0x80
    LOR = 0x81
    IXOR = 0x82
    LXOR = 0x83
    IINC = 0x84
    I2L = 0x85
    I2F = 0x86
    I2D = 0x87
    L2I = 0x88
    L2F = 0x89
    L2D = 0x8A
    F2I = 0x8B
    F2L = 0x8C
    F2D = 0x8D
    D2I = 0x8E
    D2L = 0x8F
    D2F = 0x90
    I2B = 0x91
    I2C = 0x92
    I2S = 0x93
    LCMP = 0x94
    FCMPL = 0x95
    FCMPG = 0x96
    DCMPL = 0x97
    DCMPG = 0x98
    IFEQ = 0x99
    IFNE = 0x9A
    IFLT = 0x9B
    IFGE = 0x9C
    IFGT = 0x9D
    IFLE = 0x9E
    IF_ICMPEQ = 0x9F
    IF_ICMPNE = 0xA0
    IF_ICMPLT = 0xA1
    IF_ICMPGE = 0xA2
    IF_ICMPGT = 0xA3
    IF_ICMPLE = 0xA4
    IF_ACMPEQ = 0xA5
    IF_ACMPNE = 0xA6
    GOTO = 0xA7
    JSR = 0xA8
    RET = 0xA9
    TABLESWITCH = 0xAA
    LOOKUPSWITCH = 0xAB
    IRETURN = 0xAC
    LRETURN = 0xAD
    FRETURN = 0xAE
    DRETURN = 0xAF
    ARETURN = 0xB0
    RETURN = 0xB1
    GETSTATIC = 0xB2
    PUTSTATIC = 0xB3
    GETFIELD = 0xB4
    PUTFIELD = 0xB5
    INVOKEVIRTUAL = 0xB6
    INVOKESPECIAL = 0xB7
    INVOKESTATIC = 0xB8
    INVOKEINTERFACE = 0xB9
    INVOKEDYNAMIC = 0xBA
    NEW = 0xBB
    NEWARRAY = 0xBC
    ANEWARRAY = 0xBD
    ARRAYLENGTH = 0xBE
    ATHROW = 0xBF
    CHECKCAST = 0xC0
    INSTANCEOF = 0xC1
    MONITORENTER = 0xC2
    MONITOREXIT = 0xC3
    WIDE = 0xC4
    MULTIANEWARRAY = 0xC5
    IFNULL = 0xC6
    IFNONNULL = 0xC7
    GOTO_W = 0xC8
    JSR_W = 0xC9


class ConstantPoolTag(IntEnum):
    UTF8 = 1
    INTEGER = 3
    FLOAT = 4
    LONG = 5
    DOUBLE = 6
    CLASS = 7
    STRING = 8
    FIELDREF = 9
    METHODREF = 10
    INTERFACE_METHODREF = 11
    NAME_AND_TYPE = 12
    METHOD_HANDLE = 15
    METHOD_TYPE = 16
    INVOKE_DYNAMIC = 18


class ConstantPool:
    """Manages the constant pool for a class file."""

    def __init__(self):
        self._entries: list[tuple] = [None]  # 1-indexed
        self._cache: dict = {}

    def __len__(self) -> int:
        return len(self._entries)

    def _add(self, entry: tuple) -> int:
        key = entry
        if key in self._cache:
            return self._cache[key]
        idx = len(self._entries)
        self._entries.append(entry)
        self._cache[key] = idx
        # Long and Double take two slots
        if entry[0] in (ConstantPoolTag.LONG, ConstantPoolTag.DOUBLE):
            self._entries.append(None)
        return idx

    def add_utf8(self, value: str) -> int:
        return self._add((ConstantPoolTag.UTF8, value))

    def add_integer(self, value: int) -> int:
        return self._add((ConstantPoolTag.INTEGER, value))

    def add_float(self, value: float) -> int:
        return self._add((ConstantPoolTag.FLOAT, value))

    def add_long(self, value: int) -> int:
        return self._add((ConstantPoolTag.LONG, value))

    def add_double(self, value: float) -> int:
        return self._add((ConstantPoolTag.DOUBLE, value))

    def add_class(self, internal_name: str) -> int:
        name_idx = self.add_utf8(internal_name)
        return self._add((ConstantPoolTag.CLASS, name_idx))

    def add_string(self, value: str) -> int:
        utf8_idx = self.add_utf8(value)
        return self._add((ConstantPoolTag.STRING, utf8_idx))

    def add_name_and_type(self, name: str, descriptor: str) -> int:
        name_idx = self.add_utf8(name)
        desc_idx = self.add_utf8(descriptor)
        return self._add((ConstantPoolTag.NAME_AND_TYPE, name_idx, desc_idx))

    def add_fieldref(self, class_name: str, field_name: str, descriptor: str) -> int:
        class_idx = self.add_class(class_name)
        nat_idx = self.add_name_and_type(field_name, descriptor)
        return self._add((ConstantPoolTag.FIELDREF, class_idx, nat_idx))

    def add_methodref(self, class_name: str, method_name: str, descriptor: str) -> int:
        class_idx = self.add_class(class_name)
        nat_idx = self.add_name_and_type(method_name, descriptor)
        return self._add((ConstantPoolTag.METHODREF, class_idx, nat_idx))

    def add_interface_methodref(self, class_name: str, method_name: str, descriptor: str) -> int:
        class_idx = self.add_class(class_name)
        nat_idx = self.add_name_and_type(method_name, descriptor)
        return self._add((ConstantPoolTag.INTERFACE_METHODREF, class_idx, nat_idx))

    def write(self, out: bytearray):
        out.extend(struct.pack(">H", len(self._entries)))
        for entry in self._entries[1:]:
            if entry is None:
                continue
            tag = entry[0]
            out.append(tag)
            if tag == ConstantPoolTag.UTF8:
                data = entry[1].encode("utf-8")
                out.extend(struct.pack(">H", len(data)))
                out.extend(data)
            elif tag == ConstantPoolTag.INTEGER:
                out.extend(struct.pack(">i", entry[1]))
            elif tag == ConstantPoolTag.FLOAT:
                out.extend(struct.pack(">f", entry[1]))
            elif tag == ConstantPoolTag.LONG:
                out.extend(struct.pack(">q", entry[1]))
            elif tag == ConstantPoolTag.DOUBLE:
                out.extend(struct.pack(">d", entry[1]))
            elif tag == ConstantPoolTag.CLASS:
                out.extend(struct.pack(">H", entry[1]))
            elif tag == ConstantPoolTag.STRING:
                out.extend(struct.pack(">H", entry[1]))
            elif tag == ConstantPoolTag.NAME_AND_TYPE:
                out.extend(struct.pack(">HH", entry[1], entry[2]))
            elif tag in (ConstantPoolTag.FIELDREF, ConstantPoolTag.METHODREF,
                         ConstantPoolTag.INTERFACE_METHODREF):
                out.extend(struct.pack(">HH", entry[1], entry[2]))


@dataclass
class AnnotationInfo:
    """An annotation to write to class file."""
    type_descriptor: str  # e.g., "Ljava/lang/Deprecated;"
    elements: dict = field(default_factory=dict)  # name -> (tag, value)

    def write(self, cp: ConstantPool, out: bytearray):
        type_idx = cp.add_utf8(self.type_descriptor)
        out.extend(struct.pack(">H", type_idx))
        out.extend(struct.pack(">H", len(self.elements)))
        for name, (tag, value) in self.elements.items():
            name_idx = cp.add_utf8(name)
            out.extend(struct.pack(">H", name_idx))
            self._write_element_value(cp, out, tag, value)

    def _write_element_value(self, cp: ConstantPool, out: bytearray, tag: str, value):
        out.append(ord(tag))
        if tag == 'B' or tag == 'C' or tag == 'I' or tag == 'S' or tag == 'Z':
            idx = cp.add_integer(value)
            out.extend(struct.pack(">H", idx))
        elif tag == 'D':
            idx = cp.add_double(value)
            out.extend(struct.pack(">H", idx))
        elif tag == 'F':
            idx = cp.add_float(value)
            out.extend(struct.pack(">H", idx))
        elif tag == 'J':
            idx = cp.add_long(value)
            out.extend(struct.pack(">H", idx))
        elif tag == 's':
            idx = cp.add_utf8(value)
            out.extend(struct.pack(">H", idx))
        elif tag == 'e':
            # Enum: value is (type_desc, const_name)
            type_idx = cp.add_utf8(value[0])
            name_idx = cp.add_utf8(value[1])
            out.extend(struct.pack(">HH", type_idx, name_idx))
        elif tag == 'c':
            # Class: value is class descriptor
            idx = cp.add_utf8(value)
            out.extend(struct.pack(">H", idx))
        elif tag == '@':
            # Nested annotation
            value.write(cp, out)
        elif tag == '[':
            # Array: value is list of (tag, value)
            out.extend(struct.pack(">H", len(value)))
            for elem_tag, elem_value in value:
                self._write_element_value(cp, out, elem_tag, elem_value)


def write_annotations_attribute(cp: ConstantPool, out: bytearray,
                                attr_name: str, annotations: list[AnnotationInfo]):
    """Write a RuntimeVisibleAnnotations or RuntimeInvisibleAnnotations attribute."""
    if not annotations:
        return
    attr_name_idx = cp.add_utf8(attr_name)
    data = bytearray()
    data.extend(struct.pack(">H", len(annotations)))
    for ann in annotations:
        ann.write(cp, data)
    out.extend(struct.pack(">H", attr_name_idx))
    out.extend(struct.pack(">I", len(data)))
    out.extend(data)


def write_method_parameters_attribute(cp: ConstantPool, out: bytearray,
                                      parameter_names: list[str], parameter_flags: list[int] = None):
    """Write a MethodParameters attribute for reflection."""
    if not parameter_names:
        return
    attr_name_idx = cp.add_utf8("MethodParameters")
    data = bytearray()
    data.append(len(parameter_names))  # parameters_count (u1)
    for i, name in enumerate(parameter_names):
        name_idx = cp.add_utf8(name) if name else 0
        flags = parameter_flags[i] if parameter_flags else 0
        data.extend(struct.pack(">H", name_idx))
        data.extend(struct.pack(">H", flags))
    out.extend(struct.pack(">H", attr_name_idx))
    out.extend(struct.pack(">I", len(data)))
    out.extend(data)


def write_parameter_annotations_attribute(cp: ConstantPool, out: bytearray,
                                          attr_name: str, param_annotations: list[list[AnnotationInfo]]):
    """Write RuntimeVisibleParameterAnnotations or RuntimeInvisibleParameterAnnotations."""
    if not param_annotations:
        return
    # Check if there are any annotations at all
    has_any = any(anns for anns in param_annotations)
    if not has_any:
        return
    attr_name_idx = cp.add_utf8(attr_name)
    data = bytearray()
    data.append(len(param_annotations))  # num_parameters (u1)
    for anns in param_annotations:
        data.extend(struct.pack(">H", len(anns)))  # num_annotations
        for ann in anns:
            ann.write(cp, data)
    out.extend(struct.pack(">H", attr_name_idx))
    out.extend(struct.pack(">I", len(data)))
    out.extend(data)


@dataclass
class ExceptionTableEntry:
    """An entry in the exception table."""
    start_pc: int
    end_pc: int
    handler_pc: int
    catch_type: int  # 0 for finally (catches all), otherwise constant pool index of class


@dataclass
class CodeAttribute:
    """Code attribute for a method."""
    max_stack: int = 0
    max_locals: int = 0
    code: bytearray = field(default_factory=bytearray)
    exception_table: list[ExceptionTableEntry] = field(default_factory=list)
    attributes: list = field(default_factory=list)

    def write(self, cp: ConstantPool, out: bytearray):
        attr_name_idx = cp.add_utf8("Code")
        # Build attribute data
        data = bytearray()
        data.extend(struct.pack(">H", self.max_stack))
        data.extend(struct.pack(">H", self.max_locals))
        data.extend(struct.pack(">I", len(self.code)))
        data.extend(self.code)
        data.extend(struct.pack(">H", len(self.exception_table)))
        for entry in self.exception_table:
            data.extend(struct.pack(">HHHH",
                entry.start_pc, entry.end_pc, entry.handler_pc, entry.catch_type))
        data.extend(struct.pack(">H", len(self.attributes)))
        # Sub-attributes would go here

        out.extend(struct.pack(">H", attr_name_idx))
        out.extend(struct.pack(">I", len(data)))
        out.extend(data)


@dataclass
class MethodInfo:
    """Method in a class file."""
    access_flags: int
    name: str
    descriptor: str
    code: Optional[CodeAttribute] = None
    signature: Optional[str] = None
    annotations: list = field(default_factory=list)
    exceptions: list = field(default_factory=list)
    parameter_names: list = field(default_factory=list)
    parameter_annotations: list = field(default_factory=list)

    def write(self, cp: ConstantPool, out: bytearray):
        name_idx = cp.add_utf8(self.name)
        desc_idx = cp.add_utf8(self.descriptor)
        out.extend(struct.pack(">H", self.access_flags))
        out.extend(struct.pack(">H", name_idx))
        out.extend(struct.pack(">H", desc_idx))

        # Count attributes
        attr_count = 0
        if self.code:
            attr_count += 1
        if self.signature:
            attr_count += 1
        if self.annotations:
            attr_count += 1
        if self.exceptions:
            attr_count += 1
        if self.parameter_names:
            attr_count += 1
        if self.parameter_annotations and any(self.parameter_annotations):
            attr_count += 1

        out.extend(struct.pack(">H", attr_count))
        if self.code:
            self.code.write(cp, out)
        if self.signature:
            _write_signature_attribute(cp, out, self.signature)
        if self.annotations:
            write_annotations_attribute(cp, out, "RuntimeVisibleAnnotations", self.annotations)
        if self.exceptions:
            _write_exceptions_attribute(cp, out, self.exceptions)
        if self.parameter_names:
            write_method_parameters_attribute(cp, out, self.parameter_names)
        if self.parameter_annotations and any(self.parameter_annotations):
            write_parameter_annotations_attribute(
                cp, out, "RuntimeVisibleParameterAnnotations", self.parameter_annotations)


@dataclass
class FieldInfo:
    """Field in a class file."""
    access_flags: int
    name: str
    descriptor: str
    signature: Optional[str] = None
    annotations: list = field(default_factory=list)
    constant_value: Optional[tuple[int, any]] = None  # (tag, value)

    def write(self, cp: ConstantPool, out: bytearray):
        name_idx = cp.add_utf8(self.name)
        desc_idx = cp.add_utf8(self.descriptor)
        out.extend(struct.pack(">H", self.access_flags))
        out.extend(struct.pack(">H", name_idx))
        out.extend(struct.pack(">H", desc_idx))

        # Count attributes
        attr_count = 0
        if self.signature:
            attr_count += 1
        if self.annotations:
            attr_count += 1
        if self.constant_value is not None:
            attr_count += 1

        out.extend(struct.pack(">H", attr_count))
        if self.signature:
            _write_signature_attribute(cp, out, self.signature)
        if self.annotations:
            write_annotations_attribute(cp, out, "RuntimeVisibleAnnotations", self.annotations)
        if self.constant_value is not None:
            _write_constant_value_attribute(cp, out, self.constant_value)


def _write_signature_attribute(cp: ConstantPool, out: bytearray, signature: str):
    """Write a Signature attribute."""
    attr_name_idx = cp.add_utf8("Signature")
    sig_idx = cp.add_utf8(signature)
    out.extend(struct.pack(">H", attr_name_idx))
    out.extend(struct.pack(">I", 2))
    out.extend(struct.pack(">H", sig_idx))


def _write_exceptions_attribute(cp: ConstantPool, out: bytearray, exceptions: list[str]):
    """Write an Exceptions attribute."""
    attr_name_idx = cp.add_utf8("Exceptions")
    data = bytearray()
    data.extend(struct.pack(">H", len(exceptions)))
    for exc in exceptions:
        exc_idx = cp.add_class(exc)
        data.extend(struct.pack(">H", exc_idx))
    out.extend(struct.pack(">H", attr_name_idx))
    out.extend(struct.pack(">I", len(data)))
    out.extend(data)


def _write_constant_value_attribute(cp: ConstantPool, out: bytearray, const: tuple[int, any]):
    """Write a ConstantValue attribute from (tag, value)."""
    attr_name_idx = cp.add_utf8("ConstantValue")
    tag, value = const
    if tag == ConstantPoolTag.INTEGER:
        idx = cp.add_integer(int(value))
    elif tag == ConstantPoolTag.LONG:
        idx = cp.add_long(int(value))
    elif tag == ConstantPoolTag.FLOAT:
        idx = cp.add_float(float(value))
    elif tag == ConstantPoolTag.DOUBLE:
        idx = cp.add_double(float(value))
    elif tag == ConstantPoolTag.STRING:
        idx = cp.add_string(str(value))
    else:
        raise ValueError(f"Unsupported constant value tag: {tag}")
    out.extend(struct.pack(">H", attr_name_idx))
    out.extend(struct.pack(">I", 2))
    out.extend(struct.pack(">H", idx))


@dataclass
class InnerClassInfo:
    """Represents an entry in the InnerClasses attribute."""
    inner_class: str  # Internal name like "Outer$Inner"
    outer_class: Optional[str]  # Internal name like "Outer", None for anonymous/local
    inner_name: Optional[str]  # Simple name like "Inner", None for anonymous
    access_flags: int  # Access flags for the inner class


class ClassFile:
    """Represents a Java class file."""

    MAGIC = 0xCAFEBABE

    def __init__(self, name: str, super_class: str = "java/lang/Object",
                 version: tuple[int, int] = ClassFileVersion.JAVA_6):
        self.version = version
        self.access_flags = AccessFlags.PUBLIC | AccessFlags.SUPER
        self.name = name
        self.super_class = super_class
        self.interfaces: list[str] = []
        self.fields: list[FieldInfo] = []
        self.methods: list[MethodInfo] = []
        self.cp = ConstantPool()
        self.signature: Optional[str] = None
        self.annotations: list[AnnotationInfo] = []
        self.inner_classes: list[InnerClassInfo] = []

    def add_method(self, method: MethodInfo):
        self.methods.append(method)

    def add_field(self, field_info: FieldInfo):
        self.fields.append(field_info)

    def to_bytes(self) -> bytes:
        out = bytearray()

        # Prepare constant pool entries
        this_class_idx = self.cp.add_class(self.name)
        super_class_idx = self.cp.add_class(self.super_class)
        interface_indices = [self.cp.add_class(i) for i in self.interfaces]

        # Pre-populate method/field entries
        for method in self.methods:
            self.cp.add_utf8(method.name)
            self.cp.add_utf8(method.descriptor)
        for fld in self.fields:
            self.cp.add_utf8(fld.name)
            self.cp.add_utf8(fld.descriptor)
            if fld.constant_value is not None:
                self.cp.add_utf8("ConstantValue")
                tag, val = fld.constant_value
                if tag == ConstantPoolTag.INTEGER:
                    self.cp.add_integer(int(val))
                elif tag == ConstantPoolTag.LONG:
                    self.cp.add_long(int(val))
                elif tag == ConstantPoolTag.FLOAT:
                    self.cp.add_float(float(val))
                elif tag == ConstantPoolTag.DOUBLE:
                    self.cp.add_double(float(val))
                elif tag == ConstantPoolTag.STRING:
                    self.cp.add_string(str(val))

        # Pre-add "Code" attribute name for methods with code
        if any(m.code for m in self.methods):
            self.cp.add_utf8("Code")

        # Pre-add "Signature" attribute name and values
        has_signature = (
            self.signature or
            any(m.signature for m in self.methods) or
            any(f.signature for f in self.fields)
        )
        if has_signature:
            self.cp.add_utf8("Signature")
        if self.signature:
            self.cp.add_utf8(self.signature)
        for method in self.methods:
            if method.signature:
                self.cp.add_utf8(method.signature)
        for fld in self.fields:
            if fld.signature:
                self.cp.add_utf8(fld.signature)

        # Pre-add "RuntimeVisibleAnnotations" attribute name and annotation types
        all_annotations = list(self.annotations)
        for method in self.methods:
            all_annotations.extend(method.annotations)
        for fld in self.fields:
            all_annotations.extend(fld.annotations)
        if all_annotations:
            self.cp.add_utf8("RuntimeVisibleAnnotations")
            for ann in all_annotations:
                self.cp.add_utf8(ann.type_descriptor)

        # Pre-add "Exceptions" attribute name and exception class names
        has_exceptions = any(m.exceptions for m in self.methods)
        if has_exceptions:
            self.cp.add_utf8("Exceptions")
            for method in self.methods:
                for exc in method.exceptions:
                    self.cp.add_class(exc)

        # Pre-add "MethodParameters" attribute name and parameter names
        has_method_params = any(m.parameter_names for m in self.methods)
        if has_method_params:
            self.cp.add_utf8("MethodParameters")
            for method in self.methods:
                for name in method.parameter_names:
                    if name:
                        self.cp.add_utf8(name)

        # Pre-add "RuntimeVisibleParameterAnnotations" attribute name
        has_param_annotations = any(
            any(anns for anns in m.parameter_annotations)
            for m in self.methods if m.parameter_annotations
        )
        if has_param_annotations:
            self.cp.add_utf8("RuntimeVisibleParameterAnnotations")
            for method in self.methods:
                for param_anns in method.parameter_annotations:
                    for ann in param_anns:
                        self.cp.add_utf8(ann.type_descriptor)

        # Pre-add "InnerClasses" attribute name and class names
        if self.inner_classes:
            self.cp.add_utf8("InnerClasses")
            for ic in self.inner_classes:
                self.cp.add_class(ic.inner_class)
                if ic.outer_class:
                    self.cp.add_class(ic.outer_class)
                if ic.inner_name:
                    self.cp.add_utf8(ic.inner_name)

        # Magic number
        out.extend(struct.pack(">I", self.MAGIC))

        # Version
        out.extend(struct.pack(">HH", self.version[1], self.version[0]))

        # Constant pool
        self.cp.write(out)

        # Access flags
        out.extend(struct.pack(">H", self.access_flags))

        # This class
        out.extend(struct.pack(">H", this_class_idx))

        # Super class
        out.extend(struct.pack(">H", super_class_idx))

        # Interfaces
        out.extend(struct.pack(">H", len(interface_indices)))
        for idx in interface_indices:
            out.extend(struct.pack(">H", idx))

        # Fields
        out.extend(struct.pack(">H", len(self.fields)))
        for fld in self.fields:
            fld.write(self.cp, out)

        # Methods
        out.extend(struct.pack(">H", len(self.methods)))
        for method in self.methods:
            method.write(self.cp, out)

        # Class attributes
        attr_count = 0
        if self.signature:
            attr_count += 1
        if self.annotations:
            attr_count += 1
        if self.inner_classes:
            attr_count += 1
        out.extend(struct.pack(">H", attr_count))
        if self.signature:
            _write_signature_attribute(self.cp, out, self.signature)
        if self.annotations:
            write_annotations_attribute(self.cp, out, "RuntimeVisibleAnnotations", self.annotations)
        if self.inner_classes:
            self._write_inner_classes_attribute(self.cp, out)

        return bytes(out)

    def _write_inner_classes_attribute(self, cp: ConstantPool, out: bytearray):
        """Write the InnerClasses attribute."""
        attr_name_idx = cp.add_utf8("InnerClasses")
        out.extend(struct.pack(">H", attr_name_idx))

        # Attribute length: 2 (number_of_classes) + 8 * number_of_classes
        attr_len = 2 + 8 * len(self.inner_classes)
        out.extend(struct.pack(">I", attr_len))

        # Number of classes
        out.extend(struct.pack(">H", len(self.inner_classes)))

        # Write each inner class entry
        for ic in self.inner_classes:
            inner_class_idx = cp.add_class(ic.inner_class)
            outer_class_idx = cp.add_class(ic.outer_class) if ic.outer_class else 0
            inner_name_idx = cp.add_utf8(ic.inner_name) if ic.inner_name else 0

            out.extend(struct.pack(">H", inner_class_idx))
            out.extend(struct.pack(">H", outer_class_idx))
            out.extend(struct.pack(">H", inner_name_idx))
            out.extend(struct.pack(">H", ic.access_flags))

    def write(self, path: str):
        with open(path, "wb") as f:
            f.write(self.to_bytes())


class BytecodeBuilder:
    """Helper for building bytecode."""

    def __init__(self, cp: ConstantPool):
        self.cp = cp
        self.code = bytearray()
        self.max_stack = 0
        self.max_locals = 0
        self._current_stack = 0
        self._labels: dict[str, int] = {}
        self._forward_refs: list[tuple[str, int, int]] = []  # (label, offset, size)
        self._exception_handlers: list[tuple[str, str, str, int]] = []  # (start, end, handler, catch_type_idx)

    def _push(self, count: int = 1):
        self._current_stack += count
        self.max_stack = max(self.max_stack, self._current_stack)

    def _pop(self, count: int = 1):
        self._current_stack -= count

    def position(self) -> int:
        return len(self.code)

    def label(self, name: str):
        self._labels[name] = self.position()

    def _emit(self, *data):
        for b in data:
            if isinstance(b, Opcode):
                self.code.append(b.value)
            else:
                self.code.append(b)

    def _emit_u2(self, value: int):
        self.code.extend(struct.pack(">h", value))

    def iconst(self, value: int):
        if value == -1:
            self._emit(Opcode.ICONST_M1)
        elif 0 <= value <= 5:
            self._emit(Opcode.ICONST_0 + value)
        elif -128 <= value <= 127:
            self._emit(Opcode.BIPUSH, value & 0xFF)
        elif -32768 <= value <= 32767:
            self._emit(Opcode.SIPUSH)
            self.code.extend(struct.pack(">h", value))
        else:
            idx = self.cp.add_integer(value)
            if idx <= 255:
                self._emit(Opcode.LDC, idx)
            else:
                self._emit(Opcode.LDC_W)
                self.code.extend(struct.pack(">H", idx))
        self._push()

    def lconst(self, value: int):
        if value == 0:
            self._emit(Opcode.LCONST_0)
        elif value == 1:
            self._emit(Opcode.LCONST_1)
        else:
            idx = self.cp.add_long(value)
            self._emit(Opcode.LDC2_W)
            self.code.extend(struct.pack(">H", idx))
        self._push(2)

    def fconst(self, value: float):
        if value == 0.0:
            self._emit(Opcode.FCONST_0)
        elif value == 1.0:
            self._emit(Opcode.FCONST_1)
        elif value == 2.0:
            self._emit(Opcode.FCONST_2)
        else:
            idx = self.cp.add_float(value)
            if idx <= 255:
                self._emit(Opcode.LDC, idx)
            else:
                self._emit(Opcode.LDC_W)
                self.code.extend(struct.pack(">H", idx))
        self._push()

    def dconst(self, value: float):
        if value == 0.0:
            self._emit(Opcode.DCONST_0)
        elif value == 1.0:
            self._emit(Opcode.DCONST_1)
        else:
            idx = self.cp.add_double(value)
            self._emit(Opcode.LDC2_W)
            self.code.extend(struct.pack(">H", idx))
        self._push(2)

    def aconst_null(self):
        self._emit(Opcode.ACONST_NULL)
        self._push()

    def ldc_string(self, value: str):
        idx = self.cp.add_string(value)
        if idx <= 255:
            self._emit(Opcode.LDC, idx)
        else:
            self._emit(Opcode.LDC_W)
            self.code.extend(struct.pack(">H", idx))
        self._push()

    def ldc_class(self, class_name: str):
        """Load a class constant (Class<?> object) onto the stack."""
        idx = self.cp.add_class(class_name)
        if idx <= 255:
            self._emit(Opcode.LDC, idx)
        else:
            self._emit(Opcode.LDC_W)
            self.code.extend(struct.pack(">H", idx))
        self._push()

    def iload(self, slot: int):
        if slot <= 3:
            self._emit(Opcode.ILOAD_0 + slot)
        else:
            self._emit(Opcode.ILOAD, slot)
        self._push()

    def lload(self, slot: int):
        if slot <= 3:
            self._emit(Opcode.LLOAD_0 + slot)
        else:
            self._emit(Opcode.LLOAD, slot)
        self._push(2)

    def fload(self, slot: int):
        if slot <= 3:
            self._emit(Opcode.FLOAD_0 + slot)
        else:
            self._emit(Opcode.FLOAD, slot)
        self._push()

    def dload(self, slot: int):
        if slot <= 3:
            self._emit(Opcode.DLOAD_0 + slot)
        else:
            self._emit(Opcode.DLOAD, slot)
        self._push(2)

    def aload(self, slot: int):
        if slot <= 3:
            self._emit(Opcode.ALOAD_0 + slot)
        else:
            self._emit(Opcode.ALOAD, slot)
        self._push()

    def istore(self, slot: int):
        if slot <= 3:
            self._emit(Opcode.ISTORE_0 + slot)
        else:
            self._emit(Opcode.ISTORE, slot)
        self._pop()

    def lstore(self, slot: int):
        if slot <= 3:
            self._emit(Opcode.LSTORE_0 + slot)
        else:
            self._emit(Opcode.LSTORE, slot)
        self._pop(2)

    def fstore(self, slot: int):
        if slot <= 3:
            self._emit(Opcode.FSTORE_0 + slot)
        else:
            self._emit(Opcode.FSTORE, slot)
        self._pop()

    def dstore(self, slot: int):
        if slot <= 3:
            self._emit(Opcode.DSTORE_0 + slot)
        else:
            self._emit(Opcode.DSTORE, slot)
        self._pop(2)

    def astore(self, slot: int):
        if slot <= 3:
            self._emit(Opcode.ASTORE_0 + slot)
        else:
            self._emit(Opcode.ASTORE, slot)
        self._pop()

    def iadd(self):
        self._emit(Opcode.IADD)
        self._pop()

    def ladd(self):
        self._emit(Opcode.LADD)
        self._pop(2)

    def fadd(self):
        self._emit(Opcode.FADD)
        self._pop()

    def dadd(self):
        self._emit(Opcode.DADD)
        self._pop(2)

    def isub(self):
        self._emit(Opcode.ISUB)
        self._pop()

    def lsub(self):
        self._emit(Opcode.LSUB)
        self._pop(2)

    def fsub(self):
        self._emit(Opcode.FSUB)
        self._pop()

    def dsub(self):
        self._emit(Opcode.DSUB)
        self._pop(2)

    def imul(self):
        self._emit(Opcode.IMUL)
        self._pop()

    def lmul(self):
        self._emit(Opcode.LMUL)
        self._pop(2)

    def fmul(self):
        self._emit(Opcode.FMUL)
        self._pop()

    def dmul(self):
        self._emit(Opcode.DMUL)
        self._pop(2)

    def idiv(self):
        self._emit(Opcode.IDIV)
        self._pop()

    def ldiv(self):
        self._emit(Opcode.LDIV)
        self._pop(2)

    def fdiv(self):
        self._emit(Opcode.FDIV)
        self._pop()

    def ddiv(self):
        self._emit(Opcode.DDIV)
        self._pop(2)

    def irem(self):
        self._emit(Opcode.IREM)
        self._pop()

    def lrem(self):
        self._emit(Opcode.LREM)
        self._pop(2)

    def ineg(self):
        self._emit(Opcode.INEG)

    def lneg(self):
        self._emit(Opcode.LNEG)

    def fneg(self):
        self._emit(Opcode.FNEG)

    def dneg(self):
        self._emit(Opcode.DNEG)

    def ishl(self):
        self._emit(Opcode.ISHL)
        self._pop()

    def lshl(self):
        self._emit(Opcode.LSHL)
        self._pop()

    def ishr(self):
        self._emit(Opcode.ISHR)
        self._pop()

    def lshr(self):
        self._emit(Opcode.LSHR)
        self._pop()

    def iushr(self):
        self._emit(Opcode.IUSHR)
        self._pop()

    def lushr(self):
        self._emit(Opcode.LUSHR)
        self._pop()

    def iand(self):
        self._emit(Opcode.IAND)
        self._pop()

    def land(self):
        self._emit(Opcode.LAND)
        self._pop(2)

    def ior(self):
        self._emit(Opcode.IOR)
        self._pop()

    def lor(self):
        self._emit(Opcode.LOR)
        self._pop(2)

    def ixor(self):
        self._emit(Opcode.IXOR)
        self._pop()

    def lxor(self):
        self._emit(Opcode.LXOR)
        self._pop(2)

    def iinc(self, slot: int, value: int):
        self._emit(Opcode.IINC, slot, value & 0xFF)

    def i2l(self):
        self._emit(Opcode.I2L)
        self._push()

    def i2f(self):
        self._emit(Opcode.I2F)

    def i2d(self):
        self._emit(Opcode.I2D)
        self._push()

    def l2i(self):
        self._emit(Opcode.L2I)
        self._pop()

    def l2f(self):
        self._emit(Opcode.L2F)
        self._pop()

    def l2d(self):
        self._emit(Opcode.L2D)

    def f2i(self):
        self._emit(Opcode.F2I)

    def f2l(self):
        self._emit(Opcode.F2L)
        self._push()

    def f2d(self):
        self._emit(Opcode.F2D)
        self._push()

    def d2i(self):
        self._emit(Opcode.D2I)
        self._pop()

    def d2l(self):
        self._emit(Opcode.D2L)

    def d2f(self):
        self._emit(Opcode.D2F)
        self._pop()

    def lcmp(self):
        self._emit(Opcode.LCMP)
        self._pop(3)

    def fcmpl(self):
        self._emit(Opcode.FCMPL)
        self._pop()

    def fcmpg(self):
        self._emit(Opcode.FCMPG)
        self._pop()

    def dcmpl(self):
        self._emit(Opcode.DCMPL)
        self._pop(3)

    def dcmpg(self):
        self._emit(Opcode.DCMPG)
        self._pop(3)

    def ifeq(self, label: str):
        self._emit(Opcode.IFEQ)
        self._forward_refs.append((label, self.position(), 2))
        self._emit_u2(0)
        self._pop()

    def ifne(self, label: str):
        self._emit(Opcode.IFNE)
        self._forward_refs.append((label, self.position(), 2))
        self._emit_u2(0)
        self._pop()

    def iflt(self, label: str):
        self._emit(Opcode.IFLT)
        self._forward_refs.append((label, self.position(), 2))
        self._emit_u2(0)
        self._pop()

    def ifge(self, label: str):
        self._emit(Opcode.IFGE)
        self._forward_refs.append((label, self.position(), 2))
        self._emit_u2(0)
        self._pop()

    def ifgt(self, label: str):
        self._emit(Opcode.IFGT)
        self._forward_refs.append((label, self.position(), 2))
        self._emit_u2(0)
        self._pop()

    def ifle(self, label: str):
        self._emit(Opcode.IFLE)
        self._forward_refs.append((label, self.position(), 2))
        self._emit_u2(0)
        self._pop()

    def if_icmpeq(self, label: str):
        self._emit(Opcode.IF_ICMPEQ)
        self._forward_refs.append((label, self.position(), 2))
        self._emit_u2(0)
        self._pop(2)

    def if_icmpne(self, label: str):
        self._emit(Opcode.IF_ICMPNE)
        self._forward_refs.append((label, self.position(), 2))
        self._emit_u2(0)
        self._pop(2)

    def if_icmplt(self, label: str):
        self._emit(Opcode.IF_ICMPLT)
        self._forward_refs.append((label, self.position(), 2))
        self._emit_u2(0)
        self._pop(2)

    def if_icmpge(self, label: str):
        self._emit(Opcode.IF_ICMPGE)
        self._forward_refs.append((label, self.position(), 2))
        self._emit_u2(0)
        self._pop(2)

    def if_icmpgt(self, label: str):
        self._emit(Opcode.IF_ICMPGT)
        self._forward_refs.append((label, self.position(), 2))
        self._emit_u2(0)
        self._pop(2)

    def if_icmple(self, label: str):
        self._emit(Opcode.IF_ICMPLE)
        self._forward_refs.append((label, self.position(), 2))
        self._emit_u2(0)
        self._pop(2)

    def if_acmpeq(self, label: str):
        self._emit(Opcode.IF_ACMPEQ)
        self._forward_refs.append((label, self.position(), 2))
        self._emit_u2(0)
        self._pop(2)

    def if_acmpne(self, label: str):
        self._emit(Opcode.IF_ACMPNE)
        self._forward_refs.append((label, self.position(), 2))
        self._emit_u2(0)
        self._pop(2)

    def ifnull(self, label: str):
        self._emit(Opcode.IFNULL)
        self._forward_refs.append((label, self.position(), 2))
        self._emit_u2(0)
        self._pop()

    def ifnonnull(self, label: str):
        self._emit(Opcode.IFNONNULL)
        self._forward_refs.append((label, self.position(), 2))
        self._emit_u2(0)
        self._pop()

    def instanceof_(self, class_name: str):
        """Check if object is an instance of a class. Pops reference, pushes int (0 or 1)."""
        idx = self.cp.add_class(class_name)
        self._emit(Opcode.INSTANCEOF)
        self.code.extend(struct.pack(">H", idx))
        self._pop()
        self._push()

    def checkcast(self, class_name: str):
        """Cast reference to a class type. Pops reference, pushes same reference (typed)."""
        idx = self.cp.add_class(class_name)
        self._emit(Opcode.CHECKCAST)
        self.code.extend(struct.pack(">H", idx))
        # Stack stays the same (pop ref, push ref)

    def newarray(self, atype: int):
        """Create new primitive array. atype: T_BOOLEAN=4, T_CHAR=5, T_FLOAT=6, T_DOUBLE=7, T_BYTE=8, T_SHORT=9, T_INT=10, T_LONG=11"""
        self._emit(Opcode.NEWARRAY, atype)
        self._pop()  # pop count
        self._push()  # push array ref

    def anewarray(self, class_name: str):
        """Create new reference type array."""
        idx = self.cp.add_class(class_name)
        self._emit(Opcode.ANEWARRAY)
        self.code.extend(struct.pack(">H", idx))
        self._pop()  # pop count
        self._push()  # push array ref

    def iaload(self):
        """Load int from array."""
        self._emit(Opcode.IALOAD)
        self._pop(2)  # pop arrayref, index
        self._push()  # push value

    def laload(self):
        """Load long from array."""
        self._emit(Opcode.LALOAD)
        self._pop(2)
        self._push(2)

    def faload(self):
        """Load float from array."""
        self._emit(Opcode.FALOAD)
        self._pop(2)
        self._push()

    def daload(self):
        """Load double from array."""
        self._emit(Opcode.DALOAD)
        self._pop(2)
        self._push(2)

    def aaload(self):
        """Load reference from array."""
        self._emit(Opcode.AALOAD)
        self._pop(2)
        self._push()

    def baload(self):
        """Load byte/boolean from array."""
        self._emit(Opcode.BALOAD)
        self._pop(2)
        self._push()

    def caload(self):
        """Load char from array."""
        self._emit(Opcode.CALOAD)
        self._pop(2)
        self._push()

    def saload(self):
        """Load short from array."""
        self._emit(Opcode.SALOAD)
        self._pop(2)
        self._push()

    def iastore(self):
        """Store int to array."""
        self._emit(Opcode.IASTORE)
        self._pop(3)  # pop arrayref, index, value

    def lastore(self):
        """Store long to array."""
        self._emit(Opcode.LASTORE)
        self._pop(4)  # pop arrayref, index, value (2 slots)

    def fastore(self):
        """Store float to array."""
        self._emit(Opcode.FASTORE)
        self._pop(3)

    def dastore(self):
        """Store double to array."""
        self._emit(Opcode.DASTORE)
        self._pop(4)  # arrayref, index, value (2 slots)

    def aastore(self):
        """Store reference to array."""
        self._emit(Opcode.AASTORE)
        self._pop(3)

    def bastore(self):
        """Store byte/boolean to array."""
        self._emit(Opcode.BASTORE)
        self._pop(3)

    def castore(self):
        """Store char to array."""
        self._emit(Opcode.CASTORE)
        self._pop(3)

    def sastore(self):
        """Store short to array."""
        self._emit(Opcode.SASTORE)
        self._pop(3)

    def arraylength(self):
        """Get array length."""
        self._emit(Opcode.ARRAYLENGTH)
        self._pop()  # pop arrayref
        self._push()  # push length

    def goto(self, label: str):
        self._emit(Opcode.GOTO)
        self._forward_refs.append((label, self.position(), 2))
        self._emit_u2(0)

    def ireturn(self):
        self._emit(Opcode.IRETURN)
        self._pop()

    def lreturn(self):
        self._emit(Opcode.LRETURN)
        self._pop(2)

    def freturn(self):
        self._emit(Opcode.FRETURN)
        self._pop()

    def dreturn(self):
        self._emit(Opcode.DRETURN)
        self._pop(2)

    def areturn(self):
        self._emit(Opcode.ARETURN)
        self._pop()

    def return_(self):
        self._emit(Opcode.RETURN)

    def getstatic(self, class_name: str, field_name: str, descriptor: str, size: int = 1):
        idx = self.cp.add_fieldref(class_name, field_name, descriptor)
        self._emit(Opcode.GETSTATIC)
        self.code.extend(struct.pack(">H", idx))
        self._push(size)

    def putstatic(self, class_name: str, field_name: str, descriptor: str, size: int = 1):
        idx = self.cp.add_fieldref(class_name, field_name, descriptor)
        self._emit(Opcode.PUTSTATIC)
        self.code.extend(struct.pack(">H", idx))
        self._pop(size)

    def getfield(self, class_name: str, field_name: str, descriptor: str, size: int = 1):
        idx = self.cp.add_fieldref(class_name, field_name, descriptor)
        self._emit(Opcode.GETFIELD)
        self.code.extend(struct.pack(">H", idx))
        self._pop()
        self._push(size)

    def putfield(self, class_name: str, field_name: str, descriptor: str, size: int = 1):
        idx = self.cp.add_fieldref(class_name, field_name, descriptor)
        self._emit(Opcode.PUTFIELD)
        self.code.extend(struct.pack(">H", idx))
        self._pop(1 + size)

    def invokevirtual(self, class_name: str, method_name: str, descriptor: str,
                      arg_size: int, ret_size: int):
        idx = self.cp.add_methodref(class_name, method_name, descriptor)
        self._emit(Opcode.INVOKEVIRTUAL)
        self.code.extend(struct.pack(">H", idx))
        self._pop(1 + arg_size)
        self._push(ret_size)

    def invokespecial(self, class_name: str, method_name: str, descriptor: str,
                      arg_size: int, ret_size: int):
        idx = self.cp.add_methodref(class_name, method_name, descriptor)
        self._emit(Opcode.INVOKESPECIAL)
        self.code.extend(struct.pack(">H", idx))
        self._pop(1 + arg_size)
        self._push(ret_size)

    def invokestatic(self, class_name: str, method_name: str, descriptor: str,
                     arg_size: int, ret_size: int):
        idx = self.cp.add_methodref(class_name, method_name, descriptor)
        self._emit(Opcode.INVOKESTATIC)
        self.code.extend(struct.pack(">H", idx))
        self._pop(arg_size)
        self._push(ret_size)

    def invokeinterface(self, class_name: str, method_name: str, descriptor: str,
                        arg_size: int, ret_size: int):
        idx = self.cp.add_interface_methodref(class_name, method_name, descriptor)
        self._emit(Opcode.INVOKEINTERFACE)
        self.code.extend(struct.pack(">H", idx))
        self.code.append(arg_size)  # count (includes 'this')
        self.code.append(0)  # reserved, must be zero
        self._pop(arg_size)
        self._push(ret_size)

    def new(self, class_name: str):
        idx = self.cp.add_class(class_name)
        self._emit(Opcode.NEW)
        self.code.extend(struct.pack(">H", idx))
        self._push()

    def dup(self):
        self._emit(Opcode.DUP)
        self._push()

    def dup_x1(self):
        """Duplicate the top operand stack value and insert two values down."""
        self._emit(Opcode.DUP_X1)
        self._push()

    def dup_x2(self):
        """Duplicate the top operand stack value and insert three values down."""
        self._emit(Opcode.DUP_X2)
        self._push()

    def dup2(self):
        """Duplicate the top one or two operand stack values."""
        self._emit(Opcode.DUP2)
        self._push(2)

    def dup2_x1(self):
        """Duplicate top two values and insert three values down."""
        self._emit(Opcode.DUP2_X1)
        self._push(2)

    def dup2_x2(self):
        """Duplicate top two values and insert four values down."""
        self._emit(Opcode.DUP2_X2)
        self._push(2)

    def pop(self):
        self._emit(Opcode.POP)
        self._pop()

    def athrow(self):
        """Throw exception (objectref must be on stack)."""
        self._emit(Opcode.ATHROW)
        self._pop()

    def lookupswitch(self, default_label: str, cases: list[tuple[int, str]]):
        """Emit a lookupswitch instruction.

        Args:
            default_label: Label for default case
            cases: List of (match_value, label) pairs, sorted by match value
        """
        self._emit(Opcode.LOOKUPSWITCH)

        # Padding to 4-byte alignment
        base = len(self.code)
        padding = (4 - (base % 4)) % 4
        for _ in range(padding):
            self.code.append(0)

        # Default offset (will be patched)
        self._forward_refs.append((default_label, len(self.code), 4, base - 1))
        self.code.extend(struct.pack(">i", 0))

        # npairs
        npairs = len(cases)
        self.code.extend(struct.pack(">i", npairs))

        # Match-offset pairs (must be sorted by match value)
        sorted_cases = sorted(cases, key=lambda x: x[0])
        for match, label in sorted_cases:
            self.code.extend(struct.pack(">i", match))
            self._forward_refs.append((label, len(self.code), 4, base - 1))
            self.code.extend(struct.pack(">i", 0))

        self._pop()  # Pop the switch expression value

    def add_exception_handler(self, start_label: str, end_label: str, handler_label: str, catch_type_idx: int):
        """Add an exception handler entry.

        Args:
            start_label: Label marking start of try block (inclusive)
            end_label: Label marking end of try block (exclusive)
            handler_label: Label marking start of catch handler
            catch_type_idx: Constant pool index of exception class (0 for finally/catch-all)
        """
        self._exception_handlers.append((start_label, end_label, handler_label, catch_type_idx))

    def resolve_labels(self):
        for ref in self._forward_refs:
            if len(ref) == 3:
                label, offset, size = ref
                instr_start = offset - 1  # The byte before the offset is the opcode
            else:
                label, offset, size, instr_start = ref  # For lookupswitch/tableswitch

            if label not in self._labels:
                raise ValueError(f"Undefined label: {label}")
            target = self._labels[label]
            relative = target - instr_start
            if size == 2:
                struct.pack_into(">h", self.code, offset, relative)
            else:
                struct.pack_into(">i", self.code, offset, relative)

    def build(self) -> CodeAttribute:
        self.resolve_labels()

        # Build exception table from handler entries
        exception_table = []
        for start_label, end_label, handler_label, catch_type_idx in self._exception_handlers:
            if start_label not in self._labels:
                raise ValueError(f"Undefined exception handler start label: {start_label}")
            if end_label not in self._labels:
                raise ValueError(f"Undefined exception handler end label: {end_label}")
            if handler_label not in self._labels:
                raise ValueError(f"Undefined exception handler label: {handler_label}")

            exception_table.append(ExceptionTableEntry(
                start_pc=self._labels[start_label],
                end_pc=self._labels[end_label],
                handler_pc=self._labels[handler_label],
                catch_type=catch_type_idx,
            ))

        return CodeAttribute(
            max_stack=self.max_stack,
            max_locals=self.max_locals,
            code=self.code,
            exception_table=exception_table,
        )
