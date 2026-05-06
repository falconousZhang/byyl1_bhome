"""
LALR(1) parser using PLY for the Rust-like language.
Covers grammar rules: 0.x, 1.x, 2.x, 3.x, 4.x, 5.x, 6.x, 7.x, 8.x, 9.x
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import ply.lex as lex
import ply.yacc as yacc
from ast_nodes import *

# ════════════════════════════════════════════════════════════════════════════
# PLY LEXER  (wraps our hand-written lexer so PLY can drive it)
# ════════════════════════════════════════════════════════════════════════════

# All token types PLY needs to know
tokens = (
    'IDENT', 'NUM',
    # keywords
    'I32', 'LET', 'IF', 'ELSE', 'WHILE', 'RETURN',
    'MUT', 'FN', 'FOR', 'IN', 'LOOP', 'BREAK', 'CONTINUE',
    # operators
    'PLUS', 'MINUS', 'STAR', 'SLASH',
    'EQ', 'NEQ', 'GEQ', 'LEQ', 'GT', 'LT',
    'ASSIGN', 'AMP', 'AND',
    # delimiters
    'LPAREN', 'RPAREN', 'LBRACE', 'RBRACE', 'LBRACKET', 'RBRACKET',
    # separators
    'SEMI', 'COLON', 'COMMA',
    # special
    'ARROW', 'DOT', 'DOTDOT',
    'END',
)

# Operator precedence (lowest → highest)
# This resolves dangling-else and unary * vs binary * conflicts.
precedence = (
    ('nonassoc', 'IFX'),          # sentinel for if-without-else
    ('nonassoc', 'ELSE'),
    ('left',  'EQ', 'NEQ'),
    ('left',  'LT', 'GT', 'LEQ', 'GEQ'),
    ('left',  'PLUS', 'MINUS'),
    ('left',  'STAR', 'SLASH'),
    ('right', 'UMINUS', 'UDEREF', 'UREF', 'UREFMUT'),  # unary ops
    ('left',  'LBRACKET', 'DOT'),  # index / tuple-field (highest postfix)
)


class PLYLexerAdapter:
    """Feed pre-tokenised list into PLY's token() interface."""
    def __init__(self, token_list):
        self._tokens = token_list
        self._pos = 0

    def token(self):
        while self._pos < len(self._tokens):
            t = self._tokens[self._pos]
            self._pos += 1
            if t.type == 'END':
                return None
            tok = lex.LexToken()
            tok.type = t.type
            tok.value = t.value
            tok.lineno = t.line
            tok.lexpos = 0
            return tok
        return None

    # PLY needs these attributes
    lineno = 1
    lexpos = 0


# ════════════════════════════════════════════════════════════════════════════
# GRAMMAR RULES
# ════════════════════════════════════════════════════════════════════════════

# ── Program ──────────────────────────────────────────────────────────────────

def p_program(p):
    """program : decl_list"""
    p[0] = Program(p[1])

def p_decl_list_empty(p):
    """decl_list : """
    p[0] = []

def p_decl_list(p):
    """decl_list : decl_list decl"""
    p[0] = p[1] + [p[2]]

def p_decl(p):
    """decl : func_decl"""
    p[0] = p[1]

# ── Function declaration ──────────────────────────────────────────────────────

def p_func_decl(p):
    """func_decl : func_head func_body"""
    head = p[1]
    p[0] = FunctionDecl(head['name'], head['params'], head['ret_type'], p[2],
                        lineno=head['lineno'])

def p_func_head_void(p):
    """func_head : FN IDENT LPAREN param_list RPAREN"""
    p[0] = {'name': p[2], 'params': p[4], 'ret_type': None, 'lineno': p.lineno(1)}

def p_func_head_ret(p):
    """func_head : FN IDENT LPAREN param_list RPAREN ARROW type"""
    p[0] = {'name': p[2], 'params': p[4], 'ret_type': p[7], 'lineno': p.lineno(1)}

# ── Function body: unified block (rule 1.1 + 7.2) ────────────────────────────
# We use one non-terminal <func_body> that matches both plain blocks
# and expression blocks, avoiding the 语句块 vs 函数表达式语句块 conflict.

