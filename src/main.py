"""Flask backend."""

import sys, os, re, threading, webbrowser
sys.path.insert(0, os.path.dirname(__file__))

from flask import Flask, request, jsonify, render_template, abort
from lexer import Lexer, lex
# from parser import parse  # LALR disabled
from parser_rd import parse_rd, parse_rd_sdt
from parser_lr1 import parse_lr1, parse_lr1_sdt
from semantic import analyse
from codegen import generate_ir
from mips import generate_mips
from interpreter import run_func, list_funcs

ROOT = (getattr(sys, '_MEIPASS', None)
        or os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
EXAMPLES_DIR = os.path.join(ROOT, 'examples')

app = Flask(
    __name__,
    template_folder=os.path.join(ROOT, 'templates'),
    static_folder=os.path.join(ROOT, 'static'),
)

APP_URL = 'http://127.0.0.1:5000/'


def _open_browser():
    """Open the compiler UI after the packaged server has started."""
    webbrowser.open_new_tab(APP_URL)


def _schedule_browser_open(delay=1.0):
    timer = threading.Timer(delay, _open_browser)
    timer.daemon = True
    timer.start()
    return timer


def _parse(tokens, parser_type):
    if parser_type == 'rd':
        return parse_rd(tokens)
    if parser_type == 'lr1':
        return parse_lr1(tokens)
    # return parse(tokens)  # LALR disabled — default falls through to rd
    return parse_rd(tokens)


def _scan_parse(source, parser_type):
    """Run either parser with lazy lexing and syntax-directed translation."""
    if parser_type in ('rd', 'lr1'):
        lexer = Lexer(source)
        parse_sdt = parse_rd_sdt if parser_type == 'rd' else parse_lr1_sdt
        ast, parse_errors, syntax_ir = parse_sdt(lexer)
        # A syntax error may stop before EOF; drain only for a complete token/error
        # table shown in the UI.  Successful parsing already consumed lazily to EOF.
        lexer.tokenize()
        if lexer.errors:
            ast = None
            syntax_ir = []
        return lexer.tokens, lexer.errors, ast, parse_errors, syntax_ir

    tokens, lex_errors = lex(source)
    if lex_errors:
        return tokens, lex_errors, None, [], None
    ast, parse_errors = _parse(tokens, parser_type)
    return tokens, lex_errors, ast, parse_errors, None


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/analyse', methods=['POST'])
def api_analyse():
    data        = request.get_json(force=True)
    source      = data.get('source', '')
    parser_type = data.get('parser', 'rd')

    # 1-2. Lazy lex + syntax-directed translation (RD or canonical LR(1))
    tokens, lex_errors, ast, parse_errors, syntax_ir = _scan_parse(
        source, parser_type)
    ast_dict = None
    if ast:
        ast_dict = ast.to_dict()

    # 3. Semantic (only if AST built)
    sem_errors = []
    if ast:
        sem_errors = analyse(ast)

    # 4. IR (only for a semantically valid program)
    ir_quads = []
    mips_asm = ''
    funcs    = []
    if ast and not sem_errors:
        ir_quads = syntax_ir if syntax_ir is not None else generate_ir(ast)
        mips_asm = generate_mips(ir_quads)
        funcs    = list_funcs(ir_quads, ast)

    return jsonify({
        "tokens": [
            {"type": t.type, "value": t.value, "line": t.line, "col": t.col}
            for t in tokens if t.type != 'END'
        ],
        "lex_errors":   lex_errors,
        "parse_errors": parse_errors,
        "sem_errors":   sem_errors,
        "ast":          ast_dict,
        "ir":           ir_quads,
        "mips":         mips_asm,
        "funcs":        funcs,
    })


@app.route('/api/run', methods=['POST'])
def api_run():
    data        = request.get_json(force=True)
    source      = data.get('source', '')
    func_name   = data.get('func', '')
    args        = data.get('args', [])
    parser_type = data.get('parser', 'rd')

    tokens, lex_errors, ast, parse_errors, syntax_ir = _scan_parse(
        source, parser_type)
    if lex_errors:
        return jsonify({'result': None, 'error': f'词法错误: {lex_errors[0]["msg"]}'})
    if parse_errors:
        return jsonify({'result': None, 'error': f'语法错误: {parse_errors[0]["msg"]}'})

    sem_errors = analyse(ast)
    if sem_errors:
        return jsonify({
            'result': None,
            'error': f'语义错误: {sem_errors[0]["msg"]}',
            'sem_errors': sem_errors,
        })

    ir_quads = syntax_ir if syntax_ir is not None else generate_ir(ast)
    result, err = run_func(ir_quads, func_name, args)
    return jsonify({'result': result, 'error': err})


@app.route('/api/examples')
def api_examples():
    files = []
    for name in sorted(os.listdir(EXAMPLES_DIR)):
        if not name.endswith('.rs'):
            continue
        path = os.path.join(EXAMPLES_DIR, name)
        desc = ''
        with open(path, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line.startswith('//'):
                    desc = line[2:].strip()
                    break
        files.append({'name': name, 'desc': desc})
    return jsonify(files)


@app.route('/api/examples/<path:filename>')
def api_example_content(filename):
    if not re.match(r'^[\w.\-]+\.rs$', filename):
        abort(400)
    path = os.path.join(EXAMPLES_DIR, filename)
    if not os.path.isfile(path):
        abort(404)
    return jsonify({'content': open(path, encoding='utf-8').read()})


if __name__ == '__main__':
    if getattr(sys, 'frozen', False) and os.environ.get('BYYL_NO_BROWSER') != '1':
        _schedule_browser_open()
    app.run(debug=False, use_reloader=False, port=5000)
