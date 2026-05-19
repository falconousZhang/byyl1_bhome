"""Recursive-descent parser (手写递归下降) for the Rust-like language.
Produces the same AST as the LALR(1) PLY parser.
Uses precedence-climbing (Pratt) for binary expressions.
"""

import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from ast_nodes import *


class _Parser:
    _PREC = {
        'EQ': 1, 'NEQ': 1,
        'LT': 2, 'GT': 2, 'LEQ': 2, 'GEQ': 2,
        'PLUS': 3, 'MINUS': 3,
        'STAR': 4, 'SLASH': 4,
    }
    _OP = {
        'PLUS': '+', 'MINUS': '-', 'STAR': '*', 'SLASH': '/',
        'EQ': '==', 'NEQ': '!=', 'LT': '<', 'GT': '>',
        'LEQ': '<=', 'GEQ': '>=',
    }

    def __init__(self, tokens):
        self._toks  = [t for t in tokens if t.type != 'END']
        self._pos   = 0
        self.errors = []

    # ── stream helpers ────────────────────────────────────────────────────────

    def _peek(self, off=0):
        i = self._pos + off
        return self._toks[i].type if i < len(self._toks) else 'END'

    def _cur(self):
        return self._toks[self._pos] if self._pos < len(self._toks) else None

    def _adv(self):
        t = self._cur()
        if t: self._pos += 1
        return t

    def _expect(self, typ):
        t = self._cur()
        if t and t.type == typ:
            self._pos += 1
            return t
        line = t.line if t else 0
        col  = getattr(t, 'col', 0) if t else 0
        val  = t.value if t else 'EOF'
        self.errors.append({'msg': f"Expected '{typ}', got '{val}'",
                            'line': line, 'col': col})
        return None

    def _line(self):
        t = self._cur()
        return t.line if t else 0

    # ── program ───────────────────────────────────────────────────────────────

    def parse_program(self):
        decls = []
        while self._peek() != 'END':
            if self._peek() == 'FN':
                decls.append(self._func())
            else:
                t = self._adv()
                if t:
                    self.errors.append({'msg': f"Unexpected '{t.value}'",
                                        'line': t.line, 'col': getattr(t, 'col', 0)})
        return Program(decls)

    def _func(self):
        fn  = self._expect('FN')
        ln  = fn.line if fn else 0
        nm  = self._expect('IDENT')
        name = nm.value if nm else ''
        self._expect('LPAREN')
        params = self._param_list()
        self._expect('RPAREN')
        ret = None
        if self._peek() == 'ARROW':
            self._adv(); ret = self._type()
        body = self._block()
        return FunctionDecl(name, params, ret, body, lineno=ln)

    # ── parameters ────────────────────────────────────────────────────────────

    def _param_list(self):
        ps = []
        if self._peek() == 'RPAREN':
            return ps
        ps.append(self._param())
        while self._peek() == 'COMMA':
            self._adv()
            if self._peek() == 'RPAREN': break
            ps.append(self._param())
        return ps

    def _param(self):
        ln  = self._line()
        mut = False
        if self._peek() == 'MUT':
            self._adv(); mut = True
        nm   = self._expect('IDENT')
        name = nm.value if nm else ''
        self._expect('COLON')
        return Param(mut, name, self._type(), lineno=ln)

    # ── types ─────────────────────────────────────────────────────────────────

    def _type(self):
        p = self._peek()
        if p == 'I32':
            self._adv(); return TypeI32()
        if p == 'AMP':
            self._adv()
            if self._peek() == 'MUT':
                self._adv(); return TypeRef(True, self._type())
            return TypeRef(False, self._type())
        if p == 'LBRACKET':
            self._adv()
            elem = self._type()
            self._expect('SEMI')
            n    = self._expect('NUM')
            size = int(n.value) if n else 0
            self._expect('RBRACKET')
            return TypeArray(elem, size)
        if p == 'LPAREN':
            self._adv()
            types = []
            if self._peek() != 'RPAREN':
                types.append(self._type())
                while self._peek() == 'COMMA':
                    self._adv()
                    if self._peek() == 'RPAREN': break
                    types.append(self._type())
            self._expect('RPAREN')
            return TypeTuple(types)
        t   = self._cur()
        val = t.value if t else 'EOF'
        self.errors.append({'msg': f"Expected type, got '{val}'",
                            'line': t.line if t else 0, 'col': 0})
        return TypeI32()

    # ── block ─────────────────────────────────────────────────────────────────

    def _block(self):
        self._expect('LBRACE')
        stmts, tail = [], None
        while self._peek() not in ('RBRACE', 'END'):
            r = self._stmt_or_tail()
            if r is None: break
            if isinstance(r, tuple) and r[0] == '__tail__':
                tail = r[1]; break
            stmts.append(r)
        self._expect('RBRACE')
        return Block(stmts, tail)

    # ── statement dispatcher ──────────────────────────────────────────────────

    def _stmt_or_tail(self):
        p = self._peek()

        if p == 'SEMI':
            self._adv(); return EmptyStmt()

        if p == 'RETURN':
            t = self._adv()
            if self._peek() == 'SEMI':
                self._adv(); return ReturnStmt(None, lineno=t.line)
            e = self._expr(); self._expect('SEMI')
            return ReturnStmt(e, lineno=t.line)

        if p == 'LET':
            t   = self._adv(); ln = t.line
            mut = False
            if self._peek() == 'MUT': self._adv(); mut = True
            nm   = self._expect('IDENT')
            name = nm.value if nm else ''
            typ  = None
            if self._peek() == 'COLON': self._adv(); typ = self._type()
            init = None
            if self._peek() == 'ASSIGN': self._adv(); init = self._expr()
            self._expect('SEMI')
            return LetStmt(mut, name, typ, init, lineno=ln)

        if p == 'WHILE':
            t = self._adv()
            return WhileStmt(self._expr(), self._block(), lineno=t.line)

        if p == 'FOR':
            return self._for_stmt()

        if p == 'LOOP':
            return self._loop_stmt_or_tail()

        if p == 'IF':
            return self._if_stmt_or_tail()

        if p == 'BREAK':
            t = self._adv()
            if self._peek() == 'SEMI':
                self._adv(); return BreakStmt(None, lineno=t.line)
            e = self._expr(); self._expect('SEMI')
            return BreakStmt(e, lineno=t.line)

        if p == 'CONTINUE':
            t = self._adv(); self._expect('SEMI')
            return ContinueStmt(lineno=t.line)

        # Expression or assignment
        e = self._expr()
        if self._peek() == 'ASSIGN':
            self._adv()
            rhs = self._expr(); self._expect('SEMI')
            return AssignStmt(e, rhs, lineno=getattr(e, 'lineno', None))
        if self._peek() == 'SEMI':
            self._adv()
            return ExprStmt(e, lineno=getattr(e, 'lineno', None))
        return ('__tail__', e)

    def _for_stmt(self):
        t  = self._adv(); ln = t.line
        mut = False
        if self._peek() == 'MUT': self._adv(); mut = True
        nm   = self._expect('IDENT')
        name = nm.value if nm else ''
        vtyp = None
        if self._peek() == 'COLON': self._adv(); vtyp = self._type()
        self._expect('IN')
        # iterable: expr [DOTDOT expr]
        start = self._expr()
        if self._peek() == 'DOTDOT':
            self._adv()
            end = self._expr()
            iterable = RangeExpr(start, end, lineno=getattr(start, 'lineno', None))
        else:
            iterable = start
        return ForStmt(mut, name, vtyp, iterable, self._block(), lineno=ln)

    def _loop_stmt_or_tail(self):
        t    = self._adv()
        body = self._block()
        if self._peek() == 'SEMI':
            self._adv()
        # Always LoopStmt in statement context — matches LALR reduce-reduce resolution
        return LoopStmt(body, lineno=t.line)

    def _if_stmt_or_tail(self):
        t    = self._adv(); ln = t.line
        cond = self._expr()
        then = self._block()

        if self._peek() != 'ELSE':
            return IfStmt(cond, then, [], None, lineno=ln)

        self._adv()  # ELSE

        if self._peek() == 'IF':
            # else-if chain: flatten into elseif_clauses, always IfStmt
            inner = self._if_stmt_or_tail()  # always returns IfStmt now
            if isinstance(inner, IfStmt):
                return IfStmt(cond, then,
                              [(inner.cond, inner.then_block)] + inner.elseif_clauses,
                              inner.else_block, lineno=ln)
            return IfStmt(cond, then, [], None, lineno=ln)

        else_block = self._block()
        # Always IfStmt in statement context — matches LALR reduce-reduce resolution
        return IfStmt(cond, then, [], else_block, lineno=ln)

    # ── expressions (precedence climbing) ────────────────────────────────────

    def _expr(self, min_prec=0):
        left = self._unary()
        while True:
            p = self._peek()
            if p not in self._PREC or self._PREC[p] <= min_prec:
                break
            op_tok = self._adv()
            left   = BinaryOp(self._OP[op_tok.type], left,
                               self._expr(self._PREC[op_tok.type]),
                               lineno=op_tok.line)
        return left

    def _unary(self):
        p = self._peek()
        if p == 'MINUS':
            t = self._adv(); return UnaryOp('-', self._unary(), lineno=t.line)
        if p == 'STAR':
            t = self._adv(); return UnaryOp('*', self._unary(), lineno=t.line)
        if p == 'AMP':
            t = self._adv()
            if self._peek() == 'MUT':
                self._adv(); return UnaryOp('&mut', self._unary(), lineno=t.line)
            return UnaryOp('&', self._unary(), lineno=t.line)
        return self._postfix()

    def _postfix(self):
        node = self._primary()
        while True:
            if self._peek() == 'LBRACKET':
                t   = self._adv()
                idx = self._expr()
                self._expect('RBRACKET')
                node = IndexExpr(node, idx, lineno=t.line)
            elif self._peek() == 'DOT':
                t = self._adv()
                n = self._expect('NUM')
                node = TupleFieldExpr(node, int(n.value) if n else 0, lineno=t.line)
            else:
                break
        return node

    def _primary(self):
        p = self._peek()
        t = self._cur()

        if p == 'NUM':
            self._adv(); return NumLiteral(int(t.value), lineno=t.line)

        if p == 'IDENT':
            self._adv(); return Identifier(t.value, lineno=t.line)

        if p == 'LPAREN':
            return self._paren_or_tuple()

        if p == 'LBRACKET':
            t2 = self._adv()
            elems = []
            if self._peek() != 'RBRACKET':
                elems.append(self._expr())
                while self._peek() == 'COMMA':
                    self._adv()
                    if self._peek() == 'RBRACKET': break
                    elems.append(self._expr())
            self._expect('RBRACKET')
            return ArrayExpr(elems, lineno=t2.line)

        if p == 'LBRACE':
            return self._block()

        if p == 'IF':
            return self._if_expr()

        if p == 'LOOP':
            t2 = self._adv()
            return LoopExpr(self._block(), lineno=t2.line)

        line = t.line if t else 0
        val  = t.value if t else 'EOF'
        self.errors.append({'msg': f"Unexpected '{val}' in expression",
                            'line': line, 'col': getattr(t, 'col', 0) if t else 0})
        self._adv()
        return NumLiteral(0, lineno=line)

    def _paren_or_tuple(self):
        t  = self._adv(); ln = t.line
        if self._peek() == 'RPAREN':
            self._adv(); return TupleExpr([], lineno=ln)
        first = self._expr()
        if self._peek() == 'RPAREN':
            self._adv(); return first
        elems = [first]
        while self._peek() == 'COMMA':
            self._adv()
            if self._peek() == 'RPAREN': break
            elems.append(self._expr())
        self._expect('RPAREN')
        return TupleExpr(elems, lineno=ln)

    def _if_expr(self):
        """if expr block else block  — requires else, used in expression context."""
        t    = self._adv(); ln = t.line
        cond = self._expr()
        then = self._block()
        self._expect('ELSE')
        if self._peek() == 'IF':
            inner      = self._if_expr()
            else_block = Block([], inner)
        else:
            else_block = self._block()
        return IfExpr(cond, then, else_block, lineno=ln)


# ── public API ────────────────────────────────────────────────────────────────

def parse_rd(token_list):
    """
    Recursive-descent parser.
    Returns (ast, errors) — same contract as parse() in parser.py.
    """
    p   = _Parser(token_list)
    ast = p.parse_program()
    if p.errors:
        return None, p.errors
    return ast, []
