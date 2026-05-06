"""AST node definitions for the Rust-like language."""

class Node:
    def to_dict(self):
        raise NotImplementedError

# ── Program ──────────────────────────────────────────────────────────────────

class Program(Node):
    def __init__(self, decls):
        self.decls = decls

    def to_dict(self):
        return {"type": "Program", "declarations": [d.to_dict() for d in self.decls]}

# ── Declarations ──────────────────────────────────────────────────────────────

class FunctionDecl(Node):
    def __init__(self, name, params, ret_type, body, lineno=None):
        self.name = name
        self.params = params       # list of Param
        self.ret_type = ret_type   # TypeNode or None
        self.body = body           # Block
        self.lineno = lineno

    def to_dict(self):
        return {
            "type": "FunctionDecl",
            "name": self.name,
            "params": [p.to_dict() for p in self.params],
            "ret_type": self.ret_type.to_dict() if self.ret_type else None,
            "body": self.body.to_dict(),
            "lineno": self.lineno,
        }

class Param(Node):
    def __init__(self, mutable, name, type_node, lineno=None):
        self.mutable = mutable     # bool
        self.name = name
        self.type_node = type_node
        self.lineno = lineno

    def to_dict(self):
        return {
            "type": "Param",
            "mutable": self.mutable,
            "name": self.name,
            "param_type": self.type_node.to_dict(),
            "lineno": self.lineno,
        }

# ── Types ──────────────────────────────────────────────────────────────────

class TypeI32(Node):
    def to_dict(self): return {"type": "TypeI32"}

class TypeRef(Node):
    def __init__(self, mutable, inner):
        self.mutable = mutable
        self.inner = inner

    def to_dict(self):
        return {"type": "TypeRef", "mutable": self.mutable, "inner": self.inner.to_dict()}

class TypeArray(Node):
    def __init__(self, elem_type, size):
        self.elem_type = elem_type
        self.size = size  # int

    def to_dict(self):
        return {"type": "TypeArray", "elem_type": self.elem_type.to_dict(), "size": self.size}

class TypeTuple(Node):
    def __init__(self, types):
        self.types = types  # list of TypeNode

    def to_dict(self):
        return {"type": "TypeTuple", "types": [t.to_dict() for t in self.types]}

# ── Block ──────────────────────────────────────────────────────────────────

class Block(Node):
    """{ stmts... [tail_expr] }  tail_expr is bare expression (no ;)"""
    def __init__(self, stmts, tail_expr=None):
        self.stmts = stmts
        self.tail_expr = tail_expr  # expression or None

    def to_dict(self):
        return {
            "type": "Block",
            "stmts": [s.to_dict() for s in self.stmts],
            "tail_expr": self.tail_expr.to_dict() if self.tail_expr else None,
        }

# ── Statements ──────────────────────────────────────────────────────────────

class EmptyStmt(Node):
    def to_dict(self): return {"type": "EmptyStmt"}

class ReturnStmt(Node):
    def __init__(self, expr=None, lineno=None):
        self.expr = expr
        self.lineno = lineno

    def to_dict(self):
        return {"type": "ReturnStmt", "expr": self.expr.to_dict() if self.expr else None,
                "lineno": self.lineno}

class LetStmt(Node):
    def __init__(self, mutable, name, type_node, init_expr=None, lineno=None):
        self.mutable = mutable
        self.name = name
        self.type_node = type_node  # TypeNode or None
        self.init_expr = init_expr
        self.lineno = lineno

    def to_dict(self):
        return {
            "type": "LetStmt",
            "mutable": self.mutable,
            "name": self.name,
            "var_type": self.type_node.to_dict() if self.type_node else None,
            "init": self.init_expr.to_dict() if self.init_expr else None,
            "lineno": self.lineno,
        }

class AssignStmt(Node):
    def __init__(self, lvalue, expr, lineno=None):
        self.lvalue = lvalue
        self.expr = expr
        self.lineno = lineno

    def to_dict(self):
        return {"type": "AssignStmt", "lvalue": self.lvalue.to_dict(),
                "expr": self.expr.to_dict(), "lineno": self.lineno}

class ExprStmt(Node):
    def __init__(self, expr, lineno=None):
        self.expr = expr
        self.lineno = lineno

    def to_dict(self):
        return {"type": "ExprStmt", "expr": self.expr.to_dict(), "lineno": self.lineno}

class IfStmt(Node):
    def __init__(self, cond, then_block, elseif_clauses, else_block, lineno=None):
        self.cond = cond
        self.then_block = then_block
        self.elseif_clauses = elseif_clauses  # list of (cond, block)
        self.else_block = else_block           # Block or None
        self.lineno = lineno

    def to_dict(self):
        return {
            "type": "IfStmt",
            "cond": self.cond.to_dict(),
            "then": self.then_block.to_dict(),
            "elseif": [{"cond": c.to_dict(), "block": b.to_dict()} for c, b in self.elseif_clauses],
            "else": self.else_block.to_dict() if self.else_block else None,
            "lineno": self.lineno,
        }

