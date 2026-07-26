"""
Canonical LR(1) parser for the Rust-like language.
Produces the same AST as parser.py (PLY/LALR) and parser_rd.py (recursive descent).

Table construction is done once and cached in __pycache__/lr1_tables.pkl.
Public API:
    parse_lr1(token_list) -> (ast | None, list[dict])
    parse_lr1_sdt(token_stream) -> (ast | None, list[dict], ir)
"""

import os
import sys
import pickle

sys.path.insert(0, os.path.dirname(__file__))
from ast_nodes import *   # noqa: F401,F403

# ─────────────────────────────────────────────────────────────────────────────
# 1.  Grammar definition
# ─────────────────────────────────────────────────────────────────────────────

# Sentinel for epsilon in RHS lists
EPS = None

# Every terminal that can appear as a lookahead / shift target
_TERMINALS = {
    'FN', 'IDENT', 'LPAREN', 'RPAREN', 'ARROW', 'LBRACE', 'RBRACE',
    'COMMA', 'COLON', 'MUT', 'I32', 'AMP', 'LBRACKET', 'RBRACKET',
    'SEMI', 'NUM', 'RETURN', 'LET', 'ASSIGN', 'IF', 'ELSE',
    'WHILE', 'FOR', 'IN', 'LOOP', 'BREAK', 'CONTINUE',
    'PLUS', 'MINUS', 'STAR', 'SLASH',
    'EQ', 'NEQ', 'LT', 'GT', 'LEQ', 'GEQ',
    'DOT', 'DOTDOT',
    '$',
}

# Named non-terminals (order matters only for readability)
_NONTERMINALS = {
    "S'", 'program', 'decl_list', 'decl',
    'func_decl', 'func_head', 'func_body', 'body_stmts',
    'param_list', 'param', 'var_attr',
    'type', 'type_list',
    'stmt', 'if_stmt', 'iterable',
    'expr', 'cmp', 'add', 'mul', 'unary', 'postfix', 'primary',
    'array_elems', 'tuple_inner', 'tuple_elems',
    'arg_list',
}


class Prod:
    """A single grammar production with its semantic action."""
    __slots__ = ('id', 'lhs', 'rhs', 'fn')

    def __init__(self, pid, lhs, rhs, fn):
        self.id  = pid
        self.lhs = lhs
        self.rhs = rhs   # list of symbols (str), empty list = epsilon
        self.fn  = fn    # callable(vals) -> AST node / value


# ─────────────────────────────────────────────────────────────────────────────
# 2.  Semantic actions
# ─────────────────────────────────────────────────────────────────────────────
# vals[i] for terminals  → the Token object (has .value, .line)
# vals[i] for nonterminals → whatever their reduction returned

