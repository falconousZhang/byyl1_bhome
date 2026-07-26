"""Check all positive examples for unexpected errors."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
from lexer import lex
from parser_rd import parse_rd
from semantic import analyse

examples_dir = os.path.join(os.path.dirname(__file__), 'examples')
results = []
clean = []
for name in sorted(os.listdir(examples_dir)):
    if not name.endswith('.rs'):
        continue
    if name.startswith('err.'):
        continue
    path = os.path.join(examples_dir, name)
    src = open(path, encoding='utf-8').read()
    tokens, lex_errs = lex(src)
    if lex_errs:
        results.append((name, 'LEX', [e['msg'] for e in lex_errs]))
        continue
    ast, parse_errs = parse_rd(tokens)
    if parse_errs:
        results.append((name, 'PARSE', [e['msg'] for e in parse_errs]))
        continue
    sem_errs = analyse(ast)
    if sem_errs:
        results.append((name, 'SEM', [e['msg'] for e in sem_errs]))
    else:
        clean.append(name)

print(f'Clean: {len(clean)}/{len(clean)+len(results)}')
print()
if results:
    print('=== Files with errors ===')
    for name, kind, msgs in results:
        print(f'\n{name} [{kind}]:')
        for m in msgs:
            print(f'  {m}')
else:
    print('All positive examples are clean!')

raise SystemExit(1 if results else 0)
