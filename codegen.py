# ── GG Language Code Generator ───────────────────────────────────────────────
# Input : validated AST produced by parser.py (after semantic analysis)
# Output: a Python source string
#
# GG → Python keyword map
#   hp / ping / agent / result / score  →  (type annotations dropped)
#   check   → if        or check → elif     pivot  → else
#   grind   → while     farm … in → for
#   play    → def       squad     → class
#   gg      → return    quit      → break    retry  → continue
#   display → print
#   alive   → True      defeated  → False    (handled in scanner/parser already)
#
# All operators (+  -  *  /  %  ==  !=  <  >  <=  >=  and  or  not) are
# identical in GG and Python, so they are passed through unchanged.
# ─────────────────────────────────────────────────────────────────────────────

_INDENT = "    "   # 4-space indent per level


class CodeGenerator:

    def __init__(self):
        self._depth = 0          # current indentation depth
        self._lines = []         # accumulated output lines

    # ── Public entry point ────────────────────────────────────────────────────

    def generate(self, ast):
        """
        Walk the AST and return the complete Python source as a string.
        Resets internal state so the same instance can be reused.
        """
        self._depth = 0
        self._lines = []
        self._gen(ast)
        return "\n".join(self._lines)

    # ── Indentation helpers ───────────────────────────────────────────────────

    def _emit(self, line):
        """Append one line at the current indentation level."""
        self._lines.append(_INDENT * self._depth + line)

    def _indent(self):
        self._depth += 1

    def _dedent(self):
        self._depth = max(0, self._depth - 1)

    # ── Dispatcher ────────────────────────────────────────────────────────────

    def _gen(self, node):
        """
        Route a node to its handler.
        Statement handlers call _emit() and return None.
        Expression handlers return a Python source string.
        """
        if not isinstance(node, tuple):
            return str(node)

        kind   = node[0]
        method = getattr(self, f"_gen_{kind}", None)

        if method is None:
            raise NotImplementedError(
                f"CodeGenerator: no handler for AST node '{kind}'"
            )

        return method(node)

    # ── Program ───────────────────────────────────────────────────────────────

    # ── Node field accessor ───────────────────────────────────────────────────

    @staticmethod
    def _fields(node):
        """
        Return node fields after the kind tag, skipping an optional line number
        at position 1.  Nodes from the parser include a line int; hand-built
        test ASTs may omit it.  We detect it by checking whether position 1 is
        an int.
        """
        if len(node) > 1 and isinstance(node[1], int):
            return node[2:]   # skip kind + line
        return node[1:]       # skip kind only

    # ── Program ───────────────────────────────────────────────────────────────

    def _gen_Program(self, node):
        _, stmts = node
        for stmt in stmts:
            self._gen(stmt)

    # ── Assignments ───────────────────────────────────────────────────────────

    def _gen_Assign(self, node):
        """x = expr"""
        name, expr = self._fields(node)
        self._emit(f"{name} = {self._gen(expr)}")

    def _gen_TypedAssign(self, node):
        """
        hp x = expr   →   x = expr
        The GG type keyword is dropped; Python is dynamically typed.
        """
        _type_kw, name, expr = self._fields(node)
        self._emit(f"{name} = {self._gen(expr)}")

    def _gen_AugAssign(self, node):
        """x += expr  (op already contains the full token e.g. '+=')"""
        op, name, expr = self._fields(node)
        # op from the parser is the full augmented-assign token e.g. '+='
        # If the scanner stores only the base operator ('+') we build it here.
        aug_op = op if op.endswith('=') else f"{op}="
        self._emit(f"{name} {aug_op} {self._gen(expr)}")

    # ── Print ─────────────────────────────────────────────────────────────────

    def _gen_Print(self, node):
        """display(a, b)  →  print(a, b)"""
        (args,) = self._fields(node)
        arg_str = ", ".join(self._gen(a) for a in args)
        self._emit(f"print({arg_str})")

    # ── Control-flow statements ───────────────────────────────────────────────

    def _gen_Return(self, node):
        """gg expr  →  return expr      bare gg  →  return"""
        fields = self._fields(node)
        expr   = fields[0] if fields else None
        if expr is not None:
            self._emit(f"return {self._gen(expr)}")
        else:
            self._emit("return")

    def _gen_Break(self, node):
        """quit  →  break"""
        self._emit("break")

    def _gen_Continue(self, node):
        """retry  →  continue"""
        self._emit("continue")

    def _gen_ExprStmt(self, node):
        """A bare expression used as a statement (e.g. a function call)."""
        (expr,) = self._fields(node)
        self._emit(self._gen(expr))

    # ── Compound statements ───────────────────────────────────────────────────

    def _gen_If(self, node):
        """
        check cond:          →  if cond:
            …                       …
        or check cond:       →  elif cond:
            …                       …
        pivot:               →  else:
            …                       …
        """
        cond, body, elifs, else_body = self._fields(node)

        self._emit(f"if {self._gen(cond)}:")
        self._indent()
        self._gen_body(body)
        self._dedent()

        for ec, eb in elifs:
            self._emit(f"elif {self._gen(ec)}:")
            self._indent()
            self._gen_body(eb)
            self._dedent()

        if else_body is not None:
            self._emit("else:")
            self._indent()
            self._gen_body(else_body)
            self._dedent()

    def _gen_While(self, node):
        """grind cond:  →  while cond:"""
        cond, body = self._fields(node)
        self._emit(f"while {self._gen(cond)}:")
        self._indent()
        self._gen_body(body)
        self._dedent()

    def _gen_For(self, node):
        """farm i in iterable:  →  for i in iterable:"""
        var, iterable, body = self._fields(node)
        self._emit(f"for {var} in {self._gen(iterable)}:")
        self._indent()
        self._gen_body(body)
        self._dedent()

    def _gen_FuncDef(self, node):
        """play foo(a, b):  →  def foo(a, b):"""
        name, params, body = self._fields(node)
        param_str = ", ".join(params)
        self._emit(f"def {name}({param_str}):")
        self._indent()
        self._gen_body(body)
        self._dedent()

    def _gen_ClassDef(self, node):
        """squad MyClass:  →  class MyClass:"""
        name, body = self._fields(node)
        self._emit(f"class {name}:")
        self._indent()
        self._gen_body(body)
        self._dedent()

    def _gen_body(self, stmts):
        """
        Emit a block of statements.
        An empty body emits 'pass' so the Python block is always valid.
        """
        if not stmts:
            self._emit("pass")
            return
        for stmt in stmts:
            self._gen(stmt)

    # ── Expressions (return strings) ──────────────────────────────────────────

    def _gen_BinOp(self, node):
        """
        ('BinOp', op, left, right)
        All operators are Python-identical so we pass them through directly.
        Parentheses are added around each operand to preserve precedence
        exactly as the parser resolved it.
        """
        _, op, left, right = node
        return f"({self._gen(left)} {op} {self._gen(right)})"

    def _gen_UnaryOp(self, node):
        """('UnaryOp', op, operand)  →  op operand"""
        _, op, operand = node
        # 'not' needs a space; '-' does not strictly but a space is cleaner.
        return f"({op} {self._gen(operand)})"

    def _gen_Call(self, node):
        """
        ('Call', name, args)
        'display' is GG's built-in print — mapped to Python's print().
        All other names pass through unchanged.
        """
        _, name, args = node
        py_name  = "print" if name == "display" else name
        arg_str  = ", ".join(self._gen(a) for a in args)
        return f"{py_name}({arg_str})"

    def _gen_Var(self, node):
        """('Var', name)  →  name"""
        _, name = node
        return name

    # ── Literals ──────────────────────────────────────────────────────────────

    def _gen_Int(self, node):
        """('Int', value)  →  '42'"""
        return str(node[1])

    def _gen_Float(self, node):
        """('Float', value)  →  '3.14'"""
        return repr(node[1])   # repr avoids precision surprises

    def _gen_String(self, node):
        """
        ('String', value)  →  '"hello"'
        The parser already strips the surrounding quotes, so we re-add them.
        repr() handles embedded quotes, backslashes, etc. correctly.
        """
        return repr(node[1])

    def _gen_Bool(self, node):
        """('Bool', True/False)  →  'True' / 'False'"""
        return "True" if node[1] else "False"

    def _gen_None(self, node):
        """('None', …)  →  'None'"""
        return "None"