def p_func_body(p):
    """func_body : LBRACE body_stmts RBRACE"""
    stmts, tail = p[2]
    p[0] = Block(stmts, tail)

def p_body_stmts_empty(p):
    """body_stmts : """
    p[0] = ([], None)

def p_body_stmts_stmt(p):
    """body_stmts : body_stmts stmt"""
    stmts, _ = p[1]
    p[0] = (stmts + [p[2]], None)

def p_body_stmts_tail(p):
    """body_stmts : body_stmts expr"""
    # bare expression at end = tail expression (rule 7.0/7.2)
    stmts, _ = p[1]
    p[0] = (stmts, p[2])

# ── Parameter list (rules 1.1, 1.4) ──────────────────────────────────────────

def p_param_list_empty(p):
    """param_list : """
    p[0] = []

def p_param_list_one(p):
    """param_list : param"""
    p[0] = [p[1]]

def p_param_list_many(p):
    """param_list : param COMMA param_list"""
    p[0] = [p[1]] + p[3]

def p_param(p):
    """param : var_attr IDENT COLON type"""
    p[0] = Param(p[1], p[2], p[4], lineno=p.lineno(2))

# ── Variable attribute (rules 0.1, 6.1) ──────────────────────────────────────

def p_var_attr_mut(p):
    """var_attr : MUT"""
    p[0] = True

def p_var_attr_empty(p):
    """var_attr : """
    p[0] = False

# ── Types (rules 0.2, 6.2, 6.3, 8.1, 9.1) ───────────────────────────────────

def p_type_i32(p):
    """type : I32"""
    p[0] = TypeI32()

def p_type_ref_imm(p):
    """type : AMP type"""
    p[0] = TypeRef(False, p[2])

def p_type_ref_mut(p):
    """type : AMP MUT type"""
    p[0] = TypeRef(True, p[3])

def p_type_array(p):
    """type : LBRACKET type SEMI NUM RBRACKET"""
    p[0] = TypeArray(p[2], int(p[4]))

def p_type_tuple(p):
    """type : LPAREN type_list RPAREN"""
    p[0] = TypeTuple(p[2])

def p_type_list_empty(p):
    """type_list : """
    p[0] = []

def p_type_list_one(p):
    """type_list : type"""
    p[0] = [p[1]]

def p_type_list_many(p):
    """type_list : type COMMA type_list"""
    p[0] = [p[1]] + p[3]

# ── Statements ────────────────────────────────────────────────────────────────

def p_stmt_semi(p):
    """stmt : SEMI"""
    p[0] = EmptyStmt()

def p_stmt_return_void(p):
    """stmt : RETURN SEMI"""
    p[0] = ReturnStmt(None, lineno=p.lineno(1))

def p_stmt_return_expr(p):
    """stmt : RETURN expr SEMI"""
    p[0] = ReturnStmt(p[2], lineno=p.lineno(1))

def p_stmt_let(p):
    """stmt : LET var_attr IDENT SEMI"""
    p[0] = LetStmt(p[2], p[3], None, None, lineno=p.lineno(1))

def p_stmt_let_type(p):
    """stmt : LET var_attr IDENT COLON type SEMI"""
    p[0] = LetStmt(p[2], p[3], p[5], None, lineno=p.lineno(1))

def p_stmt_let_init(p):
    """stmt : LET var_attr IDENT ASSIGN expr SEMI"""
    p[0] = LetStmt(p[2], p[3], None, p[5], lineno=p.lineno(1))

def p_stmt_let_type_init(p):
    """stmt : LET var_attr IDENT COLON type ASSIGN expr SEMI"""
    p[0] = LetStmt(p[2], p[3], p[5], p[7], lineno=p.lineno(1))

def p_stmt_assign(p):
    """stmt : lvalue ASSIGN expr SEMI"""
    p[0] = AssignStmt(p[1], p[3], lineno=p.lineno(2))

def p_stmt_expr(p):
    """stmt : expr SEMI"""
    p[0] = ExprStmt(p[1], lineno=p.lineno(2))

