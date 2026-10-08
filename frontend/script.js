// ── Tab switching ─────────────────────────────────────────────────────────────

function switchTab(name, btn) {
    document.querySelectorAll('.out-tab').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.terminal').forEach(t => t.classList.remove('active-terminal'));
    btn.classList.add('active');
    document.getElementById('tab-' + name).classList.add('active-terminal');
}


// ── Helpers ───────────────────────────────────────────────────────────────────

function setTerminal(id, content, isError = false) {
    const el = document.getElementById(id);
    el.innerHTML = '';
    const pre = document.createElement('pre');
    pre.className = isError ? 'term-error' : 'term-ok';
    pre.textContent = content;
    el.appendChild(pre);
}

function setLoading(id) {
    document.getElementById(id).innerHTML =
        '<span class="term-loading">⟳ Running…</span>';
}


// ── Auto-indent ───────────────────────────────────────────────────────────────

// Lines ending with ':' trigger an extra indent level on Enter
const INDENT_TRIGGERS = /:\s*$/;

function setupEditor() {
    const editor = document.getElementById('codeEditor');

    editor.addEventListener('keydown', function (e) {

        const start = this.selectionStart;
        const end   = this.selectionEnd;
        const value = this.value;

        // ── Tab key → insert/remove 4 spaces ─────────────────────────────
        if (e.key === 'Tab') {
            e.preventDefault();

            if (start !== end) {
                // Multi-line selection: indent or unindent each line
                const lineStart = value.lastIndexOf('\n', start - 1) + 1;
                const lineEnd   = value.indexOf('\n', end);
                const blockEnd  = lineEnd === -1 ? value.length : lineEnd;
                const block     = value.substring(lineStart, blockEnd);

                if (e.shiftKey) {
                    // Unindent: strip up to 4 leading spaces per line
                    const unindented = block.replace(/^ {1,4}/gm, '');
                    const removed    = block.length - unindented.length;
                    const cursorAdj  = Math.min(4,
                        (value.substring(lineStart, start).match(/^ */)[0] || '').length);
                    this.value = value.substring(0, lineStart) + unindented + value.substring(blockEnd);
                    this.selectionStart = Math.max(lineStart, start - cursorAdj);
                    this.selectionEnd   = end - removed;
                } else {
                    // Indent: add 4 spaces to each line
                    const indented = block.replace(/^/gm, '    ');
                    const added    = indented.length - block.length;
                    this.value = value.substring(0, lineStart) + indented + value.substring(blockEnd);
                    this.selectionStart = start + 4;
                    this.selectionEnd   = end + added;
                }
            } else {
                // No selection: insert 4 spaces at cursor
                this.value = value.substring(0, start) + '    ' + value.substring(end);
                this.selectionStart = this.selectionEnd = start + 4;
            }
            return;
        }

        // ── Enter key → carry indentation, add level after ':' ───────────
        if (e.key === 'Enter') {
            e.preventDefault();

            const lineStart   = value.lastIndexOf('\n', start - 1) + 1;
            const currentLine = value.substring(lineStart, start);

            // Preserve the leading whitespace of the current line
            const leadingWS  = currentLine.match(/^(\s*)/)[1];

            // Add one extra indent level if the line ends with ':'
            const extraIndent = INDENT_TRIGGERS.test(currentLine) ? '    ' : '';

            const insert = '\n' + leadingWS + extraIndent;
            this.value = value.substring(0, start) + insert + value.substring(end);
            this.selectionStart = this.selectionEnd = start + insert.length;
            return;
        }

        // ── Backspace → delete a whole indent block at once ───────────────
        // Only when the cursor is at a position that is a multiple of 4 spaces
        // from the start of the line and nothing else precedes it.
        if (e.key === 'Backspace' && start === end) {
            const lineStart    = value.lastIndexOf('\n', start - 1) + 1;
            const beforeCursor = value.substring(lineStart, start);

            if (beforeCursor.length >= 4 && /^( {4})+$/.test(beforeCursor)) {
                e.preventDefault();
                this.value = value.substring(0, start - 4) + value.substring(end);
                this.selectionStart = this.selectionEnd = start - 4;
            }
        }
    });
}


