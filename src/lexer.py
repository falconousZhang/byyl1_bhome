"""
Hand-written lexer for the Rust-like language.
Produces a list of Token objects with type, value, line, col.
End-of-input is signaled by token type 'END' (the '#' character or actual EOF).
"""

from dataclasses import dataclass
from typing import Optional

# ── Token definition ──────────────────────────────────────────────────────────

KEYWORDS = {
    'i32', 'let', 'if', 'else', 'while', 'return',
    'mut', 'fn', 'for', 'in', 'loop', 'break', 'continue',
}

# Two-char operators/symbols (must be tried before single-char)
TWO_CHAR = {
    '==': 'EQ', '!=': 'NEQ', '>=': 'GEQ', '<=': 'LEQ',
    '->': 'ARROW', '..': 'DOTDOT',
    '&&': 'AND',  # bonus: logical and
}

# Single-char tokens: (char -> token_type)
ONE_CHAR = {
    '+': 'PLUS',   '-': 'MINUS',  '*': 'STAR',   '/': 'SLASH',
    '>': 'GT',     '<': 'LT',     '=': 'ASSIGN',  '&': 'AMP',
    '(': 'LPAREN', ')': 'RPAREN',
    '{': 'LBRACE', '}': 'RBRACE',
    '[': 'LBRACKET', ']': 'RBRACKET',
    ';': 'SEMI',   ':': 'COLON',  ',': 'COMMA',
    '.': 'DOT',    '#': 'END',
}


@dataclass
class Token:
    type: str
    value: str
    line: int
    col: int

    def __repr__(self):
        return f"Token({self.type}, {self.value!r}, L{self.line}:C{self.col})"


# ── Lexer ──────────────────────────────────────────────────────────────────────

class LexError(Exception):
    def __init__(self, msg, line, col):
        super().__init__(msg)
        self.line = line
        self.col = col
        self.msg = msg


class Lexer:
    def __init__(self, source: str):
        self.source = source
        self.pos = 0
        self.line = 1
        self.col = 1
        self.tokens: list[Token] = []
        self.errors: list[dict] = []

    # ── helpers ───────────────────────────────────────────────────────────────

    def _peek(self, offset=0) -> Optional[str]:
        idx = self.pos + offset
        return self.source[idx] if idx < len(self.source) else None

    def _advance(self) -> str:
        ch = self.source[self.pos]
        self.pos += 1
        if ch == '\n':
            self.line += 1
            self.col = 1
        else:
            self.col += 1
        return ch

    def _skip_line_comment(self):
        while self._peek() not in ('\n', None):
            self._advance()

    def _skip_block_comment(self):
        start_line, start_col = self.line, self.col
        self._advance()  # consume *
        while True:
            ch = self._peek()
            if ch is None:
                self.errors.append({
                    "msg": "Unclosed block comment",
                    "line": start_line, "col": start_col
                })
                return
            if ch == '*' and self._peek(1) == '/':
                self._advance(); self._advance()
                return
            self._advance()

    # ── tokenize ──────────────────────────────────────────────────────────────

    def tokenize(self) -> list[Token]:
        while self.pos < len(self.source):
            ch = self._peek()

            # whitespace
            if ch in (' ', '\t', '\r', '\n'):
                self._advance()
                continue

            tok_line, tok_col = self.line, self.col

            # line comment
            if ch == '/' and self._peek(1) == '/':
                self._advance(); self._advance()
                self._skip_line_comment()
                continue

            # block comment
            if ch == '/' and self._peek(1) == '*':
                self._advance()
                self._skip_block_comment()
                continue

            # number literal
            if ch.isdigit():
                start = self.pos
                while self._peek() and self._peek().isdigit():
                    self._advance()
                val = self.source[start:self.pos]
                self.tokens.append(Token('NUM', val, tok_line, tok_col))
                continue

            # identifier or keyword
            if ch.isalpha() or ch == '_':
                start = self.pos
                while self._peek() and (self._peek().isalnum() or self._peek() == '_'):
                    self._advance()
                val = self.source[start:self.pos]
                ttype = val.upper() if val in KEYWORDS else 'IDENT'
                # store keyword tokens with their keyword name as type
                if val in KEYWORDS:
                    ttype = val.upper()  # e.g. 'IF', 'FN', 'LET', 'I32'
                self.tokens.append(Token(ttype, val, tok_line, tok_col))
                continue

            # two-char symbols
            two = (ch or '') + (self._peek(1) or '')
            if two in TWO_CHAR:
                self._advance(); self._advance()
                self.tokens.append(Token(TWO_CHAR[two], two, tok_line, tok_col))
                continue

            # single-char symbols
            if ch in ONE_CHAR:
                self._advance()
                self.tokens.append(Token(ONE_CHAR[ch], ch, tok_line, tok_col))
                continue

            # unknown character
            self.errors.append({
                "msg": f"Unknown character: {ch!r}",
                "line": tok_line, "col": tok_col
            })
            self._advance()

        # implicit EOF token (acts as '#')
        self.tokens.append(Token('END', '#', self.line, self.col))
        return self.tokens

    def get_token_table(self) -> list[dict]:
        """Return tokens as list of dicts for frontend display."""
        return [
            {"type": t.type, "value": t.value, "line": t.line, "col": t.col}
            for t in self.tokens
        ]


# ── standalone run ────────────────────────────────────────────────────────────

def lex(source: str) -> tuple[list[Token], list[dict]]:
    lx = Lexer(source)
    tokens = lx.tokenize()
    return tokens, lx.errors


if __name__ == '__main__':
    import sys, json
    src = open(sys.argv[1]).read() if len(sys.argv) > 1 else "fn main() { let x:i32 = 1; }"
    toks, errs = lex(src)
    for t in toks:
        print(t)
    if errs:
        print("ERRORS:", json.dumps(errs, indent=2))