# ── Module-level entry point ──────────────────────────────────────────────────

def generate(ast):
    """Run code generation and return the Python source string."""
    return CodeGenerator().generate(ast)


# ── Self-contained test suite ─────────────────────────────────────────────────

if __name__ == "__main__":

    from semantic import analyze

    def run(label, ast, expect_lines=None):
        print(f"\n{'─' * 60}")
        print(f"  TEST: {label}")
        print(f"{'─' * 60}")

        errors = analyze(ast)
        if errors:
            print("  [Skipped — semantic errors]")
            for e in errors:
                print(f"    {e}")
            return

        code = generate(ast)
        print(code)

        if expect_lines:
            for line in expect_lines:
                assert line in code, f"MISSING: {line!r}"
            print("  ✓ all expected lines present")

    # ── A. Assignments ────────────────────────────────────────────────────────

    run("Typed assign — hp x = 5",
        ('Program', [('TypedAssign', 'hp', 'x', ('Int', 5))]),
        expect_lines=["x = 5"])

    run("Plain assign — x = 3.14",
        ('Program', [('Assign', 'x', ('Float', 3.14))]),
        expect_lines=["x = 3.14"])

    run("Augmented assign — x += 1",
        ('Program', [
            ('Assign', 'x', ('Int', 0)),
            ('AugAssign', '+=', 'x', ('Int', 1)),
        ]),
        expect_lines=["x = 0", "x += 1"])

    run("String assign",
        ('Program', [('TypedAssign', 'agent', 'name', ('String', 'Ali'))]),
        expect_lines=["name = 'Ali'"])

    run("Bool assign — alive / defeated",
        ('Program', [
            ('TypedAssign', 'result', 'a', ('Bool', True)),
            ('TypedAssign', 'result', 'b', ('Bool', False)),
        ]),
        expect_lines=["a = True", "b = False"])

    # ── B. Expressions ────────────────────────────────────────────────────────

    run("BinOp arithmetic — 2 + 3 * 4",
        ('Program', [
            ('Assign', 'x',
                ('BinOp', '+', ('Int', 2),
                    ('BinOp', '*', ('Int', 3), ('Int', 4))))
        ]),
        expect_lines=["x = (2 + (3 * 4))"])

    run("UnaryOp — not alive",
        ('Program', [
            ('Assign', 'flag', ('UnaryOp', 'not', ('Bool', True)))
        ]),
        expect_lines=["flag = (not True)"])

    run("Comparison — a > 50",
        ('Program', [
            ('Assign', 'a', ('Int', 60)),
            ('Assign', 'ok', ('BinOp', '>', ('Var', 'a'), ('Int', 50))),
        ]),
        expect_lines=["a = 60", "ok = (a > 50)"])

    # ── C. Control flow ───────────────────────────────────────────────────────

    run("If / elif / else",
        ('Program', [
            ('Assign', 'x', ('Int', 10)),
            ('If',
                ('BinOp', '>', ('Var', 'x'), ('Int', 5)),
                [('Print', [('String', 'big')])],
                [
                    (('BinOp', '==', ('Var', 'x'), ('Int', 5)),
                     [('Print', [('String', 'equal')])])
                ],
                [('Print', [('String', 'small')])],
            ),
        ]),
        expect_lines=["if (x > 5):", "    print('big')",
                      "elif (x == 5):", "    print('equal')",
                      "else:", "    print('small')"])

    run("While loop with break and continue",
        ('Program', [
            ('Assign', 'i', ('Int', 0)),
            ('While',
                ('BinOp', '<', ('Var', 'i'), ('Int', 10)),
                [
                    ('If',
                        ('BinOp', '==', ('Var', 'i'), ('Int', 5)),
                        [('Break',)], [], None),
                    ('Continue',),
                ]),
        ]),
        expect_lines=["while (i < 10):", "    break", "    continue"])

    run("For loop",
        ('Program', [
            ('For', 'i',
                ('Call', 'range', [('Int', 5)]),
                [('Print', [('Var', 'i')])])
        ]),
        expect_lines=["for i in range(5):", "    print(i)"])

    # ── D. Functions ──────────────────────────────────────────────────────────

    run("Function definition and call",
        ('Program', [
            ('FuncDef', 'add', ['a', 'b'], [
                ('Return', ('BinOp', '+', ('Var', 'a'), ('Var', 'b')))
            ]),
            ('Assign', 'result', ('Call', 'add', [('Int', 3), ('Int', 4)])),
        ]),
        expect_lines=["def add(a, b):", "    return (a + b)",
                      "result = add(3, 4)"])

    run("Recursive function",
        ('Program', [
            ('FuncDef', 'fact', ['n'], [
                ('If',
                    ('BinOp', '==', ('Var', 'n'), ('Int', 0)),
                    [('Return', ('Int', 1))],
                    [],
                    None),
                ('Return',
                    ('BinOp', '*', ('Var', 'n'),
                        ('Call', 'fact',
                            [('BinOp', '-', ('Var', 'n'), ('Int', 1))])))
            ]),
        ]),
        expect_lines=["def fact(n):", "    if (n == 0):",
                      "        return 1", "    return (n * fact((n - 1)))"])

    run("Empty function body → pass",
        ('Program', [
            ('FuncDef', 'noop', [], []),
        ]),
        expect_lines=["def noop():", "    pass"])

    # ── E. Class ─────────────────────────────────────────────────────────────

    run("Class definition",
        ('Program', [
            ('ClassDef', 'Hero', [
                ('FuncDef', '__init__', ['self', 'name'], [
                    ('Assign', 'self.name', ('Var', 'name')),
                ]),
            ]),
        ]),
        expect_lines=["class Hero:", "    def __init__(self, name):"])

    # ── F. display → print mapping ────────────────────────────────────────────

    run("display() maps to print()",
        ('Program', [
            ('ExprStmt', ('Call', 'display', [('String', 'hello')]))
        ]),
        expect_lines=["print('hello')"])