// ── Main run function ─────────────────────────────────────────────────────────

async function runCode() {
    const code = document.getElementById('codeEditor').value;

    if (!code.trim()) {
        setTerminal('tab-output', '[Error] No code to run.', true);
        return;
    }

    ['tab-output', 'tab-scanner', 'tab-parser', 'tab-semantic', 'tab-codegen'].forEach(setLoading);

    const BASE = 'http://127.0.0.1:5000';

    const [runRes, scanRes, parseRes, semRes, codegenRes] = await Promise.allSettled([
        fetch(`${BASE}/run`,      { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({code}) }),
        fetch(`${BASE}/scan`,     { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({code}) }),
        fetch(`${BASE}/parse`,    { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({code}) }),
        fetch(`${BASE}/semantic`, { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({code}) }),
        fetch(`${BASE}/codegen`,  { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({code}) }),
    ]);

    // Output
    try {
        if (runRes.status === 'fulfilled') {
            const d = await runRes.value.json();
            setTerminal('tab-output', d.output, d.output.startsWith('['));
        } else throw new Error();
    } catch {
        setTerminal('tab-output', 'Connection Error\n\nMake sure Flask server is running.', true);
    }

    // Scanner
    try {
        if (scanRes.status === 'fulfilled') {
            const d = await scanRes.value.json();
            if (d.error) {
                setTerminal('tab-scanner', d.error, true);
            } else {
                const lines = d.tokens.map(([kind, val, line]) =>
                    `${String(line).padStart(4)}  ${kind.padEnd(14)} │  ${JSON.stringify(val)}`
                );
                setTerminal('tab-scanner',
                    `── ${d.tokens.length} tokens ─────────────────\n\n` +
                    'LINE  TOKEN          │  VALUE\n' +
                    '──────────────────────┼──────────────────────\n' +
                    lines.join('\n')
                );
            }
        }
    } catch {
        setTerminal('tab-scanner', 'Could not reach /scan endpoint.', true);
    }

    // Parser
    try {
        if (parseRes.status === 'fulfilled') {
            const d = await parseRes.value.json();
            if (d.error) setTerminal('tab-parser', d.error, true);
            else         setTerminal('tab-parser', d.ast);
        }
    } catch {
        setTerminal('tab-parser', 'Could not reach /parse endpoint.', true);
    }

    // Semantic
    try {
        if (semRes.status === 'fulfilled') {
            const d = await semRes.value.json();
            if (d.errors && d.errors.length > 0)
                setTerminal('tab-semantic', d.errors.join('\n'), true);
            else
                setTerminal('tab-semantic', d.message || 'No semantic errors found.');
        }
    } catch {
        setTerminal('tab-semantic', 'Could not reach /semantic endpoint.', true);
    }

    // Generated Python
    try {
        if (codegenRes.status === 'fulfilled') {
            const d = await codegenRes.value.json();
            if (d.error) {
                setTerminal('tab-codegen', d.error, true);
            } else {
                const numbered = d.code.split('\n').map((line, i) =>
                    `${String(i + 1).padStart(3)}  ${line}`
                ).join('\n');
                setTerminal('tab-codegen',
                    '── Generated Python ──────────────────\n\n' + numbered
                );
            }
        }
    } catch {
        setTerminal('tab-codegen', 'Could not reach /codegen endpoint.', true);
    }
}


// ── Init ──────────────────────────────────────────────────────────────────────

window.addEventListener('load', () => {
    const loader = document.getElementById('loader');
    setTimeout(() => {
        loader.style.opacity = '0';
        loader.style.pointerEvents = 'none';
    }, 3000);

    setupEditor();
});