def _make_productions():
    P = []

    def prod(lhs, rhs, fn):
        P.append(Prod(len(P), lhs, rhs, fn))

    # 0:  S' → program
    prod("S'", ['program'],
         lambda v: v[0])

    # 1:  program → decl_list
    prod('program', ['decl_list'],
         lambda v: Program(v[0]))

    # 2:  decl_list → ε
    prod('decl_list', [],
         lambda v: [])

    # 3:  decl_list → decl_list decl
    prod('decl_list', ['decl_list', 'decl'],
         lambda v: v[0] + [v[1]])

    # 4:  decl → func_decl
    prod('decl', ['func_decl'],
         lambda v: v[0])

    # 5:  func_decl → func_head func_body
    prod('func_decl', ['func_head', 'func_body'],
         lambda v: FunctionDecl(v[0]['name'], v[0]['params'],
                                v[0]['ret_type'], v[1],
                                lineno=v[0]['lineno']))

    # 6:  func_head → FN IDENT LPAREN param_list RPAREN
    prod('func_head', ['FN', 'IDENT', 'LPAREN', 'param_list', 'RPAREN'],
         lambda v: {'name': v[1].value, 'params': v[3],
                    'ret_type': None, 'lineno': v[0].line})

    # 7:  func_head → FN IDENT LPAREN param_list RPAREN ARROW type
    prod('func_head', ['FN', 'IDENT', 'LPAREN', 'param_list', 'RPAREN', 'ARROW', 'type'],
         lambda v: {'name': v[1].value, 'params': v[3],
                    'ret_type': v[6], 'lineno': v[0].line})

    # 8:  func_body → LBRACE body_stmts RBRACE
    prod('func_body', ['LBRACE', 'body_stmts', 'RBRACE'],
         lambda v: Block(v[1][0], v[1][1]))

    # 9:  body_stmts → ε
    prod('body_stmts', [],
         lambda v: ([], None))

    # 10: body_stmts → body_stmts stmt
    prod('body_stmts', ['body_stmts', 'stmt'],
         lambda v: (v[0][0] + [v[1]], None))

    # 11: body_stmts → body_stmts expr
    prod('body_stmts', ['body_stmts', 'expr'],
         lambda v: (v[0][0], v[1]))

    # 12: param_list → ε
    prod('param_list', [],
         lambda v: [])

    # 13: param_list → param
    prod('param_list', ['param'],
         lambda v: [v[0]])

    # 14: param_list → param COMMA param_list
    prod('param_list', ['param', 'COMMA', 'param_list'],
         lambda v: [v[0]] + v[2])

    # 15: param → var_attr IDENT COLON type
    prod('param', ['var_attr', 'IDENT', 'COLON', 'type'],
         lambda v: Param(v[0], v[1].value, v[3], lineno=v[1].line))

    # 16: var_attr → MUT
    prod('var_attr', ['MUT'],
         lambda v: True)

    # 17: var_attr → ε
    prod('var_attr', [],
         lambda v: False)

    # 18: type → I32
    prod('type', ['I32'],
         lambda v: TypeI32())

    # 19: type → AMP type
    prod('type', ['AMP', 'type'],
         lambda v: TypeRef(False, v[1]))

    # 20: type → AMP MUT type
    prod('type', ['AMP', 'MUT', 'type'],
         lambda v: TypeRef(True, v[2]))

    # 21: type → LBRACKET type SEMI NUM RBRACKET
    prod('type', ['LBRACKET', 'type', 'SEMI', 'NUM', 'RBRACKET'],
         lambda v: TypeArray(v[1], int(v[3].value)))

    # 22: type → LPAREN type_list RPAREN
    prod('type', ['LPAREN', 'type_list', 'RPAREN'],
         lambda v: TypeTuple(v[1]))

    # 23: type_list → ε
    prod('type_list', [],
         lambda v: [])

    # 24: type_list → type
    prod('type_list', ['type'],
         lambda v: [v[0]])

    # 25: type_list → type COMMA type_list
    prod('type_list', ['type', 'COMMA', 'type_list'],
         lambda v: [v[0]] + v[2])

    # 26: stmt → SEMI
    prod('stmt', ['SEMI'],
         lambda v: EmptyStmt())

    # 27: stmt → RETURN SEMI
    prod('stmt', ['RETURN', 'SEMI'],
         lambda v: ReturnStmt(None, lineno=v[0].line))

    # 28: stmt → RETURN expr SEMI
    prod('stmt', ['RETURN', 'expr', 'SEMI'],
         lambda v: ReturnStmt(v[1], lineno=v[0].line))

    # 29: stmt → LET var_attr IDENT SEMI
    prod('stmt', ['LET', 'var_attr', 'IDENT', 'SEMI'],
         lambda v: LetStmt(v[1], v[2].value, None, None, lineno=v[0].line))

    # 30: stmt → LET var_attr IDENT COLON type SEMI
    prod('stmt', ['LET', 'var_attr', 'IDENT', 'COLON', 'type', 'SEMI'],
         lambda v: LetStmt(v[1], v[2].value, v[4], None, lineno=v[0].line))

    # 31: stmt → LET var_attr IDENT ASSIGN expr SEMI
    prod('stmt', ['LET', 'var_attr', 'IDENT', 'ASSIGN', 'expr', 'SEMI'],
         lambda v: LetStmt(v[1], v[2].value, None, v[4], lineno=v[0].line))

    # 32: stmt → LET var_attr IDENT COLON type ASSIGN expr SEMI
    prod('stmt', ['LET', 'var_attr', 'IDENT', 'COLON', 'type', 'ASSIGN', 'expr', 'SEMI'],
         lambda v: LetStmt(v[1], v[2].value, v[4], v[6], lineno=v[0].line))

    # 33: stmt → expr ASSIGN expr SEMI
    prod('stmt', ['expr', 'ASSIGN', 'expr', 'SEMI'],
         lambda v: AssignStmt(v[0], v[2], lineno=getattr(v[0], 'lineno', None)))

    # 34: stmt → expr SEMI
    prod('stmt', ['expr', 'SEMI'],
         lambda v: ExprStmt(v[0], lineno=getattr(v[0], 'lineno', None)))

    # 35: stmt → if_stmt
    prod('stmt', ['if_stmt'],
         lambda v: v[0])

    # 36: stmt → WHILE expr func_body
    prod('stmt', ['WHILE', 'expr', 'func_body'],
         lambda v: WhileStmt(v[1], v[2], lineno=v[0].line))

    # 37: stmt → FOR var_attr IDENT IN iterable func_body
    prod('stmt', ['FOR', 'var_attr', 'IDENT', 'IN', 'iterable', 'func_body'],
         lambda v: ForStmt(v[1], v[2].value, None, v[4], v[5], lineno=v[0].line))

    # 38: stmt → FOR var_attr IDENT COLON type IN iterable func_body
    prod('stmt', ['FOR', 'var_attr', 'IDENT', 'COLON', 'type', 'IN', 'iterable', 'func_body'],
         lambda v: ForStmt(v[1], v[2].value, v[4], v[6], v[7], lineno=v[0].line))

    # 39: stmt → LOOP func_body
    prod('stmt', ['LOOP', 'func_body'],
         lambda v: LoopStmt(v[1], lineno=v[0].line))

    # 40: stmt → BREAK SEMI
    prod('stmt', ['BREAK', 'SEMI'],
         lambda v: BreakStmt(None, lineno=v[0].line))

    # 41: stmt → BREAK expr SEMI
    prod('stmt', ['BREAK', 'expr', 'SEMI'],
         lambda v: BreakStmt(v[1], lineno=v[0].line))

    # 42: stmt → CONTINUE SEMI
    prod('stmt', ['CONTINUE', 'SEMI'],
         lambda v: ContinueStmt(lineno=v[0].line))

    # 43: if_stmt → IF expr func_body
    prod('if_stmt', ['IF', 'expr', 'func_body'],
         lambda v: IfStmt(v[1], v[2], [], None, lineno=v[0].line))

    # 44: if_stmt → IF expr func_body ELSE func_body
    prod('if_stmt', ['IF', 'expr', 'func_body', 'ELSE', 'func_body'],
         lambda v: IfStmt(v[1], v[2], [], v[4], lineno=v[0].line))

    # 45: if_stmt → IF expr func_body ELSE if_stmt
    prod('if_stmt', ['IF', 'expr', 'func_body', 'ELSE', 'if_stmt'],
         lambda v: IfStmt(v[1], v[2],
                          [(v[4].cond, v[4].then_block)] + v[4].elseif_clauses,
                          v[4].else_block, lineno=v[0].line))

    # 46: iterable → expr DOTDOT expr
    prod('iterable', ['expr', 'DOTDOT', 'expr'],
         lambda v: RangeExpr(v[0], v[2], lineno=getattr(v[0], 'lineno', None)))

    # 47: iterable → expr
    prod('iterable', ['expr'],
         lambda v: v[0])

    # 48: expr → cmp
    prod('expr', ['cmp'],
         lambda v: v[0])

    # 49: cmp → add
    prod('cmp', ['add'],
         lambda v: v[0])

    # 50: cmp → cmp EQ add
    prod('cmp', ['cmp', 'EQ', 'add'],
         lambda v: BinaryOp('==', v[0], v[2], lineno=v[1].line))

    # 51: cmp → cmp NEQ add
    prod('cmp', ['cmp', 'NEQ', 'add'],
         lambda v: BinaryOp('!=', v[0], v[2], lineno=v[1].line))

    # 52: cmp → cmp LT add
    prod('cmp', ['cmp', 'LT', 'add'],
         lambda v: BinaryOp('<', v[0], v[2], lineno=v[1].line))

    # 53: cmp → cmp GT add
    prod('cmp', ['cmp', 'GT', 'add'],
         lambda v: BinaryOp('>', v[0], v[2], lineno=v[1].line))

    # 54: cmp → cmp LEQ add
    prod('cmp', ['cmp', 'LEQ', 'add'],
         lambda v: BinaryOp('<=', v[0], v[2], lineno=v[1].line))

    # 55: cmp → cmp GEQ add
    prod('cmp', ['cmp', 'GEQ', 'add'],
         lambda v: BinaryOp('>=', v[0], v[2], lineno=v[1].line))

    # 56: add → mul
    prod('add', ['mul'],
         lambda v: v[0])

    # 57: add → add PLUS mul
    prod('add', ['add', 'PLUS', 'mul'],
         lambda v: BinaryOp('+', v[0], v[2], lineno=v[1].line))

    # 58: add → add MINUS mul
    prod('add', ['add', 'MINUS', 'mul'],
         lambda v: BinaryOp('-', v[0], v[2], lineno=v[1].line))

    # 59: mul → unary
    prod('mul', ['unary'],
         lambda v: v[0])

    # 60: mul → mul STAR unary
    prod('mul', ['mul', 'STAR', 'unary'],
         lambda v: BinaryOp('*', v[0], v[2], lineno=v[1].line))

    # 61: mul → mul SLASH unary
    prod('mul', ['mul', 'SLASH', 'unary'],
         lambda v: BinaryOp('/', v[0], v[2], lineno=v[1].line))

    # 62: unary → postfix
    prod('unary', ['postfix'],
         lambda v: v[0])

    # 63: unary → MINUS unary
    prod('unary', ['MINUS', 'unary'],
         lambda v: UnaryOp('-', v[1], lineno=v[0].line))

    # 64: unary → STAR unary
    prod('unary', ['STAR', 'unary'],
         lambda v: UnaryOp('*', v[1], lineno=v[0].line))

    # 65: unary → AMP MUT unary
    prod('unary', ['AMP', 'MUT', 'unary'],
         lambda v: UnaryOp('&mut', v[2], lineno=v[0].line))

    # 66: unary → AMP unary
    prod('unary', ['AMP', 'unary'],
         lambda v: UnaryOp('&', v[1], lineno=v[0].line))

    # 67: postfix → primary
    prod('postfix', ['primary'],
         lambda v: v[0])

    # 68: postfix → postfix LBRACKET expr RBRACKET
    prod('postfix', ['postfix', 'LBRACKET', 'expr', 'RBRACKET'],
         lambda v: IndexExpr(v[0], v[2], lineno=v[1].line))

    # 69: postfix → postfix DOT NUM
    prod('postfix', ['postfix', 'DOT', 'NUM'],
         lambda v: TupleFieldExpr(v[0], int(v[2].value), lineno=v[1].line))

    # 70: primary → NUM
    prod('primary', ['NUM'],
         lambda v: NumLiteral(int(v[0].value), lineno=v[0].line))

    # 71: primary → IDENT  (plain identifier)
    prod('primary', ['IDENT'],
         lambda v: Identifier(v[0].value, lineno=v[0].line))

    # 71b: primary → IDENT LPAREN arg_list RPAREN  (function call, rule 3.5)
    prod('primary', ['IDENT', 'LPAREN', 'arg_list', 'RPAREN'],
         lambda v: CallExpr(v[0].value, v[2], lineno=v[0].line))

    # 72: primary → LPAREN expr RPAREN   (returns inner expr, NOT TupleExpr)
    prod('primary', ['LPAREN', 'expr', 'RPAREN'],
         lambda v: v[1])

    # 73: primary → LPAREN tuple_inner RPAREN
    prod('primary', ['LPAREN', 'tuple_inner', 'RPAREN'],
         lambda v: TupleExpr(v[1], lineno=v[0].line))

    # 74: primary → LBRACKET array_elems RBRACKET
    prod('primary', ['LBRACKET', 'array_elems', 'RBRACKET'],
         lambda v: ArrayExpr(v[1], lineno=v[0].line))

    # 75: primary → func_body
    prod('primary', ['func_body'],
         lambda v: v[0])

    # 76: primary → IF expr func_body ELSE func_body   (IfExpr)
    prod('primary', ['IF', 'expr', 'func_body', 'ELSE', 'func_body'],
         lambda v: IfExpr(v[1], v[2], v[4], lineno=v[0].line))

    # 77: primary → LOOP func_body   (LoopExpr)
    prod('primary', ['LOOP', 'func_body'],
         lambda v: LoopExpr(v[1], lineno=v[0].line))

    # 78: array_elems → ε
    prod('array_elems', [],
         lambda v: [])

    # 79: array_elems → expr
    prod('array_elems', ['expr'],
         lambda v: [v[0]])

    # 80: array_elems → expr COMMA array_elems
    prod('array_elems', ['expr', 'COMMA', 'array_elems'],
         lambda v: [v[0]] + v[2])

    # 81: tuple_inner → ε
    prod('tuple_inner', [],
         lambda v: [])

    # 82: tuple_inner → expr COMMA tuple_elems
    prod('tuple_inner', ['expr', 'COMMA', 'tuple_elems'],
         lambda v: [v[0]] + v[2])

    # 83: tuple_elems → ε
    prod('tuple_elems', [],
         lambda v: [])

    # 84: tuple_elems → expr
    prod('tuple_elems', ['expr'],
         lambda v: [v[0]])

    # 85: tuple_elems → expr COMMA tuple_elems
    prod('tuple_elems', ['expr', 'COMMA', 'tuple_elems'],
         lambda v: [v[0]] + v[2])

    # 86-88: arg_list  (for function calls)
    prod('arg_list', [],
         lambda v: [])
    prod('arg_list', ['expr'],
         lambda v: [v[0]])
    prod('arg_list', ['expr', 'COMMA', 'arg_list'],
         lambda v: [v[0]] + v[2])

    return P


