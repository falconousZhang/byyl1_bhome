"""
Semantic analysis: symbol table + constraint checks.

Checks performed:
  A  – Type mismatch (annotation vs initialiser / lvalue vs rhs)
  B  – for-loop iterable must be array or range
  C  – Assignment to immutable variable
  D  – break / continue outside loop
  E  – Undefined variable / function
  F  – Use of possibly uninitialized variable
  G  – return type mismatch
  H  – Array/tuple literal element count & element type
  I  – void function used as rvalue
  J  – Borrow rules (6.2/6.3): &mut requires mutable source; &mut can't coexist
  K  – loop break-value type consistency (7.4)
  L  – Array / tuple index out of bounds (static, constant index only)
  M  – Array index type must be i32
  N  – Function call: arg count / arg type
"""

from ast_nodes import *


class _TypeBool:
    """Internal sentinel: result of a comparison, distinct from i32."""
    pass


class SemanticError:
    def __init__(self, msg, line=None):
        self.msg = msg
        self.line = line

    def to_dict(self):
        return {"msg": self.msg, "line": self.line}


# ── Symbol table ──────────────────────────────────────────────────────────────

class Symbol:
    def __init__(self, name, mutable, sym_type=None, initialized=False, lineno=None):
        self.name        = name
        self.mutable     = mutable          # bool
        self.sym_type    = sym_type         # TypeNode | None
        self.initialized = initialized      # False = declared but not yet assigned
        self.lineno      = lineno           # declaration line (for error reporting)

    def __repr__(self):
        m = "mut " if self.mutable else ""
        t = f": {type_str(self.sym_type)}" if self.sym_type else ""
        return f"{m}{self.name}{t}"


def type_str(t):
    if t is None: return "?"
    if isinstance(t, _TypeBool): return "bool"
    if isinstance(t, TypeI32):   return "i32"
    if isinstance(t, TypeRef):
        m = "mut " if t.mutable else ""
        return f"&{m}{type_str(t.inner)}"
    if isinstance(t, TypeArray):
        return f"[{type_str(t.elem_type)}; {t.size}]"
    if isinstance(t, TypeTuple):
        return "(" + ", ".join(type_str(x) for x in t.types) + ")"
    return "unknown"


def types_compatible(declared, assigned):
    """Conservative structural type equality (None = unknown, always compatible)."""
    if declared is None or assigned is None:
        return True
    if type(declared) != type(assigned):
        return False
    if isinstance(declared, TypeI32):   return True
    if isinstance(declared, _TypeBool): return True
    if isinstance(declared, TypeRef):
        return declared.mutable == assigned.mutable and \
               types_compatible(declared.inner, assigned.inner)
    if isinstance(declared, TypeArray):
        return declared.size == assigned.size and \
               types_compatible(declared.elem_type, assigned.elem_type)
    if isinstance(declared, TypeTuple):
        if len(declared.types) != len(assigned.types):
            return False
        return all(types_compatible(a, b) for a, b in zip(declared.types, assigned.types))
    return True


class Scope:
    def __init__(self, parent=None):
        self.symbols: dict[str, Symbol] = {}
        self.parent = parent

    def define(self, sym: Symbol):
        self.symbols[sym.name] = sym

    def lookup(self, name: str):
        if name in self.symbols:
            return self.symbols[name]
        if self.parent:
            return self.parent.lookup(name)
        return None


# ── Analyser ──────────────────────────────────────────────────────────────────

_UNSET = object()   # sentinel for "no break value seen yet in this loop"

