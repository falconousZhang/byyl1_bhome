"""Show all semantic errors detected in error example files."""
import sys
sys.path.insert(0, 'src')
from lexer import lex
from parser_rd import parse_rd
from semantic import analyse
import os

err_files = sorted(f for f in os.listdir('examples') if f.startswith('err.'))
for fname in err_files:
    src = open('examples/' + fname, encoding='utf-8').read()
    toks, _ = lex(src)
    ast, pe = parse_rd(toks)
    errs = analyse(ast) if ast else []
    all_e = pe + errs
    status = 'OK' if all_e else 'MISS'
    print(f'[{status}] {fname}: {len(all_e)} error(s)')
    for e in all_e:
        line = e.get('line', '?')
        msg  = e['msg']
        print(f'       line {line:>3}: {msg}')