PRODS = _make_productions()

# Index productions by LHS for quick lookup
_prod_by_lhs: dict[str, list[Prod]] = {}
for _p in PRODS:
    _prod_by_lhs.setdefault(_p.lhs, []).append(_p)

# ─────────────────────────────────────────────────────────────────────────────
# 3.  FIRST sets
# ─────────────────────────────────────────────────────────────────────────────

def _compute_first() -> dict[str, set[str]]:
    """Compute FIRST sets for all grammar symbols. ε is represented as None."""
    first: dict[str, set] = {nt: set() for nt in _NONTERMINALS}
    for t in _TERMINALS:
        first[t] = {t}

    changed = True
    while changed:
        changed = False
        for p in PRODS:
            if p.lhs == "S'":
                continue
            # Add FIRST(rhs) - {ε} ∪ (ε if all rhs derive ε)
            old_size = len(first[p.lhs])
            all_eps = True
            for sym in p.rhs:
                sym_first = first.get(sym, {sym})
                first[p.lhs] |= (sym_first - {None})
                if None not in sym_first:
                    all_eps = False
                    break
            if all_eps:
                first[p.lhs].add(None)
            if len(first[p.lhs]) != old_size:
                changed = True
    return first


_FIRST = _compute_first()


def first_of_sequence(syms: list) -> set[str]:
    """Return FIRST of a sequence of symbols (terminals/nonterminals).
    Each sym is a grammar symbol string; None / '$' treated literally.
    Returns a set of terminal strings (including '$' but not None).
    """
    result: set[str] = set()
    for sym in syms:
        if sym is None:
            # Should not normally appear in a rhs list, skip
            result.add(None)
            break
        sym_first = _FIRST.get(sym, {sym})
        result |= (sym_first - {None})
        if None not in sym_first:
            return result
    result.add(None)  # all symbols derive ε
    return result


