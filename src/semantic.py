"""
Semantic analysis: symbol table + 羁绊 constraint checks.

Checks performed:
  羁绊A – Assignment type mismatch (when type annotations are present)
  羁绊B – for-loop iterable must be array or range
  羁绊C – Assignment to immutable variable (inside any scope, incl. loops)
"""

from ast_nodes import *


class SemanticError:
    def __init__(self, msg, line=None):
        self.msg = msg
        self.line = line

    def to_dict(self):
        return {"msg": self.msg, "line": self.line}


# ── Symbol table ──────────────────────────────────────────────────────────────

class Symbol:
    def __init__(self, name, mutable, sym_type=None):
        self.name = name
        self.mutable = mutable   # bool
        self.sym_type = sym_type # TypeNode or None

    def __repr__(self):
        m = "mut " if self.mutable else ""
        t = f": {type_str(self.sym_type)}" if self.sym_type else ""
        return f"{m}{self.name}{t}"


def type_str(t):
    if t is None: return "?"
    if isinstance(t, TypeI32): return "i32"
    if isinstance(t, TypeRef):
        m = "mut " if t.mutable else ""
        return f"&{m}{type_str(t.inner)}"
    if isinstance(t, TypeArray):
        return f"[{type_str(t.elem_type)}; {t.size}]"
    if isinstance(t, TypeTuple):
        return "(" + ", ".join(type_str(x) for x in t.types) + ")"
    return "unknown"


def types_compatible(declared, assigned):
    """Very conservative structural type equality check."""
    if declared is None or assigned is None:
        return True  # can't check without full type inference
    if type(declared) != type(assigned):
        return False
    if isinstance(declared, TypeI32):
        return True
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

    def lookup(self, name: str) -> Symbol | None:
        if name in self.symbols:
            return self.symbols[name]
        if self.parent:
            return self.parent.lookup(name)
        return None


# ── Analyser ──────────────────────────────────────────────────────────────────

