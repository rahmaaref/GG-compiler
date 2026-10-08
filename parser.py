# ── GG Language Parser ────────────────────────────────────────────────────────
# Input : token list from scanner.py
# Output: AST as nested tuples/lists
#
# Fixes applied:
#   FIX 1 — type keywords (hp, ping, agent, result, score, Void) followed by
#            '(' are treated as call expressions, not typed declarations.
#            Handled in BOTH simple_stmt() (statement position) and
#            primary() (expression position).
#            e.g.  s = score(2)      → ('Assign', 's', ('Call', 'score', [...]))
#                  energy = hp(control()) → ('Assign', 'energy', ('Call', 'hp', [...]))
#                  hp(control())     → ('ExprStmt', ('Call', 'hp', [...]))
#
#   FIX 2 — for-loop 'in' keyword: peek before consuming so a wrong token
#            is caught with a useful error message instead of being silently
#            eaten and causing a confusing error one token later.
#
#   FIX 3 — test code is inside  if __name__ == '__main__'  so importing
#            this module from server.py never triggers test runs.
# ─────────────────────────────────────────────────────────────────────────────

# All type-keyword token kinds that can appear as cast/constructor calls
_TYPE_TOKENS = ('INT_T', 'FLOAT_T', 'STR_T', 'BOOL_T', 'NONE_T', 'SCORE_T')


