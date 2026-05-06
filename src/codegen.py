"""Quadruple (四元式) intermediate code generation.

Quad format: (op, arg1, arg2, result)

Key ops:
  func_begin  name  n_params  _      function entry
  func_end    name  _         _      function exit
  param       name  _         _      declare parameter
  :=          src   _         dst    dst = src
  +/-/*/      a     b         t      t = a op b
  neg         a     _         t      t = -a
  </>/<=/>=/==/!= a b         t      t = (a op b) as 0/1
  &           var   _         t      t = &var
  &mut        var   _         t      t = &mut var
  deref       ptr   _         t      t = *ptr
  deref_write ptr   val       _      *ptr = val
  []          arr   idx       t      t = arr[idx]
  []:=        arr   idx       val    arr[idx] = val
  .           tup   n         t      t = tup.n
  .:=         tup   n         val    tup.n = val
  alloc[]     n     _         t      t = new [n]i32 on stack
  alloc()     n     _         t      t = new (n) on stack
  arr_len     arr   _         t      t = len(arr)
  label       _     _         L      define label L
  goto        _     _         L      unconditional jump to L
  if_false    cond  _         L      jump to L if cond == 0
  return      val   _         _      return val (val may be _)
"""

import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from ast_nodes import *


class Quad:
    __slots__ = ('op', 'arg1', 'arg2', 'result')

    def __init__(self, op, arg1='_', arg2='_', result='_'):
        self.op     = str(op)
        self.arg1   = str(arg1)   if arg1   is not None else '_'
        self.arg2   = str(arg2)   if arg2   is not None else '_'
        self.result = str(result) if result is not None else '_'

    def to_dict(self):
        return {'op': self.op, 'arg1': self.arg1,
                'arg2': self.arg2, 'result': self.result}

    def __repr__(self):
        return f'({self.op}, {self.arg1}, {self.arg2}, {self.result})'


