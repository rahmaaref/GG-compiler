# ── GG Language Semantic Analyzer ────────────────────────────────────────────
# Checks:
#   A. Type Mismatch          — declared or inferred type violated on assignment
#   B. Undeclared Identifiers — variable / function used before definition
#   C. Multiple Declarations  — same name defined twice in the same scope
#   D. Parameter/Argument Mismatch — call site arg count ≠ formal param count
#   E. Invalid Control Flow   — gg/quit/retry used in illegal positions
# ─────────────────────────────────────────────────────────────────────────────

from symbol_table import SymbolTable

# ── Type system ───────────────────────────────────────────────────────────────

# Maps GG type-keyword → the set of AST literal node kinds that are valid
# assignments for that type.
#   'ping'  accepts Int because an integer is widened to float.
#   'score' accepts both Int and Float (generic numeric type).
TYPE_KEYWORDS = {
    'hp':     {'Int'},
    'ping':   {'Float', 'Int'},
    'agent':  {'String'},
    'result': {'Bool'},
    'Void':   {'None'},
    'score':  {'Int', 'Float'},
}

# Maps AST literal node kind → GG type keyword.
# Used by infer_type() and, crucially, by _check_type_compat() when comparing
# a val_type (which is a GG keyword like 'hp') against a stored declared type
# (also a GG keyword).  The comparison must stay in the same domain.
LITERAL_TYPE = {
    'Int':    'hp',
    'Float':  'ping',
    'String': 'agent',
    'Bool':   'result',
}