# ─────────────────────────────────────────────────────────────────────────────
# 4.  LR(1) canonical collection
# ─────────────────────────────────────────────────────────────────────────────
# LR(1) item: (prod_id: int, dot: int, lookahead: str)

def _closure(items: frozenset) -> frozenset:
    """Compute the closure of a set of LR(1) items."""
    worklist = list(items)
    result = set(items)
    while worklist:
        pid, dot, la = worklist.pop()
        rhs = PRODS[pid].rhs
        if dot >= len(rhs):
            continue
        B = rhs[dot]
        if B not in _NONTERMINALS:
            continue  # terminal — no closure expansion
        # β = rhs[dot+1:] + [la]
        beta = rhs[dot + 1:] + [la]
        new_las = first_of_sequence(beta) - {None}
        for bprod in _prod_by_lhs.get(B, []):
            for new_la in new_las:
                item = (bprod.id, 0, new_la)
                if item not in result:
                    result.add(item)
                    worklist.append(item)
    return frozenset(result)


def _goto(state: frozenset, sym: str) -> frozenset:
    """Compute GOTO(state, sym)."""
    kernel = frozenset(
        (pid, dot + 1, la)
        for pid, dot, la in state
        if dot < len(PRODS[pid].rhs) and PRODS[pid].rhs[dot] == sym
    )
    if not kernel:
        return frozenset()
    return _closure(kernel)


