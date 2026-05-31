"""Compare RD parser IR against LR1 parser IR for all examples."""
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
    ast_r, errs_r = parse_rd(tokens)
    ast_l, errs_l = parse_lr1(tokens)
    if bool(errs_r) != bool(errs_l):
        print('[ERR MISMATCH]', fname)
        if errs_r: print('  RD: ', errs_r[0])
        if errs_l: print('  LR1:', errs_l[0])
        fail += 1
        continue
    if errs_r:
        ok += 1
        continue
    try:
        ir_r = generate_ir(ast_r)
        ir_l = generate_ir(ast_l)
    except Exception as e:
        print('[EXCEPTION]', fname, e)
        fail += 1
        continue
    if ir_r != ir_l:
        print('[IR MISMATCH]', fname)
        for i, (a, b) in enumerate(zip(ir_r, ir_l)):
            if a != b:
                print(f'  quad {i}: RD={a}  LR1={b}')
                break
        if len(ir_r) != len(ir_l):
            print(f'  lengths: RD={len(ir_r)} LR1={len(ir_l)}')
        fail += 1
    else:
        print('[OK]', fname)
        ok += 1

print()
print('='*40)
print(f'Total: {ok+fail}  OK: {ok}  FAIL: {fail}')