class Analyser:
    def __init__(self):
        self.errors: list[SemanticError] = []
        self.scope: Scope = Scope()
        self._loop_depth = 0

    def _err(self, msg, line=None):
        self.errors.append(SemanticError(msg, line))

    def _push(self):
        self.scope = Scope(self.scope)

    def _pop(self):
        self.scope = self.scope.parent

    # ── infer expression type (best effort, no full inference) ────────────────

    def _infer(self, node) -> 'TypeNode | None':
        if isinstance(node, NumLiteral):
            return TypeI32()
        if isinstance(node, Identifier):
            sym = self.scope.lookup(node.name)
            return sym.sym_type if sym else None
        if isinstance(node, BinaryOp):
            if node.op in ('+', '-', '*', '/'):
                return TypeI32()
            return None  # comparisons – would need bool type
        if isinstance(node, UnaryOp):
            if node.op == '-':
                return TypeI32()
            if node.op == '&':
                inner = self._infer(node.operand)
                return TypeRef(False, inner) if inner else None
            if node.op == '&mut':
                inner = self._infer(node.operand)
                return TypeRef(True, inner) if inner else None
            if node.op == '*':
                inner = self._infer(node.operand)
                if isinstance(inner, TypeRef):
                    return inner.inner
                return None
        if isinstance(node, IndexExpr):
            base_t = self._infer(node.base)
            if isinstance(base_t, TypeArray):
                return base_t.elem_type
            return None
        if isinstance(node, TupleFieldExpr):
            base_t = self._infer(node.base)
            if isinstance(base_t, TypeTuple) and node.field < len(base_t.types):
                return base_t.types[node.field]
            return None
        if isinstance(node, Block):
            if node.tail_expr:
                return self._infer(node.tail_expr)
            return None
        return None

    # ── lvalue type resolution ────────────────────────────────────────────────

    def _lvalue_type(self, lv) -> 'TypeNode | None':
        """Return the type of the location lv points to (what you assign into it)."""
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
            base_t = self._lvalue_type(lv.base)
            return base_t.elem_type if isinstance(base_t, TypeArray) else None
        if isinstance(lv, TupleFieldExpr):
            base_t = self._lvalue_type(lv.base)
            if isinstance(base_t, TypeTuple) and lv.field < len(base_t.types):
                return base_t.types[lv.field]
        return None

    def _is_mutable_lvalue(self, lv) -> bool:
        """True if this lvalue location is writable."""
        if isinstance(lv, Identifier):
            sym = self.scope.lookup(lv.name)
            return sym.mutable if sym else False
        if isinstance(lv, UnaryOp) and lv.op == '*':
            # *p is writable iff p has type &mut T
            inner_t = self._lvalue_type(lv.operand)
            return isinstance(inner_t, TypeRef) and inner_t.mutable
        if isinstance(lv, (IndexExpr, TupleFieldExpr)):
            return self._is_mutable_lvalue(lv.base)
        return False

    # ── visitors ──────────────────────────────────────────────────────────────

    def visit_program(self, node: Program):
        for d in node.decls:
            self.visit_func(d)

    def visit_func(self, node: FunctionDecl):
        self._push()
        for p in node.params:
            self.scope.define(Symbol(p.name, p.mutable, p.type_node))
        self.visit_block(node.body)
        self._pop()

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
            if node.expr: self.visit_expr(node.expr)
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
            self.visit_block(node.body)
            self._loop_depth -= 1
        elif isinstance(node, ForStmt):
            self._visit_for(node)
        elif isinstance(node, LoopStmt):
            self._loop_depth += 1
            self.visit_block(node.body)
            self._loop_depth -= 1
        elif isinstance(node, (BreakStmt, ContinueStmt)):
            if self._loop_depth == 0:
                kw = "break" if isinstance(node, BreakStmt) else "continue"
                self._err(f"'{kw}' outside of loop", node.lineno)
            if isinstance(node, BreakStmt) and node.expr:
                self.visit_expr(node.expr)

    def _visit_let(self, node: LetStmt):
        init_type = None
        if node.init_expr:
            self.visit_expr(node.init_expr)
            init_type = self._infer(node.init_expr)

        # 羁绊A: type annotation vs initialiser type
        if node.type_node and init_type:
            if not types_compatible(node.type_node, init_type):
                self._err(
                    f"Type mismatch in let '{node.name}': "
                    f"declared {type_str(node.type_node)}, got {type_str(init_type)}",
                    node.lineno,
                )

        resolved_type = node.type_node or init_type
        self.scope.define(Symbol(node.name, node.mutable, resolved_type))

    def _visit_assign(self, node: AssignStmt):
        self.visit_expr(node.expr)
        rhs_type = self._infer(node.expr)

        # 羁绊C: immutability check (uses resolved lvalue mutability)
        if not self._is_mutable_lvalue(node.lvalue):
            root = self._lvalue_root_name(node.lvalue)
            label = f"'{root}'" if root else "expression"
            self._err(f"Cannot assign to immutable {label}", node.lineno)

        # 羁绊A: type mismatch — compare lvalue element type to rhs
        lv_type = self._lvalue_type(node.lvalue)
        if lv_type and rhs_type:
            if not types_compatible(lv_type, rhs_type):
                root = self._lvalue_root_name(node.lvalue)
                self._err(
                    f"Type mismatch: lvalue is {type_str(lv_type)}, "
                    f"assigned {type_str(rhs_type)}"
                    + (f" (variable '{root}')" if root else ""),
                    node.lineno,
                )

    def _lvalue_root_name(self, lv) -> str | None:
        if isinstance(lv, Identifier): return lv.name
        if isinstance(lv, UnaryOp):    return self._lvalue_root_name(lv.operand)
        if isinstance(lv, IndexExpr):  return self._lvalue_root_name(lv.base)
        if isinstance(lv, TupleFieldExpr): return self._lvalue_root_name(lv.base)
        return None

    def _visit_if_stmt(self, node: IfStmt):
        self.visit_expr(node.cond)
        self.visit_block(node.then_block)
        for cond, blk in node.elseif_clauses:
            self.visit_expr(cond)
            self.visit_block(blk)
        if node.else_block:
            self.visit_block(node.else_block)

    def _visit_for(self, node: ForStmt):
        self.visit_expr(node.iterable) if not isinstance(node.iterable, RangeExpr) \
            else (self.visit_expr(node.iterable.start), self.visit_expr(node.iterable.end))

        # 羁绊B: iterable must be array type or range
        if isinstance(node.iterable, RangeExpr):
            pass  # range is always iterable
        else:
            iter_type = self._infer(node.iterable)
            if iter_type is not None and not isinstance(iter_type, TypeArray):
                self._err(
                    f"Cannot iterate over non-array type {type_str(iter_type)} "
                    f"in for loop",
                    node.lineno,
                )

        self._push()
        # loop variable: element type if array, i32 if range
        if isinstance(node.iterable, RangeExpr):
            elem_type = TypeI32()
        else:
            iter_type = self._infer(node.iterable)
            elem_type = iter_type.elem_type if isinstance(iter_type, TypeArray) else None
        resolved_type = node.var_type or elem_type
        self.scope.define(Symbol(node.var_name, node.mutable, resolved_type))

        self._loop_depth += 1
        for s in node.body.stmts:
            self.visit_stmt(s)
        if node.body.tail_expr:
            self.visit_expr(node.body.tail_expr)
        self._loop_depth -= 1
        self._pop()

    def visit_expr(self, node):
        if isinstance(node, (NumLiteral,)):
            pass
        elif isinstance(node, Identifier):
            if not self.scope.lookup(node.name):
                self._err(f"Undefined variable '{node.name}'", node.lineno)
        elif isinstance(node, BinaryOp):
            self.visit_expr(node.left)
            self.visit_expr(node.right)
        elif isinstance(node, UnaryOp):
            self.visit_expr(node.operand)
        elif isinstance(node, IndexExpr):
            self.visit_expr(node.base)
            self.visit_expr(node.index)
        elif isinstance(node, TupleFieldExpr):
            self.visit_expr(node.base)
        elif isinstance(node, ArrayExpr):
            for e in node.elements: self.visit_expr(e)
        elif isinstance(node, TupleExpr):
            for e in node.elements: self.visit_expr(e)
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
            self.visit_block(node.body)
            self._loop_depth -= 1


# ── Public API ────────────────────────────────────────────────────────────────

def analyse(ast: Program) -> list[dict]:
    a = Analyser()
    a.visit_program(ast)
    return [e.to_dict() for e in a.errors]
