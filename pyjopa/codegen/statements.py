"""
Statement compilation for the bytecode generator.
"""

from typing import Optional
from .. import ast
from ..types import (
    JType, ClassJType, ArrayJType,
    VOID, BOOLEAN, INT, LONG, FLOAT, DOUBLE, STRING,
)
from ..classfile import BytecodeBuilder, ExceptionTableEntry
from .types import CompileError, MethodContext, LocalVariable


class StatementCompilerMixin:
    """Mixin providing statement compilation."""
    
    # These methods are expected from other mixins/base
    class_name: str
    class_file: object
    new_label: callable
    compile_expression: callable
    _resolve_class_name: callable
    load_local: callable
    store_local: callable
    resolve_type: callable
    
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
                    # Handle array initializer: int[] arr = {1, 2, 3}
                    if isinstance(decl.initializer, ast.ArrayInitializer) and isinstance(jtype, ArrayJType):
                        self._compile_array_initializer(decl.initializer, jtype, ctx)
                    else:
                        expr_type = self.compile_expression(decl.initializer, ctx)
                        self.emit_conversion(expr_type, jtype, builder)
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
                expr_type = self.compile_expression(stmt.expression, ctx)
                # Apply conversion if needed (checkcast for generics, boxing/unboxing)
                self.emit_conversion(expr_type, ctx.return_type, builder)
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
            ctx.push_loop(end_label, loop_label)
            self.compile_statement(stmt.body, ctx)
            ctx.pop_loop()
            builder.goto(loop_label)
            builder.label(end_label)

        elif isinstance(stmt, ast.DoWhileStatement):
            loop_label = self.new_label("do")
            end_label = self.new_label("enddo")

            builder.label(loop_label)
            ctx.push_loop(end_label, loop_label)
            self.compile_statement(stmt.body, ctx)
            ctx.pop_loop()
            self.compile_condition(stmt.condition, ctx, loop_label, True)
            builder.label(end_label)

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

            # Body (continue goes to update_label, break goes to end_label)
            ctx.push_loop(end_label, update_label)
            self.compile_statement(stmt.body, ctx)
            ctx.pop_loop()

            builder.label(update_label)

            # Update
            for expr in stmt.update:
                expr_type = self.compile_expression(expr, ctx)
                if expr_type != VOID:
                    builder.pop()

            builder.goto(loop_label)
            builder.label(end_label)

        elif isinstance(stmt, ast.EnhancedForStatement):
            # for (T x : arr) { body }
            # becomes:
            # T[] $arr = arr;
            # int $len = $arr.length;
            # for (int $i = 0; $i < $len; $i++) { T x = $arr[$i]; body }
            loop_label = self.new_label("foreach")
            end_label = self.new_label("endforeach")
            update_label = self.new_label("foreach_update")

            # Compile the iterable and get its type
            iterable_type = self.compile_expression(stmt.iterable, ctx)

            if not isinstance(iterable_type, ArrayJType):
                raise CompileError(f"Enhanced for loop requires array type, got: {iterable_type}")

            elem_type = iterable_type.element_type

            # Store array reference in temp local
            arr_var = ctx.add_local("$arr", iterable_type)
            self.store_local(arr_var, builder)

            # Get length and store in temp local
            self.load_local(arr_var, builder)
            builder.arraylength()
            len_var = ctx.add_local("$len", INT)
            self.store_local(len_var, builder)

            # Initialize index to 0
            builder.iconst(0)
            idx_var = ctx.add_local("$i", INT)
            self.store_local(idx_var, builder)

            # Loop start
            builder.label(loop_label)

            # Condition: $i < $len
            self.load_local(idx_var, builder)
            self.load_local(len_var, builder)
            builder.if_icmpge(end_label)

            # T x = $arr[$i]
            elem_var_type = self.resolve_type(stmt.type)
            elem_var = ctx.add_local(stmt.name, elem_var_type)
            self.load_local(arr_var, builder)
            self.load_local(idx_var, builder)
            self._emit_array_load(elem_type, builder)
            self.store_local(elem_var, builder)

            # Body
            ctx.push_loop(end_label, update_label)
            self.compile_statement(stmt.body, ctx)
            ctx.pop_loop()

            # $i++
            builder.label(update_label)
            builder.iinc(idx_var.slot, 1)
            builder.goto(loop_label)

            builder.label(end_label)

        elif isinstance(stmt, ast.SwitchStatement):
            self._compile_switch(stmt, ctx)

        elif isinstance(stmt, ast.BreakStatement):
            builder.goto(ctx.get_break_label(stmt.label))

        elif isinstance(stmt, ast.ContinueStatement):
            builder.goto(ctx.get_continue_label(stmt.label))

        elif isinstance(stmt, ast.LabeledStatement):
            # Determine what kind of statement is labeled
            inner = stmt.statement

            # Check if the labeled statement is a loop
            is_loop = isinstance(inner, (ast.WhileStatement, ast.DoWhileStatement, ast.ForStatement, ast.EnhancedForStatement))

            if is_loop:
                # For loops, we need to track both break and continue labels
                # We'll compile the loop and register the label with its labels
                # This requires modifying how we compile loops to allow label registration

                if isinstance(inner, ast.WhileStatement):
                    loop_label = self.new_label("while")
                    end_label = self.new_label("endwhile")

                    ctx.register_label(stmt.label, end_label, loop_label)

                    builder.label(loop_label)
                    self.compile_condition(inner.condition, ctx, end_label, False)
                    ctx.push_loop(end_label, loop_label)
                    self.compile_statement(inner.body, ctx)
                    ctx.pop_loop()
                    builder.goto(loop_label)
                    builder.label(end_label)

                    ctx.unregister_label(stmt.label)

                elif isinstance(inner, ast.DoWhileStatement):
                    loop_label = self.new_label("do")
                    end_label = self.new_label("enddo")

                    ctx.register_label(stmt.label, end_label, loop_label)

                    builder.label(loop_label)
                    ctx.push_loop(end_label, loop_label)
                    self.compile_statement(inner.body, ctx)
                    ctx.pop_loop()
                    self.compile_condition(inner.condition, ctx, loop_label, True)
                    builder.label(end_label)

                    ctx.unregister_label(stmt.label)

                elif isinstance(inner, ast.ForStatement):
                    loop_label = self.new_label("for")
                    end_label = self.new_label("endfor")
                    update_label = self.new_label("update")

                    ctx.register_label(stmt.label, end_label, update_label)

                    # Init
                    if inner.init:
                        if isinstance(inner.init, ast.LocalVariableDeclaration):
                            self.compile_statement(inner.init, ctx)
                        else:
                            for expr in inner.init:
                                expr_type = self.compile_expression(expr, ctx)
                                if expr_type != VOID:
                                    builder.pop()

                    builder.label(loop_label)

                    # Condition
                    if inner.condition:
                        self.compile_condition(inner.condition, ctx, end_label, False)

                    # Body
                    ctx.push_loop(end_label, update_label)
                    self.compile_statement(inner.body, ctx)
                    ctx.pop_loop()

                    builder.label(update_label)

                    # Update
                    if inner.update:
                        for expr in inner.update:
                            expr_type = self.compile_expression(expr, ctx)
                            if expr_type != VOID:
                                builder.pop()

                    builder.goto(loop_label)
                    builder.label(end_label)

                    ctx.unregister_label(stmt.label)

                elif isinstance(inner, ast.EnhancedForStatement):
                    loop_label = self.new_label("foreach")
                    end_label = self.new_label("endforeach")
                    update_label = self.new_label("update")

                    ctx.register_label(stmt.label, end_label, update_label)

                    # Compile the iterable expression
                    arr_type = self.compile_expression(inner.iterable, ctx)
                    if not isinstance(arr_type, ArrayJType):
                        raise CompileError(f"Enhanced for requires array type, got {arr_type}")
                    elem_type = arr_type.element_type

                    # Store array in temp
                    arr_var = ctx.add_local(f"$arr_{self.new_label()}", arr_type)
                    self.store_local(arr_var, builder)

                    # Index variable: int $i = 0
                    idx_var = ctx.add_local(f"$i_{self.new_label()}", INT)
                    builder.iconst(0)
                    self.store_local(idx_var, builder)

                    # Loop: while ($i < $arr.length)
                    builder.label(loop_label)
                    self.load_local(idx_var, builder)
                    self.load_local(arr_var, builder)
                    builder.arraylength()
                    builder.if_icmpge(end_label)

                    # T x = $arr[$i]
                    elem_var_type = self.resolve_type(inner.type)
                    elem_var = ctx.add_local(inner.name, elem_var_type)
                    self.load_local(arr_var, builder)
                    self.load_local(idx_var, builder)
                    self._emit_array_load(elem_type, builder)
                    self.store_local(elem_var, builder)

                    # Body
                    ctx.push_loop(end_label, update_label)
                    self.compile_statement(inner.body, ctx)
                    ctx.pop_loop()

                    # $i++
                    builder.label(update_label)
                    builder.iinc(idx_var.slot, 1)
                    builder.goto(loop_label)

                    builder.label(end_label)

                    ctx.unregister_label(stmt.label)
            else:
                # For non-loop statements, only break is allowed (continue is not)
                end_label = self.new_label("endlabel")
                ctx.register_label(stmt.label, end_label, None)
                self.compile_statement(inner, ctx)
                builder.label(end_label)
                ctx.unregister_label(stmt.label)

        elif isinstance(stmt, ast.TryStatement):
            self._compile_try(stmt, ctx)

        elif isinstance(stmt, ast.ThrowStatement):
            self.compile_expression(stmt.expression, ctx)
            builder.athrow()

        elif isinstance(stmt, ast.EmptyStatement):
            pass

        else:
            raise CompileError(f"Unsupported statement type: {type(stmt).__name__}")

    def _compile_switch(self, stmt: ast.SwitchStatement, ctx: MethodContext):
        """Compile a switch statement."""
        builder = ctx.builder
        end_label = self.new_label("endswitch")

        # Compile the switch expression and get its type
        switch_type = self.compile_expression(stmt.expression, ctx)

        # Check if this is a String switch (Java 7 feature)
        if switch_type == STRING:
            self._compile_string_switch(stmt, ctx, end_label)
            return

        # Original integer switch logic
        # Collect case values and labels
        cases: list[tuple[int, str]] = []
        default_label = end_label  # Default to end if no default case
        case_labels: list[str] = []

        for case in stmt.cases:
            case_label = self.new_label("case")
            case_labels.append(case_label)

            for label in case.labels:
                if label is None:
                    # Default case
                    default_label = case_label
                else:
                    # Get the constant value
                    if isinstance(label, ast.Literal) and label.kind == "int":
                        value = self.parse_int_literal(label.value)
                        cases.append((value, case_label))
                    else:
                        raise CompileError(f"Switch case label must be an integer constant: {label}")

        # Emit lookupswitch
        builder.lookupswitch(default_label, cases)

        # Set switch break label
        old_switch_break = ctx.switch_break_label
        ctx.switch_break_label = end_label

        # Emit case bodies
        for i, case in enumerate(stmt.cases):
            builder.label(case_labels[i])
            for stmt_in_case in case.statements:
                self.compile_statement(stmt_in_case, ctx)

        # Restore switch break label
        ctx.switch_break_label = old_switch_break

        builder.label(end_label)

    def _compile_string_switch(self, stmt: ast.SwitchStatement, ctx: MethodContext, end_label: str):
        """Compile a switch on String using if-else chains with String.equals()."""
        builder = ctx.builder

        # Store the switch expression in a temporary variable
        temp_var = ctx.add_local(f"$switch_temp{id(stmt)}", STRING)
        self.store_local(temp_var, builder)

        # Set switch break label
        old_switch_break = ctx.switch_break_label
        ctx.switch_break_label = end_label

        # Pre-create all case body labels
        case_body_labels = [self.new_label(f"case{i}_body") for i in range(len(stmt.cases))]

        # Find default case index
        default_case_index = None
        for i, case in enumerate(stmt.cases):
            if any(label is None for label in case.labels):
                default_case_index = i
                break

        # Generate if-else chain for each case
        for i, case in enumerate(stmt.cases):
            # For each non-default label in this case
            for label in case.labels:
                if label is not None:
                    # Load the temp variable
                    self.load_local(temp_var, builder)

                    # Push the string literal
                    if isinstance(label, ast.Literal) and label.kind == "string":
                        string_value = self.parse_string_literal(label.value)
                        builder.ldc_string(string_value)
                    else:
                        raise CompileError(f"Switch case label must be a string literal: {label}")

                    # Call String.equals()
                    builder.invokevirtual("java/lang/String", "equals", "(Ljava/lang/Object;)Z", 1, 1)

                    # If true, jump to case body
                    builder.ifne(case_body_labels[i])

        # After all case comparisons, handle default or jump to end
        if default_case_index is not None:
            builder.goto(case_body_labels[default_case_index])
        else:
            builder.goto(end_label)

        # Emit case bodies
        for i, case in enumerate(stmt.cases):
            builder.label(case_body_labels[i])
            for stmt_in_case in case.statements:
                self.compile_statement(stmt_in_case, ctx)

        # Restore switch break label
        ctx.switch_break_label = old_switch_break

        builder.label(end_label)

    def _compile_try(self, stmt: ast.TryStatement, ctx: MethodContext):
        """Compile a try-catch-finally statement."""
        builder = ctx.builder

        try_start = self.new_label("try_start")
        try_end = self.new_label("try_end")
        end_label = self.new_label("try_done")

        # Labels for catch handlers
        catch_labels = []
        for catch in stmt.catches:
            catch_labels.append(self.new_label("catch"))

        # Label for finally (if present)
        finally_label = None
        if stmt.finally_block:
            finally_label = self.new_label("finally")

        # Compile try block
        builder.label(try_start)
        self.compile_block(stmt.body, ctx)
        builder.label(try_end)

        # If there's a finally block, execute it before going to end
        if stmt.finally_block:
            self.compile_block(stmt.finally_block, ctx)

        builder.goto(end_label)

        # Compile catch handlers
        for i, catch in enumerate(stmt.catches):
            builder.label(catch_labels[i])

            # At handler entry, exception reference is on stack
            # Store it in local variable
            exc_type = self.resolve_type(catch.types[0])  # For now, only handle single type
            exc_var = ctx.add_local(catch.name, exc_type)

            # Exception is pushed by JVM when handler is entered
            builder._push()  # Account for exception on stack
            self.store_local(exc_var, builder)

            # Compile catch body
            self.compile_block(catch.body, ctx)

            # If there's a finally block, execute it
            if stmt.finally_block:
                self.compile_block(stmt.finally_block, ctx)

            builder.goto(end_label)

            # Register exception handlers for this catch
            for catch_type in catch.types:
                exc_class = self._resolve_class_name(catch_type.name if isinstance(catch_type, ast.ClassType) else str(catch_type))
                catch_type_idx = builder.cp.add_class(exc_class)
                builder.add_exception_handler(try_start, try_end, catch_labels[i], catch_type_idx)

        # Compile finally handler (catches any exception)
        if stmt.finally_block:
            finally_exception_handler = self.new_label("finally_handler")
            builder.label(finally_exception_handler)

            # Store exception in temp var
            exc_slot = ctx.next_slot
            ctx.next_slot += 1
            builder.max_locals = max(builder.max_locals, ctx.next_slot)
            builder._push()  # Exception is on stack
            builder.astore(exc_slot)

            # Execute finally block
            self.compile_block(stmt.finally_block, ctx)

            # Re-throw the exception
            builder.aload(exc_slot)
            builder.athrow()

            # Register catch-all handler (catch_type=0)
            builder.add_exception_handler(try_start, try_end, finally_exception_handler, 0)

            # Also need to handle exceptions in catch blocks if there are any
            for i, catch_label in enumerate(catch_labels):
                # Get the end of catch block (start of next catch or finally_exception_handler)
                if i + 1 < len(catch_labels):
                    catch_end = catch_labels[i + 1]
                else:
                    catch_end = finally_exception_handler
                builder.add_exception_handler(catch_labels[i], catch_end, finally_exception_handler, 0)

        builder.label(end_label)

    def compile_condition(self, expr: ast.Expression, ctx: MethodContext,
                          target: str, jump_if_true: bool):
        """Compile a boolean expression as a condition for branching."""
        builder = ctx.builder

        if isinstance(expr, ast.BinaryExpression):
            op = expr.operator
            if op in ("==", "!=", "<", ">=", ">", "<="):
                # Check for null comparison
                is_left_null = isinstance(expr.left, ast.Literal) and expr.left.kind == "null"
                is_right_null = isinstance(expr.right, ast.Literal) and expr.right.kind == "null"

                if is_right_null and op in ("==", "!="):
                    # expr == null or expr != null
                    self.compile_expression(expr.left, ctx)
                    if jump_if_true:
                        if op == "==":
                            builder.ifnull(target)
                        else:
                            builder.ifnonnull(target)
                    else:
                        if op == "==":
                            builder.ifnonnull(target)
                        else:
                            builder.ifnull(target)
                    return

                if is_left_null and op in ("==", "!="):
                    # null == expr or null != expr
                    self.compile_expression(expr.right, ctx)
                    if jump_if_true:
                        if op == "==":
                            builder.ifnull(target)
                        else:
                            builder.ifnonnull(target)
                    else:
                        if op == "==":
                            builder.ifnonnull(target)
                        else:
                            builder.ifnull(target)
                    return

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

                # Float comparison
                if left_type == FLOAT or right_type == FLOAT:
                    builder.fcmpg()
                    if jump_if_true:
                        if op == "==":
                            builder.ifeq(target)
                        elif op == "!=":
                            builder.ifne(target)
                        elif op == "<":
                            builder.iflt(target)
                        elif op == ">=":
                            builder.ifge(target)
                        elif op == ">":
                            builder.ifgt(target)
                        elif op == "<=":
                            builder.ifle(target)
                    else:
                        if op == "==":
                            builder.ifne(target)
                        elif op == "!=":
                            builder.ifeq(target)
                        elif op == "<":
                            builder.ifge(target)
                        elif op == ">=":
                            builder.iflt(target)
                        elif op == ">":
                            builder.ifle(target)
                        elif op == "<=":
                            builder.ifgt(target)
                    return

                # Double comparison
                if left_type == DOUBLE or right_type == DOUBLE:
                    builder.dcmpg()
                    if jump_if_true:
                        if op == "==":
                            builder.ifeq(target)
                        elif op == "!=":
                            builder.ifne(target)
                        elif op == "<":
                            builder.iflt(target)
                        elif op == ">=":
                            builder.ifge(target)
                        elif op == ">":
                            builder.ifgt(target)
                        elif op == "<=":
                            builder.ifle(target)
                    else:
                        if op == "==":
                            builder.ifne(target)
                        elif op == "!=":
                            builder.ifeq(target)
                        elif op == "<":
                            builder.ifge(target)
                        elif op == ">=":
                            builder.iflt(target)
                        elif op == ">":
                            builder.ifle(target)
                        elif op == "<=":
                            builder.ifgt(target)
                    return

                # Reference comparison
                if left_type.is_reference and right_type.is_reference and op in ("==", "!="):
                    if jump_if_true:
                        if op == "==":
                            builder.if_acmpeq(target)
                        else:
                            builder.if_acmpne(target)
                    else:
                        if op == "==":
                            builder.if_acmpne(target)
                        else:
                            builder.if_acmpeq(target)
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