class IRGen:
    def __init__(self):
        self.quads: list[Quad] = []
        self._tc = 0                    # temp counter
        self._lc = 0                    # label counter
        self._breaks:    list[str] = [] # break-target label stack
        self._conts:     list[str] = [] # continue-target label stack
        self._brk_temps: list[str] = [] # loop-expr result temp stack

    # ── helpers ───────────────────────────────────────────────────────────────

    def _t(self) -> str:
        self._tc += 1
        return f'_t{self._tc}'

    def _l(self) -> str:
        self._lc += 1
        return f'L{self._lc}'

    def _e(self, op, a1='_', a2='_', r='_'):
        self.quads.append(Quad(op, a1, a2, r))

    # ── program ───────────────────────────────────────────────────────────────

    def gen_program(self, prog: Program):
        for fn in prog.decls:
            self._func(fn)

    def _func(self, fn: FunctionDecl):
        self._e('func_begin', fn.name, str(len(fn.params)))
        for p in fn.params:
            self._e('param', p.name)
        tail = self._block(fn.body)
        if tail and tail != '_':   # tail expression used as return value
            self._e('return', tail)
        self._e('func_end', fn.name)

    # ── block ─────────────────────────────────────────────────────────────────

    def _block(self, blk: Block):
        for s in blk.stmts:
            self._stmt(s)
        if blk.tail_expr:
            return self._expr(blk.tail_expr)
        return None

    # ── statements ────────────────────────────────────────────────────────────

    def _stmt(self, node):
        if isinstance(node, EmptyStmt):
            pass
        elif isinstance(node, LetStmt):
            self._let(node)
        elif isinstance(node, AssignStmt):
            self._assign(node)
        elif isinstance(node, ReturnStmt):
            val = self._expr(node.expr) if node.expr else '_'
            self._e('return', val)
        elif isinstance(node, ExprStmt):
            self._expr(node.expr)
        elif isinstance(node, IfStmt):
            self._if_stmt(node)
        elif isinstance(node, WhileStmt):
            self._while(node)
        elif isinstance(node, ForStmt):
            self._for(node)
        elif isinstance(node, LoopStmt):
            self._loop_stmt(node)
        elif isinstance(node, BreakStmt):
            if node.expr and self._brk_temps:
                v = self._expr(node.expr)
                self._e(':=', v, '_', self._brk_temps[-1])
            self._e('goto', '_', '_', self._breaks[-1])
        elif isinstance(node, ContinueStmt):
            self._e('goto', '_', '_', self._conts[-1])

    def _let(self, n: LetStmt):
        if n.init_expr:
            v = self._expr(n.init_expr)
            self._e(':=', v, '_', n.name)

    def _assign(self, n: AssignStmt):
        val = self._expr(n.expr)
        lv  = n.lvalue
        if isinstance(lv, Identifier):
            self._e(':=', val, '_', lv.name)
        elif isinstance(lv, UnaryOp) and lv.op == '*':
            ptr = self._expr(lv.operand)
            self._e('deref_write', ptr, val)
        elif isinstance(lv, IndexExpr):
            arr = self._expr(lv.base)
            idx = self._expr(lv.index)
            self._e('[]:=', arr, idx, val)
        elif isinstance(lv, TupleFieldExpr):
            tup = self._expr(lv.base)
            self._e('.:=', tup, str(lv.field), val)

    def _if_stmt(self, n: IfStmt):
        L_end  = self._l()
        has_more = bool(n.elseif_clauses or n.else_block)
        L_next = self._l() if has_more else L_end

        cond = self._expr(n.cond)
        self._e('if_false', cond, '_', L_next)
        self._block(n.then_block)
        if has_more:
            self._e('goto', '_', '_', L_end)

        for i, (ec, eb) in enumerate(n.elseif_clauses):
            self._e('label', '_', '_', L_next)
            last  = (i == len(n.elseif_clauses) - 1)
            L_next = self._l() if (not last or n.else_block) else L_end
            cv = self._expr(ec)
            self._e('if_false', cv, '_', L_next)
            self._block(eb)
            self._e('goto', '_', '_', L_end)

        if n.else_block:
            self._e('label', '_', '_', L_next)
            self._block(n.else_block)

        self._e('label', '_', '_', L_end)

    def _while(self, n: WhileStmt):
        Ls = self._l(); Le = self._l()
        self._breaks.append(Le); self._conts.append(Ls)
        self._e('label', '_', '_', Ls)
        c = self._expr(n.cond)
        self._e('if_false', c, '_', Le)
        self._block(n.body)
        self._e('goto', '_', '_', Ls)
        self._e('label', '_', '_', Le)
        self._breaks.pop(); self._conts.pop()

    def _for(self, n: ForStmt):
        Ls = self._l(); Le = self._l()
        self._breaks.append(Le); self._conts.append(Ls)

        if isinstance(n.iterable, RangeExpr):
            sv  = self._expr(n.iterable.start)
            te  = self._t()
            ev  = self._expr(n.iterable.end)
            self._e(':=', ev, '_', te)
            self._e(':=', sv, '_', n.var_name)
            self._e('label', '_', '_', Ls)
            tc  = self._t()
            self._e('<', n.var_name, te, tc)
            self._e('if_false', tc, '_', Le)
            for s in n.body.stmts:  self._stmt(s)
            if n.body.tail_expr:    self._expr(n.body.tail_expr)
            ti  = self._t()
            self._e('+', n.var_name, '1', ti)
            self._e(':=', ti, '_', n.var_name)
            self._e('goto', '_', '_', Ls)
        else:
            arr = self._expr(n.iterable)
            tl  = self._t(); tidx = self._t()
            self._e('arr_len', arr, '_', tl)
            self._e(':=', '0', '_', tidx)
            self._e('label', '_', '_', Ls)
            tc2 = self._t()
            self._e('<', tidx, tl, tc2)
            self._e('if_false', tc2, '_', Le)
            self._e('[]', arr, tidx, n.var_name)
            for s in n.body.stmts:  self._stmt(s)
            if n.body.tail_expr:    self._expr(n.body.tail_expr)
            ti2 = self._t()
            self._e('+', tidx, '1', ti2)
            self._e(':=', ti2, '_', tidx)
            self._e('goto', '_', '_', Ls)

        self._e('label', '_', '_', Le)
        self._breaks.pop(); self._conts.pop()

    def _loop_stmt(self, n: LoopStmt):
        Ls = self._l(); Le = self._l()
        self._breaks.append(Le); self._conts.append(Ls)
        self._brk_temps.append(None)
        self._e('label', '_', '_', Ls)
        self._block(n.body)
        self._e('goto', '_', '_', Ls)
        self._e('label', '_', '_', Le)
        self._breaks.pop(); self._conts.pop(); self._brk_temps.pop()

    # ── expressions ───────────────────────────────────────────────────────────

    def _expr(self, node) -> str:
        if isinstance(node, NumLiteral):
            return str(node.value)

        if isinstance(node, Identifier):
            return node.name

        if isinstance(node, BinaryOp):
            L = self._expr(node.left)
            R = self._expr(node.right)
            t = self._t()
            self._e(node.op, L, R, t)
            return t

        if isinstance(node, UnaryOp):
            v = self._expr(node.operand)
            t = self._t()
            op = node.op
            if   op == '-':    self._e('neg',    v, '_', t)
            elif op == '&':    self._e('&',      v, '_', t)
            elif op == '&mut': self._e('&mut',   v, '_', t)
            elif op == '*':    self._e('deref',  v, '_', t)
            return t

        if isinstance(node, IndexExpr):
            arr = self._expr(node.base)
            idx = self._expr(node.index)
            t   = self._t()
            self._e('[]', arr, idx, t)
            return t

        if isinstance(node, TupleFieldExpr):
            tup = self._expr(node.base)
            t   = self._t()
            self._e('.', tup, str(node.field), t)
            return t

        if isinstance(node, ArrayExpr):
            n = len(node.elements)
            t = self._t()
            self._e('alloc[]', str(n), '_', t)
            for i, el in enumerate(node.elements):
                v = self._expr(el)
                self._e('[]:=', t, str(i), v)
            return t

        if isinstance(node, TupleExpr):
            n = len(node.elements)
            t = self._t()
            self._e('alloc()', str(n), '_', t)
            for i, el in enumerate(node.elements):
                v = self._expr(el)
                self._e('.:=', t, str(i), v)
            return t

        if isinstance(node, RangeExpr):
            s = self._expr(node.start)
            e = self._expr(node.end)
            t = self._t()
            self._e('range', s, e, t)
            return t

        if isinstance(node, Block):
            v = self._block(node)
            return v or '_'

        if isinstance(node, IfExpr):
            t   = self._t()
            Le  = self._l(); Lend = self._l()
            c   = self._expr(node.cond)
            self._e('if_false', c, '_', Le)
            v1  = self._block(node.then_block)
            if v1: self._e(':=', v1, '_', t)
            self._e('goto', '_', '_', Lend)
            self._e('label', '_', '_', Le)
            v2  = self._block(node.else_block)
            if v2: self._e(':=', v2, '_', t)
            self._e('label', '_', '_', Lend)
            return t

        if isinstance(node, LoopExpr):
            t  = self._t()
            Ls = self._l(); Le = self._l()
            self._breaks.append(Le); self._conts.append(Ls)
            self._brk_temps.append(t)
            self._e('label', '_', '_', Ls)
            self._block(node.body)
            self._e('goto', '_', '_', Ls)
            self._e('label', '_', '_', Le)
            self._breaks.pop(); self._conts.pop(); self._brk_temps.pop()
            return t

        return '_'


# ── Public API ────────────────────────────────────────────────────────────────

def generate_ir(ast: Program) -> list[dict]:
    g = IRGen()
    g.gen_program(ast)
    return [q.to_dict() for q in g.quads]