def _build_canonical_collection():
    """BFS to build all LR(1) states and transitions."""
    # Start item: S' → • program, $
    start_item = (0, 0, '$')   # prod 0 is S' → program
    start_state = _closure(frozenset([start_item]))

    # state_id: frozenset → int
    state_id: dict[frozenset, int] = {start_state: 0}
    states: list[frozenset] = [start_state]
    # transitions[state_int][symbol] = target_state_int
    transitions: list[dict] = [{}]

    worklist = [start_state]
    while worklist:
        state = worklist.pop(0)
        sid = state_id[state]
        # Collect all symbols that appear at the dot in this state
        symbols: set[str] = set()
        for pid, dot, la in state:
            rhs = PRODS[pid].rhs
            if dot < len(rhs):
                symbols.add(rhs[dot])
        for sym in symbols:
            next_state = _goto(state, sym)
            if not next_state:
                continue
            if next_state not in state_id:
                new_id = len(states)
                state_id[next_state] = new_id
                states.append(next_state)
                transitions.append({})
                worklist.append(next_state)
            transitions[sid][sym] = state_id[next_state]

    return states, transitions


def _build_tables():
    """Build ACTION and GOTO tables from the canonical LR(1) collection."""
    print("[LR1] building tables...", flush=True)
    states, transitions = _build_canonical_collection()

    # action[state_int][terminal] = ('s', tgt) | ('r', pid) | ('acc',)
    action: list[dict] = [{} for _ in states]
    # goto_table[state_int][nonterminal] = tgt_state_int
    goto_table: list[dict] = [{} for _ in states]

    conflicts = []

    for sid, state in enumerate(states):
        # Shift / accept from transitions
        for sym, tgt in transitions[sid].items():
            if sym in _TERMINALS:
                action[sid][sym] = ('s', tgt)
            elif sym in _NONTERMINALS:
                goto_table[sid][sym] = tgt

        # Reduce from completed items
        for pid, dot, la in state:
            p = PRODS[pid]
            if dot < len(p.rhs):
                continue  # not completed
            if p.lhs == "S'" and la == '$':
                action[sid]['$'] = ('acc',)
                continue
            # Propose reduce by pid on lookahead la
            existing = action[sid].get(la)
            if existing is None:
                action[sid][la] = ('r', pid)
            elif existing[0] == 's':
                # Shift-reduce conflict: prefer shift (resolves dangling-else)
                conflicts.append(
                    f"state {sid}: S/R conflict on '{la}' "
                    f"(shift wins over reduce prod {pid})"
                )
                # keep shift — do nothing
            elif existing[0] == 'r':
                # Reduce-reduce conflict: prefer lower-numbered production
                if pid < existing[1]:
                    action[sid][la] = ('r', pid)
                    conflicts.append(
                        f"state {sid}: R/R conflict on '{la}' "
                        f"(prod {pid} wins over prod {existing[1]})"
                    )
                else:
                    conflicts.append(
                        f"state {sid}: R/R conflict on '{la}' "
                        f"(prod {existing[1]} wins over prod {pid})"
                    )

    if conflicts:
        print(f"[LR1] {len(conflicts)} conflict(s) resolved:", flush=True)
        for c in conflicts[:20]:
            print(f"  {c}", flush=True)
        if len(conflicts) > 20:
            print(f"  ... ({len(conflicts) - 20} more)", flush=True)

    print(f"[LR1] {len(states)} states built.", flush=True)
    return action, goto_table


