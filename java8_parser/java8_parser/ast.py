"""
Immutable AST representation for Java 8.
All nodes are frozen dataclasses for immutability.
"""

from dataclasses import dataclass, field
from typing import Optional, Sequence
from abc import ABC
import json


class ASTNode(ABC):
    """Base class for all AST nodes."""

    def to_dict(self) -> dict:
        """Convert node to dictionary for JSON serialization."""
        result = {"_type": self.__class__.__name__}
        for key, value in self.__dict__.items():
            if key.startswith("_"):
                continue
            result[key] = _serialize_value(value)
        return result

    def to_json(self, indent: int = 2) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)


def _serialize_value(value):
    """Helper to serialize a value for JSON."""
    if value is None:
        return None
    if isinstance(value, ASTNode):
        return value.to_dict()
    if isinstance(value, (list, tuple)):
        return [_serialize_value(v) for v in value]
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float, str)):
        return value
    return str(value)


@dataclass(frozen=True)
class CompilationUnit(ASTNode):
    """Top-level compilation unit (a .java file)."""
    package: Optional["PackageDeclaration"]
    imports: tuple["ImportDeclaration", ...]
    types: tuple["TypeDeclaration", ...]


@dataclass(frozen=True)
class PackageDeclaration(ASTNode):
    """Package declaration: package com.example;"""
    annotations: tuple["Annotation", ...]
    name: str


@dataclass(frozen=True)
class ImportDeclaration(ASTNode):
    """Import declaration."""
    name: str
    is_static: bool
    is_wildcard: bool


@dataclass(frozen=True)
class Annotation(ASTNode):
    """Annotation: @Name or @Name(value) or @Name(key=value)"""
    name: str
    arguments: tuple["AnnotationArgument", ...]


@dataclass(frozen=True)
class AnnotationArgument(ASTNode):
    """A single annotation argument."""
    name: Optional[str]
    value: "Expression"


@dataclass(frozen=True)
class Modifier(ASTNode):
    """A modifier keyword or annotation."""
    keyword: Optional[str]
    annotation: Optional[Annotation]


class TypeDeclaration(ASTNode):
    """Base class for type declarations."""
    pass


@dataclass(frozen=True)
class ClassDeclaration(TypeDeclaration):
    """Class declaration."""
    modifiers: tuple[Modifier, ...]
    name: str
    type_parameters: tuple["TypeParameter", ...]
    extends: Optional["Type"]
    implements: tuple["Type", ...]
    body: tuple["ClassBodyDeclaration", ...]


@dataclass(frozen=True)
class InterfaceDeclaration(TypeDeclaration):
    """Interface declaration."""
    modifiers: tuple[Modifier, ...]
    name: str
    type_parameters: tuple["TypeParameter", ...]
    extends: tuple["Type", ...]
    body: tuple["InterfaceBodyDeclaration", ...]


@dataclass(frozen=True)
class EnumDeclaration(TypeDeclaration):
    """Enum declaration."""
    modifiers: tuple[Modifier, ...]
    name: str
    implements: tuple["Type", ...]
    constants: tuple["EnumConstant", ...]
    body: tuple["ClassBodyDeclaration", ...]


@dataclass(frozen=True)
class AnnotationTypeDeclaration(TypeDeclaration):
    """Annotation type declaration: @interface Name {}"""
    modifiers: tuple[Modifier, ...]
    name: str
    body: tuple["AnnotationTypeElement", ...]


@dataclass(frozen=True)
class EnumConstant(ASTNode):
    """Enum constant declaration."""
    annotations: tuple[Annotation, ...]
    name: str
    arguments: tuple["Expression", ...]
    body: Optional[tuple["ClassBodyDeclaration", ...]]


@dataclass(frozen=True)
class TypeParameter(ASTNode):
    """Type parameter: T or T extends Bound"""
    name: str
    bounds: tuple["Type", ...]


class Type(ASTNode):
    """Base class for types."""
    pass


@dataclass(frozen=True)
class PrimitiveType(Type):
    """Primitive type: int, boolean, etc."""
    name: str
    annotations: tuple[Annotation, ...] = ()


@dataclass(frozen=True)
class ClassType(Type):
    """Class/interface type: List<String>"""
    name: str
    type_arguments: tuple["TypeArgument", ...]
    annotations: tuple[Annotation, ...] = ()


@dataclass(frozen=True)
class ArrayType(Type):
    """Array type: int[], String[][]"""
    element_type: Type
    dimensions: int
    annotations: tuple[Annotation, ...] = ()


@dataclass(frozen=True)
class TypeArgument(ASTNode):
    """Type argument in generics: ?, ? extends T, ? super T, or T"""
    type: Optional[Type]
    wildcard: Optional[str]  # None, "extends", "super"