class WhileStmt(Node):
    def __init__(self, cond, body, lineno=None):
        self.cond = cond
        self.body = body
        self.lineno = lineno

    def to_dict(self):
        return {"type": "WhileStmt", "cond": self.cond.to_dict(),
                "body": self.body.to_dict(), "lineno": self.lineno}

class ForStmt(Node):
    def __init__(self, mutable, var_name, var_type, iterable, body, lineno=None):
        self.mutable = mutable
        self.var_name = var_name
        self.var_type = var_type    # TypeNode or None
        self.iterable = iterable    # RangeExpr or expression
        self.body = body
        self.lineno = lineno

    def to_dict(self):
        return {
            "type": "ForStmt",
            "mutable": self.mutable,
            "var": self.var_name,
            "var_type": self.var_type.to_dict() if self.var_type else None,
            "iterable": self.iterable.to_dict(),
            "body": self.body.to_dict(),
            "lineno": self.lineno,
        }

class LoopStmt(Node):
    def __init__(self, body, lineno=None):
        self.body = body
        self.lineno = lineno

    def to_dict(self):
        return {"type": "LoopStmt", "body": self.body.to_dict(), "lineno": self.lineno}

class BreakStmt(Node):
    def __init__(self, expr=None, lineno=None):
        self.expr = expr
        self.lineno = lineno

    def to_dict(self):
        return {"type": "BreakStmt",
                "expr": self.expr.to_dict() if self.expr else None,
                "lineno": self.lineno}

class ContinueStmt(Node):
    def __init__(self, lineno=None):
        self.lineno = lineno

    def to_dict(self): return {"type": "ContinueStmt", "lineno": self.lineno}

# ── Expressions ──────────────────────────────────────────────────────────────

class NumLiteral(Node):
    def __init__(self, value, lineno=None):
        self.value = value
        self.lineno = lineno

    def to_dict(self):
        return {"type": "NumLiteral", "value": self.value, "lineno": self.lineno}

class Identifier(Node):
    def __init__(self, name, lineno=None):
        self.name = name
        self.lineno = lineno

    def to_dict(self):
        return {"type": "Identifier", "name": self.name, "lineno": self.lineno}

class BinaryOp(Node):
    def __init__(self, op, left, right, lineno=None):
        self.op = op
        self.left = left
        self.right = right
        self.lineno = lineno

    def to_dict(self):
        return {"type": "BinaryOp", "op": self.op,
                "left": self.left.to_dict(), "right": self.right.to_dict(),
                "lineno": self.lineno}

class UnaryOp(Node):
    def __init__(self, op, operand, lineno=None):
        self.op = op
        self.operand = operand
        self.lineno = lineno

    def to_dict(self):
        return {"type": "UnaryOp", "op": self.op,
                "operand": self.operand.to_dict(), "lineno": self.lineno}

class IndexExpr(Node):
    """expr[index]"""
    def __init__(self, base, index, lineno=None):
        self.base = base
        self.index = index
        self.lineno = lineno

    def to_dict(self):
        return {"type": "IndexExpr", "base": self.base.to_dict(),
                "index": self.index.to_dict(), "lineno": self.lineno}

class TupleFieldExpr(Node):
    """expr.NUM"""
    def __init__(self, base, field, lineno=None):
        self.base = base
        self.field = field  # int
        self.lineno = lineno

    def to_dict(self):
        return {"type": "TupleFieldExpr", "base": self.base.to_dict(),
                "field": self.field, "lineno": self.lineno}

class ArrayExpr(Node):
    def __init__(self, elements, lineno=None):
        self.elements = elements
        self.lineno = lineno

    def to_dict(self):
        return {"type": "ArrayExpr",
                "elements": [e.to_dict() for e in self.elements],
                "lineno": self.lineno}

class TupleExpr(Node):
    def __init__(self, elements, lineno=None):
        self.elements = elements
        self.lineno = lineno

    def to_dict(self):
        return {"type": "TupleExpr",
                "elements": [e.to_dict() for e in self.elements],
                "lineno": self.lineno}

class RangeExpr(Node):
    def __init__(self, start, end, lineno=None):
        self.start = start
        self.end = end
        self.lineno = lineno

    def to_dict(self):
        return {"type": "RangeExpr",
                "start": self.start.to_dict(), "end": self.end.to_dict(),
                "lineno": self.lineno}

class IfExpr(Node):
    """if expr { block } else { block }  — used as expression (rule 7.3)"""
    def __init__(self, cond, then_block, else_block, lineno=None):
        self.cond = cond
        self.then_block = then_block
        self.else_block = else_block
        self.lineno = lineno

    def to_dict(self):
        return {
            "type": "IfExpr",
            "cond": self.cond.to_dict(),
            "then": self.then_block.to_dict(),
            "else": self.else_block.to_dict(),
            "lineno": self.lineno,
        }

class LoopExpr(Node):
    """loop { ... }  used as expression (rule 7.4), break carries value"""
    def __init__(self, body, lineno=None):
        self.body = body
        self.lineno = lineno

    def to_dict(self):
        return {"type": "LoopExpr", "body": self.body.to_dict(), "lineno": self.lineno}