class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos    = 0
        self.line   = 1   # current source line (updated on every consume)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _tok_line(self, tok):
        """Extract line number from a token (2-tuple or 3-tuple)."""
        return tok[2] if len(tok) > 2 else self.line

    def peek(self):
        if self.pos < len(self.tokens):
            return self.tokens[self.pos][0]
        return 'EOF'

    def peek_val(self):
        if self.pos < len(self.tokens):
            return self.tokens[self.pos][1]
        return None

    def peek_next_kind(self):
        """Return the token kind one position ahead (without consuming)."""
        nxt = self.pos + 1
        if nxt < len(self.tokens):
            return self.tokens[nxt][0]
        return 'EOF'

    def consume(self):
        tok = self.tokens[self.pos]
        self.line = self._tok_line(tok)
        self.pos += 1
        return tok

    def expect(self, kind):
        if self.peek() != kind:
            raise SyntaxError(
                f"Line {self.line}: expected {kind} "
                f"but got {self.peek()!r} ({self.peek_val()!r})"
            )
        return self.consume()

    def skip_newlines(self):
        while self.peek() == 'NEWLINE':
            self.consume()

    # ── Program ───────────────────────────────────────────────────────────────

    def parse(self):
        self.skip_newlines()
        stmts = self.stmt_list()
        self.skip_newlines()

        if self.peek() != 'EOF':
            raise SyntaxError(
                f"Line {self.line}: unexpected token at end: "
                f"{self.peek()!r} ({self.peek_val()!r})"
            )

        return ('Program', stmts)

    # ── Statement list ────────────────────────────────────────────────────────

    def stmt_list(self):
        stmts = []

        while self.peek() not in ('EOF', 'DEDENT'):
            self.skip_newlines()
            if self.peek() in ('EOF', 'DEDENT'):
                break
            stmts.append(self.stmt())
            self.skip_newlines()

        return stmts

    # ── Statement ─────────────────────────────────────────────────────────────

    def stmt(self):
        k = self.peek()

        if k == 'IF':    return self.if_stmt()
        if k == 'WHILE': return self.while_stmt()
        if k == 'FOR':   return self.for_stmt()
        if k == 'DEF':   return self.func_def()
        if k == 'CLASS': return self.class_def()

        return self.simple_stmt()

    # ── Simple statements ─────────────────────────────────────────────────────

    def simple_stmt(self):
        k = self.peek()

        if k == 'PRINT':
            return self.print_stmt()

        if k == 'RETURN':
            return self.return_stmt()

        if k == 'BREAK':
            line = self.line
            self.consume()
            return ('Break', line)

        if k == 'CONTINUE':
            line = self.line
            self.consume()
            return ('Continue', line)

        # ── FIX 1 (statement position) ────────────────────────────────────────
        # A type keyword followed by '(' is a cast/constructor call, not a
        # typed declaration.
        #   score(2)        → ExprStmt  Call
        #   hp(control())   → ExprStmt  Call
        #   hp x = 5        → TypedAssign   (next token is ID, not LPAREN)
        if k in _TYPE_TOKENS:
            if self.peek_next_kind() == 'LPAREN':
                line = self.line
                name = self.consume()[1]   # consume type keyword as function name
                self.consume()             # consume '('
                args = self.expr_list()
                self.expect('RPAREN')
                return ('ExprStmt', line, ('Call', name, args))
            return self.typed_assign()

        # ID followed by ASSIGN → plain or augmented assignment
        if k == 'ID' and self.peek_next_kind() == 'ASSIGN':
            return self.assignment()

        line = self.line
        return ('ExprStmt', line, self.expr())

    def assignment(self):
        line = self.line
        name = self.expect('ID')[1]
        op   = self.expect('ASSIGN')[1]
        val  = self.expr()

        if op == '=':
            return ('Assign', line, name, val)
        return ('AugAssign', line, op, name, val)

    def typed_assign(self):
        line    = self.line
        type_kw = self.consume()[1]
        name    = self.expect('ID')[1]
        self.expect('ASSIGN')
        val = self.expr()
        return ('TypedAssign', line, type_kw, name, val)

    def print_stmt(self):
        line = self.line
        self.expect('PRINT')
        self.expect('LPAREN')
        args = self.expr_list()
        self.expect('RPAREN')
        return ('Print', line, args)

    def return_stmt(self):
        line = self.line
        self.expect('RETURN')
        if self.peek() in ('NEWLINE', 'EOF', 'DEDENT'):
            return ('Return', line, None)
        return ('Return', line, self.expr())

    # ── Compound statements ───────────────────────────────────────────────────

    def if_stmt(self):
        line = self.line
        self.expect('IF')
        cond = self.expr()
        self.expect('COLON')
        self.expect('NEWLINE')
        self.expect('INDENT')
        body = self.stmt_list()
        self.expect('DEDENT')

        elifs = []
        while self.peek() == 'ELIF':
            self.consume()
            ec = self.expr()
            self.expect('COLON')
            self.expect('NEWLINE')
            self.expect('INDENT')
            eb = self.stmt_list()
            self.expect('DEDENT')
            elifs.append((ec, eb))

        else_body = None
        if self.peek() == 'ELSE':
            self.consume()
            self.expect('COLON')
            self.expect('NEWLINE')
            self.expect('INDENT')
            else_body = self.stmt_list()
            self.expect('DEDENT')

        return ('If', line, cond, body, elifs, else_body)

    def while_stmt(self):
        line = self.line
        self.expect('WHILE')
        cond = self.expr()
        self.expect('COLON')
        self.expect('NEWLINE')
        self.expect('INDENT')
        body = self.stmt_list()
        self.expect('DEDENT')
        return ('While', line, cond, body)

    def for_stmt(self):
        # FIX 2 — peek at 'in' before consuming so errors are caught cleanly.
        line = self.line
        self.expect('FOR')
        var = self.expect('ID')[1]

        if self.peek() != 'ID' or self.peek_val() != 'in':
            raise SyntaxError(
                f"Line {self.line}: expected 'in' after loop variable '{var}' "
                f"but got {self.peek()!r} ({self.peek_val()!r})"
            )
        self.consume()   # consume 'in'

        iterable = self.expr()
        self.expect('COLON')
        self.expect('NEWLINE')
        self.expect('INDENT')
        body = self.stmt_list()
        self.expect('DEDENT')
        return ('For', line, var, iterable, body)

    def func_def(self):
        line = self.line
        self.expect('DEF')
        name = self.expect('ID')[1]
        self.expect('LPAREN')
        params = self.param_list()
        self.expect('RPAREN')
        self.expect('COLON')
        self.expect('NEWLINE')
        self.expect('INDENT')
        body = self.stmt_list()
        self.expect('DEDENT')
        return ('FuncDef', line, name, params, body)

    def class_def(self):
        line = self.line
        self.expect('CLASS')
        name = self.expect('ID')[1]
        self.expect('COLON')
        self.expect('NEWLINE')
        self.expect('INDENT')
        body = self.stmt_list()
        self.expect('DEDENT')
        return ('ClassDef', line, name, body)

    # ── Parameter / argument lists ────────────────────────────────────────────

    def param_list(self):
        params = []
        if self.peek() == 'ID':
            params.append(self.consume()[1])
            while self.peek() == 'COMMA':
                self.consume()
                params.append(self.expect('ID')[1])
        return params

    def expr_list(self):
        if self.peek() == 'RPAREN':
            return []
        args = [self.expr()]
        while self.peek() == 'COMMA':
            self.consume()
            args.append(self.expr())
        return args

    # ── Expressions ───────────────────────────────────────────────────────────

    def expr(self):
        return self.or_expr()

    def or_expr(self):
        node = self.and_expr()
        while self.peek() == 'OP' and self.peek_val() == 'or':
            self.consume()
            node = ('BinOp', 'or', node, self.and_expr())
        return node

    def and_expr(self):
        node = self.not_expr()
        while self.peek() == 'OP' and self.peek_val() == 'and':
            self.consume()
            node = ('BinOp', 'and', node, self.not_expr())
        return node

    def not_expr(self):
        if self.peek() == 'OP' and self.peek_val() == 'not':
            self.consume()
            return ('UnaryOp', 'not', self.not_expr())
        return self.rel_expr()

    def rel_expr(self):
        node = self.add_expr()
        REL  = {'==', '!=', '<', '>', '<=', '>='}
        while self.peek() == 'OP' and self.peek_val() in REL:
            op   = self.consume()[1]
            node = ('BinOp', op, node, self.add_expr())
        return node

    def add_expr(self):
        node = self.mul_expr()
        while self.peek() == 'OP' and self.peek_val() in ('+', '-'):
            op   = self.consume()[1]
            node = ('BinOp', op, node, self.mul_expr())
        return node

    def mul_expr(self):
        node = self.unary_expr()
        while self.peek() == 'OP' and self.peek_val() in ('*', '/', '%'):
            op   = self.consume()[1]
            node = ('BinOp', op, node, self.unary_expr())
        return node

    def unary_expr(self):
        if self.peek() == 'OP' and self.peek_val() == '-':
            self.consume()
            return ('UnaryOp', '-', self.unary_expr())
        return self.primary()

    # ── Primary ───────────────────────────────────────────────────────────────

    def primary(self):
        k = self.peek()
        v = self.peek_val()

        if k == 'INT':
            self.consume()
            return ('Int', int(v))

        if k == 'FLOAT':
            self.consume()
            return ('Float', float(v))

        if k == 'STRING':
            self.consume()
            return ('String', v[1:-1])

        if k == 'TRUE':
            self.consume()
            return ('Bool', True)

        if k == 'FALSE':
            self.consume()
            return ('Bool', False)

        # ── FIX 1 (expression position) ───────────────────────────────────────
        # Type keyword inside an expression — always a cast call.
        #   x = score(2)        → ('Call', 'score', [('Int', 2)])
        #   x = hp(control())   → ('Call', 'hp',    [('Call', 'control', [])])
        #   x = ping(3)         → ('Call', 'ping',  [('Int', 3)])
        if k in _TYPE_TOKENS:
            name = self.consume()[1]
            if self.peek() == 'LPAREN':
                self.consume()
                args = self.expr_list()
                self.expect('RPAREN')
                return ('Call', name, args)
            # bare type keyword used as a value — treat as variable reference
            return ('Var', name)

        if k == 'ID':
            name = self.consume()[1]
            if self.peek() == 'LPAREN':
                self.consume()
                args = self.expr_list()
                self.expect('RPAREN')
                return ('Call', name, args)
            return ('Var', name)

        if k == 'LPAREN':
            self.consume()
            node = self.expr()
            self.expect('RPAREN')
            return node

        raise SyntaxError(f"Line {self.line}: unexpected token: {k!r} ({v!r})")