class ClassBodyDeclaration(ASTNode):
    """Base for class body declarations."""
    pass


class InterfaceBodyDeclaration(ASTNode):
    """Base for interface body declarations."""
    pass


class AnnotationTypeElement(ASTNode):
    """Base for annotation type elements."""
    pass


@dataclass(frozen=True)
class FieldDeclaration(ClassBodyDeclaration, InterfaceBodyDeclaration):
    """Field declaration."""
    modifiers: tuple[Modifier, ...]
    type: Type
    declarators: tuple["VariableDeclarator", ...]


@dataclass(frozen=True)
class MethodDeclaration(ClassBodyDeclaration, InterfaceBodyDeclaration):
    """Method declaration."""
    modifiers: tuple[Modifier, ...]
    type_parameters: tuple[TypeParameter, ...]
    return_type: Type
    name: str
    parameters: tuple["FormalParameter", ...]
    throws: tuple[Type, ...]
    body: Optional["Block"]
    dimensions: int = 0  # for old-style array return type: int foo()[]
    default_value: Optional["Expression"] = None  # for annotation methods


@dataclass(frozen=True)
class ConstructorDeclaration(ClassBodyDeclaration):
    """Constructor declaration."""
    modifiers: tuple[Modifier, ...]
    type_parameters: tuple[TypeParameter, ...]
    name: str
    parameters: tuple["FormalParameter", ...]
    throws: tuple[Type, ...]
    body: "Block"


@dataclass(frozen=True)
class StaticInitializer(ClassBodyDeclaration):
    """Static initializer block."""
    body: "Block"


@dataclass(frozen=True)
class InstanceInitializer(ClassBodyDeclaration):
    """Instance initializer block."""
    body: "Block"


@dataclass(frozen=True)
class VariableDeclarator(ASTNode):
    """Variable declarator: name = initializer"""
    name: str
    dimensions: int
    initializer: Optional["Expression"]


@dataclass(frozen=True)
class FormalParameter(ASTNode):
    """Formal parameter in method/constructor."""
    modifiers: tuple[Modifier, ...]
    type: Type
    varargs: bool
    name: str
    dimensions: int = 0


class Statement(ASTNode):
    """Base class for statements."""
    pass


@dataclass(frozen=True)
class Block(Statement):
    """Block: { statements }"""
    statements: tuple[Statement, ...]


@dataclass(frozen=True)
class LocalVariableDeclaration(Statement):
    """Local variable declaration."""
    modifiers: tuple[Modifier, ...]
    type: Type
    declarators: tuple[VariableDeclarator, ...]


@dataclass(frozen=True)
class ExpressionStatement(Statement):
    """Expression statement."""
    expression: "Expression"


@dataclass(frozen=True)
class IfStatement(Statement):
    """If statement."""
    condition: "Expression"
    then_branch: Statement
    else_branch: Optional[Statement]


@dataclass(frozen=True)
class WhileStatement(Statement):
    """While statement."""
    condition: "Expression"
    body: Statement


@dataclass(frozen=True)
class DoWhileStatement(Statement):
    """Do-while statement."""
    body: Statement
    condition: "Expression"


@dataclass(frozen=True)
class ForStatement(Statement):
    """Basic for statement."""
    init: Optional[tuple["Expression", ...] | LocalVariableDeclaration]
    condition: Optional["Expression"]
    update: tuple["Expression", ...]
    body: Statement


@dataclass(frozen=True)
class EnhancedForStatement(Statement):
    """Enhanced for (foreach) statement."""
    modifiers: tuple[Modifier, ...]
    type: Type
    name: str
    iterable: "Expression"
    body: Statement


@dataclass(frozen=True)
class SwitchStatement(Statement):
    """Switch statement."""
    expression: "Expression"
    cases: tuple["SwitchCase", ...]


@dataclass(frozen=True)
class SwitchCase(ASTNode):
    """Switch case."""
    labels: tuple[Optional["Expression"], ...]  # None for default
    statements: tuple[Statement, ...]


@dataclass(frozen=True)
class ReturnStatement(Statement):
    """Return statement."""
    expression: Optional["Expression"]


@dataclass(frozen=True)
class ThrowStatement(Statement):
    """Throw statement."""
    expression: "Expression"


@dataclass(frozen=True)
class BreakStatement(Statement):
    """Break statement."""
    label: Optional[str]


@dataclass(frozen=True)
class ContinueStatement(Statement):
    """Continue statement."""
    label: Optional[str]


@dataclass(frozen=True)
class LabeledStatement(Statement):
    """Labeled statement."""
    label: str
    statement: Statement