# Built-in names pre-populated into the global scope so that calls to
# display(), len(), range(), etc. are not flagged as undeclared.
# 'arity=None' means "variadic / don't check argument count".
_BUILTINS = {
    'display': None,
    'control': None,
    'range':   None,
    'len':     None,
    'print':   None,
    # type constructors — callable but variadic
    'hp':      None,
    'ping':    None,
    'agent':   None,
    'result':  None,
    'score':   None,
    'Void':    None,
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def infer_type(node):
    """
    Return the GG *keyword* for a literal node (e.g. 'hp' for an Int literal),
    or None for composite/dynamic expressions (BinOp, Var, Call, …).
    """
    if not isinstance(node, tuple):
        return None
    return LITERAL_TYPE.get(node[0])   # None for BinOp, Var, Call, etc.


# ── Analyzer ──────────────────────────────────────────────────────────────────

class SemanticAnalyzer:
    def __init__(self):
        self.table    = SymbolTable()
        self.errors   = []
        self._in_func = 0   # nesting depth inside function bodies
        self._in_loop = 0   # nesting depth inside loop bodies
        self._current_line = None   # line of the current statement being checked

        # Seed the global scope with built-ins.
        for name, arity in _BUILTINS.items():
            self.table.define(name, kind='builtin', arity=arity)

    # ── Error recording ───────────────────────────────────────────────────────

    def error(self, msg, line=None):
        prefix = f"Line {line}: " if line is not None else ""
        self.errors.append(f"[Semantic Error] {prefix}{msg}")

    # ── Line extraction ───────────────────────────────────────────────────────

    @staticmethod
    def _line(node):
        """
        Return the source line stored at position 1 of a statement node,
        or None for hand-built test ASTs that omit the line number.
        """
        if isinstance(node, tuple) and len(node) > 1 and isinstance(node[1], int):
            return node[1]
        return None

    # ── Entry point ───────────────────────────────────────────────────────────

    def analyze(self, ast):
        self.visit(ast)
        return self.errors

    # ── Generic visitor ───────────────────────────────────────────────────────

    def visit(self, node):
        if not isinstance(node, tuple):
            return
        # Update current line whenever a statement node carries one.
        line = self._line(node)
        if line is not None:
            self._current_line = line
        kind   = node[0]
        method = getattr(self, f'visit_{kind}', self.visit_default)
        method(node)

    def visit_default(self, node):
        """
        Fallback: recursively visit every child that is itself a node or list.
        This ensures that unrecognised compound nodes are still traversed
        rather than silently dropped.
        """
        for child in node[1:]:
            if isinstance(child, list):
                for item in child:
                    self.visit(item)
            elif isinstance(child, tuple):
                self.visit(child)

    def visit_children(self, items):
        """Visit a list of statement/expression nodes."""
        if isinstance(items, list):
            for item in items:
                self.visit(item)
        elif isinstance(items, tuple):
            self.visit(items)

    # ── Program ───────────────────────────────────────────────────────────────

    def visit_Program(self, node):
        _, stmts = node
        self.visit_children(stmts)

    # ── Assignments ───────────────────────────────────────────────────────────

    def visit_Assign(self, node):
        """Plain assignment without type annotation:  x = expr"""
        line = self._line(node)
        if line is not None:
            self._current_line = line
        fields = node[2:] if line is not None else node[1:]
        name, expr = fields[0], fields[1]
        self.visit(expr)

        val_type = infer_type(expr)
        existing = self.table.lookup(name)

        if existing is None or not self.table.is_defined_locally(name):
            self.table.define(name, kind='var', typ=val_type, declared=False)
        else:
            self._check_type_compat(name, existing, val_type, line)

    def visit_TypedAssign(self, node):
        """
        Typed declaration:  hp x = expr
        """
        line   = self._line(node)
        fields = node[2:] if line is not None else node[1:]
        type_kw, name, expr = fields[0], fields[1], fields[2]
        self.visit(expr)

        val_type = infer_type(expr)

        # ── C. Multiple Declarations ──────────────────────────────────────────
        if self.table.is_defined_locally(name):
            self.error(
                f"Multiple declarations: '{name}' is already declared "
                f"in this scope",
                line
            )

        # ── A. Type Mismatch ──────────────────────────────────────────────────
        if val_type is not None:
            allowed_ast_kinds = TYPE_KEYWORDS.get(type_kw, set())
            val_ast_kind = _gw_keyword_to_ast_kind(val_type)
            if val_ast_kind not in allowed_ast_kinds:
                self.error(
                    f"Type mismatch: '{name}' declared as '{type_kw}' "
                    f"but assigned a '{val_type}' value",
                    line
                )

        self.table.define(name, kind='var', typ=type_kw, declared=True)

    def visit_AugAssign(self, node):
        """Augmented assignment:  x += expr"""
        line   = self._line(node)
        fields = node[2:] if line is not None else node[1:]
        _op, name, expr = fields[0], fields[1], fields[2]
        # ── B. Undeclared Identifier ──────────────────────────────────────────
        if not self.table.lookup(name):
            self.error(
                f"Undeclared variable '{name}' used in augmented assignment",
                line
            )
        self.visit(expr)

    # ── Type-check helper ─────────────────────────────────────────────────────

    def _check_type_compat(self, name, existing, val_type, line=None):
        """
        Compare the stored type of 'name' against the incoming value type.
        Only reports an error when *both* sides are concretely known.
        """
        stored = existing.get('type')

        if stored is None or val_type is None:
            if stored is None and val_type is not None:
                self.table.update_type(name, val_type)
            return

        if existing.get('declared'):
            allowed_ast_kinds = TYPE_KEYWORDS.get(stored, set())
            val_ast_kind      = _gw_keyword_to_ast_kind(val_type)
            if val_ast_kind not in allowed_ast_kinds:
                self.error(
                    f"Type mismatch: '{name}' was declared as '{stored}' "
                    f"but reassigned a '{val_type}' value",
                    line
                )
        else:
            if val_type != stored:
                self.error(
                    f"Type mismatch: '{name}' was inferred as '{stored}' "
                    f"but reassigned a '{val_type}' value",
                    line
                )

    # ── Control-flow statements ───────────────────────────────────────────────

    def visit_Print(self, node):
        line   = self._line(node)
        fields = node[2:] if line is not None else node[1:]
        self.visit_children(fields[0])

    def visit_Return(self, node):
        line = self._line(node)
        # ── E. Invalid Control Flow ───────────────────────────────────────────
        if self._in_func == 0:
            self.error("'gg' (return) used outside a function", line)
        fields = node[2:] if line is not None else node[1:]
        expr = fields[0] if fields else None
        if expr:
            self.visit(expr)

    def visit_Break(self, node):
        line = self._line(node)
        # ── E. Invalid Control Flow ───────────────────────────────────────────
        if self._in_loop == 0:
            self.error("'quit' (break) used outside a loop", line)

    def visit_Continue(self, node):
        line = self._line(node)
        # ── E. Invalid Control Flow ───────────────────────────────────────────
        if self._in_loop == 0:
            self.error("'retry' (continue) used outside a loop", line)

    def visit_ExprStmt(self, node):
        fields = node[2:] if self._line(node) is not None else node[1:]
        self.visit(fields[0])

    # ── Compound statements ───────────────────────────────────────────────────

    def visit_If(self, node):
        line   = self._line(node)
        fields = node[2:] if line is not None else node[1:]
        cond, body, elifs, else_body = fields[0], fields[1], fields[2], fields[3]
        self.visit(cond)
        self.table.enter_scope()
        self.visit_children(body)
        self.table.exit_scope()

        for ec, eb in elifs:
            self.visit(ec)
            self.table.enter_scope()
            self.visit_children(eb)
            self.table.exit_scope()

        if else_body:
            self.table.enter_scope()
            self.visit_children(else_body)
            self.table.exit_scope()

    def visit_While(self, node):
        line   = self._line(node)
        fields = node[2:] if line is not None else node[1:]
        cond, body = fields[0], fields[1]
        self.visit(cond)
        self._in_loop += 1
        self.table.enter_scope()
        self.visit_children(body)
        self.table.exit_scope()
        self._in_loop -= 1

    def visit_For(self, node):
        line   = self._line(node)
        fields = node[2:] if line is not None else node[1:]
        var, iterable, body = fields[0], fields[1], fields[2]
        self.visit(iterable)
        self._in_loop += 1
        self.table.enter_scope()
        self.table.define(var, kind='var')
        self.visit_children(body)
        self.table.exit_scope()
        self._in_loop -= 1

    def visit_FuncDef(self, node):
        """Function definition."""
        line   = self._line(node)
        fields = node[2:] if line is not None else node[1:]
        name, params, body = fields[0], fields[1], fields[2]

        # ── C. Multiple Declarations ──────────────────────────────────────────
        if self.table.is_defined_locally(name):
            self.error(
                f"Multiple declarations: function '{name}' is already defined "
                f"in this scope",
                line
            )

        self.table.define(name, kind='func', arity=len(params))

        self.table.enter_scope()
        self._in_func += 1
        for p in params:
            param_name = p if isinstance(p, str) else p[-1]
            self.table.define(param_name, kind='param')
        self.visit_children(body)
        self._in_func -= 1
        self.table.exit_scope()

    def visit_ClassDef(self, node):
        line   = self._line(node)
        fields = node[2:] if line is not None else node[1:]
        name, body = fields[0], fields[1]
        # ── C. Multiple Declarations ──────────────────────────────────────────
        if self.table.is_defined_locally(name):
            self.error(
                f"Multiple declarations: class '{name}' is already defined "
                f"in this scope",
                line
            )
        self.table.define(name, kind='class')

        self.table.enter_scope()
        self.visit_children(body)
        self.table.exit_scope()

    # ── Expressions ───────────────────────────────────────────────────────────

    def visit_Var(self, node):
        _, name = node
        # ── B. Undeclared Identifier ──────────────────────────────────────────
        if not self.table.lookup(name):
            self.error(f"Undeclared variable '{name}'", self._current_line)

    def visit_Call(self, node):
        """
        Check function calls: undeclared target and argument count.
        """
        _, target, args = node

        # ── Resolve the function name from either form ────────────────────────
        if isinstance(target, str):
            func_name = target
        elif isinstance(target, tuple) and target[0] == 'Var':
            func_name = target[1]
        else:
            func_name = None

        if func_name is not None:
            sym = self.table.lookup(func_name)

            # ── B. Undeclared Identifier ──────────────────────────────────────
            if sym is None:
                self.error(
                    f"Call to undeclared function '{func_name}'",
                    self._current_line
                )
            else:
                # ── D. Parameter/Argument Mismatch ────────────────────────────
                expected = sym.get('arity')
                if expected is not None:
                    got = len(args)
                    if got != expected:
                        self.error(
                            f"Argument mismatch: '{func_name}' expects "
                            f"{expected} argument(s) but got {got}",
                            self._current_line
                        )

        self.visit_children(args)


    def visit_BinOp(self, node):
        _, _op, left, right = node
        self.visit(left)
        self.visit(right)

    def visit_UnaryOp(self, node):
        _, _op, operand = node
        self.visit(operand)

    # Literal leaf nodes — nothing to check, just stop recursion.
    def visit_Int(self, node):    pass
    def visit_Float(self, node):  pass
    def visit_String(self, node): pass
    def visit_Bool(self, node):   pass
    def visit_None(self, node):   pass


# ── Module-level helpers ──────────────────────────────────────────────────────

# Reverse map: GG keyword → the canonical AST literal kind for that type.
# Used when we need to look up a GG keyword in TYPE_KEYWORDS (which stores
# AST kinds as values).  For widened types like 'ping' (Float|Int) and
# 'score' (Int|Float) we return the *primary* AST kind; the full set in
# TYPE_KEYWORDS handles the widening check.
_GW_KEYWORD_TO_AST = {v: k for k, v in LITERAL_TYPE.items()}
# LITERAL_TYPE = {'Int':'hp', 'Float':'ping', 'String':'agent', 'Bool':'result'}
# Reversed:      {'hp':'Int', 'ping':'Float', 'agent':'String', 'result':'Bool'}

def _gw_keyword_to_ast_kind(gw_keyword):
    """
    Convert a GG type keyword to its primary AST literal kind.
    e.g. 'hp' → 'Int',  'ping' → 'Float',  'agent' → 'String'
    Returns None if the keyword is not a literal type (e.g. 'Void').
    """
    return _GW_KEYWORD_TO_AST.get(gw_keyword)


# ── Public entry point ────────────────────────────────────────────────────────

def analyze(ast):
    """Run semantic analysis and return a (possibly empty) list of error strings."""
    return SemanticAnalyzer().analyze(ast)


# ── Self-contained test (no scanner/parser needed) ───────────────────────────

if __name__ == '__main__':
    def run(label, ast):
        errors = analyze(ast)
        print(f"\n{'─'*60}")
        print(f"  TEST: {label}")
        print(f"{'─'*60}")
        if errors:
            for e in errors:
                print(f"  {e}")
        else:
            print("  OK — no errors")

    # ── A. Type Mismatch ─────────────────────────────────────────────────────

    run("A1 — declared hp, reassigned agent (should error)",
        ('Program', [
            ('TypedAssign', 'hp',    'x', ('Int',    5)),
            ('Assign',               'x', ('String', 'hi')),
        ]))

    run("A2 — inferred hp, reassigned agent (should error)",
        ('Program', [
            ('Assign', 'y', ('Int',    10)),
            ('Assign', 'y', ('String', 'hello')),
        ]))

    run("A3 — ping accepts Int literal (widening, should be OK)",
        ('Program', [
            ('TypedAssign', 'ping', 'f', ('Int', 3)),
        ]))

    run("A4 — TypedAssign mismatch on declaration itself (should error)",
        ('Program', [
            ('TypedAssign', 'agent', 'name', ('Int', 42)),
        ]))

    # ── B. Undeclared Identifiers ────────────────────────────────────────────

    run("B1 — use undeclared variable (should error)",
        ('Program', [
            ('ExprStmt', ('Var', 'ghost')),
        ]))

    run("B2 — call undeclared function (should error)",
        ('Program', [
            ('ExprStmt', ('Call', 'mystery', [])),
        ]))

    run("B3 — augmented assign to undeclared var (should error)",
        ('Program', [
            ('AugAssign', '+=', 'z', ('Int', 1)),
        ]))

    # ── C. Multiple Declarations ─────────────────────────────────────────────

    run("C1 — redeclare variable in same scope (should error)",
        ('Program', [
            ('TypedAssign', 'hp', 'x', ('Int', 1)),
            ('TypedAssign', 'hp', 'x', ('Int', 2)),
        ]))

    run("C2 — redeclare function in same scope (should error)",
        ('Program', [
            ('FuncDef', 'foo', [], [('Return', ('Int', 0))]),
            ('FuncDef', 'foo', [], [('Return', ('Int', 1))]),
        ]))

    run("C3 — same name OK in nested scope (should be OK)",
        ('Program', [
            ('TypedAssign', 'hp', 'x', ('Int', 1)),
            ('If',
                ('Bool', True),
                [('TypedAssign', 'hp', 'x', ('Int', 2))],  # inner scope
                [],
                None),
        ]))

    # ── D. Parameter/Argument Mismatch ──────────────────────────────────────

    run("D1 — too few arguments (should error)",
        ('Program', [
            ('FuncDef', 'add', ['a', 'b'], [('Return', ('Var', 'a'))]),
            ('ExprStmt', ('Call', 'add', [('Int', 1)])),
        ]))

    run("D2 — too many arguments (should error)",
        ('Program', [
            ('FuncDef', 'greet', ['name'], [('Return', ('Var', 'name'))]),
            ('ExprStmt', ('Call', 'greet', [('String', 'Ali'), ('Int', 99)])),
        ]))

    run("D3 — correct argument count (should be OK)",
        ('Program', [
            ('FuncDef', 'square', ['n'], [('Return', ('Var', 'n'))]),
            ('ExprStmt', ('Call', 'square', [('Int', 4)])),
        ]))

    # ── E. Invalid Control Flow ──────────────────────────────────────────────

    run("E1 — gg (return) outside function (should error)",
        ('Program', [
            ('Return', ('Int', 0)),
        ]))

    run("E2 — quit (break) outside loop (should error)",
        ('Program', [
            ('Break',),
        ]))

    run("E3 — retry (continue) outside loop (should error)",
        ('Program', [
            ('Continue',),
        ]))

    run("E4 — gg inside function, quit inside loop (should be OK)",
        ('Program', [
            ('FuncDef', 'demo', [], [
                ('While',
                    ('Bool', True),
                    [
                        ('Break',),
                        ('Continue',),
                    ]),
                ('Return', ('Int', 1)),
            ]),
        ]))