import sys
sys.path.insert(0, 'src')
from lexer import lex
from parser_rd import parse_rd
from parser_lr1 import parse_lr1
from codegen import generate_ir
import os

examples_dir = 'examples'
files = sorted(f for f in os.listdir(examples_dir) if f.endswith('.rs'))

ok = fail = 0
for fname in files:
    src = open(os.path.join(examples_dir, fname), encoding='utf-8').read()
    tokens, lex_errs = lex(src)
    if lex_errs:
        print('[LEX ERR]', fname)
        continue
    ast_l, errs_l = parse_rd(tokens)
    ast_r, errs_r = parse_lr1(tokens)
    if bool(errs_l) != bool(errs_r):
        print('[ERR MISMATCH]', fname)
        if errs_l: print('  RD:  ', errs_l[0])
        if errs_r: print('  LR1: ', errs_r[0])
        fail += 1
        continue
    if errs_l:
        ok += 1
        continue
    try:
        ir_l = generate_ir(ast_l)
        ir_r = generate_ir(ast_r)
    except Exception as e:
        print('[EXCEPTION]', fname, e)
        fail += 1
        continue
    if ir_l != ir_r:
        print('[IR MISMATCH]', fname)
        for i, (a, b) in enumerate(zip(ir_l, ir_r)):
            if a != b:
                print(f'  quad {i}: RD={a}  LR1={b}')
                break
        if len(ir_l) != len(ir_r):
            print(f'  lengths: LALR={len(ir_l)} LR1={len(ir_r)}')
        fail += 1
    else:
        print('[OK]', fname)
        ok += 1

print()
print('='*40)
print(f'Total: {ok+fail}  OK: {ok}  FAIL: {fail}')
raise SystemExit(1 if fail else 0)
