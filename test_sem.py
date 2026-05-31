import sys
sys.path.insert(0, 'src')
from lexer import lex
from parser_rd import parse_rd
from semantic import analyse

cases = [
    ('函数调用参数数量错',   'fn f(mut a:i32){} fn g(){ f(1,2); }'),
    ('函数无返回值作右值',   'fn f(){} fn g(){ let mut x=f(); }'),
    ('return类型不匹配',     'fn f() -> i32 { return; }'),
    ('未初始化变量使用',     'fn f(){ let mut b:i32; let mut c:i32 = b; }'),
    ('数组索引非整型',       'fn f(){ let mut a:[i32;3]=[1,2,3]; let mut c:i32=a[1==1]; }'),
    ('未声明变量',           'fn f(){ a=1; }'),
    ('不可变变量赋值',       'fn f(){ let a:i32=1; a=2; }'),
    ('break不在循环内',      'fn f(){ break; }'),
    ('未定义函数调用',       'fn f(){ g(); }'),
]

for name, src in cases:
    toks, _ = lex(src)
    ast, pe = parse_rd(toks)
    errs = analyse(ast) if ast else []
    all_errs = pe + errs
    if all_errs:
        print(f'[OK] {name}: {all_errs[0]["msg"]}')
    else:
        print(f'[MISS] {name}: no error detected')