def p_stmt_if(p):
    """stmt : if_stmt"""
    p[0] = p[1]

def p_stmt_while(p):
    """stmt : WHILE expr func_body"""
    p[0] = WhileStmt(p[2], p[3], lineno=p.lineno(1))

def p_stmt_for(p):
    """stmt : FOR var_attr IDENT IN iterable func_body"""
    p[0] = ForStmt(p[2], p[3], None, p[5], p[6], lineno=p.lineno(1))

def p_stmt_for_typed(p):
    """stmt : FOR var_attr IDENT COLON type IN iterable func_body"""
    p[0] = ForStmt(p[2], p[3], p[5], p[7], p[8], lineno=p.lineno(1))

def p_stmt_loop(p):
    """stmt : LOOP func_body"""
    p[0] = LoopStmt(p[2], lineno=p.lineno(1))

def p_stmt_break(p):
    """stmt : BREAK SEMI"""
    p[0] = BreakStmt(None, lineno=p.lineno(1))

def p_stmt_break_expr(p):
    """stmt : BREAK expr SEMI"""
    p[0] = BreakStmt(p[2], lineno=p.lineno(1))

def p_stmt_continue(p):
    """stmt : CONTINUE SEMI"""
    p[0] = ContinueStmt(lineno=p.lineno(1))

# ── If statement (rules 4.1, 4.2, 4.3) ───────────────────────────────────────

def p_if_stmt_no_else(p):
    """if_stmt : IF expr func_body %prec IFX"""
    p[0] = IfStmt(p[2], p[3], [], None, lineno=p.lineno(1))

def p_if_stmt_else(p):
    """if_stmt : IF expr func_body ELSE func_body"""
    p[0] = IfStmt(p[2], p[3], [], p[5], lineno=p.lineno(1))

def p_if_stmt_elseif(p):
    """if_stmt : IF expr func_body ELSE if_stmt"""
    inner = p[5]
    # flatten: merge elseif chain
    p[0] = IfStmt(p[2], p[3],
                  [(inner.cond, inner.then_block)] + inner.elseif_clauses,
                  inner.else_block,
                  lineno=p.lineno(1))

# ── Iterable (rules 5.2, 8.2) ────────────────────────────────────────────────

def p_iterable_range(p):
    """iterable : expr DOTDOT expr"""
    p[0] = RangeExpr(p[1], p[3], lineno=p.lineno(2))

def p_iterable_expr(p):
    """iterable : expr"""
    p[0] = p[1]

# ── Left values (rules 0.3, 6.4) ──────────────────────────────────────────────

def p_lvalue_ident(p):
    """lvalue : IDENT"""
    p[0] = Identifier(p[1], lineno=p.lineno(1))

def p_lvalue_deref(p):
    """lvalue : STAR lvalue %prec UDEREF"""
    p[0] = UnaryOp('*', p[2], lineno=p.lineno(1))

def p_lvalue_ref_imm(p):
    """lvalue : AMP lvalue %prec UREF"""
    p[0] = UnaryOp('&', p[2], lineno=p.lineno(1))

def p_lvalue_ref_mut(p):
    """lvalue : AMP MUT lvalue %prec UREFMUT"""
    p[0] = UnaryOp('&mut', p[3], lineno=p.lineno(1))

def p_lvalue_index(p):
    """lvalue : lvalue LBRACKET expr RBRACKET"""
    p[0] = IndexExpr(p[1], p[3], lineno=p.lineno(2))

def p_lvalue_field(p):
    """lvalue : lvalue DOT NUM"""
    p[0] = TupleFieldExpr(p[1], int(p[3]), lineno=p.lineno(2))

# ── Expressions (rules 3.1–3.5, 7.3, 7.4, 8.2, 8.3, 9.2, 9.3) ──────────────

def p_expr_binop(p):
    """expr : expr PLUS  expr
            | expr MINUS expr
            | expr STAR  expr
            | expr SLASH expr
            | expr EQ    expr
            | expr NEQ   expr
            | expr GT    expr
            | expr GEQ   expr
            | expr LT    expr
            | expr LEQ   expr"""
    p[0] = BinaryOp(p[2], p[1], p[3], lineno=p.lineno(2))

