"""
Java class file reader for extracting signatures from rt.jar.
Supports reading Java 6-8 class files.
"""

import struct
import zipfile
from dataclasses import dataclass, field
from typing import Optional, BinaryIO
from pathlib import Path
from .classfile import ConstantPoolTag, AccessFlags


@dataclass
class ConstantPoolEntry:
    """A constant pool entry."""
    tag: int
    value: any


@dataclass
class FieldInfo:
    """Parsed field information."""
    access_flags: int
    name: str
    descriptor: str
    signature: Optional[str] = None
    attributes: dict = field(default_factory=dict)


@dataclass
class MethodInfo:
    """Parsed method information."""
    access_flags: int
    name: str
    descriptor: str
    signature: Optional[str] = None
    exceptions: tuple = ()
    attributes: dict = field(default_factory=dict)


@dataclass
class AnnotationValue:
    """An annotation element value."""
    tag: str
    value: any


@dataclass
class Annotation:
    """A parsed annotation."""
    type_name: str
    elements: dict = field(default_factory=dict)


@dataclass
class ClassInfo:
    """Parsed class file information."""
    version: tuple[int, int]
    access_flags: int
    name: str
    super_class: Optional[str]
    interfaces: tuple[str, ...]
    fields: tuple[FieldInfo, ...]
    methods: tuple[MethodInfo, ...]
    signature: Optional[str] = None
    source_file: Optional[str] = None
    annotations: tuple[Annotation, ...] = ()
    inner_classes: tuple = ()


