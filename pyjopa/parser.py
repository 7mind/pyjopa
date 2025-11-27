"""
Java 8 Parser using Lark.
"""

import re
import sys
from pathlib import Path
from lark import Lark, Transformer, v_args, Token, Tree
from typing import Optional
from . import ast

sys.setrecursionlimit(100000)


GRAMMAR_FILE = Path(__file__).parent / "java8.lark"


def preprocess_unicode_escapes(source: str) -> str:
    r"""
    Preprocess Unicode escapes in Java source code.
    Java requires \\uXXXX escapes to be processed before lexical analysis.
    """
    result = []
    i = 0
    while i < len(source):
        if i < len(source) - 5 and source[i] == '\\' and source[i+1] == 'u':
            j = i + 2
            while j < len(source) and source[j] == 'u':
                j += 1
            if j + 4 <= len(source):
                hex_digits = source[j:j+4]
                if all(c in '0123456789abcdefABCDEF' for c in hex_digits):
                    code_point = int(hex_digits, 16)
                    result.append(chr(code_point))
                    i = j + 4
                    continue
        result.append(source[i])
        i += 1
    return ''.join(result)


class Java8Transformer(Transformer):
    """Transforms Lark parse tree to AST nodes."""

    def __init__(self):
        super().__init__()

    def _to_tuple(self, items) -> tuple:
        """Convert list to tuple, filtering None values."""
        if items is None:
            return ()
        return tuple(item for item in items if item is not None)

    def _get_token_value(self, token) -> str:
        """Get string value from token or tree."""
        if isinstance(token, Token):
            return str(token)
        if isinstance(token, str):
            return token
        if isinstance(token, Tree):
            return self._get_token_value(token.children[0]) if token.children else ""
        return str(token)

    # ==================== COMPILATION UNIT ====================

    def start(self, items):
        return items[0]

    def compilation_unit(self, items):
        package = None
        imports = []
        types = []
        for item in items:
            if item is None:
                continue
            if isinstance(item, ast.PackageDeclaration):
                package = item
            elif isinstance(item, ast.ImportDeclaration):
                imports.append(item)
            elif isinstance(item, ast.TypeDeclaration):
                types.append(item)
        return ast.CompilationUnit(
            package=package,
            imports=tuple(imports),
            types=tuple(types)
        )

    def import_or_semicolon(self, items):
        for item in items:
            if isinstance(item, ast.ImportDeclaration):
                return item
        return None

    def package_declaration(self, items):
        annotations = []
        name = None
        for item in items:
            if isinstance(item, ast.Annotation):
                annotations.append(item)
            elif isinstance(item, str):
                name = item
        return ast.PackageDeclaration(
            annotations=tuple(annotations),
            name=name or ""
        )

    def import_declaration(self, items):
        is_static = False
        is_wildcard = False
        name_parts = []

        for item in items:
            if isinstance(item, Token):
                if item.type == "IDENTIFIER":
                    name_parts.append(str(item))
                elif item.type == "STATIC":
                    is_static = True
                elif item.type == "STAR":
                    is_wildcard = True
            elif isinstance(item, str):
                name_parts.append(item)

        return ast.ImportDeclaration(
            name=".".join(name_parts),
            is_static=is_static,
            is_wildcard=is_wildcard
        )

    def type_declaration(self, items):
        for item in items:
            if isinstance(item, ast.TypeDeclaration):
                return item
        return None

    # ==================== CLASS DECLARATION ====================

    def class_declaration(self, items):
        modifiers = []
        name = None
        type_params = ()
        extends = None
        implements = ()
        body = ()

        for item in items:
            if isinstance(item, ast.Modifier):
                modifiers.append(item)
            elif isinstance(item, Token) and item.type == "IDENTIFIER":
                name = str(item)
            elif isinstance(item, tuple) and item and isinstance(item[0], ast.TypeParameter):
                type_params = item
            elif isinstance(item, ast.Type) and extends is None:
                extends = item
            elif isinstance(item, tuple) and item and isinstance(item[0], ast.Type):
                implements = item
            elif isinstance(item, tuple) and (not item or isinstance(item[0], (ast.ClassBodyDeclaration, ast.TypeDeclaration))):
                body = item

        return ast.ClassDeclaration(
            modifiers=tuple(modifiers),
            name=name or "",
            type_parameters=type_params,
            extends=extends,
            implements=implements,
            body=body
        )

    def superclass(self, items):
        for item in items:
            if isinstance(item, ast.Type):
                return item
        return None

    def superinterfaces(self, items):
        return self._extract_types(items)

    def class_body(self, items):
        declarations = []
        for item in items:
            if isinstance(item, (ast.ClassBodyDeclaration, ast.TypeDeclaration)):
                declarations.append(item)
        return tuple(declarations)

    def class_body_declaration(self, items):
        for item in items:
            if isinstance(item, (ast.ClassBodyDeclaration, ast.TypeDeclaration)):
                return item
        return None

    # ==================== FIELDS AND METHODS ====================

    def field_declaration(self, items):
        modifiers = []
        field_type = None
        declarators = ()

        for item in items:
            if isinstance(item, ast.Modifier):
                modifiers.append(item)
            elif isinstance(item, ast.Type):
                field_type = item
            elif isinstance(item, tuple) and item and isinstance(item[0], ast.VariableDeclarator):
                declarators = item

        return ast.FieldDeclaration(
            modifiers=tuple(modifiers),
            type=field_type or ast.PrimitiveType(name="int"),
            declarators=declarators
        )

    def variable_declarators(self, items):
        return tuple(item for item in items if isinstance(item, ast.VariableDeclarator))

    def variable_declarator(self, items):
        name = None
        dims = 0
        initializer = None

        for item in items:
            if isinstance(item, Token) and item.type == "IDENTIFIER":
                name = str(item)
            elif isinstance(item, int):
                dims = item
            elif isinstance(item, (ast.Expression, ast.ArrayInitializer)):
                initializer = item

        return ast.VariableDeclarator(
            name=name or "",
            dimensions=dims,
            initializer=initializer
        )

    def variable_initializer(self, items):
        for item in items:
            if isinstance(item, (ast.Expression, ast.ArrayInitializer)):
                return item
        return None

    def method_declaration(self, items):
        modifiers = []
        type_params = ()
        return_type = None
        name = None
        params = ()
        throws = ()
        body = None
        dims = 0
        default_value = None

        for item in items:
            if isinstance(item, ast.Modifier):
                modifiers.append(item)
            elif isinstance(item, tuple) and item and isinstance(item[0], ast.TypeParameter):
                type_params = item
            elif isinstance(item, ast.Type) and return_type is None:
                return_type = item
            elif item == "void":
                return_type = ast.PrimitiveType(name="void")
            elif isinstance(item, Token) and item.type == "IDENTIFIER":
                name = str(item)
            elif isinstance(item, dict) and "name" in item:
                name = item["name"]
                params = item.get("params", ())
                dims = item.get("dims", 0)
            elif isinstance(item, tuple) and (not item or isinstance(item[0], ast.FormalParameter)):
                params = item
            elif isinstance(item, tuple) and item and isinstance(item[0], ast.Type):
                throws = item
            elif isinstance(item, ast.Block):
                body = item
            elif isinstance(item, int):
                dims = item
            elif isinstance(item, ast.Expression):
                default_value = item

        return ast.MethodDeclaration(
            modifiers=tuple(modifiers),
            type_parameters=type_params,
            return_type=return_type or ast.PrimitiveType(name="void"),
            name=name or "",
            parameters=params,
            throws=throws,
            body=body,
            dimensions=dims,
            default_value=default_value
        )

    def result(self, items):
        for item in items:
            if isinstance(item, ast.Type):
                return item
            if item == "void":
                return "void"
        return "void"

    def method_declarator(self, items):
        result = {"name": None, "params": (), "dims": 0}
        for item in items:
            if isinstance(item, Token) and item.type == "IDENTIFIER":
                result["name"] = str(item)
            elif isinstance(item, tuple):
                result["params"] = item
            elif isinstance(item, int):
                result["dims"] = item
        return result

    def method_body(self, items):
        for item in items:
            if isinstance(item, ast.Block):
                return item
        return None

    def constructor_declaration(self, items):
        modifiers = []
        type_params = ()
        name = None
        params = ()
        throws = ()
        body = None

        for item in items:
            if isinstance(item, ast.Modifier):
                modifiers.append(item)
            elif isinstance(item, tuple) and item and isinstance(item[0], ast.TypeParameter):
                type_params = item
            elif isinstance(item, Token) and item.type == "IDENTIFIER":
                name = str(item)
            elif isinstance(item, tuple) and (not item or isinstance(item[0], ast.FormalParameter)):
                params = item
            elif isinstance(item, tuple) and item and isinstance(item[0], ast.Type):
                throws = item
            elif isinstance(item, ast.Block):
                body = item

        return ast.ConstructorDeclaration(
            modifiers=tuple(modifiers),
            type_parameters=type_params,
            name=name or "",
            parameters=params,
            throws=throws,
            body=body or ast.Block(statements=())
        )

    def static_initializer(self, items):
        for item in items:
            if isinstance(item, ast.Block):
                return ast.StaticInitializer(body=item)
        return ast.StaticInitializer(body=ast.Block(statements=()))

    def instance_initializer(self, items):
        for item in items:
            if isinstance(item, ast.Block):
                return ast.InstanceInitializer(body=item)
        return ast.InstanceInitializer(body=ast.Block(statements=()))

    # ==================== INTERFACE DECLARATION ====================

    def interface_declaration(self, items):
        modifiers = []
        name = None
        type_params = ()
        extends = ()
        body = ()

        for item in items:
            if isinstance(item, ast.Modifier):
                modifiers.append(item)
            elif isinstance(item, Token) and item.type == "IDENTIFIER":
                name = str(item)
            elif isinstance(item, tuple) and item and isinstance(item[0], ast.TypeParameter):
                type_params = item
            elif isinstance(item, tuple) and item and isinstance(item[0], ast.Type):
                extends = item
            elif isinstance(item, tuple) and (not item or isinstance(item[0], ast.InterfaceBodyDeclaration)):
                body = item

        return ast.InterfaceDeclaration(
            modifiers=tuple(modifiers),
            name=name or "",
            type_parameters=type_params,
            extends=extends,
            body=body
        )

    def extends_interfaces(self, items):
        return self._extract_types(items)

    def interface_body(self, items):
        declarations = []
        for item in items:
            if isinstance(item, ast.InterfaceBodyDeclaration):
                declarations.append(item)
        return tuple(declarations)

    def interface_body_declaration(self, items):
        for item in items:
            if isinstance(item, ast.InterfaceBodyDeclaration):
                return item
        return None

    def constant_declaration(self, items):
        return self.field_declaration(items)

    def interface_method_declaration(self, items):
        return self.method_declaration(items)

    # ==================== ENUM DECLARATION ====================

    def enum_declaration(self, items):
        modifiers = []
        name = None
        implements = ()
        constants = ()
        body = ()

        for item in items:
            if isinstance(item, ast.Modifier):
                modifiers.append(item)
            elif isinstance(item, Token) and item.type == "IDENTIFIER":
                name = str(item)
            elif isinstance(item, tuple) and item and isinstance(item[0], ast.Type):
                implements = item
            elif isinstance(item, tuple):
                if len(item) == 2 and item and isinstance(item[0], tuple) and (not item[0] or isinstance(item[0][0], ast.EnumConstant)):
                    constants = item[0]
                    body = item[1]
                elif item and isinstance(item[0], ast.EnumConstant):
                    constants = item
                elif not item or (item and isinstance(item[0], ast.ClassBodyDeclaration)):
                    body = item

        return ast.EnumDeclaration(
            modifiers=tuple(modifiers),
            name=name or "",
            implements=implements,
            constants=constants,
            body=body
        )

    def enum_body(self, items):
        constants = []
        body = []
        for item in items:
            if isinstance(item, ast.EnumConstant):
                constants.append(item)
            elif isinstance(item, tuple) and item and isinstance(item[0], ast.EnumConstant):
                constants.extend(item)
            elif isinstance(item, ast.ClassBodyDeclaration):
                body.append(item)
            elif isinstance(item, tuple) and item and isinstance(item[0], ast.ClassBodyDeclaration):
                body.extend(item)
        return (tuple(constants), tuple(body))

    def enum_constant_list(self, items):
        return tuple(item for item in items if isinstance(item, ast.EnumConstant))

    def enum_constant(self, items):
        annotations = []
        name = None
        arguments = ()
        body = None

        for item in items:
            if isinstance(item, ast.Annotation):
                annotations.append(item)
            elif isinstance(item, Token) and item.type == "IDENTIFIER":
                name = str(item)
            elif isinstance(item, tuple) and (not item or isinstance(item[0], ast.Expression)):
                arguments = item
            elif isinstance(item, tuple) and item and isinstance(item[0], ast.ClassBodyDeclaration):
                body = item

        return ast.EnumConstant(
            annotations=tuple(annotations),
            name=name or "",
            arguments=arguments,
            body=body
        )

    def enum_body_declarations(self, items):
        return tuple(item for item in items if isinstance(item, ast.ClassBodyDeclaration))

    # ==================== ANNOTATION TYPE ====================

    def annotation_type_declaration(self, items):
        modifiers = []
        name = None
        body = ()

        for item in items:
            if isinstance(item, ast.Modifier):
                modifiers.append(item)
            elif isinstance(item, Token) and item.type == "IDENTIFIER":
                name = str(item)
            elif isinstance(item, tuple):
                body = item

        return ast.AnnotationTypeDeclaration(
            modifiers=tuple(modifiers),
            name=name or "",
            body=body
        )

    def annotation_type_body(self, items):
        return tuple(item for item in items if isinstance(item, ast.AnnotationTypeElement))

    def annotation_type_element(self, items):
        return self.method_declaration(items)

    def default_value(self, items):
        for item in items:
            if isinstance(item, ast.Expression):
                return item
        return None

    # ==================== TYPES ====================

    def type(self, items):
        for item in items:
            if isinstance(item, ast.Type):
                return item
        return None

    def primitive_type(self, items):
        annotations = []
        name = None
        for item in items:
            if isinstance(item, ast.Annotation):
                annotations.append(item)
            elif isinstance(item, str):
                name = item
        return ast.PrimitiveType(name=name or "int", annotations=tuple(annotations))

    def primitive_type_name(self, items):
        for item in items:
            if hasattr(item, 'type') and item.type in {'BYTE', 'SHORT', 'INT', 'LONG', 'CHAR', 'FLOAT', 'DOUBLE', 'BOOLEAN'}:
                return str(item)
            elif isinstance(item, str):
                return item
        return "int"

    def reference_type(self, items):
        for item in items:
            if isinstance(item, ast.Type):
                return item
        return None

    def class_type(self, items):
        annotations = []
        name_parts = []
        type_args = ()

        for item in items:
            if isinstance(item, ast.Annotation):
                annotations.append(item)
            elif isinstance(item, Token) and item.type == "IDENTIFIER":
                name_parts.append(str(item))
            elif isinstance(item, tuple) and item and isinstance(item[0], ast.TypeArgument):
                type_args = item

        return ast.ClassType(
            name=".".join(name_parts),
            type_arguments=type_args,
            annotations=tuple(annotations)
        )

    def class_type_list(self, items):
        return tuple(item for item in items if isinstance(item, ast.Type))

    def array_type(self, items):
        element_type = None
        dims = 0
        annotations = []

        for item in items:
            if isinstance(item, ast.Type):
                element_type = item
            elif isinstance(item, int):
                dims = item
            elif isinstance(item, ast.Annotation):
                annotations.append(item)

        return ast.ArrayType(
            element_type=element_type or ast.PrimitiveType(name="int"),
            dimensions=dims,
            annotations=tuple(annotations)
        )

    def dims(self, items):
        count = 0
        for item in items:
            if item == "[" or item == "]":
                pass
            count += 1
        return max(1, count // 2) if count > 0 else 1

    # ==================== TYPE PARAMETERS ====================

    def type_parameters(self, items):
        params = []
        for item in items:
            if isinstance(item, ast.TypeParameter):
                params.append(item)
            elif isinstance(item, tuple):
                params.extend(p for p in item if isinstance(p, ast.TypeParameter))
        return tuple(params)

    def type_parameter_list(self, items):
        return tuple(item for item in items if isinstance(item, ast.TypeParameter))

    def type_parameter(self, items):
        annotations = []
        name = None
        bounds = ()

        for item in items:
            if isinstance(item, ast.Annotation):
                annotations.append(item)
            elif isinstance(item, Token) and item.type == "IDENTIFIER":
                name = str(item)
            elif isinstance(item, tuple) and item and isinstance(item[0], ast.Type):
                bounds = item

        return ast.TypeParameter(name=name or "", bounds=bounds)

    def type_bound(self, items):
        bounds = []
        for item in items:
            if isinstance(item, ast.Type):
                bounds.append(item)
        return tuple(bounds)

    def additional_bounds(self, items):
        for item in items:
            if isinstance(item, ast.Type):
                return item
        return None

    def type_arguments(self, items):
        args = []
        for item in items:
            if isinstance(item, ast.TypeArgument):
                args.append(item)
            elif isinstance(item, tuple):
                args.extend(a for a in item if isinstance(a, ast.TypeArgument))
        return tuple(args)

    def type_argument_list(self, items):
        return tuple(item for item in items if isinstance(item, ast.TypeArgument))

    def type_argument(self, items):
        for item in items:
            if isinstance(item, ast.TypeArgument):
                return item
            if isinstance(item, ast.Type):
                return ast.TypeArgument(type=item, wildcard=None)
        return ast.TypeArgument(type=None, wildcard=None)

    def wildcard(self, items):
        wildcard_type = None
        bound_kind = None
        annotations = []

        for item in items:
            if isinstance(item, ast.Annotation):
                annotations.append(item)
            elif isinstance(item, ast.Type):
                wildcard_type = item
            elif item == "extends":
                bound_kind = "extends"
            elif item == "super":
                bound_kind = "super"

        return ast.TypeArgument(type=wildcard_type, wildcard=bound_kind or "?")

    def wildcard_bounds(self, items):
        return items

    # ==================== MODIFIERS ====================

    def modifier(self, items):
        for item in items:
            if isinstance(item, ast.Annotation):
                return ast.Modifier(keyword=None, annotation=item)
            # Check Token before str since Token is a str subclass
            if isinstance(item, Token):
                return ast.Modifier(keyword=str(item), annotation=None)
            if isinstance(item, str):
                return ast.Modifier(keyword=item, annotation=None)
        return None

    def annotation(self, items):
        name = None
        arguments = ()

        for item in items:
            if isinstance(item, str):
                name = item
            elif isinstance(item, tuple):
                arguments = item

        return ast.Annotation(name=name or "", arguments=arguments)

    def annotation_arguments(self, items):
        args = []
        for item in items:
            if isinstance(item, ast.AnnotationArgument):
                args.append(item)
            elif isinstance(item, ast.Expression):
                args.append(ast.AnnotationArgument(name=None, value=item))
            elif isinstance(item, tuple):
                args.extend(a for a in item if isinstance(a, ast.AnnotationArgument))
        return tuple(args)

    def element_value_pairs(self, items):
        return tuple(item for item in items if isinstance(item, ast.AnnotationArgument))

    def element_value_pair(self, items):
        name = None
        value = None
        for item in items:
            if isinstance(item, Token) and item.type == "IDENTIFIER":
                name = str(item)
            elif isinstance(item, ast.Expression):
                value = item
        return ast.AnnotationArgument(name=name, value=value or ast.Literal(value="null", kind="null"))

    def element_value(self, items):
        for item in items:
            if isinstance(item, (ast.Expression, ast.Annotation)):
                return item
        return None

    def element_value_array(self, items):
        elements = []
        for item in items:
            if isinstance(item, ast.Expression):
                elements.append(item)
        return ast.ArrayInitializer(elements=tuple(elements))

    def element_values(self, items):
        return tuple(item for item in items if isinstance(item, ast.Expression))

    # ==================== PARAMETERS ====================

    def formal_parameter_list(self, items):
        params = []
        for item in items:
            if isinstance(item, ast.FormalParameter):
                params.append(item)
            elif isinstance(item, tuple):
                params.extend(p for p in item if isinstance(p, ast.FormalParameter))
        return tuple(params)

    def formal_parameters(self, items):
        return tuple(item for item in items if isinstance(item, ast.FormalParameter))

    def formal_parameter(self, items):
        modifiers = []
        param_type = None
        name = None
        dims = 0

        for item in items:
            if isinstance(item, ast.Modifier):
                modifiers.append(item)
            elif isinstance(item, ast.Type):
                param_type = item
            elif isinstance(item, Token) and item.type == "IDENTIFIER":
                name = str(item)
            elif isinstance(item, int):
                dims = item

        return ast.FormalParameter(
            modifiers=tuple(modifiers),
            type=param_type or ast.PrimitiveType(name="int"),
            varargs=False,
            name=name or "",
            dimensions=dims
        )

    def last_formal_parameter(self, items):
        modifiers = []
        param_type = None
        name = None
        dims = 0

        for item in items:
            if isinstance(item, ast.Modifier):
                modifiers.append(item)
            elif isinstance(item, ast.Type):
                param_type = item
            elif isinstance(item, Token) and item.type == "IDENTIFIER":
                name = str(item)
            elif isinstance(item, int):
                dims = item

        return ast.FormalParameter(
            modifiers=tuple(modifiers),
            type=param_type or ast.PrimitiveType(name="int"),
            varargs=True,
            name=name or "",
            dimensions=dims
        )

    def receiver_parameter(self, items):
        return None

    def throws_clause(self, items):
        return self._extract_types(items)

    def exception_type_list(self, items):
        return tuple(item for item in items if isinstance(item, ast.Type))

    # ==================== STATEMENTS ====================

    def block(self, items):
        statements = []
        for item in items:
            if isinstance(item, ast.Statement):
                statements.append(item)
        return ast.Block(statements=tuple(statements))

    def block_statement(self, items):
        for item in items:
            if isinstance(item, ast.Statement):
                return item
            if isinstance(item, ast.TypeDeclaration):
                return item
        return None

    def explicit_constructor_invocation(self, items):
        kind = "super"
        arguments = ()
        qualifier = None
        type_args = ()

        for item in items:
            if isinstance(item, Token):
                if item.type == "THIS":
                    kind = "this"
                elif item.type == "SUPER":
                    kind = "super"
            elif isinstance(item, str):
                if item in ("this", "super"):
                    kind = item
            elif isinstance(item, tuple) and item and isinstance(item[0], ast.Type):
                type_args = item
            elif isinstance(item, tuple) and (not item or isinstance(item[0], ast.Expression)):
                arguments = item
            elif isinstance(item, ast.Expression):
                qualifier = item

        return ast.ExplicitConstructorInvocation(
            kind=kind,
            arguments=arguments,
            qualifier=qualifier,
            type_arguments=type_args
        )

    def local_variable_declaration(self, items):
        modifiers = []
        var_type = None
        declarators = ()

        for item in items:
            if isinstance(item, ast.Modifier):
                modifiers.append(item)
            elif isinstance(item, ast.Type):
                var_type = item
            elif isinstance(item, tuple) and item and isinstance(item[0], ast.VariableDeclarator):
                declarators = item

        # Detect misparsed break/continue statements
        # Due to grammar ambiguity, "break label;" can be parsed as a variable declaration
        # where "break" is the type and "label" is the variable name
        if (not modifiers and var_type and isinstance(var_type, ast.ClassType) and
            len(declarators) == 1 and declarators[0].dimensions == 0 and
            declarators[0].initializer is None):
            type_name = var_type.name
            label = declarators[0].name
            if type_name == "break":
                return ast.BreakStatement(label=label)
            elif type_name == "continue":
                return ast.ContinueStatement(label=label)

        return ast.LocalVariableDeclaration(
            modifiers=tuple(modifiers),
            type=var_type or ast.PrimitiveType(name="int"),
            declarators=declarators
        )

    def statement(self, items):
        for item in items:
            if isinstance(item, ast.Statement):
                return item
        return None

    def statement_without_trailing_substatement(self, items):
        for item in items:
            if isinstance(item, ast.Statement):
                return item
        return None

    def empty_statement(self, items):
        return ast.EmptyStatement()

    def labeled_statement(self, items):
        label = None
        statement = None
        for item in items:
            if isinstance(item, Token) and item.type == "IDENTIFIER":
                label = str(item)
            elif isinstance(item, ast.Statement):
                statement = item
        return ast.LabeledStatement(label=label or "", statement=statement or ast.EmptyStatement())

    def labeled_statement_no_short_if(self, items):
        return self.labeled_statement(items)

    def expression_statement(self, items):
        for item in items:
            if isinstance(item, ast.Expression):
                return ast.ExpressionStatement(expression=item)
        return ast.EmptyStatement()

    def statement_expression(self, items):
        for item in items:
            if isinstance(item, ast.Expression):
                return item
        return None

    def if_then_statement(self, items):
        condition = None
        then_branch = None
        for item in items:
            if isinstance(item, ast.Expression) and condition is None:
                condition = item
            elif isinstance(item, ast.Statement):
                then_branch = item
        return ast.IfStatement(
            condition=condition or ast.Literal(value="false", kind="boolean"),
            then_branch=then_branch or ast.EmptyStatement(),
            else_branch=None
        )

    def if_then_else_statement(self, items):
        condition = None
        then_branch = None
        else_branch = None
        for item in items:
            if isinstance(item, ast.Expression) and condition is None:
                condition = item
            elif isinstance(item, ast.Statement) and then_branch is None:
                then_branch = item
            elif isinstance(item, ast.Statement):
                else_branch = item
        return ast.IfStatement(
            condition=condition or ast.Literal(value="false", kind="boolean"),
            then_branch=then_branch or ast.EmptyStatement(),
            else_branch=else_branch
        )

    def if_then_else_statement_no_short_if(self, items):
        return self.if_then_else_statement(items)

    def statement_no_short_if(self, items):
        for item in items:
            if isinstance(item, ast.Statement):
                return item
        return None

    def while_statement(self, items):
        condition = None
        body = None
        for item in items:
            if isinstance(item, ast.Expression):
                condition = item
            elif isinstance(item, ast.Statement):
                body = item
        return ast.WhileStatement(
            condition=condition or ast.Literal(value="true", kind="boolean"),
            body=body or ast.EmptyStatement()
        )

    def while_statement_no_short_if(self, items):
        return self.while_statement(items)

    def do_statement(self, items):
        body = None
        condition = None
        for item in items:
            if isinstance(item, ast.Statement) and body is None:
                body = item
            elif isinstance(item, ast.Expression):
                condition = item
        return ast.DoWhileStatement(
            body=body or ast.EmptyStatement(),
            condition=condition or ast.Literal(value="true", kind="boolean")
        )

    def for_statement(self, items):
        for item in items:
            if isinstance(item, ast.Statement):
                return item
        return None

    def for_statement_no_short_if(self, items):
        return self.for_statement(items)

    def basic_for_statement(self, items):
        init = None
        condition = None
        update = ()
        body = None

        for item in items:
            if isinstance(item, ast.LocalVariableDeclaration):
                init = item
            elif isinstance(item, tuple) and item and isinstance(item[0], ast.Expression):
                if init is None:
                    init = item
                elif update == ():
                    update = item
            elif isinstance(item, ast.Expression) and condition is None:
                condition = item
            elif isinstance(item, ast.Statement):
                body = item

        return ast.ForStatement(
            init=init,
            condition=condition,
            update=update,
            body=body or ast.EmptyStatement()
        )

    def basic_for_statement_no_short_if(self, items):
        return self.basic_for_statement(items)

    def for_init(self, items):
        for item in items:
            if isinstance(item, ast.LocalVariableDeclaration):
                return item
            if isinstance(item, tuple):
                return item
        return None

    def for_update(self, items):
        for item in items:
            if isinstance(item, tuple):
                return item
        return self.statement_expression_list(items)

    def statement_expression_list(self, items):
        return tuple(item for item in items if isinstance(item, ast.Expression))

    def enhanced_for_statement(self, items):
        modifiers = []
        var_type = None
        name = None
        iterable = None
        body = None

        for item in items:
            if isinstance(item, ast.Modifier):
                modifiers.append(item)
            elif isinstance(item, ast.Type):
                var_type = item
            elif isinstance(item, Token) and item.type == "IDENTIFIER":
                name = str(item)
            elif isinstance(item, ast.Expression):
                iterable = item
            elif isinstance(item, ast.Statement):
                body = item

        return ast.EnhancedForStatement(
            modifiers=tuple(modifiers),
            type=var_type or ast.PrimitiveType(name="int"),
            name=name or "",
            iterable=iterable or ast.Literal(value="null", kind="null"),
            body=body or ast.EmptyStatement()
        )

    def enhanced_for_statement_no_short_if(self, items):
        return self.enhanced_for_statement(items)

    def assert_statement(self, items):
        condition = None
        message = None
        for item in items:
            if isinstance(item, ast.Expression):
                if condition is None:
                    condition = item
                else:
                    message = item
        return ast.AssertStatement(
            condition=condition or ast.Literal(value="false", kind="boolean"),
            message=message
        )

    def switch_statement(self, items):
        expression = None
        cases = ()
        for item in items:
            if isinstance(item, ast.Expression):
                expression = item
            elif isinstance(item, tuple) and item and isinstance(item[0], ast.SwitchCase):
                cases = item
        return ast.SwitchStatement(
            expression=expression or ast.Literal(value="0", kind="int"),
            cases=cases
        )

    def switch_block(self, items):
        cases = []
        for item in items:
            if isinstance(item, ast.SwitchCase):
                cases.append(item)
        return tuple(cases)

    def switch_block_statement_group(self, items):
        labels = []
        statements = []
        for item in items:
            if isinstance(item, ast.Expression) or item is None:
                labels.append(item)
            elif isinstance(item, ast.Statement):
                statements.append(item)
            elif isinstance(item, tuple):
                if item and isinstance(item[0], ast.Expression):
                    labels.extend(item)
                elif item and isinstance(item[0], ast.Statement):
                    statements.extend(item)
        return ast.SwitchCase(labels=tuple(labels), statements=tuple(statements))

    def switch_labels(self, items):
        labels = []
        for item in items:
            if isinstance(item, ast.Expression) or item is None:
                labels.append(item)
        return tuple(labels)

    def switch_label(self, items):
        for item in items:
            if isinstance(item, ast.Expression):
                return item
        return None

    def enum_constant_name(self, items):
        for item in items:
            if isinstance(item, Token):
                return ast.Identifier(name=str(item))
        return None

    def break_statement(self, items):
        label = None
        for item in items:
            if isinstance(item, Token) and item.type == "IDENTIFIER":
                label = str(item)
        return ast.BreakStatement(label=label)

    def continue_statement(self, items):
        label = None
        for item in items:
            if isinstance(item, Token) and item.type == "IDENTIFIER":
                label = str(item)
        return ast.ContinueStatement(label=label)

    def return_statement(self, items):
        expression = None
        for item in items:
            if isinstance(item, ast.Expression):
                expression = item
        return ast.ReturnStatement(expression=expression)

    def throw_statement(self, items):
        expression = None
        for item in items:
            if isinstance(item, ast.Expression):
                expression = item
        return ast.ThrowStatement(expression=expression or ast.Literal(value="null", kind="null"))

    def synchronized_statement(self, items):
        expression = None
        body = None
        for item in items:
            if isinstance(item, ast.Expression):
                expression = item
            elif isinstance(item, ast.Block):
                body = item
        return ast.SynchronizedStatement(
            expression=expression or ast.Literal(value="null", kind="null"),
            body=body or ast.Block(statements=())
        )

    def try_statement(self, items):
        resources = ()
        body = None
        catches = ()
        finally_block = None

        for item in items:
            if isinstance(item, tuple) and item and isinstance(item[0], ast.Resource):
                resources = item
            elif isinstance(item, ast.Block) and body is None:
                body = item
            elif isinstance(item, tuple) and item and isinstance(item[0], ast.CatchClause):
                catches = item
            elif isinstance(item, ast.Block):
                finally_block = item

        return ast.TryStatement(
            resources=resources,
            body=body or ast.Block(statements=()),
            catches=catches,
            finally_block=finally_block
        )

    def catches(self, items):
        return tuple(item for item in items if isinstance(item, ast.CatchClause))

    def catch_clause(self, items):
        modifiers = ()
        types = ()
        name = ""
        body = None

        for item in items:
            # catch_formal_parameter returns (modifiers, types, name)
            if isinstance(item, tuple) and len(item) == 3:
                param_modifiers, param_types, param_name = item
                if isinstance(param_modifiers, tuple) and (not param_modifiers or isinstance(param_modifiers[0], ast.Modifier)):
                    modifiers = param_modifiers
                if isinstance(param_types, tuple) and param_types and isinstance(param_types[0], ast.Type):
                    types = param_types
                if param_name:
                    name = param_name
            elif isinstance(item, ast.Block):
                body = item

        return ast.CatchClause(
            modifiers=modifiers,
            types=types,
            name=name,
            body=body or ast.Block(statements=())
        )

    def catch_formal_parameter(self, items):
        modifiers = []
        types = []
        name = None

        for item in items:
            if isinstance(item, ast.Modifier):
                modifiers.append(item)
            elif isinstance(item, ast.Type):
                types.append(item)
            elif isinstance(item, tuple) and item and isinstance(item[0], ast.Type):
                # catch_type returns a tuple of types
                types.extend(item)
            elif isinstance(item, Token) and item.type == "IDENTIFIER":
                name = str(item)

        return (tuple(modifiers), tuple(types), name)

    def catch_type(self, items):
        return tuple(item for item in items if isinstance(item, ast.Type))

    def finally_clause(self, items):
        for item in items:
            if isinstance(item, ast.Block):
                return item
        return None

    def try_with_resources_statement(self, items):
        return self.try_statement(items)

    def resource_specification(self, items):
        resources = []
        for item in items:
            if isinstance(item, ast.Resource):
                resources.append(item)
            elif isinstance(item, tuple):
                resources.extend(r for r in item if isinstance(r, ast.Resource))
        return tuple(resources)

    def resource_list(self, items):
        return tuple(item for item in items if isinstance(item, ast.Resource))

    def resource(self, items):
        modifiers = []
        res_type = None
        name = None
        expression = None

        for item in items:
            if isinstance(item, ast.Modifier):
                modifiers.append(item)
            elif isinstance(item, ast.Type):
                res_type = item
            elif isinstance(item, Token) and item.type == "IDENTIFIER":
                name = str(item)
            elif isinstance(item, ast.Expression):
                expression = item

        return ast.Resource(
            modifiers=tuple(modifiers),
            type=res_type or ast.PrimitiveType(name="int"),
            name=name or "",
            expression=expression or ast.Literal(value="null", kind="null")
        )

    # ==================== EXPRESSIONS ====================

    def constant_expression(self, items):
        for item in items:
            if isinstance(item, ast.Expression):
                return item
        return None

    def expression(self, items):
        for item in items:
            if isinstance(item, ast.Expression):
                return item
        return None

    def lambda_expression(self, items):
        params = ()
        body = None

        for item in items:
            if isinstance(item, tuple):
                params = item
            elif isinstance(item, Token) and item.type == "IDENTIFIER":
                params = (str(item),)
            elif isinstance(item, (ast.Expression, ast.Block)):
                body = item

        return ast.LambdaExpression(
            parameters=params,
            body=body or ast.Literal(value="null", kind="null")
        )

    def lambda_parameters(self, items):
        params = []
        for item in items:
            if isinstance(item, ast.FormalParameter):
                params.append(item)
            elif isinstance(item, Token) and item.type == "IDENTIFIER":
                params.append(str(item))
            elif isinstance(item, tuple):
                params.extend(item)
        return tuple(params)

    def inferred_formal_parameter_list(self, items):
        return tuple(str(item) for item in items if isinstance(item, Token) and item.type == "IDENTIFIER")

    def lambda_body(self, items):
        for item in items:
            if isinstance(item, (ast.Expression, ast.Block)):
                return item
        return None

    def assignment_expression(self, items):
        for item in items:
            if isinstance(item, ast.Expression):
                return item
        return None

    def assignment(self, items):
        target = None
        operator = "="
        value = None

        assignment_ops = {
            'ASSIGN', 'PLUS_ASSIGN', 'MINUS_ASSIGN', 'STAR_ASSIGN',
            'SLASH_ASSIGN', 'PERCENT_ASSIGN', 'AMP_ASSIGN', 'PIPE_ASSIGN',
            'CARET_ASSIGN', 'LSHIFT_ASSIGN', 'RSHIFT_ASSIGN', 'URSHIFT_ASSIGN'
        }

        for item in items:
            if isinstance(item, ast.Expression):
                if target is None:
                    target = item
                else:
                    value = item
            elif hasattr(item, 'type') and item.type in assignment_ops:
                operator = str(item)
            elif isinstance(item, str) and "=" in item:
                operator = item

        return ast.Assignment(
            target=target or ast.Identifier(name=""),
            operator=operator,
            value=value or ast.Literal(value="null", kind="null")
        )

    def left_hand_side(self, items):
        for item in items:
            if isinstance(item, ast.Expression):
                return item
        return None

    def assignment_operator(self, items):
        for item in items:
            if hasattr(item, 'type'):
                return str(item)
        return str(items[0]) if items else "="

    def conditional_expression(self, items):
        if len(items) == 1:
            return items[0]

        condition = None
        then_expr = None
        else_expr = None

        for item in items:
            if isinstance(item, ast.Expression):
                if condition is None:
                    condition = item
                elif then_expr is None:
                    then_expr = item
                else:
                    else_expr = item

        if then_expr is None:
            return condition

        return ast.ConditionalExpression(
            condition=condition or ast.Literal(value="false", kind="boolean"),
            then_expr=then_expr or ast.Literal(value="null", kind="null"),
            else_expr=else_expr or ast.Literal(value="null", kind="null")
        )

    def _binary_expression(self, items, operators):
        """Helper for binary expressions."""
        result = None
        pending_op = None

        for item in items:
            if isinstance(item, ast.Expression):
                if result is None:
                    result = item
                elif pending_op:
                    result = ast.BinaryExpression(left=result, operator=pending_op, right=item)
                    pending_op = None
            elif isinstance(item, Token) and str(item) in operators:
                # Check Token before str since Token is a str subclass
                pending_op = str(item)
            elif isinstance(item, str) and item in operators:
                pending_op = item

        return result

    def conditional_or_expression(self, items):
        return self._binary_expression(items, {"||"})

    def conditional_and_expression(self, items):
        return self._binary_expression(items, {"&&"})

    def inclusive_or_expression(self, items):
        return self._binary_expression(items, {"|"})

    def exclusive_or_expression(self, items):
        return self._binary_expression(items, {"^"})

    def and_expression(self, items):
        return self._binary_expression(items, {"&"})

    def equality_expression(self, items):
        return self._binary_expression(items, {"==", "!="})

    def relational_expression(self, items):
        result = None
        pending_op = None

        for item in items:
            if isinstance(item, ast.Expression):
                if result is None:
                    result = item
                elif pending_op:
                    result = ast.BinaryExpression(left=result, operator=pending_op, right=item)
                    pending_op = None
            elif isinstance(item, ast.Type) and pending_op == "instanceof":
                result = ast.InstanceOfExpression(expression=result, type=item)
                pending_op = None
            # Check Token before str since Token is a str subclass
            elif isinstance(item, Token) and (str(item) in {"<", ">", "<=", ">="} or item.type == 'INSTANCEOF'):
                pending_op = str(item)
            elif isinstance(item, str) and item in {"<", ">", "<=", ">=", "instanceof"}:
                pending_op = item

        return result

    def shift_expression(self, items):
        return self._binary_expression(items, {"<<", ">>", ">>>"})

    def additive_expression(self, items):
        return self._binary_expression(items, {"+", "-"})

    def multiplicative_expression(self, items):
        return self._binary_expression(items, {"*", "/", "%"})

    def unary_expression(self, items):
        op = None
        expr = None

        for item in items:
            if isinstance(item, ast.Expression):
                expr = item
            elif hasattr(item, 'type') and item.type in {'PLUS', 'MINUS'}:
                op = str(item)
            elif item in {'+', '-'}:
                op = item

        if op and expr:
            return ast.UnaryExpression(operator=op, operand=expr, prefix=True)
        return expr

    def pre_increment_expression(self, items):
        for item in items:
            if isinstance(item, ast.Expression):
                return ast.UnaryExpression(operator="++", operand=item, prefix=True)
        return None

    def pre_decrement_expression(self, items):
        for item in items:
            if isinstance(item, ast.Expression):
                return ast.UnaryExpression(operator="--", operand=item, prefix=True)
        return None

    def unary_expression_not_plus_minus(self, items):
        op = None
        expr = None

        for item in items:
            if isinstance(item, ast.Expression):
                expr = item
            elif hasattr(item, 'type') and item.type in {'BANG', 'TILDE'}:
                op = str(item)
            elif item in {"~", "!"}:
                op = item

        if op and expr:
            return ast.UnaryExpression(operator=op, operand=expr, prefix=True)
        return expr

    def postfix_expression(self, items):
        for item in items:
            if isinstance(item, ast.Expression):
                return item
        return None

    def post_increment_expression(self, items):
        for item in items:
            if isinstance(item, ast.Expression):
                return ast.UnaryExpression(operator="++", operand=item, prefix=False)
        return None

    def post_decrement_expression(self, items):
        for item in items:
            if isinstance(item, ast.Expression):
                return ast.UnaryExpression(operator="--", operand=item, prefix=False)
        return None

    def cast_expression(self, items):
        cast_type = None
        expr = None

        for item in items:
            if isinstance(item, ast.Type):
                cast_type = item
            elif isinstance(item, ast.Expression):
                expr = item

        return ast.CastExpression(
            type=cast_type or ast.PrimitiveType(name="int"),
            expression=expr or ast.Literal(value="null", kind="null")
        )

    def additional_bound(self, items):
        for item in items:
            if isinstance(item, ast.Type):
                return item
        return None

    # ==================== PRIMARY EXPRESSIONS ====================

    def primary(self, items):
        for item in items:
            if isinstance(item, ast.Expression):
                return item
        return None

    def primary_no_new_array(self, items):
        for item in items:
            if isinstance(item, ast.Expression):
                return item
        return None

    def literal(self, items):
        if not items:
            return ast.Literal(value="null", kind="null")

        token = items[0]
        value = str(token)

        if token.type == "INTEGER_LITERAL":
            kind = "long" if value.endswith(("l", "L")) else "int"
        elif token.type == "FLOATING_POINT_LITERAL":
            kind = "float" if value.endswith(("f", "F")) else "double"
        elif token.type == "BOOLEAN_LITERAL":
            kind = "boolean"
        elif token.type == "CHARACTER_LITERAL":
            kind = "char"
        elif token.type == "STRING_LITERAL":
            kind = "string"
        elif token.type == "NULL_LITERAL":
            kind = "null"
        else:
            kind = "unknown"

        return ast.Literal(value=value, kind=kind)

    def class_literal(self, items):
        for item in items:
            if isinstance(item, ast.Type):
                return ast.ClassLiteral(type=item)
            if isinstance(item, str):
                return ast.ClassLiteral(type=ast.PrimitiveType(name=item))
        return ast.ClassLiteral(type=ast.PrimitiveType(name="void"))

    def class_instance_creation_expression(self, items):
        # Can be: unqualified_class_instance_creation
        # Or: expression "." unqualified_class_instance_creation
        # Or: primary "." unqualified_class_instance_creation
        qualifier = None
        new_instance = None

        for item in items:
            if isinstance(item, ast.NewInstance):
                new_instance = item
            elif isinstance(item, ast.Expression):
                qualifier = item

        if new_instance and qualifier:
            # Qualified allocation: outer.new Inner()
            return ast.NewInstance(
                qualifier=qualifier,
                type_arguments=new_instance.type_arguments,
                type=new_instance.type,
                arguments=new_instance.arguments,
                body=new_instance.body
            )
        elif new_instance:
            return new_instance
        return None

    def unqualified_class_instance_creation(self, items):
        type_args = ()
        inst_type = None
        arguments = ()
        body = None

        for item in items:
            if isinstance(item, tuple) and item and isinstance(item[0], ast.Type):
                type_args = item
            elif isinstance(item, ast.Type):
                inst_type = item
            elif isinstance(item, tuple) and (not item or isinstance(item[0], ast.Expression)):
                arguments = item
            elif isinstance(item, tuple) and item and isinstance(item[0], ast.ClassBodyDeclaration):
                body = item

        return ast.NewInstance(
            qualifier=None,
            type_arguments=type_args,
            type=inst_type or ast.ClassType(name="Object", type_arguments=()),
            arguments=arguments,
            body=body
        )

    def class_type_to_instantiate(self, items):
        annotations = []
        name_parts = []
        type_args = ()

        for item in items:
            if isinstance(item, ast.Annotation):
                annotations.append(item)
            elif isinstance(item, Token) and item.type == "IDENTIFIER":
                name_parts.append(str(item))
            elif isinstance(item, tuple) and item and isinstance(item[0], ast.TypeArgument):
                type_args = item

        return ast.ClassType(
            name=".".join(name_parts),
            type_arguments=type_args,
            annotations=tuple(annotations)
        )

    def type_arguments_or_diamond(self, items):
        for item in items:
            if isinstance(item, tuple):
                return item
        return ()

    def field_access(self, items):
        target = None
        field = None

        for item in items:
            if isinstance(item, ast.Expression):
                target = item
            elif isinstance(item, Token) and item.type == "SUPER":
                target = ast.SuperExpression(qualifier=None)
            elif isinstance(item, str) and item == "super":
                target = ast.SuperExpression(qualifier=None)
            elif isinstance(item, Token) and item.type == "IDENTIFIER":
                field = str(item)

        return ast.FieldAccess(
            target=target or ast.ThisExpression(qualifier=None),
            field=field or ""
        )

    def field_access_super(self, items):
        field = None
        for item in items:
            if isinstance(item, Token) and item.type == "IDENTIFIER":
                field = str(item)
        return ast.FieldAccess(
            target=ast.SuperExpression(qualifier=None),
            field=field or ""
        )

    def field_access_type_super(self, items):
        qualifier = None
        field = None
        for item in items:
            if isinstance(item, ast.ClassType) and qualifier is None:
                qualifier = item.name
            elif isinstance(item, Token) and item.type == "IDENTIFIER":
                field = str(item)
        return ast.FieldAccess(
            target=ast.SuperExpression(qualifier=qualifier),
            field=field or ""
        )

    def array_access(self, items):
        array = None
        index = None

        for item in items:
            if isinstance(item, ast.Expression):
                if array is None:
                    array = item
                else:
                    index = item

        return ast.ArrayAccess(
            array=array or ast.Identifier(name=""),
            index=index or ast.Literal(value="0", kind="int")
        )

    def method_invocation(self, items):
        target = None
        type_args = ()
        method = None
        arguments = ()

        for item in items:
            if isinstance(item, Token) and item.type == "SUPER" and method is None and target is None:
                target = ast.SuperExpression(qualifier=None)
            elif isinstance(item, str) and item == "super" and method is None and target is None:
                target = ast.SuperExpression(qualifier=None)
            elif isinstance(item, ast.Expression) and method is None:
                target = item
            elif isinstance(item, ast.ClassType) and method is None:
                # Convert type name to QualifiedName for use as target
                # e.g., System.out becomes QualifiedName(("System", "out"))
                parts = tuple(item.name.split("."))
                target = ast.QualifiedName(parts=parts)
            elif isinstance(item, tuple) and item and isinstance(item[0], ast.Type):
                type_args = item
            elif isinstance(item, Token) and item.type == "IDENTIFIER":
                method = str(item)
            elif isinstance(item, str):
                method = item
            elif isinstance(item, tuple) and (not item or isinstance(item[0], ast.Expression)):
                arguments = item

        return ast.MethodInvocation(
            target=target,
            type_arguments=type_args,
            method=method or "",
            arguments=arguments
        )

    def method_invocation_type(self, items):
        return self.method_invocation(items)

    def method_invocation_expr(self, items):
        return self.method_invocation(items)

    def method_invocation_primary(self, items):
        return self.method_invocation(items)

    def method_invocation_super(self, items):
        # Prepend an explicit super target to leverage common handling
        return self.method_invocation([ast.SuperExpression(qualifier=None)] + list(items))

    def method_invocation_type_super(self, items):
        qualifier = None
        rest = []
        for item in items:
            if isinstance(item, ast.ClassType) and qualifier is None:
                qualifier = item.name
            else:
                rest.append(item)
        return self.method_invocation([ast.SuperExpression(qualifier=qualifier)] + rest)

    def argument_list(self, items):
        return tuple(item for item in items if isinstance(item, ast.Expression))

    def method_reference(self, items):
        target = None
        type_args = ()
        method = None

        for item in items:
            if isinstance(item, (ast.Expression, ast.Type)) and target is None:
                target = item
            elif isinstance(item, tuple) and item and isinstance(item[0], ast.Type):
                type_args = item
            elif isinstance(item, Token) and item.type == "IDENTIFIER":
                method = str(item)
            elif item == "new":
                method = "new"

        return ast.MethodReference(
            target=target or ast.Identifier(name=""),
            type_arguments=type_args,
            method=method or ""
        )

    def array_creation_expression(self, items):
        arr_type = None
        dimensions = []
        initializer = None

        for item in items:
            if isinstance(item, ast.Type):
                arr_type = item
            elif isinstance(item, ast.Expression):
                dimensions.append(item)
            elif isinstance(item, tuple) and item and isinstance(item[0], ast.Expression):
                dimensions.extend(item)
            elif isinstance(item, int):
                dimensions.extend([None] * item)
            elif isinstance(item, ast.ArrayInitializer):
                initializer = item

        return ast.NewArray(
            type=arr_type or ast.PrimitiveType(name="int"),
            dimensions=tuple(dimensions) if dimensions else (None,),
            initializer=initializer
        )

    def dim_exprs(self, items):
        return tuple(item for item in items if isinstance(item, ast.Expression))

    def dim_expr(self, items):
        for item in items:
            if isinstance(item, ast.Expression):
                return item
        return None

    def array_initializer(self, items):
        elements = []
        for item in items:
            if isinstance(item, ast.Expression):
                elements.append(item)
            elif isinstance(item, tuple):
                elements.extend(e for e in item if isinstance(e, ast.Expression))
        return ast.ArrayInitializer(elements=tuple(elements))

    def variable_initializer_list(self, items):
        return tuple(item for item in items if isinstance(item, ast.Expression))

    # ==================== NAMES ====================

    def expression_name(self, items):
        parts = []
        for item in items:
            if isinstance(item, Token) and item.type == "IDENTIFIER":
                parts.append(str(item))
            elif isinstance(item, str):
                parts.append(item)

        if len(parts) == 1 and parts[0] == "super":
            return ast.SuperExpression(qualifier=None)
        if len(parts) == 1:
            return ast.Identifier(name=parts[0])
        return ast.QualifiedName(parts=tuple(parts))

    def method_name(self, items):
        for item in items:
            if isinstance(item, Token) and item.type == "IDENTIFIER":
                return str(item)
        return ""

    def type_name(self, items):
        parts = []
        for item in items:
            if isinstance(item, Token) and item.type == "IDENTIFIER":
                parts.append(str(item))
            elif isinstance(item, str):
                parts.append(item)

        return ast.ClassType(name=".".join(parts), type_arguments=())

    def package_or_type_name(self, items):
        parts = []
        for item in items:
            if isinstance(item, Token) and item.type == "IDENTIFIER":
                parts.append(str(item))
            elif isinstance(item, str):
                parts.append(item)
        return ".".join(parts)

    def ambiguous_name(self, items):
        parts = []
        for item in items:
            if isinstance(item, Token) and item.type == "IDENTIFIER":
                parts.append(str(item))
            elif isinstance(item, str):
                parts.append(item)
        return ".".join(parts)

    def qualified_name(self, items):
        parts = []
        for item in items:
            if isinstance(item, Token) and item.type == "IDENTIFIER":
                parts.append(str(item))
        return ".".join(parts)

    def arguments(self, items):
        # argument_list returns a tuple of expressions, so we need to flatten it
        result = []
        for item in items:
            if isinstance(item, ast.Expression):
                result.append(item)
            elif isinstance(item, tuple) and item and isinstance(item[0], ast.Expression):
                # This is the result from argument_list - extend with all expressions
                result.extend(item)
        return tuple(result)

    # ==================== HELPERS ====================

    def _extract_types(self, items) -> tuple:
        """Extract types from items."""
        types = []
        for item in items:
            if isinstance(item, ast.Type):
                types.append(item)
            elif isinstance(item, tuple):
                types.extend(t for t in item if isinstance(t, ast.Type))
        return tuple(types)

    def IDENTIFIER(self, token):
        return token

    def INTEGER_LITERAL(self, token):
        return token

    def FLOATING_POINT_LITERAL(self, token):
        return token

    def BOOLEAN_LITERAL(self, token):
        return token

    def CHARACTER_LITERAL(self, token):
        return token

    def STRING_LITERAL(self, token):
        return token

    def NULL_LITERAL(self, token):
        return token


class Java8Parser:
    """Main parser class for Java 8."""

    def __init__(self):
        with open(GRAMMAR_FILE, "r") as f:
            grammar = f.read()

        self._parser = Lark(
            grammar,
            parser="earley",
            propagate_positions=True,
            maybe_placeholders=False,
        )
        self._transformer = Java8Transformer()

    def parse(self, source: str) -> ast.CompilationUnit:
        """Parse Java source code and return AST."""
        preprocessed = preprocess_unicode_escapes(source)
        tree = self._parser.parse(preprocessed)
        return self._transformer.transform(tree)

    def parse_file(self, path: str) -> ast.CompilationUnit:
        """Parse a Java file and return AST."""
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            source = f.read()
        return self.parse(source)
