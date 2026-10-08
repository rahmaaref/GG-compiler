# ── GG Language Symbol Table ──────────────────────────────────────────────────
# A stack of scopes. Each scope is a plain dict: { name → symbol_info }
#
# symbol_info fields:
#   kind     : 'var' | 'func' | 'class' | 'param' | 'builtin'
#   type     : GG type keyword (e.g. 'hp', 'agent') or None if unknown
#   declared : True  → type came from an explicit annotation  (hp x = 5)
#              False → type was inferred from first assignment (x = 5)
#   arity    : int | None  — only set for 'func' entries; holds the number
#              of formal parameters so call sites can check argument count.
# ─────────────────────────────────────────────────────────────────────────────

class SymbolTable:
    def __init__(self):
        self.scopes = [{}]          # stack; index 0 = global scope

    # ── Scope management ──────────────────────────────────────────────────────

    def enter_scope(self):
        """Push a new (inner) scope."""
        self.scopes.append({})

    def exit_scope(self):
        """Pop the current (inner) scope."""
        if len(self.scopes) > 1:           # never pop the global scope
            self.scopes.pop()

    # ── Define / look up ──────────────────────────────────────────────────────

    def define(self, name, kind='var', typ=None, declared=False, arity=None):
        """Add (or overwrite) a name in the current (innermost) scope."""
        self.scopes[-1][name] = {
            'kind':     kind,
            'type':     typ,
            'declared': declared,
            'arity':    arity,      # None for non-functions
        }

    def update_type(self, name, typ):
        """Update the inferred type of an already-defined name (innermost match)."""
        for scope in reversed(self.scopes):
            if name in scope:
                scope[name]['type'] = typ
                return

    def lookup(self, name):
        """
        Search from innermost scope outward.
        Returns the symbol_info dict, or None if not found.
        """
        for scope in reversed(self.scopes):
            if name in scope:
                return scope[name]
        return None

    def is_defined_locally(self, name):
        """True if name exists in the *current* scope (ignores outer scopes)."""
        return name in self.scopes[-1]

    # ── Debug helper ──────────────────────────────────────────────────────────

    def dump(self):
        for i, scope in enumerate(self.scopes):
            label = 'global' if i == 0 else f'scope-{i}'
            print(f"  [{label}]")
            for name, info in scope.items():
                declared = '(declared)' if info['declared'] else '(inferred)'
                arity    = f" arity={info['arity']}" if info['arity'] is not None else ''
                print(f"    {name}: {info['type']} {declared} [{info['kind']}]{arity}")