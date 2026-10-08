# ── GG Language Compiler ─────────────────────────────────────────────────────
#
#   Usage:
#       python program.py <source.gg>            compile + run
#       python program.py <source.gg> --output   compile + print generated Python
#       python program.py <source.gg> --ast      compile + print AST
#       python program.py --example              run a built-in demo program
#
#   Pipeline:
#       GG source
#           ↓  scanner   (scanner.py)   →  token list
#           ↓  parser    (parser.py)    →  AST
#           ↓  semantic  (semantic.py)  →  validated AST  (or error list)
#           ↓  codegen   (codegen.py)   →  Python source string
#           ↓  exec()                   →  runs the program
# ─────────────────────────────────────────────────────────────────────────────

import sys
import os

from scanner  import scan
from parser   import parse
from semantic import analyze
from codegen  import generate


# ── ANSI colours (disabled automatically on Windows or when not a TTY) ────────

_USE_COLOR = sys.stdout.isatty() and os.name != 'nt'

def _c(code, text):
    return f"\033[{code}m{text}\033[0m" if _USE_COLOR else text

def red(t):    return _c('31;1', t)
def green(t):  return _c('32;1', t)
def yellow(t): return _c('33;1', t)
def cyan(t):   return _c('36;1', t)
def bold(t):   return _c('1',    t)


# ── Pipeline ──────────────────────────────────────────────────────────────────

def compile_source(source: str, filename: str = "<string>"):
    """
    Run the full GG compilation pipeline on *source*.

    Returns:
        (python_code: str, ast)   on success
    Raises:
        SystemExit                on any error (scanner / parser / semantic)
    """

    # ── 1. Scan ───────────────────────────────────────────────────────────────
    print(cyan("── [1/3] Scanning …"))
    try:
        tokens = scan(source)
    except IndentationError as e:
        print(red(f"\n[Scanner Error] {e}"))
        sys.exit(1)

    # ── 2. Parse ──────────────────────────────────────────────────────────────
    print(cyan("── [2/3] Parsing …"))
    try:
        ast = parse(tokens)
    except SyntaxError as e:
        print(red(f"\n[Parser Error] {e}"))
        sys.exit(1)

    # ── 3. Semantic analysis ──────────────────────────────────────────────────
    print(cyan("── [3/3] Analysing …"))
    errors = analyze(ast)
    if errors:
        print(red(f"\nSemantic errors in {bold(filename)}:\n"))
        for err in errors:
            print(f"  {red('✖')}  {err}")
        print()
        sys.exit(1)

    # ── 4. Code generation ────────────────────────────────────────────────────
    python_code = generate(ast)
    return python_code, ast


def run_python(python_code: str, filename: str = "<string>"):
    """Execute the generated Python code in a fresh namespace."""
    namespace = {"__name__": "__main__", "__file__": filename}
    try:
        exec(compile(python_code, filename, "exec"), namespace)
    except Exception as e:
        print(red(f"\n[Runtime Error] {type(e).__name__}: {e}"))
        sys.exit(1)


# ── Built-in demo program ─────────────────────────────────────────────────────

EXAMPLE_SOURCE = """\
hp pts = 0
hp lives = 3

play win(n):
    check n > 50:
        gg Alive
    pivot:
        gg Defeated

play greet(name):
    display("Player:", name)
    check name == "Ali":
        display("Welcome back, Ali!")
    pivot:
        display("Hello, stranger.")

play total(a, b, c, d, e):
    gg a + b + c + d + e

greet("Ali")

hp res = total(1, 2, 3, 4, 5)
display("Total:", res)

check res > 10:
    display("High score!")
pivot:
    display("Keep playing.")
"""


# ── CLI entry point ───────────────────────────────────────────────────────────

def print_help():
    print(f"""
{bold('GG Compiler')} — transpiles GG source to Python and runs it.

{bold('Usage:')}
  python program.py {yellow('<file.gg>')}                 compile and run a GG file
  python program.py {yellow('<file.gg>')} {cyan('--output')}        print generated Python
  python program.py {yellow('<file.gg>')} {cyan('--ast')}           print the AST
  python program.py {cyan('--example')}                  run the built-in demo
  python program.py {cyan('--help')}                     show this message
""")


def main():
    args = sys.argv[1:]

    if not args or '--help' in args or '-h' in args:
        print_help()
        sys.exit(0)

    # ── --example flag ────────────────────────────────────────────────────────
    if '--example' in args:
        print(bold("\n── Running built-in GG example ──\n"))
        print(yellow("Source:"))
        print(EXAMPLE_SOURCE)
        print(bold("─" * 50))
        python_code, ast = compile_source(EXAMPLE_SOURCE, "<example>")
        print(green("\n✔  Compilation successful — running …\n"))
        print(bold("─" * 50))
        run_python(python_code, "<example>")
        return

    # ── File argument ─────────────────────────────────────────────────────────
    filepath = args[0]

    if not os.path.isfile(filepath):
        print(red(f"[Error] File not found: {filepath!r}"))
        sys.exit(1)

    with open(filepath, encoding='utf-8') as f:
        source = f.read()

    show_output = '--output' in args
    show_ast    = '--ast'    in args

    print(bold(f"\n── GG Compiler ── {filepath}\n"))

    python_code, ast = compile_source(source, filepath)

    # ── Optional: print AST ───────────────────────────────────────────────────
    if show_ast:
        from parser import print_ast
        print(bold("\n── AST ──"))
        print_ast(ast)
        print()

    # ── Optional: print generated Python ─────────────────────────────────────
    if show_output:
        print(bold("\n── Generated Python ──"))
        for i, line in enumerate(python_code.splitlines(), 1):
            print(f"  {yellow(str(i).rjust(3))}  {line}")
        print()

    # ── Always run ────────────────────────────────────────────────────────────
    print(green("\n✔  Compilation successful — running …\n"))
    print(bold("─" * 50))
    run_python(python_code, filepath)
    print(bold("─" * 50))
    print(green("\n✔  Done.\n"))


if __name__ == '__main__':
    main()