@dataclass(frozen=True)
class SynchronizedStatement(Statement):
    """Synchronized statement."""
    expression: "Expression"
    body: Block


@dataclass(frozen=True)
class TryStatement(Statement):
    """Try statement."""
    resources: tuple["Resource", ...]
    body: Block
    catches: tuple["CatchClause", ...]
    finally_block: Optional[Block]


@dataclass(frozen=True)
class Resource(ASTNode):
    """Try-with-resources resource."""
    modifiers: tuple[Modifier, ...]
    type: Type
    name: str
    expression: "Expression"


@dataclass(frozen=True)
class CatchClause(ASTNode):
    """Catch clause."""
    modifiers: tuple[Modifier, ...]
    types: tuple[Type, ...]  # multi-catch: catch (A | B e)
    name: str
    body: Block


@dataclass(frozen=True)
class AssertStatement(Statement):
    """Assert statement."""
    condition: "Expression"
    message: Optional["Expression"]


@dataclass(frozen=True)
class EmptyStatement(Statement):
    """Empty statement: ;"""
    pass


class Expression(ASTNode):
    """Base class for expressions."""
    pass


@dataclass(frozen=True)
class Literal(Expression):
    """Literal value."""
    value: str
    kind: str  # "int", "long", "float", "double", "char", "string", "boolean", "null"


@dataclass(frozen=True)
class Identifier(Expression):
    """Simple identifier."""
    name: str


@dataclass(frozen=True)
class QualifiedName(Expression):
    """Qualified name: a.b.c"""
    parts: tuple[str, ...]


@dataclass(frozen=True)
class ThisExpression(Expression):
    """this or Outer.this"""
    qualifier: Optional[str]


@dataclass(frozen=True)
class SuperExpression(Expression):
    """super or Outer.super"""
    qualifier: Optional[str]


@dataclass(frozen=True)
class ParenthesizedExpression(Expression):
    """Parenthesized expression: (expr)"""
    expression: Expression


@dataclass(frozen=True)
class ClassLiteral(Expression):
    """Class literal: Type.class"""
    type: Type


@dataclass(frozen=True)
class FieldAccess(Expression):
    """Field access: expr.field"""
    target: Expression
    field: str


@dataclass(frozen=True)
class ArrayAccess(Expression):
    """Array access: expr[index]"""
    array: Expression
    index: Expression


@dataclass(frozen=True)
class MethodInvocation(Expression):
    """Method invocation."""
    target: Optional[Expression]
    type_arguments: tuple[Type, ...]
    method: str
    arguments: tuple[Expression, ...]


@dataclass(frozen=True)
class NewInstance(Expression):
    """New instance creation: new Type(args)"""
    qualifier: Optional[Expression]
    type_arguments: tuple[Type, ...]
    type: Type
    arguments: tuple[Expression, ...]
    body: Optional[tuple[ClassBodyDeclaration, ...]]


@dataclass(frozen=True)
class NewArray(Expression):
    """Array creation: new int[10] or new int[] {1, 2}"""
    type: Type
    dimensions: tuple[Optional[Expression], ...]
    initializer: Optional["ArrayInitializer"]


@dataclass(frozen=True)
class ArrayInitializer(Expression):
    """Array initializer: {1, 2, 3}"""
    elements: tuple[Expression, ...]


@dataclass(frozen=True)
class Assignment(Expression):
    """Assignment: a = b, a += b, etc."""
    target: Expression
    operator: str
    value: Expression


@dataclass(frozen=True)
class BinaryExpression(Expression):
    """Binary expression: a + b, a && b, etc."""
    left: Expression
    operator: str
    right: Expression


@dataclass(frozen=True)
class UnaryExpression(Expression):
    """Unary expression: -a, !a, ++a, a++, etc."""
    operator: str
    operand: Expression
    prefix: bool


@dataclass(frozen=True)
class CastExpression(Expression):
    """Cast expression: (Type) expr"""
    type: Type
    expression: Expression


@dataclass(frozen=True)
class InstanceOfExpression(Expression):
    """instanceof expression."""
    expression: Expression
    type: Type


@dataclass(frozen=True)
class ConditionalExpression(Expression):
    """Conditional (ternary) expression: a ? b : c"""
    condition: Expression
    then_expr: Expression
    else_expr: Expression


@dataclass(frozen=True)
class LambdaExpression(Expression):
    """Lambda expression: (params) -> body"""
    parameters: tuple[FormalParameter | str, ...]  # str for inferred types
    body: Expression | Block


@dataclass(frozen=True)
class MethodReference(Expression):
    """Method reference: Type::method"""
    target: Expression | Type
    type_arguments: tuple[Type, ...]
    method: str  # "new" for constructor reference
