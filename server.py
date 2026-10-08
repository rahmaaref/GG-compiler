# ── GG Language — Flask Server ───────────────────────────────────────────────
#
#   Endpoints:
#       POST /run       → full pipeline, returns stdout
#       POST /scan      → scanner only, returns token list
#       POST /parse     → scanner + parser, returns pretty AST
#       POST /semantic  → scanner + parser + semantic, returns errors or OK
#
#   Run:
#       python server.py
#   Open:
#       http://127.0.0.1:5000
# ─────────────────────────────────────────────────────────────────────────────

import sys
import os
import io
import contextlib
import traceback

BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
COMPILER_DIR = os.path.join(BASE_DIR, 'compiler')
FRONTEND_DIR = os.path.join(BASE_DIR, 'frontend')

sys.path.insert(0, COMPILER_DIR)

from scanner  import scan
from parser   import parse
from semantic import analyze
from codegen  import generate

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

app = Flask(__name__, static_folder=FRONTEND_DIR)
CORS(app)


# ── Frontend ──────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return send_from_directory(FRONTEND_DIR, 'index.html')

@app.route('/<path:filename>')
def static_files(filename):
    return send_from_directory(FRONTEND_DIR, filename)


# ── /run  (full pipeline) ─────────────────────────────────────────────────────

@app.route('/run', methods=['POST'])
def run():
    data      = request.get_json(force=True)
    gg_source = data.get('code', '').strip()

    if not gg_source:
        return jsonify({'output': '[Error] No code provided.'})

    try:
        tokens = scan(gg_source)
    except Exception as e:
        return jsonify({'output': f'[Scanner Error]\n{e}'})

    try:
        ast = parse(tokens)
    except SyntaxError as e:
        return jsonify({'output': f'[Parser Error]\n{e}'})
    except Exception as e:
        return jsonify({'output': f'[Parser Error]\n{e}'})

    errors = analyze(ast)
    if errors:
        return jsonify({'output': '[Semantic Errors]\n' + '\n'.join(errors)})

    try:
        python_code = generate(ast)
    except Exception as e:
        return jsonify({'output': f'[Code Generation Error]\n{e}'})

    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()

    try:
        with contextlib.redirect_stdout(stdout_buf), \
             contextlib.redirect_stderr(stderr_buf):
            exec(compile(python_code, '<gg>', 'exec'),
                 {'__builtins__': __builtins__})
    except Exception:
        tb  = traceback.format_exc()
        out = stdout_buf.getvalue()
        return jsonify({'output': (out + f'\n[Runtime Error]\n{tb}').strip()})

    output = stdout_buf.getvalue() + stderr_buf.getvalue()
    return jsonify({'output': output.rstrip() or '(program finished with no output)'})


# ── /scan  (scanner only) ─────────────────────────────────────────────────────

@app.route('/scan', methods=['POST'])
def scan_route():
    data      = request.get_json(force=True)
    gg_source = data.get('code', '').strip()

    if not gg_source:
        return jsonify({'error': '[Error] No code provided.'})

    try:
        tokens = scan(gg_source)
        # Tokens are now (kind, value, line) triples — serialise as lists for JSON.
        return jsonify({'tokens': [list(t) for t in tokens]})
    except Exception as e:
        return jsonify({'error': f'[Scanner Error]\n{e}'})


# ── /parse  (scanner + parser → pretty AST) ───────────────────────────────────

@app.route('/parse', methods=['POST'])
def parse_route():
    data      = request.get_json(force=True)
    gg_source = data.get('code', '').strip()

    if not gg_source:
        return jsonify({'error': '[Error] No code provided.'})

    try:
        tokens = scan(gg_source)
    except Exception as e:
        return jsonify({'error': f'[Scanner Error]\n{e}'})

    try:
        ast = parse(tokens)
        return jsonify({'ast': _pretty_ast(ast)})
    except SyntaxError as e:
        return jsonify({'error': f'[Parser Error]\n{e}'})
    except Exception as e:
        return jsonify({'error': f'[Parser Error]\n{e}'})


def _pretty_ast(node, depth=0):
    """Recursively render the AST as an indented string."""
    pad = '  ' * depth
    if isinstance(node, tuple):
        lines = [f"{pad}{node[0]}"]
        for child in node[1:]:
            lines.append(_pretty_ast(child, depth + 1))
        return '\n'.join(lines)
    elif isinstance(node, list):
        if not node:
            return f"{pad}(empty)"
        return '\n'.join(_pretty_ast(item, depth) for item in node)
    else:
        return f"{pad}{repr(node)}"


# ── /codegen  (scanner + parser + semantic + codegen → Python source) ─────────

@app.route('/codegen', methods=['POST'])
def codegen_route():
    data      = request.get_json(force=True)
    gg_source = data.get('code', '').strip()

    if not gg_source:
        return jsonify({'error': '[Error] No code provided.'})

    try:
        tokens = scan(gg_source)
    except Exception as e:
        return jsonify({'error': f'[Scanner Error]\n{e}'})

    try:
        ast = parse(tokens)
    except SyntaxError as e:
        return jsonify({'error': f'[Parser Error]\n{e}'})
    except Exception as e:
        return jsonify({'error': f'[Parser Error]\n{e}'})

    errors = analyze(ast)
    if errors:
        return jsonify({'error': '[Semantic Errors — cannot generate code]\n' + '\n'.join(errors)})

    try:
        python_code = generate(ast)
        return jsonify({'code': python_code})
    except Exception as e:
        return jsonify({'error': f'[Code Generation Error]\n{e}'})


# ── /semantic  (scanner + parser + semantic analysis) ────────────────────────

@app.route('/semantic', methods=['POST'])
def semantic_route():
    data      = request.get_json(force=True)
    gg_source = data.get('code', '').strip()

    if not gg_source:
        return jsonify({'errors': [], 'message': '[Error] No code provided.'})

    try:
        tokens = scan(gg_source)
    except Exception as e:
        return jsonify({'errors': [f'[Scanner Error] {e}']})

    try:
        ast = parse(tokens)
    except SyntaxError as e:
        return jsonify({'errors': [f'[Parser Error] {e}']})
    except Exception as e:
        return jsonify({'errors': [f'[Parser Error] {e}']})

    errors = analyze(ast)

    if errors:
        return jsonify({'errors': errors})

    return jsonify({
        'errors':  [],
        'message': '✔  Semantic analysis passed — no errors found.'
    })


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == '__main__':
    print()
    print('  ██████╗  ██████╗     Server')
    print('  ██╔════╝ ██╔════╝     http://127.0.0.1:5000')
    print('  ██║  ███╗██║  ███╗')
    print('  ██║   ██║██║   ██║    Press Ctrl+C to stop')
    print('  ╚██████╔╝╚██████╔╝')
    print('   ╚═════╝  ╚═════╝')
    print()
    app.run(debug=True, port=5000)