# ─────────────────────────────────────────────────────────────────────────────
# 5.  Table caching
# ─────────────────────────────────────────────────────────────────────────────

_CACHE_DIR  = os.path.join(os.path.dirname(__file__), '__pycache__')
_CACHE_FILE = os.path.join(_CACHE_DIR, 'lr1_tables.pkl')

_action_table = None
_goto_table   = None


def _get_tables():
    global _action_table, _goto_table
    if _action_table is not None:
        return _action_table, _goto_table

    # Try loading from cache
    if os.path.exists(_CACHE_FILE):
        try:
            with open(_CACHE_FILE, 'rb') as f:
                _action_table, _goto_table = pickle.load(f)
            return _action_table, _goto_table
        except Exception:
            pass  # Cache corrupt — rebuild

    # Build from scratch
    _action_table, _goto_table = _build_tables()

    # Save to cache
    os.makedirs(_CACHE_DIR, exist_ok=True)
    try:
        with open(_CACHE_FILE, 'wb') as f:
            pickle.dump((_action_table, _goto_table), f)
    except Exception as e:
        print(f"[LR1] warning: could not save cache: {e}", flush=True)

    return _action_table, _goto_table


# ─────────────────────────────────────────────────────────────────────────────
# 6.  LR(1) parsing algorithm
# ─────────────────────────────────────────────────────────────────────────────

