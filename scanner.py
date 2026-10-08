import re

# ---------------------------------------------------------------------------
# Token patterns
# ---------------------------------------------------------------------------

TOKEN_PATTERNS = [
    # --- Keywords -----------------------------------------------------------
    ('PRINT',     r'\bdisplay\b'),
    ('INPUT',     r'\bcontrol\b'),
    ('IF',        r'\bcheck\b'),
    ('ELIF',      r'\brecheck\b'),
    ('ELSE',      r'\bpivot\b'),
    ('WHILE',     r'\bsurvive\b'),
    ('FOR',       r'\bstage\b'),
    ('DEF',       r'\bplay\b'),
    ('RETURN',    r'\bgg\b'),
    ('BREAK',     r'\bquit\b'),
    ('CONTINUE',  r'\bretry\b'),
    ('IMPORT',    r'\bload\b'),
    ('CLASS',     r'\bteam\b'),

    ('TRUE',      r'\bAlive\b'),
    ('FALSE',     r'\bDefeated\b'),

    # --- Data-type keywords -------------------------------------------------
    ('INT_T',     r'\bhp\b'),
    ('FLOAT_T',   r'\bping\b'),
    ('STR_T',     r'\bagent\b'),
    ('NONE_T',    r'\bVoid\b'),
    ('BOOL_T',    r'\bresult\b'),
    ('SCORE_T',   r'\bscore\b'),

    # --- Literals -----------------------------------------------------------
    ('FLOAT',     r'\d+\.\d+'),
    ('INT',       r'\d+'),
    ('STRING',    r'\'[^\']*\'|"[^"]*"'),

    # --- Operators & assignment ---------------------------------------------
    # ASSIGN  = augmented operators (two-char) — MUST come before OP
    #           so '-=' is not split into OP('-') + ASSIGN_EQ('=')
    # OP      = comparisons and arithmetic (includes single-char + - * / %)
    # ASSIGN_EQ = bare '=' — MUST come after OP so '==' is already consumed
    ('ASSIGN',    r'\+=|-=|\*=|/=|%='),
    ('OP',        r'==|!=|<=|>=|<|>|[+\-*/%]|\band\b|\bor\b|\bnot\b'),
    ('ASSIGN_EQ', r'='),

    # --- Punctuation --------------------------------------------------------
    ('LPAREN',    r'\('),
    ('RPAREN',    r'\)'),
    ('LBRACKET',  r'\['),
    ('RBRACKET',  r'\]'),
    ('COLON',     r':'),
    ('COMMA',     r','),
    ('DOT',       r'\.'),

    # --- Identifiers --------------------------------------------------------
    ('ID',        r'[a-zA-Z_]\w*'),

    # --- Whitespace / structural --------------------------------------------
    ('NEWLINE',   r'\n[ \t]*'),
    ('SKIP',      r'[ \t]+'),
    ('COMMENT',   r'#.*'),

    # --- Catch-all ----------------------------------------------------------
    ('UNKNOWN',   r'.'),
]

MASTER_RE = re.compile(
    '|'.join(f'(?P<{name}>{pattern})' for name, pattern in TOKEN_PATTERNS)
)


# ---------------------------------------------------------------------------
# Scanner
# ---------------------------------------------------------------------------

def scan(source: str) -> list[tuple[str, str, int]]:

    tokens: list[tuple[str, str, int]] = []  # kind, value, line_num
    indent_stack: list[int] = [0]
    line_num: int = 1

    matches = list(MASTER_RE.finditer(source))
    total   = len(matches)
    i       = 0

    while i < total:
        match = matches[i]
        kind  = match.lastgroup
        value = match.group()

        # Normalise ASSIGN_EQ → ASSIGN so the rest of the pipeline
        # only ever sees the single token kind 'ASSIGN'.
        if kind == 'ASSIGN_EQ':
            kind = 'ASSIGN'

        # ── discard comments ──────────────────────
        if kind in ('SKIP', 'COMMENT'):
            i += 1
            continue

        # ── Newline + indentation handling ────────────────────────────────
        if kind == 'NEWLINE': # '\n    '
            line_num += 1

            # Look ahead past blanks/comments to the next real token.
            j = i + 1
            while j < total and matches[j].lastgroup in ('SKIP', 'COMMENT'):
                j += 1

            # Blank line or end-of-file — skip indentation logic.
            if j >= total or matches[j].lastgroup == 'NEWLINE':
                i += 1
                continue

            tokens.append(('NEWLINE', '\n', line_num))

            new_indent = len(value) - 1   # strip the leading '\n'

            if new_indent > indent_stack[-1]:
                indent_stack.append(new_indent)
                tokens.append(('INDENT', '>>', line_num))

            elif new_indent < indent_stack[-1]:
                while new_indent < indent_stack[-1]:
                    indent_stack.pop()
                    tokens.append(('DEDENT', '<<', line_num))

                if new_indent != indent_stack[-1]:
                    raise IndentationError(
                        f"Line {line_num}: unmatched dedent "
                        f"(expected {indent_stack[-1]}, got {new_indent})"
                    )

            i += 1
            continue

        # ── Unknown character — warn and skip ─────────────────────────────
        if kind == 'UNKNOWN':
            print(f"[Warning] Line {line_num}: unknown character {value!r}")
            i += 1
            continue

        # ── Normal token ──────────────────────────────────────────────────
        tokens.append((kind, value, line_num))
        i += 1

    # Flush any open indentation blocks at end-of-file
    while len(indent_stack) > 1:
        indent_stack.pop()
        tokens.append(('DEDENT', '<<', line_num))

    tokens.append(('EOF', '', line_num))
    return tokens


# ---------------------------------------------------------------------------
# Quick self-test  (python scanner.py)
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    tests = [
        ('x -= 2',  [('ID','x',1), ('ASSIGN','-=',1), ('INT','2',1), ('EOF','',1)]),
        ('x += 1',  [('ID','x',1), ('ASSIGN','+=',1), ('INT','1',1), ('EOF','',1)]),
        ('x *= 3',  [('ID','x',1), ('ASSIGN','*=',1), ('INT','3',1), ('EOF','',1)]),
        ('x /= 4',  [('ID','x',1), ('ASSIGN','/=',1), ('INT','4',1), ('EOF','',1)]),
        ('x %= 5',  [('ID','x',1), ('ASSIGN','%=',1), ('INT','5',1), ('EOF','',1)]),
        ('x = 10',  [('ID','x',1), ('ASSIGN','=',1),  ('INT','10',1), ('EOF','',1)]),
        ('x == 10', [('ID','x',1), ('OP','==',1),      ('INT','10',1), ('EOF','',1)]),
        ('x-=2',    [('ID','x',1), ('ASSIGN','-=',1), ('INT','2',1), ('EOF','',1)]),
        ('x+=1',    [('ID','x',1), ('ASSIGN','+=',1), ('INT','1',1), ('EOF','',1)]),
    ]

    all_pass = True
    for src, expected in tests:
        result = scan(src)
        ok     = result == expected
        print(f"  {'PASS' if ok else 'FAIL'}  {src!r}")
        if not ok:
            print(f"         expected: {expected}")
            print(f"         got:      {result}")
            all_pass = False

    print()
    print('All tests passed.' if all_pass else 'Some tests FAILED.')