from pathlib import Path
import re
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from codegen import generate_ir
from interpreter import run_func
from lexer import Lexer, lex
import main as main_module
from main import app
from mips import generate_mips
from parser_lr1 import parse_lr1, parse_lr1_sdt
from parser_rd import parse_rd, parse_rd_sdt
from semantic import analyse


def compile_source(source, parser=parse_rd):
    tokens, lex_errors = lex(source)
    assert lex_errors == []
    ast, parse_errors = parser(tokens)
    assert parse_errors == []
    sem_errors = analyse(ast)
    assert sem_errors == []
    return ast, generate_ir(ast)


@pytest.mark.parametrize("parser", [parse_rd, parse_lr1])
def test_all_positive_examples_compile(parser):
    for path in sorted((ROOT / "examples").glob("*.rs")):
        if path.name.startswith("err."):
            continue
        compile_source(path.read_text(encoding="utf-8"), parser)


@pytest.mark.parametrize("parse_sdt", [parse_rd_sdt, parse_lr1_sdt])
def test_lazy_syntax_directed_ir_matches_ast_codegen(parse_sdt):
    source = "fn add(a:i32,b:i32)->i32{a+b}fn main()->i32{add(3,4)}"
    lexer = Lexer(source)
    ast, errors, syntax_ir = parse_sdt(lexer)
    assert errors == []
    assert lexer.errors == []
    assert syntax_ir == generate_ir(ast)


def test_rd_and_lr1_lazy_ir_match_for_all_positive_examples():
    for path in sorted((ROOT / "examples").glob("*.rs")):
        if path.name.startswith("err."):
            continue
        source = path.read_text(encoding="utf-8")
        rd_ast, rd_errors, rd_ir = parse_rd_sdt(Lexer(source))
        lr_ast, lr_errors, lr_ir = parse_lr1_sdt(Lexer(source))
        assert rd_errors == [], path.name
        assert lr_errors == [], path.name
        assert rd_ast.to_dict() == lr_ast.to_dict(), path.name
        assert rd_ir == lr_ir, path.name


@pytest.mark.parametrize(
    ("source", "message"),
    [
        ("fn f()->i32{1==1}", "tail expression type mismatch"),
        ("fn f()->i32{;}", "may exit without returning"),
        ("fn f(){for mut i in (1==1)..2{;}}", "Range start must be i32"),
        ("fn f(){let mut a=[1,1==1];}", "Array element 1 type mismatch"),
        ("fn f(){let mut a=(1==1)+2;}", "Arithmetic left operand must be i32"),
        (
            "fn f(){let mut a:i32=if 1==1{1}else{2==2};}",
            "If-expression branch type mismatch",
        ),
        ("fn f(){let mut a:[i32;0];}", "Array size must be a positive integer"),
        ("fn f(){a=1;}", "Undefined variable 'a'"),
    ],
)
def test_semantic_regressions(source, message):
    tokens, lex_errors = lex(source)
    assert lex_errors == []
    ast, parse_errors = parse_rd(tokens)
    assert parse_errors == []
    errors = analyse(ast)
    assert any(message in error["msg"] for error in errors)


@pytest.mark.parametrize(
    ("source", "function", "args", "expected"),
    [
        (
            "fn add(a:i32,b:i32)->i32{a+b}"
            "fn main()->i32{add(3,4)}",
            "main",
            [],
            7,
        ),
        (
            "fn factorial(n:i32)->i32{"
            "if n<=1{return 1;}return n*factorial(n-1);}",
            "factorial",
            [5],
            120,
        ),
        (
            "fn f()->i32{let mut a:i32=1;"
            "let mut b:i32={let mut a:i32=2;a};a}",
            "f",
            [],
            1,
        ),
        (
            "fn f()->i32{let mut a:[i32;2]=[1,2];"
            "let mut p:&mut i32=&mut a[0];*p=9;a[0]}",
            "f",
            [],
            9,
        ),
        (
            "fn f()->i32{let mut s:i32=0;"
            "for mut i in 0..5{if i==2{continue;}s=s+i;}s}",
            "f",
            [],
            8,
        ),
    ],
)
def test_ir_runtime(source, function, args, expected):
    _, ir = compile_source(source)
    assert run_func(ir, function, args) == (expected, None)


def test_runtime_reports_dynamic_bounds_error():
    _, ir = compile_source(
        "fn f(i:i32)->i32{let mut a:[i32;2]=[1,2];a[i]}"
    )
    result, error = run_func(ir, "f", [4])
    assert result is None
    assert "越界" in error


def test_mips_has_calls_bounds_and_no_unhandled_operations():
    _, ir = compile_source(
        "fn add(a:i32,b:i32)->i32{a+b}"
        "fn main()->i32{let mut a:[i32;2]=[1,2];add(a[0],a[1])}"
    )
    asm = generate_mips(ir)
    assert "jal     add" in asm
    assert "__bounds_error" in asm
    assert "(unhandled)" not in asm


def test_api_blocks_semantic_errors_and_returns_mips():
    client = app.test_client()

    invalid = client.post(
        "/api/analyse", json={"source": "fn f(){break;}", "parser": "rd"}
    )
    assert invalid.status_code == 200
    invalid_data = invalid.get_json()
    assert invalid_data["sem_errors"]
    assert invalid_data["ir"] == []
    assert invalid_data["mips"] == ""

    run_invalid = client.post(
        "/api/run",
        json={
            "source": "fn f(){let a:i32=1;a=2;}",
            "func": "f",
            "args": [],
            "parser": "rd",
        },
    )
    assert "语义错误" in run_invalid.get_json()["error"]

    valid = client.post(
        "/api/analyse",
        json={"source": "fn main()->i32{7}", "parser": "rd"},
    )
    assert "main:" in valid.get_json()["mips"]


@pytest.mark.parametrize("parser_name", ["rd", "lr1"])
def test_api_both_parser_paths_emit_and_run(parser_name):
    client = app.test_client()
    source = "fn add(a:i32,b:i32)->i32{a+b}fn main()->i32{add(20,22)}"
    analysed = client.post(
        "/api/analyse", json={"source": source, "parser": parser_name}
    ).get_json()
    assert analysed["sem_errors"] == []
    assert analysed["ir"]
    assert "jal     add" in analysed["mips"]
    assert analysed["funcs"]

    executed = client.post(
        "/api/run",
        json={"source": source, "func": "main", "args": [], "parser": parser_name},
    ).get_json()
    assert executed == {"error": None, "result": 42}


def test_frontend_mips_renderer_and_source_highlight_are_enabled():
    html = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
    script = re.search(r"<script>([\s\S]*?)</script>", html).group(1)
    style = re.search(r"<style>([\s\S]*?)</style>", html).group(1)
    active_script = re.sub(r"/\*[\s\S]*?\*/", "", script)
    active_style = re.sub(r"/\*[\s\S]*?\*/", "", style)

    assert "function renderMIPS(asm)" in active_script
    assert "renderMIPS(data.mips);" in active_script
    assert "showHighlight(highlightSource(source" in active_script
    assert "#mips-code" in active_style


def test_packaged_launcher_opens_compiler_url(monkeypatch):
    opened = []
    monkeypatch.setattr(
        main_module.webbrowser, "open_new_tab", lambda url: opened.append(url)
    )
    main_module._open_browser()
    assert opened == ["http://127.0.0.1:5000/"]
