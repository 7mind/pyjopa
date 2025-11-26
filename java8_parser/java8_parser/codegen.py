"""
Bytecode generator for Java 8 AST.
Generates Java 6 bytecode (version 50.0).
"""

from dataclasses import dataclass, field
from typing import Optional
from . import ast
from .types import (
    JType, PrimitiveJType, ClassJType, ArrayJType, MethodType,
    VOID, BOOLEAN, BYTE, CHAR, SHORT, INT, LONG, FLOAT, DOUBLE,
    OBJECT, STRING, SYSTEM, PRINTSTREAM,
    PRIMITIVE_TYPES, is_numeric, binary_numeric_promotion,
)
from .classfile import (
    ClassFile, MethodInfo, FieldInfo, CodeAttribute, BytecodeBuilder,
    AccessFlags,
)


class CompileError(Exception):
    """Error during compilation."""
    pass


@dataclass
class LocalVariable:
    """A local variable in a method."""
    name: str
    type: JType
    slot: int


@dataclass
class MethodContext:
    """Context for compiling a method."""
    class_name: str
    method_name: str
    return_type: JType
    builder: BytecodeBuilder
    locals: dict[str, LocalVariable] = field(default_factory=dict)
    next_slot: int = 0

    def add_local(self, name: str, jtype: JType) -> LocalVariable:
        var = LocalVariable(name, jtype, self.next_slot)
        self.locals[name] = var
        self.next_slot += jtype.size
        self.builder.max_locals = max(self.builder.max_locals, self.next_slot)
        return var

    def get_local(self, name: str) -> LocalVariable:
        if name not in self.locals:
            raise CompileError(f"Undefined variable: {name}")
        return self.locals[name]


