# this file makes it simple to define new syntax for idot.

from __future__ import annotations
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Any, List, Optional


# ─────────────────────────────────────────────────────────────────────────────
#  TOKEN TYPES
#  Add new TT members here when introducing new syntax.
# ─────────────────────────────────────────────────────────────────────────────

class TT(Enum):
    # ── Literals ──────────────────────────────
    NUMBER    = auto()
    STRING    = auto()
    IDENT     = auto()

    # ── Keywords ──────────────────────────────
    # Add new keywords here, then add them to KEYWORDS dict below
    LET       = auto()
    CONST     = auto()
    PRINT     = auto()
    REPEAT    = auto()
    FN        = auto()
    BRING     = auto()
    FROM      = auto()
    AS        = auto()
    INPUT_GET = auto()

    # ── Symbols ───────────────────────────────
    LPAREN    = auto()
    RPAREN    = auto()
    LBRACE    = auto()
    RBRACE    = auto()
    EQ        = auto()
    COMMA     = auto()
    PLUS      = auto()
    MINUS     = auto()
    STAR      = auto()
    SLASH     = auto()
    INTERP    = auto()   # {varname} inside print args

    # ── Internal ──────────────────────────────
    COMMENT   = auto()   # consumed silently; never reaches the parser
    EOF       = auto()


# ─────────────────────────────────────────────────────────────────────────────
#  KEYWORD MAP
#  Maps source text → TT.  Add new reserved words here.
# ─────────────────────────────────────────────────────────────────────────────

KEYWORDS: dict[str, TT] = {
    "let":       TT.LET,
    "const":     TT.CONST,
    "print":     TT.PRINT,
    "repeat":    TT.REPEAT,
    "fn":        TT.FN,
    "bring":     TT.BRING,
    "from":      TT.FROM,
    "as":        TT.AS,
    "input_get": TT.INPUT_GET,
}


# ─────────────────────────────────────────────────────────────────────────────
#  TOKEN
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Token:
    type:  TT
    value: Any
    line:  int

    def __repr__(self) -> str:
        return f"Token({self.type.name}, {self.value!r}, ln{self.line})"


# ─────────────────────────────────────────────────────────────────────────────
#  AST NODES — EXPRESSIONS
#  Add new expression nodes here.
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class NumberLit:
    """A numeric literal: 42  or  3.14"""
    value: float | int

@dataclass
class StringLit:
    """A string literal: "hello" """
    value: str

@dataclass
class VarRef:
    """A bare variable reference: x"""
    name: str

@dataclass
class Interp:
    """{varname} interpolation inside print args"""
    name: str

@dataclass
class BinOp:
    """Binary operation: left OP right  (e.g. x + 5)"""
    op:    str   # "+", "-", "*", "/"
    left:  Any
    right: Any

@dataclass
class InputGet:
    """input_get() — reads a line from stdin"""
    pass

@dataclass
class FnCall:
    """A function call: name(arg1, arg2, ...)"""
    name: str
    args: List[Any]


# ─────────────────────────────────────────────────────────────────────────────
#  AST NODES — STATEMENTS
#  Add new statement nodes here.
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class LetStmt:
    """let x = expr  /  const x = expr"""
    name:  str
    const: bool   # True when declared with `const`
    value: Any

@dataclass
class AssignStmt:
    """x = expr  (reassignment, no let/const)"""
    name:  str
    value: Any

@dataclass
class PrintStmt:
    """print(arg1, arg2, ...)"""
    args: List[Any]

@dataclass
class RepeatStmt:
    """repeat N { body }"""
    count: Any        # expression evaluating to a number
    body:  List[Any]  # list of statements

@dataclass
class FnDef:
    """fn name(param1, param2) { body }"""
    name:   str
    params: List[str]
    body:   List[Any]

@dataclass
class BringStmt:
    """
    bring math                                  → builtin
    bring "utils.idot" as tools                 → idot file (whole module)
    bring {fn} from "utils.idot" as fn_alias    → idot file (one symbol)
    bring(py) "legacy.py" as pymod              → external Python file
    bring(js) "legacy.js" as jsmod              → external JS file (stub)
    """
    kind:   str            # "builtin" | "idot" | "external"
    lang:   Optional[str]  # "py" or "js" for external brings
    path:   Optional[str]  # file path for idot / external brings
    symbol: Optional[str]  # specific function name for selective idot brings
    alias:  str            # local name to bind the module/function to
