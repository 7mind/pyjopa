"""
Expression compilation for the bytecode generator.
"""

from typing import Optional
from .. import ast
from ..types import (
    JType, PrimitiveJType, ClassJType, ArrayJType, MethodType,
    VOID, BOOLEAN, BYTE, CHAR, SHORT, INT, LONG, FLOAT, DOUBLE,
    STRING, is_numeric, binary_numeric_promotion,
)
from ..classfile import BytecodeBuilder, AccessFlags
from .types import CompileError, MethodContext, LocalVariable, ResolvedMethod


class ExpressionCompilerMixin:
    """Mixin providing expression compilation."""
    
    # These methods are expected from other mixins/base
    class_name: str
    class_file: object
    new_label: callable
    resolve_type: callable
    _resolve_class_name: callable
    _find_method: callable
    _find_field: callable
    load_local: callable
    store_local: callable
    _emit_newarray: callable
    _emit_array_store: callable
    _emit_array_load: callable
    emit_boxing: callable
    emit_unboxing: callable
    needs_boxing: callable
    needs_unboxing: callable
    emit_conversion: callable
    compile_condition: callable
    _compile_array_initializer: callable
    
    def compile_expression(self, expr: ast.Expression, ctx: MethodContext) -> JType:
        """Compile an expression and return its type."""
        builder = ctx.builder

        if isinstance(expr, ast.Literal):
            return self.compile_literal(expr, ctx)

        elif isinstance(expr, ast.Identifier):
            # Check locals first
            if expr.name in ctx.locals:
                var = ctx.get_local(expr.name)
                self.load_local(var, builder)
                return var.type
            field = self._find_field(self.class_name, expr.name)
            if field:
                if field.is_static:
                    builder.getstatic(field.owner, expr.name, field.descriptor)
                else:
                    builder.aload(0)
                    builder.getfield(field.owner, expr.name, field.descriptor)
                return field.type
            raise CompileError(f"Undefined variable: {expr.name}")

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

        elif isinstance(expr, ast.InstanceOfExpression):
            self.compile_expression(expr.expression, ctx)
            target_type = self.resolve_type(expr.type)
            if isinstance(target_type, ClassJType):
                builder.instanceof_(target_type.internal_name())
            elif isinstance(target_type, ArrayJType):
                builder.instanceof_(target_type.descriptor())
            else:
                raise CompileError(f"Invalid instanceof type: {target_type}")
            return BOOLEAN

        elif isinstance(expr, ast.ThisExpression):
            builder.aload(0)
            return ClassJType(self.class_name)

        elif isinstance(expr, ast.SuperExpression):
            builder.aload(0)
            return ClassJType(getattr(self, "super_class_name", "java/lang/Object"))

        elif isinstance(expr, ast.FieldAccess):
            return self.compile_field_access(expr, ctx)

        elif isinstance(expr, ast.NewInstance):
            return self.compile_new_instance(expr, ctx)

        elif isinstance(expr, ast.QualifiedName):
            return self.compile_qualified_name(expr, ctx)

        elif isinstance(expr, ast.NewArray):
            return self.compile_new_array(expr, ctx)

        elif isinstance(expr, ast.ArrayAccess):
            return self.compile_array_access(expr, ctx)

        elif isinstance(expr, ast.ArrayInitializer):
            raise CompileError("ArrayInitializer must be part of NewArray or variable declaration")

        else:
            raise CompileError(f"Unsupported expression type: {type(expr).__name__}")

    def _estimate_expression_type(self, expr, ctx: MethodContext) -> JType:
        """Estimate the type of an expression without generating code."""
        if isinstance(expr, ast.Literal):
            if expr.kind == "int":
                return INT
            elif expr.kind == "long":
                return LONG
            elif expr.kind == "float":
                return FLOAT
            elif expr.kind == "double":
                return DOUBLE
            elif expr.kind == "boolean":
                return BOOLEAN
            elif expr.kind == "char":
                return CHAR
            elif expr.kind == "string":
                return STRING
            elif expr.kind == "null":
                return ClassJType("java/lang/Object")
        elif isinstance(expr, ast.Identifier):
            if expr.name in ctx.locals:
                return ctx.get_local(expr.name).type
            field = self._find_field(self.class_name, expr.name)
            if field:
                return field.type
            return ClassJType("java/lang/Object")
        elif isinstance(expr, ast.QualifiedName) and expr.parts == ("super",):
            return ClassJType(getattr(self, "super_class_name", "java/lang/Object"))
        elif isinstance(expr, ast.SuperExpression):
            return ClassJType(getattr(self, "super_class_name", "java/lang/Object"))
        elif isinstance(expr, ast.BinaryExpression):
            left_type = self._estimate_expression_type(expr.left, ctx)
            right_type = self._estimate_expression_type(expr.right, ctx)
            if left_type == LONG or right_type == LONG:
                return LONG
            if left_type == DOUBLE or right_type == DOUBLE:
                return DOUBLE
            if left_type == FLOAT or right_type == FLOAT:
                return FLOAT
            return INT
        elif isinstance(expr, ast.UnaryExpression):
            return self._estimate_expression_type(expr.operand, ctx)
        elif isinstance(expr, ast.ParenthesizedExpression):
            return self._estimate_expression_type(expr.expression, ctx)
        return ClassJType("java/lang/Object")

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
        if op == "+" and self._is_string_concat(expr, ctx):
            return self.compile_string_concat(expr, ctx)

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
            elif left_type == FLOAT or right_type == FLOAT:
                builder.fcmpg()
                if op == "==":
                    builder.ifeq(true_label)
                elif op == "!=":
                    builder.ifne(true_label)
                elif op == "<":
                    builder.iflt(true_label)
                elif op == ">=":
                    builder.ifge(true_label)
                elif op == ">":
                    builder.ifgt(true_label)
                elif op == "<=":
                    builder.ifle(true_label)
            elif left_type == DOUBLE or right_type == DOUBLE:
                builder.dcmpg()
                if op == "==":
                    builder.ifeq(true_label)
                elif op == "!=":
                    builder.ifne(true_label)
                elif op == "<":
                    builder.iflt(true_label)
                elif op == ">=":
                    builder.ifge(true_label)
                elif op == ">":
                    builder.ifgt(true_label)
                elif op == "<=":
                    builder.ifle(true_label)

            builder.iconst(0)
            builder.goto(end_label)
            builder.label(true_label)
            builder.iconst(1)
            builder.label(end_label)
            return BOOLEAN
        else:
            raise CompileError(f"Unsupported binary operator: {op}")

        return result_type

    def _is_string_concat(self, expr: ast.BinaryExpression, ctx: MethodContext) -> bool:
        """Check if a binary expression is string concatenation."""
        if expr.operator != "+":
            return False
        left_type = self._estimate_expression_type(expr.left, ctx)
        right_type = self._estimate_expression_type(expr.right, ctx)
        return left_type == STRING or right_type == STRING

    def _collect_concat_parts(self, expr: ast.Expression, parts: list, ctx: MethodContext):
        """Collect all parts of a string concatenation expression."""
        if isinstance(expr, ast.BinaryExpression) and expr.operator == "+":
            left_type = self._estimate_expression_type(expr.left, ctx)
            right_type = self._estimate_expression_type(expr.right, ctx)
            if left_type == STRING or right_type == STRING:
                self._collect_concat_parts(expr.left, parts, ctx)
                self._collect_concat_parts(expr.right, parts, ctx)
                return
        parts.append(expr)

    def compile_string_concat(self, expr: ast.BinaryExpression, ctx: MethodContext) -> JType:
        """Compile string concatenation using StringBuilder."""
        builder = ctx.builder

        # Collect all parts of the concatenation
        parts = []
        self._collect_concat_parts(expr, parts, ctx)

        # Create StringBuilder: new StringBuilder()
        builder.new("java/lang/StringBuilder")
        builder.dup()
        builder.invokespecial("java/lang/StringBuilder", "<init>", "()V", 0, 0)

        # Append each part
        for part in parts:
            part_type = self.compile_expression(part, ctx)

            # Choose the right append method based on type
            if part_type == STRING:
                builder.invokevirtual("java/lang/StringBuilder", "append",
                                      "(Ljava/lang/String;)Ljava/lang/StringBuilder;", 1, 1)
            elif part_type == INT:
                builder.invokevirtual("java/lang/StringBuilder", "append",
                                      "(I)Ljava/lang/StringBuilder;", 1, 1)
            elif part_type == LONG:
                builder.invokevirtual("java/lang/StringBuilder", "append",
                                      "(J)Ljava/lang/StringBuilder;", 2, 1)
            elif part_type == FLOAT:
                builder.invokevirtual("java/lang/StringBuilder", "append",
                                      "(F)Ljava/lang/StringBuilder;", 1, 1)
            elif part_type == DOUBLE:
                builder.invokevirtual("java/lang/StringBuilder", "append",
                                      "(D)Ljava/lang/StringBuilder;", 2, 1)
            elif part_type == BOOLEAN:
                builder.invokevirtual("java/lang/StringBuilder", "append",
                                      "(Z)Ljava/lang/StringBuilder;", 1, 1)
            elif part_type == CHAR:
                builder.invokevirtual("java/lang/StringBuilder", "append",
                                      "(C)Ljava/lang/StringBuilder;", 1, 1)
            else:
                # Reference type - use append(Object)
                builder.invokevirtual("java/lang/StringBuilder", "append",
                                      "(Ljava/lang/Object;)Ljava/lang/StringBuilder;", 1, 1)

        # Call toString()
        builder.invokevirtual("java/lang/StringBuilder", "toString",
                              "()Ljava/lang/String;", 0, 1)

        return STRING

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
            name = expr.operand.name
            delta = 1 if op == "++" else -1

            # Check if it's a local variable
            if name in ctx.locals:
                var = ctx.get_local(name)
                if var.type != INT:
                    raise CompileError("Increment/decrement only supported for int")
                if expr.prefix:
                    builder.iinc(var.slot, delta)
                    builder.iload(var.slot)
                else:
                    builder.iload(var.slot)
                    builder.iinc(var.slot, delta)
                return INT

            # Check if it's a field
            if hasattr(self, '_local_fields') and name in self._local_fields:
                field = self._local_fields[name]
                if field.jtype != INT:
                    raise CompileError("Increment/decrement only supported for int")

                if field.is_static:
                    if expr.prefix:
                        # ++count: load, add 1, dup, store
                        builder.getstatic(self.class_name, field.name, field.descriptor)
                        builder.iconst(delta)
                        builder.iadd()
                        builder.dup()
                        builder.putstatic(self.class_name, field.name, field.descriptor)
                    else:
                        # count++: load, dup, add 1, store
                        builder.getstatic(self.class_name, field.name, field.descriptor)
                        builder.dup()
                        builder.iconst(delta)
                        builder.iadd()
                        builder.putstatic(self.class_name, field.name, field.descriptor)
                else:
                    # Instance field
                    if expr.prefix:
                        builder.aload(0)
                        builder.dup()
                        builder.getfield(self.class_name, field.name, field.descriptor)
                        builder.iconst(delta)
                        builder.iadd()
                        builder.dup_x1()
                        builder.putfield(self.class_name, field.name, field.descriptor)
                    else:
                        builder.aload(0)
                        builder.dup()
                        builder.getfield(self.class_name, field.name, field.descriptor)
                        builder.dup_x1()
                        builder.iconst(delta)
                        builder.iadd()
                        builder.putfield(self.class_name, field.name, field.descriptor)
                return INT

            raise CompileError(f"Undefined variable: {name}")

        else:
            raise CompileError(f"Unsupported unary operator: {op}")

    def compile_assignment(self, expr: ast.Assignment, ctx: MethodContext) -> JType:
        builder = ctx.builder

        # Handle FieldAccess target (this.x = value or obj.field = value)
        if isinstance(expr.target, ast.FieldAccess):
            return self._compile_field_assignment(expr, ctx)

        # Handle QualifiedName target (e.g., this.x = value)
        if isinstance(expr.target, ast.QualifiedName):
            return self._compile_qualified_assignment(expr, ctx)

        # Handle ArrayAccess target (arr[i] = value)
        if isinstance(expr.target, ast.ArrayAccess):
            return self._compile_array_assignment(expr, ctx)

        # Handle simple Identifier target
        if isinstance(expr.target, ast.Identifier):
            name = expr.target.name

            # Check if it's a local variable
            if name in ctx.locals:
                var = ctx.get_local(name)

                if expr.operator == "=":
                    self.compile_expression(expr.value, ctx)
                else:
                    # Compound assignment: +=, -=, etc.
                    self.load_local(var, builder)
                    self.compile_expression(expr.value, ctx)
                    self._compile_compound_op(expr.operator, var.type, builder)

                builder.dup()
                self.store_local(var, builder)
                return var.type

            # Check if it's an instance/static field
            if hasattr(self, '_local_fields') and name in self._local_fields:
                field = self._local_fields[name]

                if field.is_static:
                    if expr.operator != "=":
                        builder.getstatic(self.class_name, field.name, field.descriptor)
                        self.compile_expression(expr.value, ctx)
                        self._compile_compound_op(expr.operator, field.jtype, builder)
                    else:
                        self.compile_expression(expr.value, ctx)
                    builder.dup()
                    builder.putstatic(self.class_name, field.name, field.descriptor)
                else:
                    builder.aload(0)  # load this
                    if expr.operator != "=":
                        builder.dup()
                        builder.getfield(self.class_name, field.name, field.descriptor)
                        self.compile_expression(expr.value, ctx)
                        self._compile_compound_op(expr.operator, field.jtype, builder)
                    else:
                        self.compile_expression(expr.value, ctx)
                    builder.dup_x1()
                    builder.putfield(self.class_name, field.name, field.descriptor)
                return field.jtype

            raise CompileError(f"Undefined variable: {name}")

        raise CompileError(f"Unsupported assignment target: {type(expr.target).__name__}")

    def _compile_field_assignment(self, expr: ast.Assignment, ctx: MethodContext) -> JType:
        """Compile assignment to a field (this.x = value or obj.field = value)."""
        builder = ctx.builder
        fa = expr.target

        # Handle this.field = value
        if isinstance(fa.target, ast.ThisExpression):
            if hasattr(self, '_local_fields') and fa.field in self._local_fields:
                field = self._local_fields[fa.field]
                if field.is_static:
                    if expr.operator != "=":
                        builder.getstatic(self.class_name, field.name, field.descriptor)
                        self.compile_expression(expr.value, ctx)
                        self._compile_compound_op(expr.operator, field.jtype, builder)
                    else:
                        self.compile_expression(expr.value, ctx)
                    builder.dup()
                    builder.putstatic(self.class_name, field.name, field.descriptor)
                else:
                    builder.aload(0)
                    if expr.operator != "=":
                        builder.dup()
                        builder.getfield(self.class_name, field.name, field.descriptor)
                        self.compile_expression(expr.value, ctx)
                        self._compile_compound_op(expr.operator, field.jtype, builder)
                    else:
                        self.compile_expression(expr.value, ctx)
                    builder.dup_x1()
                    builder.putfield(self.class_name, field.name, field.descriptor)
                return field.jtype
            raise CompileError(f"Unknown field: {fa.field}")

        # Handle obj.field = value
        target_type = self.compile_expression(fa.target, ctx)
        if not isinstance(target_type, ClassJType):
            raise CompileError(f"Cannot access field on type: {target_type}")

        field_info = self._find_field(target_type.internal_name(), fa.field)
        if field_info:
            owner, desc, ftype = field_info
            if expr.operator != "=":
                builder.dup()
                builder.getfield(owner, fa.field, desc)
                self.compile_expression(expr.value, ctx)
                self._compile_compound_op(expr.operator, ftype, builder)
            else:
                self.compile_expression(expr.value, ctx)
            builder.dup_x1()
            builder.putfield(owner, fa.field, desc)
            return ftype

        raise CompileError(f"Unknown field: {target_type.internal_name()}.{fa.field}")

    def _compile_array_assignment(self, expr: ast.Assignment, ctx: MethodContext) -> JType:
        """Compile assignment to an array element (arr[i] = value)."""
        builder = ctx.builder
        aa = expr.target

        # Compile array reference
        array_type = self.compile_expression(aa.array, ctx)
        if not isinstance(array_type, ArrayJType):
            raise CompileError(f"Cannot index non-array type: {array_type}")

        elem_type = array_type.element_type

        # Compile index
        self.compile_expression(aa.index, ctx)

        if expr.operator == "=":
            # Simple assignment: arr[i] = value
            self.compile_expression(expr.value, ctx)
        else:
            # Compound assignment: arr[i] += value
            # Stack: arrayref, index
            # Need to dup2 to keep arrayref and index for the store
            builder.dup2()  # arrayref, index, arrayref, index
            self._emit_array_load(elem_type, builder)  # arrayref, index, value
            self.compile_expression(expr.value, ctx)  # arrayref, index, value, rhs
            self._compile_compound_op(expr.operator, elem_type, builder)  # arrayref, index, result

        # Stack: arrayref, index, value
        # dup value under array ref and index for expression result
        if elem_type.size == 2:
            builder.dup2_x2()  # value, arrayref, index, value
        else:
            builder.dup_x2()  # value, arrayref, index, value

        # Store to array
        self._emit_array_store(elem_type, builder)

        return elem_type

    def _compile_qualified_assignment(self, expr: ast.Assignment, ctx: MethodContext) -> JType:
        """Compile assignment to a qualified name (e.g., this.x = value)."""
        builder = ctx.builder
        qn = expr.target

        # Handle this.field = value
        if qn.parts[0] == "this" and len(qn.parts) == 2:
            field_name = qn.parts[1]
            if hasattr(self, '_local_fields') and field_name in self._local_fields:
                field = self._local_fields[field_name]
                if field.is_static:
                    if expr.operator != "=":
                        builder.getstatic(self.class_name, field.name, field.descriptor)
                        self.compile_expression(expr.value, ctx)
                        self._compile_compound_op(expr.operator, field.jtype, builder)
                    else:
                        self.compile_expression(expr.value, ctx)
                    builder.dup()
                    builder.putstatic(self.class_name, field.name, field.descriptor)
                else:
                    builder.aload(0)
                    if expr.operator != "=":
                        builder.dup()
                        builder.getfield(self.class_name, field.name, field.descriptor)
                        self.compile_expression(expr.value, ctx)
                        self._compile_compound_op(expr.operator, field.jtype, builder)
                    else:
                        self.compile_expression(expr.value, ctx)
                    builder.dup_x1()
                    builder.putfield(self.class_name, field.name, field.descriptor)
                return field.jtype
            raise CompileError(f"Unknown field: {field_name}")

        raise CompileError(f"Unsupported qualified name assignment: {qn.parts}")

    def _compile_compound_op(self, operator: str, jtype: JType, builder: BytecodeBuilder):
        """Compile the operation part of a compound assignment."""
        base_op = operator[:-1]
        if jtype == INT:
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

    def compile_method_call(self, expr: ast.MethodInvocation, ctx: MethodContext) -> JType:
        builder = ctx.builder

        # Check for System.out.println/print (hardcoded common case)
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
                    if arg_type in {INT, BYTE, SHORT}:
                        builder.invokevirtual("java/io/PrintStream", "println", "(I)V", 1, 0)
                    elif arg_type == LONG:
                        builder.invokevirtual("java/io/PrintStream", "println", "(J)V", 2, 0)
                    elif arg_type == FLOAT:
                        builder.invokevirtual("java/io/PrintStream", "println", "(F)V", 1, 0)
                    elif arg_type == DOUBLE:
                        builder.invokevirtual("java/io/PrintStream", "println", "(D)V", 2, 0)
                    elif arg_type == BOOLEAN:
                        builder.invokevirtual("java/io/PrintStream", "println", "(Z)V", 1, 0)
                    elif arg_type == CHAR:
                        builder.invokevirtual("java/io/PrintStream", "println", "(C)V", 1, 0)
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
                    if arg_type in {INT, BYTE, SHORT}:
                        builder.invokevirtual("java/io/PrintStream", "print", "(I)V", 1, 0)
                    elif arg_type == CHAR:
                        builder.invokevirtual("java/io/PrintStream", "print", "(C)V", 1, 0)
                    elif arg_type == STRING:
                        builder.invokevirtual("java/io/PrintStream", "print",
                                              "(Ljava/lang/String;)V", 1, 0)
                    else:
                        builder.invokevirtual("java/io/PrintStream", "print",
                                              "(Ljava/lang/Object;)V", 1, 0)
                return VOID

        # Try to resolve using classpath
        return self._compile_general_method_call(expr, ctx)

    def _compile_general_method_call(self, expr: ast.MethodInvocation, ctx: MethodContext) -> JType:
        """Compile a general method call using classpath resolution."""
        builder = ctx.builder

        # Determine the target type (but don't load it yet - need to check if static first)
        target_type = None
        is_static_call = False
        is_super_call = False
        needs_this_load = False  # Will be set if we need to load 'this' later

        if expr.target is None:
            # Method call on this (or static call to same class - need to check later)
            target_type = ClassJType(self.class_name)
            needs_this_load = True  # Tentatively - will skip if method is static
        elif isinstance(expr.target, ast.SuperExpression):
            target_type = ClassJType(getattr(self, "super_class_name", "java/lang/Object"))
            is_super_call = True
            builder.aload(0)
        elif isinstance(expr.target, ast.Identifier):
            # Could be a local variable or a class name
            if expr.target.name in ctx.locals:
                var = ctx.get_local(expr.target.name)
                self.load_local(var, builder)
                target_type = var.type
            else:
                # Assume it's a class name (static call)
                is_static_call = True
                resolved_name = self._resolve_class_name(expr.target.name)
                target_type = ClassJType(resolved_name)
        elif isinstance(expr.target, ast.QualifiedName) and expr.target.parts == ("super",):
            target_type = ClassJType(getattr(self, "super_class_name", "java/lang/Object"))
            is_super_call = True
            builder.aload(0)
        elif isinstance(expr.target, ast.QualifiedName):
            # Could be a local variable (single name) or a class name for static call
            if len(expr.target.parts) == 1:
                first_part = expr.target.parts[0]
                # Check if it's a local variable
                if first_part in ctx.locals:
                    var = ctx.get_local(first_part)
                    self.load_local(var, builder)
                    target_type = var.type
                else:
                    # Assume it's a class name (static call)
                    is_static_call = True
                    resolved_name = self._resolve_class_name(first_part)
                    target_type = ClassJType(resolved_name)
            else:
                # Qualified name like "java.lang.Math" - assume static call
                is_static_call = True
                class_name = "/".join(expr.target.parts)
                target_type = ClassJType(class_name)
        elif isinstance(expr.target, ast.FieldAccess):
            # e.g., obj.field.method()
            target_type = self._compile_field_access_for_call(expr.target, ctx)
        else:
            # Some other expression - compile it
            target_type = self.compile_expression(expr.target, ctx)

        if not isinstance(target_type, ClassJType):
            raise CompileError(f"Cannot call method on type: {target_type}")

        # First, determine argument types without compiling them yet
        # We need to resolve the method first to know if it's static
        class_internal_name = target_type.internal_name()

        # Estimate arg types for method resolution
        # Note: This is a simplified approach - we compile args once after knowing the method
        arg_types_estimate = []
        for arg in expr.arguments:
            arg_type = self._estimate_expression_type(arg, ctx)
            arg_types_estimate.append(arg_type)

        # Try to resolve the method
        resolved = self._find_method(class_internal_name, expr.method, arg_types_estimate)

        if not resolved:
            raise CompileError(f"Cannot resolve method: {class_internal_name}.{expr.method}")

        # Now we know if the method is static - load 'this' if needed
        if needs_this_load and not resolved.is_static:
            builder.aload(0)  # load 'this'

        # Compile arguments
        if resolved.is_varargs and resolved.param_types:
            # Handle varargs - package trailing arguments into an array
            num_regular = len(resolved.param_types) - 1
            varargs_type = resolved.param_types[-1]  # This is an ArrayJType

            # Compile regular (non-varargs) arguments
            for i in range(num_regular):
                self.compile_expression(expr.arguments[i], ctx)

            # Package remaining arguments into an array
            varargs_args = expr.arguments[num_regular:]
            varargs_count = len(varargs_args)

            # Get the element type
            if isinstance(varargs_type, ArrayJType):
                elem_type = varargs_type.element_type
            else:
                raise CompileError(f"Varargs parameter must be array type, got: {varargs_type}")

            # Create the array
            builder.iconst(varargs_count)
            self._emit_newarray(elem_type, builder)

            # Fill the array
            for i, arg in enumerate(varargs_args):
                builder.dup()  # dup array ref
                builder.iconst(i)  # push index
                self.compile_expression(arg, ctx)  # push value
                self._emit_array_store(elem_type, builder)
        else:
            # Normal argument compilation
            for arg in expr.arguments:
                self.compile_expression(arg, ctx)

        # Calculate stack effect
        args_slots = sum(t.size for t in resolved.param_types)
        return_slots = 0 if resolved.return_type == VOID else resolved.return_type.size

        # Emit the call
        if is_static_call or resolved.is_static:
            builder.invokestatic(resolved.owner, resolved.name, resolved.descriptor, args_slots, return_slots)
        elif resolved.is_interface:
            builder.invokeinterface(resolved.owner, resolved.name, resolved.descriptor,
                                    args_slots + 1, return_slots)
        elif is_super_call:
            builder.invokespecial(resolved.owner, resolved.name, resolved.descriptor,
                                  args_slots + 1, return_slots)
        else:
            builder.invokevirtual(resolved.owner, resolved.name, resolved.descriptor,
                                  args_slots + 1, return_slots)

        return resolved.return_type

    def _compile_field_access_for_call(self, fa: ast.FieldAccess, ctx: MethodContext) -> JType:
        """Compile a field access and return its type (for method calls)."""
        builder = ctx.builder

        # First compile the target
        if isinstance(fa.target, ast.Identifier):
            if fa.target.name in ctx.locals:
                var = ctx.get_local(fa.target.name)
                self.load_local(var, builder)
                target_type = var.type
            else:
                # Class name - static field access
                target_type = ClassJType(fa.target.name)
                # Look up the field
                field_info = self._find_field(target_type.internal_name(), fa.field)
                if field_info:
                    if not field_info.is_static:
                        raise CompileError(f"Field {fa.field} on {target_type.internal_name()} is not static")
                    builder.getstatic(field_info.owner, fa.field, field_info.descriptor)
                    return field_info.type
                raise CompileError(f"Cannot find field: {fa.target.name}.{fa.field}")
        else:
            target_type = self.compile_expression(fa.target, ctx)

        if not isinstance(target_type, ClassJType):
            raise CompileError(f"Cannot access field on type: {target_type}")

        # Look up the field in the class
        field_info = self._find_field(target_type.internal_name(), fa.field)
        if field_info:
            if field_info.is_static:
                raise CompileError("Static field access through instance is not supported")
            builder.getfield(field_info.owner, fa.field, field_info.descriptor)
            return field_info.type

        raise CompileError(f"Cannot find field: {target_type.internal_name()}.{fa.field}")

    def compile_qualified_name(self, expr: ast.QualifiedName, ctx: MethodContext) -> JType:
        """Compile a qualified name expression (e.g., this.x or obj.field)."""
        builder = ctx.builder

        # Handle this.field
        if expr.parts[0] == "this" and len(expr.parts) == 2:
            field_name = expr.parts[1]
            field = self._find_field(self.class_name, field_name)
            if field:
                if field.is_static:
                    builder.getstatic(field.owner, field_name, field.descriptor)
                else:
                    builder.aload(0)
                    builder.getfield(field.owner, field_name, field.descriptor)
                return field.type
            raise CompileError(f"Unknown field: {field_name}")

        # Check if first part is a local variable (e.g., obj.field)
        if expr.parts[0] in ctx.locals:
            var = ctx.get_local(expr.parts[0])
            self.load_local(var, builder)
            current_type = var.type

            # Follow chain of field accesses
            for part in expr.parts[1:]:
                # Handle array.length
                if isinstance(current_type, ArrayJType):
                    if part == "length":
                        builder.arraylength()
                        current_type = INT
                    else:
                        raise CompileError(f"Arrays only have 'length' field, not: {part}")
                elif isinstance(current_type, ClassJType):
                    field_info = self._find_field(current_type.internal_name(), part)
                    if not field_info:
                        raise CompileError(f"Unknown field: {current_type.internal_name()}.{part}")
                    if field_info.is_static:
                        raise CompileError("Static field access through instance is not supported")
                    builder.getfield(field_info.owner, part, field_info.descriptor)
                    current_type = field_info.type
                else:
                    raise CompileError(f"Cannot access field on type: {current_type}")

            return current_type

        # For other qualified names, they might be class names or package paths
        # For now, just return a ClassJType for the full path
        full_name = "/".join(expr.parts)
        return ClassJType(full_name)

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

    def compile_field_access(self, expr: ast.FieldAccess, ctx: MethodContext) -> JType:
        """Compile a field access expression (obj.field or this.field)."""
        builder = ctx.builder

        # Handle this.field
        if isinstance(expr.target, ast.ThisExpression):
            field = self._find_field(self.class_name, expr.field)
            if field:
                if field.is_static:
                    builder.getstatic(field.owner, expr.field, field.descriptor)
                else:
                    builder.aload(0)
                    builder.getfield(field.owner, expr.field, field.descriptor)
                return field.type
            raise CompileError(f"Unknown field: {expr.field}")

        if isinstance(expr.target, ast.SuperExpression):
            field = self._find_field(getattr(self, "super_class_name", self.class_name), expr.field)
            if field:
                if field.is_static:
                    raise CompileError("Accessing static fields through super is not supported")
                builder.aload(0)
                builder.getfield(field.owner, expr.field, field.descriptor)
                return field.type
            raise CompileError(f"Unknown field: {expr.field}")

        # Compile the target expression
        target_type = self.compile_expression(expr.target, ctx)

        # Handle array.length
        if isinstance(target_type, ArrayJType):
            if expr.field == "length":
                builder.arraylength()
                return INT
            raise CompileError(f"Arrays only have 'length' field, not: {expr.field}")

        if not isinstance(target_type, ClassJType):
            raise CompileError(f"Cannot access field on type: {target_type}")

        # Look up the field
        field_info = self._find_field(target_type.internal_name(), expr.field)
        if field_info:
            if field_info.is_static:
                raise CompileError("Static field access through instance is not supported")
            builder.getfield(field_info.owner, expr.field, field_info.descriptor)
            return field_info.type

        raise CompileError(f"Unknown field: {target_type.internal_name()}.{expr.field}")

    def compile_new_instance(self, expr: ast.NewInstance, ctx: MethodContext) -> JType:
        """Compile a new instance creation expression."""
        builder = ctx.builder

        type_name = self._resolve_class_name(expr.type.name) if isinstance(expr.type, ast.ClassType) else str(expr.type)
        # Prevent instantiation of abstract classes or interfaces when info is available
        cls_info = self._lookup_class(type_name) if hasattr(self, "_lookup_class") else None
        if cls_info:
            if cls_info.access_flags & AccessFlags.INTERFACE:
                raise CompileError(f"Cannot instantiate interface {type_name}")
            if cls_info.access_flags & AccessFlags.ABSTRACT:
                raise CompileError(f"Cannot instantiate abstract class {type_name}")
        elif type_name == self.class_name and self.class_file:
            if self.class_file.access_flags & AccessFlags.ABSTRACT:
                raise CompileError(f"Cannot instantiate abstract class {type_name}")

        # new ClassName
        builder.new(type_name)
        builder.dup()

        # Compile constructor arguments
        arg_types = []
        for arg in expr.arguments:
            arg_type = self.compile_expression(arg, ctx)
            arg_types.append(arg_type)

        # Build descriptor for constructor
        desc = "(" + "".join(t.descriptor() for t in arg_types) + ")V"

        # Invoke constructor
        args_slots = sum(t.size for t in arg_types)
        builder.invokespecial(type_name, "<init>", desc, args_slots, 0)

        return ClassJType(type_name)