def _parse_tokens(token_stream, action_tbl, goto_tbl, irgen=None):
    """
    Standard stack-based LR(1) parse.
    Returns (result_value, errors_list).
    """
    # Pull tokens only when the LR driver needs a new lookahead.
    source = iter(token_stream)
    toks = []
    ended = False

    errors = []

    class _EOF:
        type = '$'
        value = '$'
        line  = 0
        col   = 0

    _eof_tok = _EOF()

    def cur_tok(pos):
        nonlocal ended
        while len(toks) <= pos and not ended:
            try:
                token = next(source)
            except StopIteration:
                ended = True
                break
            if token.type == 'END':
                ended = True
                break
            toks.append(token)
        return toks[pos] if pos < len(toks) else _eof_tok

    def cur_sym(pos):
        return cur_tok(pos).type

    state_stack = [0]
    val_stack   = [None]
    pos = 0

    while True:
        state = state_stack[-1]
        sym   = cur_sym(pos)
        act   = action_tbl[state].get(sym)

        if act is None:
            # Error recovery: record error and skip token
            t = cur_tok(pos)
            if sym == '$':
                errors.append({
                    'msg': 'Syntax error at end of input',
                    'line': t.line, 'col': getattr(t, 'col', 0),
                })
                break
            errors.append({
                'msg': f"Syntax error at '{t.value}'",
                'line': t.line, 'col': getattr(t, 'col', 0),
            })
            # Try to skip tokens until we find something actionable
            pos += 1
            continue

        if act == ('acc',):
            # Accept: result is on top of val_stack (under the start-state sentinel)
            return val_stack[-1], errors

        if act[0] == 's':
            # Shift
            _, tgt = act
            state_stack.append(tgt)
            val_stack.append(cur_tok(pos))
            pos += 1

        elif act[0] == 'r':
            # Reduce
            _, pid = act
            p = PRODS[pid]
            n = len(p.rhs)
            if n > 0:
                vals = val_stack[-n:]
                del state_stack[-n:]
                del val_stack[-n:]
            else:
                vals = []
            try:
                result = p.fn(vals)
                # Syntax-directed translation: a function is emitted as soon
                # as func_decl is reduced, before the whole program accepts.
                if irgen is not None and p.lhs == 'func_decl' \
                        and isinstance(result, FunctionDecl) and not errors:
                    irgen._func(result)
            except Exception as e:
                errors.append({
                    'msg': f'Internal error in action for prod {pid}: {e}',
                    'line': 0, 'col': 0,
                })
                result = None
            # GOTO
            top_state = state_stack[-1]
            new_state = goto_tbl[top_state].get(p.lhs)
            if new_state is None:
                errors.append({
                    'msg': f'Missing GOTO entry for state {top_state} on {p.lhs!r}',
                    'line': 0, 'col': 0,
                })
                break
            state_stack.append(new_state)
            val_stack.append(result)

    # If we exit the loop without accept, return None
    # The S' → program reduction's value ends up in val_stack[-1]
    # when the parse completes normally via 'acc'; if errors, best-effort:
    if len(val_stack) >= 2:
        return val_stack[-1], errors
    return None, errors