class CodeGenerator:
    """Generates bytecode from AST."""

    def __init__(self):
        self.class_file: Optional[ClassFile] = None
        self.class_name: str = ""
        self._label_counter = 0

    def new_label(self, prefix: str = "L") -> str:
        self._label_counter += 1
        return f"{prefix}{self._label_counter}"

    def compile(self, unit: ast.CompilationUnit) -> dict[str, bytes]:
        """Compile a compilation unit to class files."""
        results = {}
        for type_decl in unit.types:
            if isinstance(type_decl, ast.ClassDeclaration):
                class_bytes = self.compile_class(type_decl)
                results[type_decl.name] = class_bytes
        return results

    def compile_class(self, cls: ast.ClassDeclaration) -> bytes:
        """Compile a class declaration."""
        self.class_name = cls.name
        self.class_file = ClassFile(cls.name)

        # Set access flags
        flags = AccessFlags.SUPER
        for mod in cls.modifiers:
            if mod.keyword == "public":
                flags |= AccessFlags.PUBLIC
            elif mod.keyword == "private":
                flags |= AccessFlags.PRIVATE
            elif mod.keyword == "protected":
                flags |= AccessFlags.PROTECTED
            elif mod.keyword == "final":
                flags |= AccessFlags.FINAL
            elif mod.keyword == "abstract":
                flags |= AccessFlags.ABSTRACT
        self.class_file.access_flags = flags

        # Process members
        for member in cls.body:
            if isinstance(member, ast.MethodDeclaration):
                self.compile_method(member)
            elif isinstance(member, ast.FieldDeclaration):
                self.compile_field(member)
            elif isinstance(member, ast.ConstructorDeclaration):
                self.compile_constructor(member)

        return self.class_file.to_bytes()

    def compile_field(self, fld: ast.FieldDeclaration):
        """Compile a field declaration."""
        flags = 0
        for mod in fld.modifiers:
            if mod.keyword == "public":
                flags |= AccessFlags.PUBLIC
            elif mod.keyword == "private":
                flags |= AccessFlags.PRIVATE
            elif mod.keyword == "protected":
                flags |= AccessFlags.PROTECTED
            elif mod.keyword == "static":
                flags |= AccessFlags.STATIC
            elif mod.keyword == "final":
                flags |= AccessFlags.FINAL

        jtype = self.resolve_type(fld.type)
        for decl in fld.declarators:
            field_info = FieldInfo(
                access_flags=flags,
                name=decl.name,
                descriptor=jtype.descriptor()
            )
            self.class_file.add_field(field_info)

    def compile_constructor(self, ctor: ast.ConstructorDeclaration):
        """Compile a constructor."""
        flags = 0
        for mod in ctor.modifiers:
            if mod.keyword == "public":
                flags |= AccessFlags.PUBLIC
            elif mod.keyword == "private":
                flags |= AccessFlags.PRIVATE
            elif mod.keyword == "protected":
                flags |= AccessFlags.PROTECTED

        # Build method descriptor
        param_types = [self.resolve_type(p.type) for p in ctor.parameters]
        descriptor = "(" + "".join(t.descriptor() for t in param_types) + ")V"

        builder = BytecodeBuilder(self.class_file.cp)
        ctx = MethodContext(
            class_name=self.class_name,
            method_name="<init>",
            return_type=VOID,
            builder=builder,
        )

        # 'this' is slot 0
        ctx.add_local("this", ClassJType(self.class_name))

        # Add parameters
        for param, jtype in zip(ctor.parameters, param_types):
            ctx.add_local(param.name, jtype)

        # Call super constructor
        builder.aload(0)
        builder.invokespecial("java/lang/Object", "<init>", "()V", 0, 0)

        # Compile body
        self.compile_block(ctor.body, ctx)

        # Add return
        builder.return_()

        method_info = MethodInfo(
            access_flags=flags,
            name="<init>",
            descriptor=descriptor,
            code=builder.build()
        )
        self.class_file.add_method(method_info)

    def compile_method(self, method: ast.MethodDeclaration):
        """Compile a method declaration."""
        flags = 0
        is_static = False
        for mod in method.modifiers:
            if mod.keyword == "public":
                flags |= AccessFlags.PUBLIC
            elif mod.keyword == "private":
                flags |= AccessFlags.PRIVATE
            elif mod.keyword == "protected":
                flags |= AccessFlags.PROTECTED
            elif mod.keyword == "static":
                flags |= AccessFlags.STATIC
                is_static = True
            elif mod.keyword == "final":
                flags |= AccessFlags.FINAL
            elif mod.keyword == "native":
                flags |= AccessFlags.NATIVE
            elif mod.keyword == "abstract":
                flags |= AccessFlags.ABSTRACT

        # Build method descriptor
        param_types = [self.resolve_type(p.type) for p in method.parameters]
        return_type = self.resolve_type(method.return_type)
        descriptor = MethodType(return_type, tuple(param_types)).descriptor()

        # Abstract/native methods have no code
        if method.body is None:
            method_info = MethodInfo(
                access_flags=flags,
                name=method.name,
                descriptor=descriptor,
                code=None
            )
            self.class_file.add_method(method_info)
            return

        builder = BytecodeBuilder(self.class_file.cp)
        ctx = MethodContext(
            class_name=self.class_name,
            method_name=method.name,
            return_type=return_type,
            builder=builder,
        )

        # Add 'this' for instance methods
        if not is_static:
            ctx.add_local("this", ClassJType(self.class_name))

        # Add parameters
        for param, jtype in zip(method.parameters, param_types):
            ctx.add_local(param.name, jtype)

        # Compile body
        self.compile_block(method.body, ctx)

        # Add implicit return for void methods
        if return_type == VOID:
            builder.return_()

        method_info = MethodInfo(
            access_flags=flags,
            name=method.name,
            descriptor=descriptor,
            code=builder.build()
        )
        self.class_file.add_method(method_info)

    def compile_block(self, block: ast.Block, ctx: MethodContext):
        """Compile a block of statements."""
        for stmt in block.statements:
            self.compile_statement(stmt, ctx)

    def compile_statement(self, stmt: ast.Statement, ctx: MethodContext):
        """Compile a statement."""
        builder = ctx.builder

        if isinstance(stmt, ast.Block):
            self.compile_block(stmt, ctx)

        elif isinstance(stmt, ast.LocalVariableDeclaration):
            jtype = self.resolve_type(stmt.type)
            for decl in stmt.declarators:
                var = ctx.add_local(decl.name, jtype)
                if decl.initializer:
                    self.compile_expression(decl.initializer, ctx)
                    self.store_local(var, builder)

        elif isinstance(stmt, ast.ExpressionStatement):
            expr_type = self.compile_expression(stmt.expression, ctx)
            # Pop result if not void
            if expr_type != VOID:
                if expr_type.size == 2:
                    builder._emit(0x58)  # pop2
                    builder._pop(2)
                else:
                    builder.pop()

        elif isinstance(stmt, ast.ReturnStatement):
            if stmt.expression:
                self.compile_expression(stmt.expression, ctx)
                if ctx.return_type == VOID:
                    builder.return_()
                elif ctx.return_type == INT or ctx.return_type == BOOLEAN:
                    builder.ireturn()
                elif ctx.return_type == LONG:
                    builder.lreturn()
                elif ctx.return_type == FLOAT:
                    builder.freturn()
                elif ctx.return_type == DOUBLE:
                    builder.dreturn()
                elif ctx.return_type.is_reference:
                    builder.areturn()
                else:
                    builder.ireturn()
            else:
                builder.return_()

        elif isinstance(stmt, ast.IfStatement):
            else_label = self.new_label("else")
            end_label = self.new_label("endif")

            # Compile condition
            self.compile_condition(stmt.condition, ctx, else_label, False)

            # Then branch
            self.compile_statement(stmt.then_branch, ctx)

            if stmt.else_branch:
                builder.goto(end_label)
                builder.label(else_label)
                self.compile_statement(stmt.else_branch, ctx)
                builder.label(end_label)
            else:
                builder.label(else_label)

        elif isinstance(stmt, ast.WhileStatement):
            loop_label = self.new_label("while")
            end_label = self.new_label("endwhile")

            builder.label(loop_label)
            self.compile_condition(stmt.condition, ctx, end_label, False)
            self.compile_statement(stmt.body, ctx)
            builder.goto(loop_label)
            builder.label(end_label)

        elif isinstance(stmt, ast.DoWhileStatement):
            loop_label = self.new_label("do")

            builder.label(loop_label)
            self.compile_statement(stmt.body, ctx)
            self.compile_condition(stmt.condition, ctx, loop_label, True)

        elif isinstance(stmt, ast.ForStatement):
            loop_label = self.new_label("for")
            end_label = self.new_label("endfor")
            update_label = self.new_label("update")

            # Init
            if stmt.init:
                if isinstance(stmt.init, ast.LocalVariableDeclaration):
                    self.compile_statement(stmt.init, ctx)
                else:
                    for expr in stmt.init:
                        expr_type = self.compile_expression(expr, ctx)
                        if expr_type != VOID:
                            builder.pop()

            builder.label(loop_label)

            # Condition
            if stmt.condition:
                self.compile_condition(stmt.condition, ctx, end_label, False)

            # Body
            self.compile_statement(stmt.body, ctx)

            builder.label(update_label)

            # Update
            for expr in stmt.update:
                expr_type = self.compile_expression(expr, ctx)
                if expr_type != VOID:
                    builder.pop()

            builder.goto(loop_label)
            builder.label(end_label)

        elif isinstance(stmt, ast.EmptyStatement):
            pass

        else:
            raise CompileError(f"Unsupported statement type: {type(stmt).__name__}")

    def compile_condition(self, expr: ast.Expression, ctx: MethodContext,
                          target: str, jump_if_true: bool):
        """Compile a boolean expression as a condition for branching."""
        builder = ctx.builder

        if isinstance(expr, ast.BinaryExpression):
            op = expr.operator
            if op in ("==", "!=", "<", ">=", ">", "<="):
                left_type = self.compile_expression(expr.left, ctx)
                right_type = self.compile_expression(expr.right, ctx)

                if left_type == INT and right_type == INT:
                    if jump_if_true:
                        if op == "==":
                            builder.if_icmpeq(target)
                        elif op == "!=":
                            builder.if_icmpne(target)
                        elif op == "<":
                            builder.if_icmplt(target)
                        elif op == ">=":
                            builder.if_icmpge(target)
                        elif op == ">":
                            builder.if_icmpgt(target)
                        elif op == "<=":
                            builder.if_icmple(target)
                    else:
                        # Jump if false (inverted)
                        if op == "==":
                            builder.if_icmpne(target)
                        elif op == "!=":
                            builder.if_icmpeq(target)
                        elif op == "<":
                            builder.if_icmpge(target)
                        elif op == ">=":
                            builder.if_icmplt(target)
                        elif op == ">":
                            builder.if_icmple(target)
                        elif op == "<=":
                            builder.if_icmpgt(target)
                    return

            elif op == "&&":
                if jump_if_true:
                    next_label = self.new_label("and")
                    self.compile_condition(expr.left, ctx, next_label, False)
                    self.compile_condition(expr.right, ctx, target, True)
                    builder.label(next_label)
                else:
                    self.compile_condition(expr.left, ctx, target, False)
                    self.compile_condition(expr.right, ctx, target, False)
                return

            elif op == "||":
                if jump_if_true:
                    self.compile_condition(expr.left, ctx, target, True)
                    self.compile_condition(expr.right, ctx, target, True)
                else:
                    next_label = self.new_label("or")
                    self.compile_condition(expr.left, ctx, next_label, True)
                    self.compile_condition(expr.right, ctx, target, False)
                    builder.label(next_label)
                return

        elif isinstance(expr, ast.UnaryExpression) and expr.operator == "!":
            self.compile_condition(expr.operand, ctx, target, not jump_if_true)
            return

        # Default: evaluate as boolean and branch
        self.compile_expression(expr, ctx)
        if jump_if_true:
            builder.ifne(target)
        else:
            builder.ifeq(target)

    def compile_expression(self, expr: ast.Expression, ctx: MethodContext) -> JType:
        """Compile an expression and return its type."""
        builder = ctx.builder

        if isinstance(expr, ast.Literal):
            return self.compile_literal(expr, ctx)

        elif isinstance(expr, ast.Identifier):
            var = ctx.get_local(expr.name)
            self.load_local(var, builder)
            return var.type

        elif isinstance(expr, ast.ParenthesizedExpression):
            return self.compile_expression(expr.expression, ctx)

        elif isinstance(expr, ast.BinaryExpression):
            return self.compile_binary(expr, ctx)

        elif isinstance(expr, ast.UnaryExpression):
            return self.compile_unary(expr, ctx)

        elif isinstance(expr, ast.Assignment):
            return self.compile_assignment(expr, ctx)

        elif isinstance(expr, ast.MethodInvocation):
            return self.compile_method_call(expr, ctx)

        elif isinstance(expr, ast.ConditionalExpression):
            return self.compile_ternary(expr, ctx)

        elif isinstance(expr, ast.CastExpression):
            return self.compile_cast(expr, ctx)

        else:
            raise CompileError(f"Unsupported expression type: {type(expr).__name__}")

    def compile_literal(self, lit: ast.Literal, ctx: MethodContext) -> JType:
        builder = ctx.builder

        if lit.kind == "int":
            value = self.parse_int_literal(lit.value)
            builder.iconst(value)
            return INT

        elif lit.kind == "long":
            value = self.parse_long_literal(lit.value)
            builder.lconst(value)
            return LONG

        elif lit.kind == "float":
            value = float(lit.value.rstrip("fF"))
            builder.fconst(value)
            return FLOAT

        elif lit.kind == "double":
            value = float(lit.value.rstrip("dD"))
            builder.dconst(value)
            return DOUBLE

        elif lit.kind == "boolean":
            builder.iconst(1 if lit.value == "true" else 0)
            return BOOLEAN

        elif lit.kind == "char":
            # Parse character literal
            s = lit.value[1:-1]  # Remove quotes
            if s.startswith("\\"):
                ch = self.parse_escape(s)
            else:
                ch = ord(s)
            builder.iconst(ch)
            return CHAR

        elif lit.kind == "string":
            # Remove quotes and parse escapes
            s = self.parse_string_literal(lit.value)
            builder.ldc_string(s)
            return STRING

        elif lit.kind == "null":
            builder.aconst_null()
            return ClassJType("java/lang/Object")

        else:
            raise CompileError(f"Unknown literal kind: {lit.kind}")

    def parse_int_literal(self, s: str) -> int:
        s = s.replace("_", "")
        if s.startswith("0x") or s.startswith("0X"):
            return int(s, 16)
        elif s.startswith("0b") or s.startswith("0B"):
            return int(s, 2)
        elif s.startswith("0") and len(s) > 1 and s[1].isdigit():
            return int(s, 8)
        return int(s)

    def parse_long_literal(self, s: str) -> int:
        return self.parse_int_literal(s.rstrip("lL"))

    def parse_escape(self, s: str) -> int:
        escapes = {"n": 10, "r": 13, "t": 9, "b": 8, "f": 12, "\\": 92, "'": 39, '"': 34}
        if s[1] in escapes:
            return escapes[s[1]]
        elif s[1] == "u":
            return int(s[2:6], 16)
        elif s[1].isdigit():
            return int(s[1:], 8)
        return ord(s[1])

    def parse_string_literal(self, s: str) -> str:
        result = []
        s = s[1:-1]  # Remove quotes
        i = 0
        while i < len(s):
            if s[i] == "\\" and i + 1 < len(s):
                if s[i + 1] == "n":
                    result.append("\n")
                    i += 2
                elif s[i + 1] == "r":
                    result.append("\r")
                    i += 2
                elif s[i + 1] == "t":
                    result.append("\t")
                    i += 2
                elif s[i + 1] == "\\":
                    result.append("\\")
                    i += 2
                elif s[i + 1] == '"':
                    result.append('"')
                    i += 2
                elif s[i + 1] == "u":
                    result.append(chr(int(s[i + 2:i + 6], 16)))
                    i += 6
                else:
                    result.append(s[i + 1])
                    i += 2
            else:
                result.append(s[i])
                i += 1
        return "".join(result)

    def compile_binary(self, expr: ast.BinaryExpression, ctx: MethodContext) -> JType:
        builder = ctx.builder
        op = expr.operator

        # Special handling for string concatenation
        # For now, just handle numeric operations

        left_type = self.compile_expression(expr.left, ctx)
        right_type = self.compile_expression(expr.right, ctx)

        # Numeric promotion
        result_type = binary_numeric_promotion(left_type, right_type)

        if op == "+":
            if result_type == INT:
                builder.iadd()
            elif result_type == LONG:
                builder.ladd()
            elif result_type == FLOAT:
                builder.fadd()
            elif result_type == DOUBLE:
                builder.dadd()
        elif op == "-":
            if result_type == INT:
                builder.isub()
            elif result_type == LONG:
                builder.lsub()
            elif result_type == FLOAT:
                builder.fsub()
            elif result_type == DOUBLE:
                builder.dsub()
        elif op == "*":
            if result_type == INT:
                builder.imul()
            elif result_type == LONG:
                builder.lmul()
            elif result_type == FLOAT:
                builder.fmul()
            elif result_type == DOUBLE:
                builder.dmul()
        elif op == "/":
            if result_type == INT:
                builder.idiv()
            elif result_type == LONG:
                builder.ldiv()
            elif result_type == FLOAT:
                builder.fdiv()
            elif result_type == DOUBLE:
                builder.ddiv()
        elif op == "%":
            if result_type == INT:
                builder.irem()
            elif result_type == LONG:
                builder.lrem()
        elif op == "<<":
            if result_type == INT:
                builder.ishl()
            elif result_type == LONG:
                builder.lshl()
        elif op == ">>":
            if result_type == INT:
                builder.ishr()
            elif result_type == LONG:
                builder.lshr()
        elif op == ">>>":
            if result_type == INT:
                builder.iushr()
            elif result_type == LONG:
                builder.lushr()
        elif op == "&":
            if result_type == INT:
                builder.iand()
            elif result_type == LONG:
                builder.land()
        elif op == "|":
            if result_type == INT:
                builder.ior()
            elif result_type == LONG:
                builder.lor()
        elif op == "^":
            if result_type == INT:
                builder.ixor()
            elif result_type == LONG:
                builder.lxor()
        elif op in ("==", "!=", "<", ">=", ">", "<="):
            # Comparison - result is boolean (int)
            true_label = self.new_label("true")
            end_label = self.new_label("end")

            if left_type == INT and right_type == INT:
                if op == "==":
                    builder.if_icmpeq(true_label)
                elif op == "!=":
                    builder.if_icmpne(true_label)
                elif op == "<":
                    builder.if_icmplt(true_label)
                elif op == ">=":
                    builder.if_icmpge(true_label)
                elif op == ">":
                    builder.if_icmpgt(true_label)
                elif op == "<=":
                    builder.if_icmple(true_label)

            builder.iconst(0)
            builder.goto(end_label)
            builder.label(true_label)
            builder.iconst(1)
            builder.label(end_label)
            return BOOLEAN
        else:
            raise CompileError(f"Unsupported binary operator: {op}")

        return result_type

    def compile_unary(self, expr: ast.UnaryExpression, ctx: MethodContext) -> JType:
        builder = ctx.builder
        op = expr.operator

        if op == "-" and expr.prefix:
            operand_type = self.compile_expression(expr.operand, ctx)
            if operand_type == INT:
                builder.ineg()
            elif operand_type == LONG:
                builder.lneg()
            elif operand_type == FLOAT:
                builder.fneg()
            elif operand_type == DOUBLE:
                builder.dneg()
            return operand_type

        elif op == "+" and expr.prefix:
            return self.compile_expression(expr.operand, ctx)

        elif op == "!" and expr.prefix:
            # Boolean negation
            true_label = self.new_label("true")
            end_label = self.new_label("end")
            self.compile_expression(expr.operand, ctx)
            builder.ifeq(true_label)
            builder.iconst(0)
            builder.goto(end_label)
            builder.label(true_label)
            builder.iconst(1)
            builder.label(end_label)
            return BOOLEAN

        elif op == "~" and expr.prefix:
            operand_type = self.compile_expression(expr.operand, ctx)
            if operand_type == INT:
                builder.iconst(-1)
                builder.ixor()
            elif operand_type == LONG:
                builder.lconst(-1)
                builder.lxor()
            return operand_type

        elif op == "++" or op == "--":
            if not isinstance(expr.operand, ast.Identifier):
                raise CompileError("Increment/decrement requires variable")
            var = ctx.get_local(expr.operand.name)
            if var.type != INT:
                raise CompileError("Increment/decrement only supported for int")

            if expr.prefix:
                builder.iinc(var.slot, 1 if op == "++" else -1)
                builder.iload(var.slot)
            else:
                builder.iload(var.slot)
                builder.iinc(var.slot, 1 if op == "++" else -1)
            return INT

        else:
            raise CompileError(f"Unsupported unary operator: {op}")

    def compile_assignment(self, expr: ast.Assignment, ctx: MethodContext) -> JType:
        builder = ctx.builder

        if not isinstance(expr.target, ast.Identifier):
            raise CompileError("Only simple variable assignment supported")

        var = ctx.get_local(expr.target.name)

        if expr.operator == "=":
            self.compile_expression(expr.value, ctx)
        else:
            # Compound assignment: +=, -=, etc.
            self.load_local(var, builder)
            self.compile_expression(expr.value, ctx)

            base_op = expr.operator[:-1]
            if var.type == INT:
                if base_op == "+":
                    builder.iadd()
                elif base_op == "-":
                    builder.isub()
                elif base_op == "*":
                    builder.imul()
                elif base_op == "/":
                    builder.idiv()
                elif base_op == "%":
                    builder.irem()
                elif base_op == "&":
                    builder.iand()
                elif base_op == "|":
                    builder.ior()
                elif base_op == "^":
                    builder.ixor()
                elif base_op == "<<":
                    builder.ishl()
                elif base_op == ">>":
                    builder.ishr()
                elif base_op == ">>>":
                    builder.iushr()

        # Duplicate value for expression result, then store
        builder.dup()
        self.store_local(var, builder)
        return var.type

    def compile_method_call(self, expr: ast.MethodInvocation, ctx: MethodContext) -> JType:
        builder = ctx.builder

        # Check for System.out.println/print
        is_system_out = False
        if isinstance(expr.target, ast.FieldAccess):
            if (isinstance(expr.target.target, ast.Identifier) and
                    expr.target.target.name == "System" and
                    expr.target.field == "out"):
                is_system_out = True
        elif isinstance(expr.target, ast.QualifiedName):
            if expr.target.parts == ("System", "out"):
                is_system_out = True

        if is_system_out:
            if expr.method == "println":
                builder.getstatic("java/lang/System", "out", "Ljava/io/PrintStream;")
                if expr.arguments:
                    arg_type = self.compile_expression(expr.arguments[0], ctx)
                    if arg_type == INT:
                        builder.invokevirtual("java/io/PrintStream", "println", "(I)V", 1, 0)
                    elif arg_type == LONG:
                        builder.invokevirtual("java/io/PrintStream", "println", "(J)V", 2, 0)
                    elif arg_type == FLOAT:
                        builder.invokevirtual("java/io/PrintStream", "println", "(F)V", 1, 0)
                    elif arg_type == DOUBLE:
                        builder.invokevirtual("java/io/PrintStream", "println", "(D)V", 2, 0)
                    elif arg_type == BOOLEAN:
                        builder.invokevirtual("java/io/PrintStream", "println", "(Z)V", 1, 0)
                    elif arg_type == STRING:
                        builder.invokevirtual("java/io/PrintStream", "println",
                                              "(Ljava/lang/String;)V", 1, 0)
                    else:
                        builder.invokevirtual("java/io/PrintStream", "println",
                                              "(Ljava/lang/Object;)V", 1, 0)
                else:
                    builder.invokevirtual("java/io/PrintStream", "println", "()V", 0, 0)
                return VOID

            elif expr.method == "print":
                builder.getstatic("java/lang/System", "out", "Ljava/io/PrintStream;")
                if expr.arguments:
                    arg_type = self.compile_expression(expr.arguments[0], ctx)
                    if arg_type == INT:
                        builder.invokevirtual("java/io/PrintStream", "print", "(I)V", 1, 0)
                    elif arg_type == STRING:
                        builder.invokevirtual("java/io/PrintStream", "print",
                                              "(Ljava/lang/String;)V", 1, 0)
                return VOID

        raise CompileError(f"Unsupported method call: {expr.method}")

    def compile_ternary(self, expr: ast.ConditionalExpression, ctx: MethodContext) -> JType:
        builder = ctx.builder
        else_label = self.new_label("else")
        end_label = self.new_label("end")

        self.compile_condition(expr.condition, ctx, else_label, False)
        then_type = self.compile_expression(expr.then_expr, ctx)
        builder.goto(end_label)
        builder.label(else_label)
        else_type = self.compile_expression(expr.else_expr, ctx)
        builder.label(end_label)

        return then_type  # Simplified - should compute common type

    def compile_cast(self, expr: ast.CastExpression, ctx: MethodContext) -> JType:
        builder = ctx.builder
        source_type = self.compile_expression(expr.expression, ctx)
        target_type = self.resolve_type(expr.type)

        # Numeric conversions
        if source_type == INT:
            if target_type == LONG:
                builder.i2l()
            elif target_type == FLOAT:
                builder.i2f()
            elif target_type == DOUBLE:
                builder.i2d()
            elif target_type == BYTE:
                builder._emit(0x91)  # i2b
            elif target_type == CHAR:
                builder._emit(0x92)  # i2c
            elif target_type == SHORT:
                builder._emit(0x93)  # i2s
        elif source_type == LONG:
            if target_type == INT:
                builder.l2i()
            elif target_type == FLOAT:
                builder.l2f()
            elif target_type == DOUBLE:
                builder.l2d()
        elif source_type == FLOAT:
            if target_type == INT:
                builder.f2i()
            elif target_type == LONG:
                builder.f2l()
            elif target_type == DOUBLE:
                builder.f2d()
        elif source_type == DOUBLE:
            if target_type == INT:
                builder.d2i()
            elif target_type == LONG:
                builder.d2l()
            elif target_type == FLOAT:
                builder.d2f()

        return target_type

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

    def resolve_type(self, t: ast.Type) -> JType:
        """Resolve an AST type to a JType."""
        if isinstance(t, ast.PrimitiveType):
            if t.name in PRIMITIVE_TYPES:
                return PRIMITIVE_TYPES[t.name]
            raise CompileError(f"Unknown primitive type: {t.name}")

        elif isinstance(t, ast.ClassType):
            # Handle void (may come through as ClassType in some cases)
            if t.name == "void":
                return VOID
            # Handle some common types
            if t.name == "String":
                return STRING
            elif t.name == "Object":
                return OBJECT
            return ClassJType(t.name)

        elif isinstance(t, ast.ArrayType):
            elem = self.resolve_type(t.element_type)
            return ArrayJType(elem, t.dimensions)

        else:
            raise CompileError(f"Unsupported type: {type(t).__name__}")


def compile_file(source_path: str, output_dir: str = "."):
    """Compile a Java source file to class file(s)."""
    from .parser import Java8Parser
    from pathlib import Path

    parser = Java8Parser()
    unit = parser.parse_file(source_path)

    codegen = CodeGenerator()
    class_files = codegen.compile(unit)

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    for name, bytecode in class_files.items():
        class_path = output_path / f"{name}.class"
        with open(class_path, "wb") as f:
            f.write(bytecode)
        print(f"Wrote {class_path}")

    return class_files