class ClassReader:
    """Reads Java class files."""

    def __init__(self, data: bytes):
        self.data = data
        self.pos = 0
        self.constant_pool: list[ConstantPoolEntry] = [None]  # 1-indexed

    def _read_u1(self) -> int:
        val = self.data[self.pos]
        self.pos += 1
        return val

    def _read_u2(self) -> int:
        val = struct.unpack_from(">H", self.data, self.pos)[0]
        self.pos += 2
        return val

    def _read_u4(self) -> int:
        val = struct.unpack_from(">I", self.data, self.pos)[0]
        self.pos += 4
        return val

    def _read_i4(self) -> int:
        val = struct.unpack_from(">i", self.data, self.pos)[0]
        self.pos += 4
        return val

    def _read_i8(self) -> int:
        val = struct.unpack_from(">q", self.data, self.pos)[0]
        self.pos += 8
        return val

    def _read_f4(self) -> float:
        val = struct.unpack_from(">f", self.data, self.pos)[0]
        self.pos += 4
        return val

    def _read_f8(self) -> float:
        val = struct.unpack_from(">d", self.data, self.pos)[0]
        self.pos += 8
        return val

    def _read_bytes(self, length: int) -> bytes:
        val = self.data[self.pos:self.pos + length]
        self.pos += length
        return val

    def _get_utf8(self, index: int) -> str:
        """Get UTF8 string from constant pool."""
        if index == 0:
            return None
        entry = self.constant_pool[index]
        if entry.tag == ConstantPoolTag.UTF8:
            return entry.value
        raise ValueError(f"Expected UTF8 at index {index}, got tag {entry.tag}")

    def _get_class_name(self, index: int) -> Optional[str]:
        """Get class name from constant pool."""
        if index == 0:
            return None
        entry = self.constant_pool[index]
        if entry.tag == ConstantPoolTag.CLASS:
            return self._get_utf8(entry.value)
        raise ValueError(f"Expected CLASS at index {index}, got tag {entry.tag}")

    def _read_constant_pool(self):
        """Read the constant pool."""
        count = self._read_u2()
        i = 1
        while i < count:
            tag = self._read_u1()
            entry = None

            if tag == ConstantPoolTag.UTF8:
                length = self._read_u2()
                value = self._read_bytes(length).decode("utf-8", errors="replace")
                entry = ConstantPoolEntry(tag, value)

            elif tag == ConstantPoolTag.INTEGER:
                entry = ConstantPoolEntry(tag, self._read_i4())

            elif tag == ConstantPoolTag.FLOAT:
                entry = ConstantPoolEntry(tag, self._read_f4())

            elif tag == ConstantPoolTag.LONG:
                entry = ConstantPoolEntry(tag, self._read_i8())
                self.constant_pool.append(entry)
                self.constant_pool.append(None)  # Long takes 2 slots
                i += 2
                continue

            elif tag == ConstantPoolTag.DOUBLE:
                entry = ConstantPoolEntry(tag, self._read_f8())
                self.constant_pool.append(entry)
                self.constant_pool.append(None)  # Double takes 2 slots
                i += 2
                continue

            elif tag == ConstantPoolTag.CLASS:
                entry = ConstantPoolEntry(tag, self._read_u2())

            elif tag == ConstantPoolTag.STRING:
                entry = ConstantPoolEntry(tag, self._read_u2())

            elif tag == ConstantPoolTag.FIELDREF:
                class_idx = self._read_u2()
                nat_idx = self._read_u2()
                entry = ConstantPoolEntry(tag, (class_idx, nat_idx))

            elif tag == ConstantPoolTag.METHODREF:
                class_idx = self._read_u2()
                nat_idx = self._read_u2()
                entry = ConstantPoolEntry(tag, (class_idx, nat_idx))

            elif tag == ConstantPoolTag.INTERFACE_METHODREF:
                class_idx = self._read_u2()
                nat_idx = self._read_u2()
                entry = ConstantPoolEntry(tag, (class_idx, nat_idx))

            elif tag == ConstantPoolTag.NAME_AND_TYPE:
                name_idx = self._read_u2()
                desc_idx = self._read_u2()
                entry = ConstantPoolEntry(tag, (name_idx, desc_idx))

            elif tag == ConstantPoolTag.METHOD_HANDLE:
                kind = self._read_u1()
                ref_idx = self._read_u2()
                entry = ConstantPoolEntry(tag, (kind, ref_idx))

            elif tag == ConstantPoolTag.METHOD_TYPE:
                desc_idx = self._read_u2()
                entry = ConstantPoolEntry(tag, desc_idx)

            elif tag == ConstantPoolTag.INVOKE_DYNAMIC:
                bootstrap_idx = self._read_u2()
                nat_idx = self._read_u2()
                entry = ConstantPoolEntry(tag, (bootstrap_idx, nat_idx))

            else:
                raise ValueError(f"Unknown constant pool tag: {tag}")

            self.constant_pool.append(entry)
            i += 1

    def _read_annotation(self) -> Annotation:
        """Read a single annotation."""
        type_idx = self._read_u2()
        type_name = self._get_utf8(type_idx)
        num_pairs = self._read_u2()
        elements = {}
        for _ in range(num_pairs):
            name_idx = self._read_u2()
            name = self._get_utf8(name_idx)
            value = self._read_element_value()
            elements[name] = value
        return Annotation(type_name=type_name, elements=elements)

    def _read_element_value(self) -> AnnotationValue:
        """Read an annotation element value."""
        tag = chr(self._read_u1())

        if tag in "BCDFIJSZs":
            # Constant value
            const_idx = self._read_u2()
            entry = self.constant_pool[const_idx]
            if tag == "s":
                value = self._get_utf8(const_idx)
            else:
                value = entry.value
            return AnnotationValue(tag, value)

        elif tag == "e":
            # Enum constant
            type_idx = self._read_u2()
            const_idx = self._read_u2()
            return AnnotationValue(tag, (self._get_utf8(type_idx), self._get_utf8(const_idx)))

        elif tag == "c":
            # Class
            class_idx = self._read_u2()
            return AnnotationValue(tag, self._get_utf8(class_idx))

        elif tag == "@":
            # Nested annotation
            return AnnotationValue(tag, self._read_annotation())

        elif tag == "[":
            # Array
            num_values = self._read_u2()
            values = [self._read_element_value() for _ in range(num_values)]
            return AnnotationValue(tag, values)

        else:
            raise ValueError(f"Unknown annotation element value tag: {tag}")

    def _read_attributes(self) -> dict:
        """Read attributes and return as dict."""
        count = self._read_u2()
        attrs = {}
        for _ in range(count):
            name_idx = self._read_u2()
            name = self._get_utf8(name_idx)
            length = self._read_u4()
            start = self.pos

            if name == "Signature":
                sig_idx = self._read_u2()
                attrs["Signature"] = self._get_utf8(sig_idx)

            elif name == "Exceptions":
                num_exc = self._read_u2()
                exc_names = []
                for _ in range(num_exc):
                    exc_idx = self._read_u2()
                    exc_names.append(self._get_class_name(exc_idx))
                attrs["Exceptions"] = tuple(exc_names)

            elif name == "RuntimeVisibleAnnotations":
                num_ann = self._read_u2()
                annotations = [self._read_annotation() for _ in range(num_ann)]
                attrs["RuntimeVisibleAnnotations"] = annotations

            elif name == "RuntimeInvisibleAnnotations":
                num_ann = self._read_u2()
                annotations = [self._read_annotation() for _ in range(num_ann)]
                attrs["RuntimeInvisibleAnnotations"] = annotations

            elif name == "SourceFile":
                sf_idx = self._read_u2()
                attrs["SourceFile"] = self._get_utf8(sf_idx)

            elif name == "InnerClasses":
                num_classes = self._read_u2()
                inner = []
                for _ in range(num_classes):
                    inner_class_idx = self._read_u2()
                    outer_class_idx = self._read_u2()
                    inner_name_idx = self._read_u2()
                    inner_access = self._read_u2()
                    inner.append({
                        "inner_class": self._get_class_name(inner_class_idx) if inner_class_idx else None,
                        "outer_class": self._get_class_name(outer_class_idx) if outer_class_idx else None,
                        "inner_name": self._get_utf8(inner_name_idx) if inner_name_idx else None,
                        "access_flags": inner_access,
                    })
                attrs["InnerClasses"] = inner

            elif name == "ConstantValue":
                cv_idx = self._read_u2()
                entry = self.constant_pool[cv_idx]
                attrs["ConstantValue"] = entry.value

            # Skip other attributes
            self.pos = start + length

        return attrs

    def _read_field(self) -> FieldInfo:
        """Read a field."""
        access = self._read_u2()
        name_idx = self._read_u2()
        desc_idx = self._read_u2()
        attrs = self._read_attributes()

        return FieldInfo(
            access_flags=access,
            name=self._get_utf8(name_idx),
            descriptor=self._get_utf8(desc_idx),
            signature=attrs.get("Signature"),
            attributes=attrs,
        )

    def _read_method(self) -> MethodInfo:
        """Read a method."""
        access = self._read_u2()
        name_idx = self._read_u2()
        desc_idx = self._read_u2()
        attrs = self._read_attributes()

        return MethodInfo(
            access_flags=access,
            name=self._get_utf8(name_idx),
            descriptor=self._get_utf8(desc_idx),
            signature=attrs.get("Signature"),
            exceptions=attrs.get("Exceptions", ()),
            attributes=attrs,
        )

    def read(self) -> ClassInfo:
        """Read the class file and return ClassInfo."""
        # Magic number
        magic = self._read_u4()
        if magic != 0xCAFEBABE:
            raise ValueError(f"Invalid class file magic: {hex(magic)}")

        # Version
        minor = self._read_u2()
        major = self._read_u2()

        # Constant pool
        self._read_constant_pool()

        # Access flags
        access_flags = self._read_u2()

        # This/super class
        this_class_idx = self._read_u2()
        super_class_idx = self._read_u2()
        this_class = self._get_class_name(this_class_idx)
        super_class = self._get_class_name(super_class_idx)

        # Interfaces
        interfaces_count = self._read_u2()
        interfaces = tuple(
            self._get_class_name(self._read_u2())
            for _ in range(interfaces_count)
        )

        # Fields
        fields_count = self._read_u2()
        fields = tuple(self._read_field() for _ in range(fields_count))

        # Methods
        methods_count = self._read_u2()
        methods = tuple(self._read_method() for _ in range(methods_count))

        # Class attributes
        attrs = self._read_attributes()

        # Extract annotations
        annotations = []
        if "RuntimeVisibleAnnotations" in attrs:
            annotations.extend(attrs["RuntimeVisibleAnnotations"])
        if "RuntimeInvisibleAnnotations" in attrs:
            annotations.extend(attrs["RuntimeInvisibleAnnotations"])

        return ClassInfo(
            version=(major, minor),
            access_flags=access_flags,
            name=this_class,
            super_class=super_class,
            interfaces=interfaces,
            fields=fields,
            methods=methods,
            signature=attrs.get("Signature"),
            source_file=attrs.get("SourceFile"),
            annotations=tuple(annotations),
            inner_classes=tuple(attrs.get("InnerClasses", [])),
        )


