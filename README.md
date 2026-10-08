# GG Compiler

A simple compiler project implemented in **Python**.

The project demonstrates the main stages of a compiler pipeline, starting from source-code scanning and parsing and continuing through semantic analysis and code generation.

##  Features

* **Lexical Analysis** — scans source code and produces tokens.
* **Parsing** — analyzes the token stream according to the language grammar.
* **Semantic Analysis** — checks the meaning and validity of the program.
* **Symbol Table** — stores and manages information about identifiers.
* **Code Generation** — generates output from the analyzed program.
* **Frontend** — provides an interface for interacting with the compiler.
* **Server** — handles communication between the compiler and the frontend.


##  Compiler Pipeline

The compiler follows the typical compilation process:

```text
Source Code
    │
    ▼
┌─────────────┐
│   Scanner   │
└──────┬──────┘
       │ Tokens
       ▼
┌─────────────┐
│    Parser   │
└──────┬──────┘
       │ Parse Tree / AST
       ▼
┌─────────────┐
│  Semantic   │
│   Analysis  │
└──────┬──────┘
       │ Validated Program
       ▼
┌─────────────┐
│    Code     │
│ Generation  │
└──────┬──────┘
       │
       ▼
   Generated Code
```

##  Technologies

* **Python**
* **HTML / CSS / JavaScript** for the frontend
* Compiler-design concepts including:

  * Lexical analysis
  * Syntax analysis
  * Semantic analysis
  * Symbol tables
  * Code generation

##  Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/rahmaaref/GG-compiler.git
cd GG-compiler
```

### 2. Run the project

Make sure Python 3 is installed.

```bash
python server.py
```

##  Compiler Components

### Scanner

`scanner.py` is responsible for **lexical analysis**. It reads the source code and breaks it into meaningful tokens such as keywords, identifiers, operators, and literals.

### Parser

`parser.py` performs **syntax analysis** by processing the tokens produced by the scanner and checking whether they follow the language grammar.

### Semantic Analyzer

`semantic.py` checks semantic rules that cannot be determined from syntax alone, such as identifier usage and type-related constraints.

### Symbol Table

`symbol_table.py` manages information about identifiers encountered during compilation.

### Code Generator

`codegen.py` handles the final stage of the compiler pipeline and produces the target representation from the analyzed program.