# ─────────────────────────────────────────────────────────────────────────────
# 7.  Public API
# ─────────────────────────────────────────────────────────────────────────────

def parse_lr1(token_list):
    """
    Canonical LR(1) parser.
    Returns (ast, errors) — same contract as parse() and parse_rd().
    ast is a Program node or None if the input is fatally malformed.
    errors is a list of dicts with 'msg', 'line', 'col' keys.
    """
    action_tbl, goto_tbl = _get_tables()
    result, errors = _parse_tokens(token_list, action_tbl, goto_tbl)
    if errors:
        return None, errors
    return result, []


def parse_lr1_sdt(token_stream):
    """Canonical LR(1) with lazy lexing and reduction-time IR generation."""
    from codegen import IRGen

    action_tbl, goto_tbl = _get_tables()
    irgen = IRGen()
    result, errors = _parse_tokens(
        token_stream, action_tbl, goto_tbl, irgen=irgen)
    if errors:
        return None, errors, []
    ir = [q.to_dict() for q in irgen.quads]
    return result, [], ir


# ─────────────────────────────────────────────────────────────────────────────
# 8.  Standalone smoke-test
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    import json
    sys.path.insert(0, os.path.dirname(__file__))
    from lexer import lex

    _src = """
    fn add(a: i32, b: i32) -> i32 {
        a + b
    }

    fn main() {
        let x: i32 = 1;
        let mut y: i32 = 2;
        let z = add(x, y);
        if x < y {
            return z;
        } else {
            return 0;
        }
    }
    """
    _toks, _lex_errs = lex(_src)
    if _lex_errs:
        print("Lex errors:", _lex_errs)
    _ast, _errs = parse_lr1(_toks)
    if _errs:
        print("Parse errors:", _errs)
    else:
        print(json.dumps(_ast.to_dict(), indent=2))