def p_expr_uminus(p):
    """expr : MINUS expr %prec UMINUS"""
    p[0] = UnaryOp('-', p[2], lineno=p.lineno(1))

def p_expr_deref(p):
    """expr : STAR expr %prec UDEREF"""
    p[0] = UnaryOp('*', p[2], lineno=p.lineno(1))

def p_expr_ref(p):
    """expr : AMP expr %prec UREF"""
    p[0] = UnaryOp('&', p[2], lineno=p.lineno(1))

def p_expr_ref_mut(p):
    """expr : AMP MUT expr %prec UREFMUT"""
    p[0] = UnaryOp('&mut', p[3], lineno=p.lineno(1))

def p_expr_num(p):
    """expr : NUM"""
    p[0] = NumLiteral(int(p[1]), lineno=p.lineno(1))

def p_expr_lvalue(p):
    """expr : lvalue"""
    p[0] = p[1]

def p_expr_paren(p):
    """expr : LPAREN expr RPAREN"""
    p[0] = p[2]

def p_expr_index(p):
    """expr : expr LBRACKET expr RBRACKET"""
    p[0] = IndexExpr(p[1], p[3], lineno=p.lineno(2))

def p_expr_tuple_field(p):
    """expr : expr DOT NUM"""
    p[0] = TupleFieldExpr(p[1], int(p[3]), lineno=p.lineno(2))

def p_expr_array(p):
    """expr : LBRACKET array_elems RBRACKET"""
    p[0] = ArrayExpr(p[2], lineno=p.lineno(1))

def p_array_elems_empty(p):
    """array_elems : """
    p[0] = []

def p_array_elems_one(p):
    """array_elems : expr"""
    p[0] = [p[1]]

def p_array_elems_many(p):
    """array_elems : expr COMMA array_elems"""
    p[0] = [p[1]] + p[3]

def p_expr_tuple(p):
    """expr : LPAREN tuple_inner RPAREN"""
    p[0] = TupleExpr(p[2], lineno=p.lineno(1))

def p_tuple_inner_empty(p):
    """tuple_inner : """
    p[0] = []

def p_tuple_inner(p):
    """tuple_inner : expr COMMA tuple_elems"""
    p[0] = [p[1]] + p[3]

def p_tuple_elems_empty(p):
    """tuple_elems : """
    p[0] = []

def p_tuple_elems_one(p):
    """tuple_elems : expr"""
    p[0] = [p[1]]

def p_tuple_elems_many(p):
    """tuple_elems : expr COMMA tuple_elems"""
    p[0] = [p[1]] + p[3]

def p_expr_block(p):
    """expr : func_body"""
    p[0] = p[1]

def p_expr_if(p):
    """expr : IF expr func_body ELSE func_body"""
    p[0] = IfExpr(p[2], p[3], p[5], lineno=p.lineno(1))

def p_expr_loop(p):
    """expr : LOOP func_body"""
    p[0] = LoopExpr(p[2], lineno=p.lineno(1))

# ── Error handling ────────────────────────────────────────────────────────────

parse_errors = []

def p_error(p):
    if p:
        parse_errors.append({
            "msg": f"Syntax error at '{p.value}'",
            "line": p.lineno,
            "col": 0,
        })
    else:
        parse_errors.append({
            "msg": "Syntax error at end of input",
            "line": 0, "col": 0,
        })


# ════════════════════════════════════════════════════════════════════════════
# PUBLIC API
# ════════════════════════════════════════════════════════════════════════════

_parser = None

def _get_parser():
    global _parser
    if _parser is None:
        _parser = yacc.yacc(
            debug=False,
            outputdir=os.path.dirname(__file__),
            errorlog=yacc.NullLogger(),
        )
    return _parser


def parse(token_list) -> tuple[Program | None, list[dict]]:
    """
    token_list: list of lexer.Token objects
    Returns (ast, errors).
    """
    global parse_errors
    parse_errors = []
    adapter = PLYLexerAdapter(token_list)
    parser = _get_parser()
    ast = parser.parse(lexer=adapter, tracking=True)
    return ast, list(parse_errors)