# ── Pretty print ──────────────────────────────────────────────────────────────

def print_ast(node, indent=0):
    space = "  " * indent
    if isinstance(node, tuple):
        print(f"{space}{node[0]}")
        for child in node[1:]:
            print_ast(child, indent + 1)
    elif isinstance(node, list):
        for item in node:
            print_ast(item, indent)
    else:
        print(f"{space}{repr(node)}")


# ── Public entry point ────────────────────────────────────────────────────────

def parse(tokens):
    return Parser(tokens).parse()


# ── Self-tests ────────────────────────────────────────────────────────────────
# FIX 3 — guarded so importing this file never triggers tests.

if __name__ == '__main__':
    from scanner import scan

    def run_test(label, source, expect_pass=True):
        print(f"\n{'='*60}")
        print(f"  {label}")
        print(f"{'='*60}")
        print(source)
        try:
            tokens = scan(source)
            ast    = parse(tokens)
            print_ast(ast)
            print("  → PASS" if expect_pass else "  → UNEXPECTED PASS")
        except Exception as e:
            if not expect_pass:
                print(f"  → PASS (expected error: {e})")
            else:
                print(f"  → FAIL: {type(e).__name__}: {e}")

    # Basic
    run_test("display",           'display("hello")')
    run_test("typed assign",      'hp x = 5')

    # FIX 1 — cast calls in statement position
    run_test("hp() as stmt",      'hp(control())')
    run_test("score() as stmt",   'score(2)')

    # FIX 1 — cast calls in expression position (RHS of assignment)
    run_test("s = score(2)",      's = score(2)')
    run_test("e = hp(control())", 'energy = hp(control())')
    run_test("f = ping(3)",       'f = ping(3)')

    # Augmented assignment
    run_test("a -= 1",            'a = 10\na -= 1')
    run_test("a += 5",            'a = 0\na += 5')

    # FIX 2 — for loop
    run_test("for loop",          'stage i in range(5):\n    display(i)')

    # While loop with augmented assign
    run_test("while + -=", '''\
play health(a):
    survive a > 0:
        display("Fighting")
        a -= 1
    display("Game over")
health(10)
''')

    # If / elif / else
    run_test("if/elif/pivot", '''\
hp x = 3
check x > 5:
    display("big")
recheck x == 3:
    display("three")
pivot:
    display("small")
''')

    # Function returning score cast
    run_test("play score(a)", '''\
play score(a):
    a = a * 100
    gg a
s = score(2)
display(s)
''')