class Analyser:
    def __init__(self):
        self.errors: list[SemanticError] = []
        self.scope: Scope = Scope()
        self._loop_depth    = 0
        self._func_table: dict = {}       # name → {'params': [...], 'ret': TypeNode|None}
        self._cur_ret_type  = None        # return type of current function

        # Borrow tracking (J): per-scope list of {var_name: 'imm'|'mut'}
        self._borrow_stack: list[dict] = [{}]

        # Loop break-value type stack (K): one entry per active loop
        self._break_type_stack: list = []   # each entry: _UNSET | None | TypeNode

    def _err(self, msg, line=None):
        self.errors.append(SemanticError(msg, line))

    def _push(self):
        self.scope = Scope(self.scope)
        self._borrow_stack.append({})

    def _pop(self):
        # Check for variables whose type can never be inferred (rule 2.1)
        for sym in self.scope.symbols.values():
            if sym.sym_type is None and not sym.initialized:
                self._err(
                    f"Cannot infer type of '{sym.name}': "
                    f"declared without type annotation and never assigned",
                    sym.lineno)
        self.scope = self.scope.parent
        self._borrow_stack.pop()

    # ── borrow helpers (J) ────────────────────────────────────────────────────

    def _get_borrow(self, var_name):
        """Return 'imm', 'mut', or None."""
        for d in reversed(self._borrow_stack):
            if var_name in d:
                return d[var_name]
        return None

    def _add_borrow(self, var_name, kind):
        if self._borrow_stack:
            self._borrow_stack[-1][var_name] = kind

    def _ref_source_name(self, expr):
        """Extract variable name from &x or &mut x operand."""
        if isinstance(expr, Identifier):
            return expr.name
        if isinstance(expr, UnaryOp) and expr.op in ('&', '&mut', '*'):
            return self._ref_source_name(expr.operand)
        if isinstance(expr, IndexExpr):
            return self._ref_source_name(expr.base)
        if isinstance(expr, TupleFieldExpr):
            return self._ref_source_name(expr.base)
        return None

    # ── type inference (best-effort) ─────────────────────────────────────────

    def _infer(self, node):
        if isinstance(node, NumLiteral):   return TypeI32()
        if isinstance(node, Identifier):
            sym = self.scope.lookup(node.name)
            return sym.sym_type if sym else None
        if isinstance(node, BinaryOp):
            if node.op in ('+', '-', '*', '/'):
                return TypeI32()
            if node.op in ('==', '!=', '<', '>', '<=', '>='):
                return _TypeBool()
            return None
        if isinstance(node, UnaryOp):
            if node.op == '-':    return TypeI32()
            if node.op == '&':
                inner = self._infer(node.operand)
                return TypeRef(False, inner) if inner else None
            if node.op == '&mut':
                inner = self._infer(node.operand)
                return TypeRef(True, inner) if inner else None
            if node.op == '*':
                inner = self._infer(node.operand)
                return inner.inner if isinstance(inner, TypeRef) else None
        if isinstance(node, IndexExpr):
            bt = self._infer(node.base)
            return bt.elem_type if isinstance(bt, TypeArray) else None
        if isinstance(node, TupleFieldExpr):
            bt = self._infer(node.base)
            if isinstance(bt, TypeTuple) and node.field < len(bt.types):
                return bt.types[node.field]
            return None
        if isinstance(node, Block):
            return self._infer(node.tail_expr) if node.tail_expr else None
        if isinstance(node, CallExpr):
            fn = self._func_table.get(node.name)
            return fn['ret'] if fn else None
        if isinstance(node, IfExpr):
            return self._infer(node.then_block)
        if isinstance(node, ArrayExpr):
            if node.elements:
                et = self._infer(node.elements[0])
                return TypeArray(et, len(node.elements)) if et else None
            return None
        if isinstance(node, TupleExpr):
            types = [self._infer(e) for e in node.elements]
            if all(t is not None for t in types):
                return TypeTuple(types)
            return None
        return None

    # ── lvalue helpers ────────────────────────────────────────────────────────

    def _lvalue_type(self, lv):
        if isinstance(lv, Identifier):
            sym = self.scope.lookup(lv.name)
            return sym.sym_type if sym else None
        if isinstance(lv, UnaryOp):
            if lv.op == '*':
                inner = self._lvalue_type(lv.operand)
                return inner.inner if isinstance(inner, TypeRef) else None
            if lv.op == '&':
                return TypeRef(False, self._lvalue_type(lv.operand))
            if lv.op == '&mut':
                return TypeRef(True, self._lvalue_type(lv.operand))
        if isinstance(lv, IndexExpr):
            bt = self._lvalue_type(lv.base)
            return bt.elem_type if isinstance(bt, TypeArray) else None
        if isinstance(lv, TupleFieldExpr):
            bt = self._lvalue_type(lv.base)
            if isinstance(bt, TypeTuple) and lv.field < len(bt.types):
                return bt.types[lv.field]
        return None

    def _is_mutable_lvalue(self, lv) -> bool:
        if isinstance(lv, Identifier):
            sym = self.scope.lookup(lv.name)
            return sym.mutable if sym else False
        if isinstance(lv, UnaryOp) and lv.op == '*':
            inner_t = self._lvalue_type(lv.operand)
            return isinstance(inner_t, TypeRef) and inner_t.mutable
        if isinstance(lv, (IndexExpr, TupleFieldExpr)):
            return self._is_mutable_lvalue(lv.base)
        return False

    def _lvalue_root_name(self, lv):
        if isinstance(lv, Identifier):        return lv.name
        if isinstance(lv, UnaryOp):           return self._lvalue_root_name(lv.operand)
        if isinstance(lv, IndexExpr):         return self._lvalue_root_name(lv.base)
        if isinstance(lv, TupleFieldExpr):    return self._lvalue_root_name(lv.base)
        return None

    # ── literal shape check (H) ───────────────────────────────────────────────

    def _check_literal_shape(self, expr, decl_t, lineno):
        """Check array/tuple literal matches declared type (count + element types)."""
        if isinstance(expr, ArrayExpr) and isinstance(decl_t, TypeArray):
            if len(expr.elements) != decl_t.size:
                self._err(
                    f"Array has {len(expr.elements)} element(s), "
                    f"declared size is {decl_t.size}", lineno)
            else:
                for i, el in enumerate(expr.elements):
                    el_t = self._infer(el)
                    if el_t is not None and not types_compatible(decl_t.elem_type, el_t):
                        self._err(
                            f"Array element {i} type mismatch: "
                            f"expected {type_str(decl_t.elem_type)}, "
                            f"got {type_str(el_t)}", lineno)
        elif isinstance(expr, TupleExpr) and isinstance(decl_t, TypeTuple):
            if len(expr.elements) != len(decl_t.types):
                self._err(
                    f"Tuple has {len(expr.elements)} element(s), "
                    f"declared type has {len(decl_t.types)}", lineno)
            else:
                for i, (el, t) in enumerate(zip(expr.elements, decl_t.types)):
                    el_t = self._infer(el)
                    if el_t is not None and not types_compatible(t, el_t):
                        self._err(
                            f"Tuple element {i} type mismatch: "
                            f"expected {type_str(t)}, got {type_str(el_t)}", lineno)

    # ── void-rvalue check (I) ─────────────────────────────────────────────────

    def _check_not_void(self, expr, lineno):
        """Report error if expr is a call to a void function."""
        if isinstance(expr, CallExpr):
            fn = self._func_table.get(expr.name)
            if fn and fn['ret'] is None:
                self._err(
                    f"Function '{expr.name}' has no return value "
                    f"and cannot be used as a value", lineno)

    # ── visitors ──────────────────────────────────────────────────────────────

    def visit_program(self, node: Program):
        for d in node.decls:
            self._func_table[d.name] = {'params': d.params, 'ret': d.ret_type}
        for d in node.decls:
            self.visit_func(d)

    def visit_func(self, node: FunctionDecl):
        self._cur_ret_type = node.ret_type
        self._push()
        for p in node.params:
            self.scope.define(Symbol(p.name, p.mutable, p.type_node,
                                     initialized=True, lineno=getattr(p, 'lineno', None)))
        self.visit_block(node.body)
        self._pop()
        self._cur_ret_type = None

    def visit_block(self, node: Block):
        self._push()
        for s in node.stmts:
            self.visit_stmt(s)
        if node.tail_expr:
            self.visit_expr(node.tail_expr)
        self._pop()

    def visit_stmt(self, node):
        if isinstance(node, EmptyStmt):
            pass

        elif isinstance(node, ReturnStmt):
            if node.expr:
                self.visit_expr(node.expr)
                self._check_not_void(node.expr, node.lineno)
                ret_actual = self._infer(node.expr)
                if self._cur_ret_type is None:
                    if ret_actual is not None and not isinstance(ret_actual, _TypeBool):
                        self._err(
                            f"Function has no return type but 'return' carries a value "
                            f"({type_str(ret_actual)})", node.lineno)
                elif ret_actual is not None:
                    if not types_compatible(self._cur_ret_type, ret_actual):
                        self._err(
                            f"Return type mismatch: expected {type_str(self._cur_ret_type)}, "
                            f"got {type_str(ret_actual)}", node.lineno)
            else:
                if self._cur_ret_type is not None:
                    self._err(
                        f"Function returns {type_str(self._cur_ret_type)} but "
                        f"'return' carries no value", node.lineno)

        elif isinstance(node, LetStmt):
            self._visit_let(node)

        elif isinstance(node, AssignStmt):
            self._visit_assign(node)

        elif isinstance(node, ExprStmt):
            self.visit_expr(node.expr)

        elif isinstance(node, IfStmt):
            self._visit_if_stmt(node)

        elif isinstance(node, WhileStmt):
            self.visit_expr(node.cond)
            self._loop_depth += 1
            self._break_type_stack.append(_UNSET)
            self.visit_block(node.body)
            self._break_type_stack.pop()
            self._loop_depth -= 1

        elif isinstance(node, ForStmt):
            self._visit_for(node)

        elif isinstance(node, LoopStmt):
            self._loop_depth += 1
            self._break_type_stack.append(_UNSET)
            self.visit_block(node.body)
            self._break_type_stack.pop()
            self._loop_depth -= 1

        elif isinstance(node, BreakStmt):
            if self._loop_depth == 0:
                self._err("'break' outside of loop", node.lineno)
            elif node.expr:
                self.visit_expr(node.expr)
                self._check_not_void(node.expr, node.lineno)
                # K: break-value type consistency
                if self._break_type_stack:
                    bv_type = self._infer(node.expr)
                    top = self._break_type_stack[-1]
                    if top is _UNSET:
                        self._break_type_stack[-1] = bv_type
                    elif top is None:
                        self._err(
                            "Inconsistent break values: previous 'break' had no value, "
                            "this one does", node.lineno)
                    elif bv_type is not None and not types_compatible(top, bv_type):
                        self._err(
                            f"Inconsistent break value types: expected {type_str(top)}, "
                            f"got {type_str(bv_type)}", node.lineno)
            else:
                # K: bare break in loop that may already expect a value
                if self._break_type_stack:
                    top = self._break_type_stack[-1]
                    if top is _UNSET:
                        self._break_type_stack[-1] = None
                    elif top is not None:
                        self._err(
                            "Inconsistent break values: previous 'break' had a value, "
                            "this one does not", node.lineno)

        elif isinstance(node, ContinueStmt):
            if self._loop_depth == 0:
                self._err("'continue' outside of loop", node.lineno)

    def _visit_let(self, node: LetStmt):
        has_init = node.init_expr is not None
        init_type = None
        if has_init:
            self.visit_expr(node.init_expr)
            # I: void function as rvalue
            self._check_not_void(node.init_expr, node.lineno)
            init_type = self._infer(node.init_expr)

        # A: declared type vs initialiser type
        if node.type_node and init_type:
            if not types_compatible(node.type_node, init_type):
                self._err(
                    f"Type mismatch in let '{node.name}': "
                    f"declared {type_str(node.type_node)}, got {type_str(init_type)}",
                    node.lineno)

        # H: array / tuple literal shape
        if has_init and node.type_node:
            self._check_literal_shape(node.init_expr, node.type_node, node.lineno)

        # J: borrow rules for &x / &mut x initialisers
        if has_init:
            self._check_borrow_in_let(node.init_expr, node.lineno)

        resolved_type = node.type_node or init_type
        self.scope.define(Symbol(node.name, node.mutable, resolved_type,
                                 initialized=has_init, lineno=node.lineno))

    def _check_borrow_in_let(self, expr, lineno):
        """Apply borrow rules when init expr is a reference expression."""
        if not isinstance(expr, UnaryOp):
            return
        if expr.op not in ('&', '&mut'):
            return
        source = self._ref_source_name(expr.operand)
        if source is None:
            return
        if expr.op == '&mut':
            # J1: source must be mutable
            sym = self.scope.lookup(source)
            if sym and not sym.mutable:
                self._err(
                    f"Cannot take mutable reference of immutable variable '{source}'",
                    lineno)
            # J2: no existing borrow of source
            existing = self._get_borrow(source)
            if existing == 'imm':
                self._err(
                    f"Cannot borrow '{source}' as mutable because it is "
                    f"already borrowed as immutable", lineno)
            elif existing == 'mut':
                self._err(
                    f"Cannot borrow '{source}' as mutable more than once", lineno)
            else:
                self._add_borrow(source, 'mut')
        else:  # &
            # J3: no existing mutable borrow of source
            existing = self._get_borrow(source)
            if existing == 'mut':
                self._err(
                    f"Cannot borrow '{source}' as immutable because it is "
                    f"already borrowed as mutable", lineno)
            else:
                self._add_borrow(source, 'imm')

    def _visit_assign(self, node: AssignStmt):
        self.visit_expr(node.expr)
        # I: void function as rvalue
        self._check_not_void(node.expr, node.lineno)
        rhs_type = self._infer(node.expr)

        # Mark lvalue root as initialized
        root = self._lvalue_root_name(node.lvalue)
        if root:
            sym = self.scope.lookup(root)
            if sym:
                sym.initialized = True

        # C: immutability check
        if not self._is_mutable_lvalue(node.lvalue):
            label = f"'{root}'" if root else "expression"
            self._err(f"Cannot assign to immutable {label}", node.lineno)

        # A: lvalue type vs rhs type
        lv_type = self._lvalue_type(node.lvalue)
        if lv_type and rhs_type:
            if not types_compatible(lv_type, rhs_type):
                self._err(
                    f"Type mismatch: lvalue is {type_str(lv_type)}, "
                    f"assigned {type_str(rhs_type)}"
                    + (f" (variable '{root}')" if root else ""),
                    node.lineno)

        # H: array / tuple literal shape vs lvalue type
        if lv_type:
            self._check_literal_shape(node.expr, lv_type, node.lineno)

    def _visit_call(self, node: CallExpr):
        for arg in node.args:
            self.visit_expr(arg)
            # I: void function as argument
            self._check_not_void(arg, node.lineno)
        fn = self._func_table.get(node.name)
        if fn is None:
            self._err(f"Undefined function '{node.name}'", node.lineno)
            return
        params = fn['params']
        # N: arg count
        if len(node.args) != len(params):
            self._err(
                f"Function '{node.name}' expects {len(params)} argument(s), "
                f"got {len(node.args)}", node.lineno)
            return
        # N: arg types
        for i, (arg, param) in enumerate(zip(node.args, params)):
            if param.type_node is None:
                continue
            arg_type = self._infer(arg)
            if arg_type is not None and not types_compatible(param.type_node, arg_type):
                self._err(
                    f"Argument {i+1} of '{node.name}': "
                    f"expected {type_str(param.type_node)}, got {type_str(arg_type)}",
                    node.lineno)

    def _visit_if_stmt(self, node: IfStmt):
        self.visit_expr(node.cond)
        self.visit_block(node.then_block)
        for cond, blk in node.elseif_clauses:
            self.visit_expr(cond)
            self.visit_block(blk)
        if node.else_block:
            self.visit_block(node.else_block)

    def _visit_for(self, node: ForStmt):
        if isinstance(node.iterable, RangeExpr):
            self.visit_expr(node.iterable.start)
            self.visit_expr(node.iterable.end)
        else:
            self.visit_expr(node.iterable)
            iter_type = self._infer(node.iterable)
            if iter_type is not None and not isinstance(iter_type, TypeArray):
                self._err(
                    f"Cannot iterate over non-array type {type_str(iter_type)}",
                    node.lineno)

        self._push()
        if isinstance(node.iterable, RangeExpr):
            elem_type = TypeI32()
        else:
            it = self._infer(node.iterable)
            elem_type = it.elem_type if isinstance(it, TypeArray) else None
        resolved = node.var_type or elem_type
        self.scope.define(Symbol(node.var_name, node.mutable, resolved,
                                 initialized=True, lineno=node.lineno))
        self._loop_depth += 1
        self._break_type_stack.append(_UNSET)
        for s in node.body.stmts:
            self.visit_stmt(s)
        if node.body.tail_expr:
            self.visit_expr(node.body.tail_expr)
        self._break_type_stack.pop()
        self._loop_depth -= 1
        self._pop()

    def visit_expr(self, node):
        if isinstance(node, NumLiteral):
            pass

        elif isinstance(node, Identifier):
            sym = self.scope.lookup(node.name)
            if not sym:
                self._err(f"Undefined variable '{node.name}'", node.lineno)
            elif not sym.initialized:
                self._err(
                    f"Use of possibly uninitialized variable '{node.name}'",
                    node.lineno)

        elif isinstance(node, BinaryOp):
            self.visit_expr(node.left)
            self.visit_expr(node.right)
            # I: void call in binary expression
            self._check_not_void(node.left, node.lineno)
            self._check_not_void(node.right, node.lineno)

        elif isinstance(node, UnaryOp):
            self.visit_expr(node.operand)

        elif isinstance(node, IndexExpr):
            self.visit_expr(node.base)
            self.visit_expr(node.index)
            # M: index must be i32
            idx_type = self._infer(node.index)
            if idx_type is not None and not isinstance(idx_type, TypeI32):
                self._err(
                    f"Array index must be i32, got {type_str(idx_type)}",
                    node.lineno)
            # L: static bounds check (constant index)
            base_t = self._infer(node.base)
            if isinstance(base_t, TypeArray) and isinstance(node.index, NumLiteral):
                if node.index.value < 0 or node.index.value >= base_t.size:
                    self._err(
                        f"Array index {node.index.value} out of bounds "
                        f"(size {base_t.size})", node.lineno)

        elif isinstance(node, TupleFieldExpr):
            self.visit_expr(node.base)
            # L: tuple field bounds check
            base_t = self._infer(node.base)
            if isinstance(base_t, TypeTuple):
                if node.field >= len(base_t.types):
                    self._err(
                        f"Tuple field index {node.field} out of bounds "
                        f"(tuple has {len(base_t.types)} element(s))", node.lineno)

        elif isinstance(node, ArrayExpr):
            for e in node.elements:
                self.visit_expr(e)

        elif isinstance(node, TupleExpr):
            for e in node.elements:
                self.visit_expr(e)

        elif isinstance(node, RangeExpr):
            self.visit_expr(node.start)
            self.visit_expr(node.end)

        elif isinstance(node, Block):
            self.visit_block(node)

        elif isinstance(node, IfExpr):
            self.visit_expr(node.cond)
            self.visit_block(node.then_block)
            self.visit_block(node.else_block)

        elif isinstance(node, LoopExpr):
            self._loop_depth += 1
            self._break_type_stack.append(_UNSET)
            self.visit_block(node.body)
            self._break_type_stack.pop()
            self._loop_depth -= 1

        elif isinstance(node, CallExpr):
            self._visit_call(node)


# ── Public API ────────────────────────────────────────────────────────────────

def analyse(ast: Program) -> list[dict]:
    a = Analyser()
    a.visit_program(ast)
    return [e.to_dict() for e in a.errors]