class ClassPath:
    """Manages a classpath for looking up classes."""

    def __init__(self):
        self.entries: list[Path | zipfile.ZipFile] = []
        self._cache: dict[str, ClassInfo] = {}
        self._zip_files: list[zipfile.ZipFile] = []

    def add_path(self, path: str | Path):
        """Add a path to the classpath (directory or jar/zip)."""
        path = Path(path)
        if path.suffix in (".jar", ".zip"):
            zf = zipfile.ZipFile(path, "r")
            self._zip_files.append(zf)
            self.entries.append(zf)
        elif path.is_dir():
            self.entries.append(path)
        else:
            raise ValueError(f"Invalid classpath entry: {path}")

    def add_rt_jar(self):
        """Add the JDK rt.jar to the classpath."""
        import subprocess
        result = subprocess.run(
            ["java", "-XshowSettings:properties", "-version"],
            capture_output=True, text=True
        )
        # Parse java.home from output
        for line in result.stderr.split("\n"):
            if "java.home" in line:
                java_home = line.split("=")[1].strip()
                rt_jar = Path(java_home) / "lib" / "rt.jar"
                if rt_jar.exists():
                    self.add_path(rt_jar)
                    return
                # JDK 8 alternate location
                rt_jar = Path(java_home) / ".." / "jre" / "lib" / "rt.jar"
                if rt_jar.exists():
                    self.add_path(rt_jar.resolve())
                    return
        raise FileNotFoundError("Could not find rt.jar")

    def find_class(self, class_name: str) -> Optional[ClassInfo]:
        """Find and parse a class by name (e.g., 'java/lang/String')."""
        if class_name in self._cache:
            return self._cache[class_name]

        class_file = class_name + ".class"

        for entry in self.entries:
            if isinstance(entry, zipfile.ZipFile):
                try:
                    data = entry.read(class_file)
                    reader = ClassReader(data)
                    info = reader.read()
                    self._cache[class_name] = info
                    return info
                except KeyError:
                    continue
            elif isinstance(entry, Path):
                path = entry / class_file
                if path.exists():
                    data = path.read_bytes()
                    reader = ClassReader(data)
                    info = reader.read()
                    self._cache[class_name] = info
                    return info

        return None

    def close(self):
        """Close all zip files."""
        for zf in self._zip_files:
            zf.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def read_class_file(path: str | Path) -> ClassInfo:
    """Read a single class file."""
    data = Path(path).read_bytes()
    reader = ClassReader(data)
    return reader.read()
