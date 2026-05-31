"""Flask backend."""

import sys, os, re
sys.path.insert(0, os.path.dirname(__file__))

from flask import Flask, request, jsonify, render_template, abort
from lexer import lex
# from parser import parse  # LALR disabled
from parser_rd import parse_rd
from parser_lr1 import parse_lr1
from semantic import analyse
from codegen import generate_ir
# from mips import generate_mips
from interpreter import run_func, list_funcs

ROOT = os.path.join(os.path.dirname(__file__), '..')
EXAMPLES_DIR = os.path.join(ROOT, 'examples')

app = Flask(
    __name__,
    template_folder=os.path.join(ROOT, 'templates'),
    static_folder=os.path.join(ROOT, 'static'),
)


def _parse(tokens, parser_type):
    if parser_type == 'rd':
        return parse_rd(tokens)
    if parser_type == 'lr1':
        return parse_lr1(tokens)
    # return parse(tokens)  # LALR disabled — default falls through to rd
    return parse_rd(tokens)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/analyse', methods=['POST'])
def api_analyse():
    data        = request.get_json(force=True)
    source      = data.get('source', '')
    parser_type = data.get('parser', 'lalr')

    # 1. Lex
    tokens, lex_errors = lex(source)

    # 2. Parse (only if no lex errors)
    ast = None
    parse_errors = []
    ast_dict = None
    if not lex_errors:
        ast, parse_errors = _parse(tokens, parser_type)
        if ast:
            ast_dict = ast.to_dict()

    # 3. Semantic (only if AST built)
    sem_errors = []
    if ast:
        sem_errors = analyse(ast)

    # 4. IR (only if AST built)
    ir_quads = []
    funcs    = []
    if ast:
        ir_quads = generate_ir(ast)
        # mips_asm = generate_mips(ir_quads)
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
        # "mips":       mips_asm,
        "funcs":        funcs,
    })


@app.route('/api/run', methods=['POST'])
def api_run():
    data        = request.get_json(force=True)
    source      = data.get('source', '')
    func_name   = data.get('func', '')
    args        = data.get('args', [])
    parser_type = data.get('parser', 'lalr')

    tokens, lex_errors = lex(source)
    if lex_errors:
        return jsonify({'result': None, 'error': f'词法错误: {lex_errors[0]["msg"]}'})
    ast, parse_errors = _parse(tokens, parser_type)
    if parse_errors:
        return jsonify({'result': None, 'error': f'语法错误: {parse_errors[0]["msg"]}'})

    ir_quads = generate_ir(ast)
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
    app.run(debug=True, port=5000)
