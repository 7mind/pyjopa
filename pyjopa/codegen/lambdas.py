"""
Lambda expression compilation for Java 8.

Lambdas are desugared into:
1. A synthetic method containing the lambda body
2. An invokedynamic instruction that calls LambdaMetafactory.metafactory
3. The LambdaMetafactory creates an instance of the functional interface at runtime
"""

from .. import ast
from ..types import JType, ClassJType, VOID
from ..classfile import BytecodeBuilder, AccessFlags
from .types import CompileError, MethodContext


class LambdaCompilerMixin:
    """Mixin providing lambda compilation operations."""

    # Expected from other mixins/base
    compile_expression: callable
    compile_statement: callable
    resolve_type: callable
    class_name: str
    class_file: any  # ClassFile instance
    _lambda_counter: int  # Initialized in generator

    def compile_lambda(self, expr: ast.LambdaExpression, ctx: MethodContext) -> JType:
        """Compile a lambda expression.

        Lambda desugaring process:
        1. Create synthetic method: lambda$N(captured_vars..., params...) -> return_type
        2. Determine functional interface type
        3. Create bootstrap method entry for LambdaMetafactory
        4. Emit invokedynamic instruction
        """
        builder = ctx.builder

        # Generate unique name for synthetic lambda method
        lambda_name = f"lambda${self._lambda_counter}"
        self._lambda_counter += 1

        # Analyze lambda to determine:
        # - Parameter types
        # - Return type
        # - Captured variables
        # - Functional interface

        lambda_info = self._analyze_lambda(expr, ctx)

        # Create synthetic method for lambda body
        self._create_lambda_method(
            lambda_name,
            expr,
            lambda_info,
            ctx
        )

        # Load captured variables onto stack (if any)
        for captured_var in lambda_info['captured_vars']:
            var_slot = ctx.locals.get(captured_var)
            if var_slot is None:
                raise CompileError(f"Cannot capture variable '{captured_var}' - not found in scope")
            builder.aload(var_slot)

        # Create bootstrap method entry
        bootstrap_idx = self._create_lambda_bootstrap(lambda_name, lambda_info)

        # Emit invokedynamic
        # The invokedynamic creates an instance of the functional interface
        functional_interface = lambda_info['functional_interface']
        sam_method = lambda_info['sam_method_name']
        sam_descriptor = lambda_info['sam_descriptor']

        # invokedynamic: (captured_vars...) -> FunctionalInterface
        num_captured = len(lambda_info['captured_vars'])
        builder.invokedynamic(
            bootstrap_idx,
            sam_method,
            self._make_invokedynamic_descriptor(lambda_info),
            arg_size=num_captured,
            ret_size=1
        )

        return lambda_info['functional_interface']

    def _analyze_lambda(self, expr: ast.LambdaExpression, ctx: MethodContext) -> dict:
        """Analyze lambda to determine types and captured variables.

        Returns a dict with:
        - param_types: list of JType
        - return_type: JType
        - captured_vars: list of str (variable names)
        - functional_interface: ClassJType
        - sam_method_name: str (Single Abstract Method name)
        - sam_descriptor: str (SAM descriptor)
        """
        # For now, we need to infer the functional interface from context
        # In a full implementation, we'd use type inference

        # Parse parameters
        param_types = []
        param_names = []
        if isinstance(expr.parameters, tuple):
            for param in expr.parameters:
                if isinstance(param, ast.FormalParameter):
                    param_types.append(self.resolve_type(param.type))
                    param_names.append(param.name)
                elif isinstance(param, str):
                    # Inferred parameter type - need context
                    param_names.append(param)
                    # For now, assume Object for inferred params
                    param_types.append(ClassJType("java/lang/Object"))

        # Determine return type
        if isinstance(expr.body, ast.Expression):
            # Expression lambda: () -> expr
            # Return type is the type of the expression
            # For now, we'll determine this when compiling the body
            return_type = VOID  # Placeholder
        else:
            # Block lambda: () -> { statements }
            # Scan for return statements
            return_type = VOID

        # Find captured variables
        captured_vars = self._find_captured_variables(expr, ctx, param_names)

        # Determine functional interface
        # For Runnable: run() -> void
        # For Function<T,R>: apply(T) -> R
        # For Consumer<T>: accept(T) -> void
        # For Supplier<T>: get() -> T

        # Simple heuristic based on signature:
        if len(param_types) == 0 and return_type == VOID:
            functional_interface = ClassJType("java/lang/Runnable")
            sam_method_name = "run"
            sam_descriptor = "()V"
        elif len(param_types) == 1 and return_type == VOID:
            functional_interface = ClassJType("java/util/function/Consumer")
            sam_method_name = "accept"
            sam_descriptor = "(Ljava/lang/Object;)V"
        elif len(param_types) == 1 and return_type != VOID:
            functional_interface = ClassJType("java/util/function/Function")
            sam_method_name = "apply"
            sam_descriptor = "(Ljava/lang/Object;)Ljava/lang/Object;"
        elif len(param_types) == 0 and return_type != VOID:
            functional_interface = ClassJType("java/util/function/Supplier")
            sam_method_name = "get"
            sam_descriptor = "()Ljava/lang/Object;"
        else:
            # Fallback: use a generic functional interface
            functional_interface = ClassJType("java/lang/Runnable")
            sam_method_name = "run"
            sam_descriptor = "()V"

        return {
            'param_types': param_types,
            'param_names': param_names,
            'return_type': return_type,
            'captured_vars': captured_vars,
            'functional_interface': functional_interface,
            'sam_method_name': sam_method_name,
            'sam_descriptor': sam_descriptor,
        }

    def _find_captured_variables(self, expr: ast.LambdaExpression, ctx: MethodContext, param_names: list) -> list:
        """Find variables captured by the lambda from the enclosing scope."""
        # For now, return empty list
        # In a full implementation, we'd walk the lambda body AST and find
        # all variable references that are not parameters
        return []

    def _create_lambda_method(self, lambda_name: str, expr: ast.LambdaExpression,
                              lambda_info: dict, ctx: MethodContext):
        """Create a synthetic method for the lambda body.

        The method signature is: (captured_vars..., params...) -> return_type
        """
        from ..classfile import MethodInfo, BytecodeBuilder

        # Build method descriptor
        descriptor_parts = []

        # Captured variables (all as Object for simplicity)
        for _ in lambda_info['captured_vars']:
            descriptor_parts.append("Ljava/lang/Object;")

        # Parameters
        for param_type in lambda_info['param_types']:
            descriptor_parts.append(param_type.descriptor())

        # Return type
        return_desc = lambda_info['return_type'].descriptor() if lambda_info['return_type'] != VOID else "V"

        descriptor = f"({''.join(descriptor_parts)}){return_desc}"

        # Create method
        method_flags = AccessFlags.PRIVATE | AccessFlags.STATIC | AccessFlags.SYNTHETIC

        # Build method code
        builder = BytecodeBuilder(self.class_file.cp)

        # Set up local variables
        # Slot 0, 1, ... : captured variables
        # Slot N, N+1, ... : parameters
        local_slot = 0
        lambda_ctx = MethodContext(
            class_name=self.class_name,
            method_name=lambda_name,
            builder=builder,
            locals={},
            return_type=lambda_info['return_type']
        )

        # Map captured vars to slots
        for var_name in lambda_info['captured_vars']:
            lambda_ctx.locals[var_name] = local_slot
            local_slot += 1

        # Map parameters to slots
        for param_name in lambda_info['param_names']:
            lambda_ctx.locals[param_name] = local_slot
            local_slot += 1

        builder.max_locals = local_slot

        # Compile lambda body
        if isinstance(expr.body, ast.Expression):
            # Expression lambda: return the expression value
            expr_type = self.compile_expression(expr.body, lambda_ctx)
            if lambda_info['return_type'] != VOID:
                # Return the value
                if lambda_info['return_type'].size() == 2:
                    builder.lreturn()
                elif lambda_info['return_type'].size() == 1:
                    if lambda_info['return_type'].descriptor() in ('F',):
                        builder.freturn()
                    elif lambda_info['return_type'].descriptor() in ('D',):
                        builder.dreturn()
                    elif lambda_info['return_type'].descriptor().startswith('L') or \
                         lambda_info['return_type'].descriptor().startswith('['):
                        builder.areturn()
                    else:
                        builder.ireturn()
            else:
                # Void return - only pop if expression left a value on stack
                if expr_type != VOID:
                    builder.pop()
                builder.return_()
        else:
            # Block lambda: compile the block
            for stmt in expr.body.statements:
                self.compile_statement(stmt, lambda_ctx)
            # Ensure method ends with return
            if lambda_info['return_type'] == VOID:
                builder.return_()

        code_attr = builder.build()

        method_info = MethodInfo(
            name=lambda_name,
            descriptor=descriptor,
            access_flags=method_flags,
            code=code_attr
        )

        self.class_file.add_method(method_info)

    def _create_lambda_bootstrap(self, lambda_name: str, lambda_info: dict) -> int:
        """Create bootstrap method entry for LambdaMetafactory.

        Returns the index in the BootstrapMethods table.
        """
        cp = self.class_file.cp

        # Create CONSTANT_MethodHandle for LambdaMetafactory.metafactory
        # REF_invokeStatic = 6
        metafactory_ref = cp.add_methodref(
            "java/lang/invoke/LambdaMetafactory",
            "metafactory",
            "(Ljava/lang/invoke/MethodHandles$Lookup;"
            "Ljava/lang/String;"
            "Ljava/lang/invoke/MethodType;"
            "Ljava/lang/invoke/MethodType;"
            "Ljava/lang/invoke/MethodHandle;"
            "Ljava/lang/invoke/MethodType;)"
            "Ljava/lang/invoke/CallSite;"
        )
        metafactory_handle = cp.add_method_handle(6, metafactory_ref)  # REF_invokeStatic

        # Bootstrap arguments:
        # 1. samMethodType: MethodType of the SAM method
        # 2. implMethod: MethodHandle to our lambda$ method
        # 3. instantiatedMethodType: MethodType after type specialization

        # Argument 1: SAM method type
        sam_method_type_idx = cp.add_method_type(lambda_info['sam_descriptor'])

        # Argument 2: Implementation method handle (our lambda$N method)
        impl_method_ref = cp.add_methodref(
            self.class_name,
            lambda_name,
            self._make_lambda_method_descriptor(lambda_info)
        )
        impl_method_handle = cp.add_method_handle(6, impl_method_ref)  # REF_invokeStatic

        # Argument 3: Instantiated method type (same as SAM for non-generic)
        instantiated_method_type_idx = sam_method_type_idx

        bootstrap_args = [
            sam_method_type_idx,
            impl_method_handle,
            instantiated_method_type_idx
        ]

        return self.class_file.add_bootstrap_method(metafactory_handle, bootstrap_args)

    def _make_lambda_method_descriptor(self, lambda_info: dict) -> str:
        """Create descriptor for the synthetic lambda method."""
        descriptor_parts = []

        # Captured variables
        for _ in lambda_info['captured_vars']:
            descriptor_parts.append("Ljava/lang/Object;")

        # Parameters
        for param_type in lambda_info['param_types']:
            descriptor_parts.append(param_type.descriptor())

        # Return type
        return_desc = lambda_info['return_type'].descriptor() if lambda_info['return_type'] != VOID else "V"

        return f"({''.join(descriptor_parts)}){return_desc}"

    def _make_invokedynamic_descriptor(self, lambda_info: dict) -> str:
        """Create descriptor for the invokedynamic instruction.

        This is: (captured_types...) -> FunctionalInterface
        """
        descriptor_parts = []

        # Captured variables
        for _ in lambda_info['captured_vars']:
            descriptor_parts.append("Ljava/lang/Object;")

        # Return functional interface
        return_desc = lambda_info['functional_interface'].descriptor()

        return f"({''.join(descriptor_parts)}){return_desc}"
