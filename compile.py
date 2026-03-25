# interprets directly
# python idot.py run myscript.idot --mode dev
# compiles to python
# python idot.py run myscript.idot --mode prod

import sys
import re
import os
import argparse
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Any, List, Optional

# ─────────────────────────────────────────────
#  TOKEN TYPES
# ─────────────────────────────────────────────

class TT(Enum):
    # Literals
    NUMBER   = auto()
    STRING   = auto()
    IDENT    = auto()

    # Keywords
    LET      = auto()
    CONST    = auto()
    PRINT    = auto()
    REPEAT   = auto()
    FN       = auto()
    BRING    = auto()
    FROM     = auto()
    AS       = auto()
    INPUT_GET= auto()

    # Symbols
    LPAREN   = auto()
    RPAREN   = auto()
    LBRACE   = auto()
    RBRACE   = auto()
    EQ       = auto()
    COMMA    = auto()
    PLUS     = auto()
    MINUS    = auto()
    STAR     = auto()
    SLASH    = auto()
    INTERP   = auto()   # {varname}

    # Comments (consumed silently)
    COMMENT  = auto()

    EOF      = auto()


KEYWORDS = {
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


@dataclass
class Token:
    type: TT
    value: Any
    line: int

    def __repr__(self):
        return f"Token({self.type.name}, {self.value!r}, ln{self.line})"


# ─────────────────────────────────────────────
#  LEXER
# ─────────────────────────────────────────────

class LexError(Exception):
    pass


class Lexer:
    def __init__(self, source: str):
        self.src   = source
        self.pos   = 0
        self.line  = 1
        self.tokens: List[Token] = []

    def peek(self, offset=0) -> str:
        p = self.pos + offset
        return self.src[p] if p < len(self.src) else "\0"

    def advance(self) -> str:
        ch = self.src[self.pos]
        self.pos += 1
        if ch == "\n":
            self.line += 1
        return ch

    def match(self, expected: str) -> bool:
        if self.pos < len(self.src) and self.src[self.pos] == expected:
            self.pos += 1
            return True
        return False

    def skip_whitespace(self):
        while self.pos < len(self.src) and self.src[self.pos] in " \t\r\n":
            self.advance()

    # ── comment handlers ──────────────────────

    def read_header_comment(self):
        """/// ... ///"""
        self.pos += 3  # skip ///
        start = self.pos
        while self.pos < len(self.src):
            if self.src[self.pos:self.pos+3] == "///":
                text = self.src[start:self.pos].strip()
                self.pos += 3
                return Token(TT.COMMENT, ("header", text), self.line)
            self.advance()
        raise LexError(f"Unterminated header comment at line {self.line}")

    def read_line_comment(self):
        """// ..."""
        self.pos += 2
        start = self.pos
        while self.pos < len(self.src) and self.src[self.pos] != "\n":
            self.pos += 1
        return Token(TT.COMMENT, ("line", self.src[start:self.pos].strip()), self.line)

    def read_block_comment(self):
        """/* ... */"""
        self.pos += 2
        start = self.pos
        while self.pos < len(self.src):
            if self.src[self.pos:self.pos+2] == "*/":
                text = self.src[start:self.pos].strip()
                self.pos += 2
                return Token(TT.COMMENT, ("block", text), self.line)
            self.advance()
        raise LexError(f"Unterminated block comment at line {self.line}")

    def read_doc_comment(self):
        """~ ... ~"""
        self.pos += 1  # skip first ~
        start = self.pos
        while self.pos < len(self.src):
            if self.src[self.pos] == "~":
                text = self.src[start:self.pos].strip()
                self.pos += 1
                return Token(TT.COMMENT, ("doc", text), self.line)
            self.advance()
        raise LexError(f"Unterminated doc comment at line {self.line}")

    # ── value readers ─────────────────────────

    def read_string(self):
        line = self.line
        self.pos += 1  # skip opening "
        buf = []
        while self.pos < len(self.src):
            ch = self.src[self.pos]
            if ch == '"':
                self.pos += 1
                return Token(TT.STRING, "".join(buf), line)
            if ch == "\\":
                self.pos += 1
                esc = self.src[self.pos]
                buf.append({"n": "\n", "t": "\t", '"': '"', "\\": "\\"}.get(esc, esc))
                self.pos += 1
            else:
                buf.append(ch)
                self.advance()
        raise LexError(f"Unterminated string at line {line}")

    def read_number(self):
        start = self.pos
        while self.pos < len(self.src) and self.src[self.pos] in "0123456789.":
            self.pos += 1
        raw = self.src[start:self.pos]
        val = float(raw) if "." in raw else int(raw)
        return Token(TT.NUMBER, val, self.line)

    def read_ident_or_kw(self):
        start = self.pos
        while self.pos < len(self.src) and (self.src[self.pos].isalnum() or self.src[self.pos] == "_"):
            self.pos += 1
        word = self.src[start:self.pos]
        tt   = KEYWORDS.get(word, TT.IDENT)
        return Token(tt, word, self.line)

    def read_interp(self):
        """{ ident } used inside print args — only called when we know we're in that context"""
        line = self.line
        self.pos += 1  # skip {
        start = self.pos
        while self.pos < len(self.src) and self.src[self.pos] != "}":
            self.pos += 1
        name = self.src[start:self.pos].strip()
        self.pos += 1  # skip }
        return Token(TT.INTERP, name, line)

    def _last_meaningful(self) -> Optional[Token]:
        """Return the most recently appended non-comment token."""
        for tok in reversed(self.tokens):
            if tok.type != TT.COMMENT:
                return tok
        return None

    def read_bring_lang(self):
        """bring(py) or bring(js) — returns the lang tag"""
        self.pos += 1  # skip (
        start = self.pos
        while self.pos < len(self.src) and self.src[self.pos] != ")":
            self.pos += 1
        lang = self.src[start:self.pos]
        self.pos += 1  # skip )
        return lang

    # ── main tokenise ─────────────────────────

    def tokenise(self) -> List[Token]:
        while self.pos < len(self.src):
            self.skip_whitespace()
            if self.pos >= len(self.src):
                break

            ch = self.src[self.pos]

            # comments
            if ch == "/" and self.peek(1) == "/" and self.peek(2) == "/":
                tok = self.read_header_comment()
            elif ch == "/" and self.peek(1) == "/":
                tok = self.read_line_comment()
            elif ch == "/" and self.peek(1) == "*":
                tok = self.read_block_comment()
            elif ch == "~":
                tok = self.read_doc_comment()

            # bring with lang tag
            elif self.src[self.pos:self.pos+5] == "bring" and self.peek(5) == "(":
                self.pos += 5  # skip "bring"
                lang = self.read_bring_lang()
                tok  = Token(TT.BRING, ("external", lang), self.line)

            # strings
            elif ch == '"':
                tok = self.read_string()

            # numbers
            elif ch.isdigit():
                tok = self.read_number()

            # identifiers / keywords
            elif ch.isalpha() or ch == "_":
                tok = self.read_ident_or_kw()

            # { is INTERP only when last token was COMMA or LPAREN (inside a print/call arg)
            elif ch == "{":
                last = self._last_meaningful()
                if last and last.type in (TT.COMMA, TT.LPAREN):
                    tok = self.read_interp()
                else:
                    self.pos += 1
                    tok = Token(TT.LBRACE, "{", self.line)

            # single-char symbols
            elif ch == "(": self.pos += 1; tok = Token(TT.LPAREN,  "(", self.line)
            elif ch == ")": self.pos += 1; tok = Token(TT.RPAREN,  ")", self.line)
            elif ch == "}": self.pos += 1; tok = Token(TT.RBRACE,  "}", self.line)
            elif ch == "=": self.pos += 1; tok = Token(TT.EQ,      "=", self.line)
            elif ch == ",": self.pos += 1; tok = Token(TT.COMMA,   ",", self.line)
            elif ch == "+": self.pos += 1; tok = Token(TT.PLUS,    "+", self.line)
            elif ch == "-": self.pos += 1; tok = Token(TT.MINUS,   "-", self.line)
            elif ch == "*": self.pos += 1; tok = Token(TT.STAR,    "*", self.line)
            elif ch == "/": self.pos += 1; tok = Token(TT.SLASH,   "/", self.line)
            else:
                raise LexError(f"Unexpected character {ch!r} at line {self.line}")

            # silently discard comments
            if tok.type != TT.COMMENT:
                self.tokens.append(tok)

        self.tokens.append(Token(TT.EOF, None, self.line))
        return self.tokens


# ─────────────────────────────────────────────
#  AST NODES
# ─────────────────────────────────────────────

@dataclass
class NumberLit:   value: float | int
@dataclass
class StringLit:   value: str
@dataclass
class VarRef:      name: str
@dataclass
class Interp:      name: str               # {varname} inside print
@dataclass
class BinOp:
    op:    str
    left:  Any
    right: Any

@dataclass
class PrintStmt:   args: List[Any]
@dataclass
class LetStmt:
    name:    str
    const:   bool
    value:   Any

@dataclass
class AssignStmt:
    name:  str
    value: Any

@dataclass
class RepeatStmt:
    count: Any
    body:  List[Any]

@dataclass
class FnDef:
    name:   str
    params: List[str]
    body:   List[Any]

@dataclass
class BringStmt:
    kind:    str           # "builtin" | "idot" | "external"
    lang:    Optional[str] # py / js
    path:    Optional[str]
    symbol:  Optional[str]
    alias:   str

@dataclass
class InputGet: pass
@dataclass
class FnCall:
    name: str
    args: List[Any]

@dataclass
class ReturnExpr:  expr: Any   # implicit return (last expr in fn body)


# ─────────────────────────────────────────────
#  PARSER
# ─────────────────────────────────────────────

class ParseError(Exception):
    pass


class Parser:
    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.pos    = 0

    def peek(self) -> Token:
        return self.tokens[self.pos]

    def advance(self) -> Token:
        tok = self.tokens[self.pos]
        if tok.type != TT.EOF:
            self.pos += 1
        return tok

    def expect(self, tt: TT) -> Token:
        tok = self.advance()
        if tok.type != tt:
            raise ParseError(
                f"Line {tok.line}: expected {tt.name}, got {tok.type.name} ({tok.value!r})"
            )
        return tok

    def check(self, *types) -> bool:
        return self.peek().type in types

    # ── entry ─────────────────────────────────

    def parse(self) -> List[Any]:
        stmts = []
        while not self.check(TT.EOF):
            stmts.append(self.parse_stmt())
        return stmts

    # ── statements ────────────────────────────

    def parse_stmt(self) -> Any:
        t = self.peek()

        if t.type == TT.LET:
            return self.parse_let(const=False)
        if t.type == TT.CONST:
            return self.parse_let(const=True)
        if t.type == TT.PRINT:
            return self.parse_print()
        if t.type == TT.REPEAT:
            return self.parse_repeat()
        if t.type == TT.FN:
            return self.parse_fn()
        if t.type == TT.BRING:
            return self.parse_bring()

        # ident = expr  (reassignment)  or  fn call
        if t.type == TT.IDENT:
            return self.parse_ident_stmt()

        raise ParseError(f"Line {t.line}: unexpected token {t.type.name} ({t.value!r})")

    def parse_let(self, const: bool) -> LetStmt:
        self.advance()                      # consume let/const
        name = self.expect(TT.IDENT).value
        self.expect(TT.EQ)
        value = self.parse_expr()
        return LetStmt(name=name, const=const, value=value)

    def parse_print(self) -> PrintStmt:
        self.advance()                      # consume print
        self.expect(TT.LPAREN)
        args = []
        while not self.check(TT.RPAREN, TT.EOF):
            if self.check(TT.INTERP):
                tok = self.advance()
                args.append(Interp(tok.value))
            elif self.check(TT.COMMA):
                self.advance()
            else:
                args.append(self.parse_expr())
        self.expect(TT.RPAREN)
        return PrintStmt(args=args)

    def parse_repeat(self) -> RepeatStmt:
        self.advance()                      # consume repeat
        count = self.parse_expr()
        self.expect(TT.LBRACE) if not self.check(TT.LBRACE) else self.advance()
        body  = []
        while not self.check(TT.RBRACE, TT.EOF):
            body.append(self.parse_stmt())
        self.expect(TT.RBRACE)
        return RepeatStmt(count=count, body=body)

    def parse_fn(self) -> FnDef:
        self.advance()                      # consume fn
        name = self.expect(TT.IDENT).value
        self.expect(TT.LPAREN)
        params = []
        while not self.check(TT.RPAREN, TT.EOF):
            if self.check(TT.COMMA):
                self.advance()
            else:
                params.append(self.expect(TT.IDENT).value)
        self.expect(TT.RPAREN)
        self.expect(TT.LBRACE)
        body = []
        while not self.check(TT.RBRACE, TT.EOF):
            body.append(self.parse_stmt())
        self.expect(TT.RBRACE)
        return FnDef(name=name, params=params, body=body)

    def parse_bring(self) -> BringStmt:
        tok = self.advance()                # consume bring (may carry lang info)

        # bring(py) / bring(js)
        if isinstance(tok.value, tuple) and tok.value[0] == "external":
            lang = tok.value[1]
            path = self.expect(TT.STRING).value
            self.expect(TT.AS)
            alias = self.expect(TT.IDENT).value
            return BringStmt(kind="external", lang=lang, path=path, symbol=None, alias=alias)

        # bring {symbol} from "file.idot" as alias
        # symbol may arrive as INTERP or as LBRACE IDENT RBRACE
        if self.check(TT.INTERP):
            symbol = self.advance().value
        elif self.check(TT.LBRACE):
            self.advance()  # {
            symbol = self.expect(TT.IDENT).value
            self.expect(TT.RBRACE)
        else:
            symbol = None  # fall through to other cases

        if symbol is not None:
            self.expect(TT.FROM)
            path = self.expect(TT.STRING).value
            self.expect(TT.AS)
            alias = self.expect(TT.IDENT).value
            return BringStmt(kind="idot", lang=None, path=path, symbol=symbol, alias=alias)

        # bring "file.idot" as alias
        if self.check(TT.STRING):
            path = self.advance().value
            self.expect(TT.AS)
            alias = self.expect(TT.IDENT).value
            return BringStmt(kind="idot", lang=None, path=path, symbol=None, alias=alias)

        # bring math  (builtin)
        if self.check(TT.IDENT):
            name = self.advance().value
            return BringStmt(kind="builtin", lang=None, path=None, symbol=None, alias=name)

        raise ParseError(f"Line {self.peek().line}: malformed bring statement")

    def parse_ident_stmt(self) -> Any:
        name = self.advance().value         # consume ident

        # fn call
        if self.check(TT.LPAREN):
            return self.parse_call(name)

        # reassignment
        if self.check(TT.EQ):
            self.advance()
            return AssignStmt(name=name, value=self.parse_expr())

        # bare expression (e.g. implicit return in fn body)
        return self.parse_binop_rhs(VarRef(name))

    def parse_call(self, name: str) -> FnCall:
        self.expect(TT.LPAREN)
        args = []
        while not self.check(TT.RPAREN, TT.EOF):
            if self.check(TT.COMMA):
                self.advance()
            else:
                args.append(self.parse_expr())
        self.expect(TT.RPAREN)
        return FnCall(name=name, args=args)

    # ── expressions ───────────────────────────

    def parse_expr(self) -> Any:
        left = self.parse_primary()
        return self.parse_binop_rhs(left)

    def parse_binop_rhs(self, left: Any) -> Any:
        OPS = {TT.PLUS: "+", TT.MINUS: "-", TT.STAR: "*", TT.SLASH: "/"}
        while self.peek().type in OPS:
            op  = OPS[self.advance().type]
            rhs = self.parse_primary()
            left = BinOp(op=op, left=left, right=rhs)
        return left

    def parse_primary(self) -> Any:
        t = self.peek()

        if t.type == TT.NUMBER:
            self.advance(); return NumberLit(t.value)

        if t.type == TT.STRING:
            self.advance(); return StringLit(t.value)

        if t.type == TT.INTERP:
            self.advance(); return Interp(t.value)

        if t.type == TT.INPUT_GET:
            self.advance()
            self.expect(TT.LPAREN)
            self.expect(TT.RPAREN)
            return InputGet()

        if t.type == TT.IDENT:
            name = self.advance().value
            if self.check(TT.LPAREN):
                return self.parse_call(name)
            return VarRef(name)

        if t.type == TT.LPAREN:
            self.advance()
            expr = self.parse_expr()
            self.expect(TT.RPAREN)
            return expr

        raise ParseError(f"Line {t.line}: unexpected token in expression: {t.type.name} ({t.value!r})")

    # ── LBRACE helper (repeat uses this) ──────
    # override expect to also handle already-advanced LBRACE
    def _lbrace(self):
        if self.check(TT.LBRACE):
            self.advance()


# ─────────────────────────────────────────────
#  INTERPRETER  (dev mode)
# ─────────────────────────────────────────────

class RuntimeError_(Exception):
    pass

class ReturnSignal(Exception):
    def __init__(self, value): self.value = value

class Env:
    def __init__(self, parent=None):
        self.vars:   dict       = {}
        self.consts: set        = set()
        self.parent: "Env|None" = parent

    def get(self, name: str) -> Any:
        if name in self.vars:
            return self.vars[name]
        if self.parent:
            return self.parent.get(name)
        raise RuntimeError_(f"Undefined variable: {name!r}")

    def set(self, name: str, value: Any, const: bool = False):
        if name in self.consts:
            raise RuntimeError_(f"Cannot reassign const: {name!r}")
        self.vars[name] = value
        if const:
            self.consts.add(name)

    def assign(self, name: str, value: Any):
        if name in self.vars:
            if name in self.consts:
                raise RuntimeError_(f"Cannot reassign const: {name!r}")
            self.vars[name] = value
            return
        if self.parent:
            self.parent.assign(name, value)
            return
        raise RuntimeError_(f"Undefined variable: {name!r}")


class Interpreter:
    def __init__(self):
        self.global_env = Env()
        self.functions: dict = {}

    def run(self, stmts: List[Any]):
        for stmt in stmts:
            self.exec(stmt, self.global_env)

    def exec(self, node: Any, env: Env) -> Any:
        t = type(node)

        if t == LetStmt:
            val = self.eval(node.value, env)
            env.set(node.name, val, node.const)

        elif t == AssignStmt:
            val = self.eval(node.value, env)
            env.assign(node.name, val)

        elif t == PrintStmt:
            parts = []
            for a in node.args:
                if isinstance(a, Interp):
                    parts.append(str(env.get(a.name)))
                else:
                    v = self.eval(a, env)
                    parts.append(str(v) if not isinstance(v, str) else v)
            print(" ".join(parts))

        elif t == RepeatStmt:
            count = int(self.eval(node.count, env))
            for _ in range(count):
                loop_env = Env(parent=env)
                for s in node.body:
                    self.exec(s, loop_env)

        elif t == FnDef:
            self.functions[node.name] = node

        elif t == FnCall:
            return self.call_fn(node, env)

        elif t == BringStmt:
            self.handle_bring(node, env)

        elif t == BinOp:
            return self.eval(node, env)

        else:
            return self.eval(node, env)

    def eval(self, node: Any, env: Env) -> Any:
        t = type(node)

        if t == NumberLit: return node.value
        if t == StringLit: return node.value
        if t == VarRef:    return env.get(node.name)
        if t == Interp:    return env.get(node.name)
        if t == InputGet:  return input()

        if t == BinOp:
            l = self.eval(node.left,  env)
            r = self.eval(node.right, env)
            if node.op == "+": return l + r
            if node.op == "-": return l - r
            if node.op == "*": return l * r
            if node.op == "/": return l / r

        if t == FnCall:
            return self.call_fn(node, env)

        raise RuntimeError_(f"Cannot evaluate node: {node}")

    def call_fn(self, node: FnCall, env: Env) -> Any:
        if node.name not in self.functions:
            raise RuntimeError_(f"Undefined function: {node.name!r}")
        fn  = self.functions[node.name]
        if len(node.args) != len(fn.params):
            raise RuntimeError_(
                f"Function {node.name!r} expects {len(fn.params)} args, got {len(node.args)}"
            )
        fn_env = Env(parent=self.global_env)
        for param, arg in zip(fn.params, node.args):
            fn_env.set(param, self.eval(arg, env))

        result = None
        for stmt in fn.body:
            result = self.exec(stmt, fn_env)
        return result

    def handle_bring(self, node: BringStmt, env: Env):
        if node.kind == "builtin":
            print(f"[bring] builtin module {node.alias!r} loaded (stub)")
        elif node.kind == "idot":
            path = node.path
            if not os.path.exists(path):
                print(f"[bring] WARNING: {path!r} not found — skipping")
                return
            src    = open(path).read()
            tokens = Lexer(src).tokenise()
            ast    = Parser(tokens).parse()
            sub    = Interpreter()
            sub.run(ast)
            if node.symbol:
                if node.symbol in sub.functions:
                    self.functions[node.alias] = sub.functions[node.symbol]
                else:
                    print(f"[bring] WARNING: symbol {node.symbol!r} not found in {path!r}")
            else:
                self.functions.update(sub.functions)
                print(f"[bring] loaded {path!r} as {node.alias!r}")
        elif node.kind == "external":
            print(f"[bring] external {node.lang} file {node.path!r} as {node.alias!r} (stub)")


# ─────────────────────────────────────────────
#  COMPILER  (prod mode → Python source)
# ─────────────────────────────────────────────

class Compiler:
    def __init__(self):
        self.lines:  List[str] = []
        self.indent: int       = 0
        self.consts: set       = set()

    def emit(self, line: str):
        self.lines.append("    " * self.indent + line)

    def emit_blank(self):
        self.lines.append("")

    def compile(self, stmts: List[Any]) -> str:
        self.emit("# Generated by idot compiler (prod mode)")
        self.emit("import sys")
        self.emit_blank()
        for stmt in stmts:
            self.compile_stmt(stmt)
        return "\n".join(self.lines)

    def compile_stmt(self, node: Any):
        t = type(node)

        if t == LetStmt:
            val = self.compile_expr(node.value)
            self.emit(f"{node.name} = {val}")
            if node.const:
                self.consts.add(node.name)

        elif t == AssignStmt:
            if node.name in self.consts:
                raise RuntimeError_(f"Cannot reassign const {node.name!r}")
            self.emit(f"{node.name} = {self.compile_expr(node.value)}")

        elif t == PrintStmt:
            parts = []
            for a in node.args:
                if isinstance(a, Interp):
                    parts.append(f"str({a.name})")
                else:
                    e = self.compile_expr(a)
                    parts.append(f"str({e})")
            self.emit(f"print(' '.join([{', '.join(parts)}]))")

        elif t == RepeatStmt:
            count = self.compile_expr(node.count)
            self.emit(f"for _i in range(int({count})):")
            self.indent += 1
            for s in node.body:
                self.compile_stmt(s)
            self.indent -= 1
            self.emit_blank()

        elif t == FnDef:
            params = ", ".join(node.params)
            self.emit_blank()
            self.emit(f"def {node.name}({params}):")
            self.indent += 1
            body = node.body
            for i, s in enumerate(body):
                if i == len(body) - 1 and not isinstance(s, (LetStmt, AssignStmt, PrintStmt, RepeatStmt, BringStmt)):
                    self.emit(f"return {self.compile_expr(s)}")
                else:
                    self.compile_stmt(s)
            self.indent -= 1
            self.emit_blank()

        elif t == FnCall:
            self.emit(self.compile_expr(node))

        elif t == BringStmt:
            self.compile_bring(node)

        elif isinstance(node, (BinOp, VarRef, NumberLit, StringLit)):
            self.emit(self.compile_expr(node))

    def compile_expr(self, node: Any) -> str:
        t = type(node)
        if t == NumberLit: return repr(node.value)
        if t == StringLit: return repr(node.value)
        if t == VarRef:    return node.name
        if t == Interp:    return node.name
        if t == InputGet:  return "input()"
        if t == BinOp:
            l = self.compile_expr(node.left)
            r = self.compile_expr(node.right)
            return f"({l} {node.op} {r})"
        if t == FnCall:
            args = ", ".join(self.compile_expr(a) for a in node.args)
            return f"{node.name}({args})"
        return repr(node)

    def compile_bring(self, node: BringStmt):
        if node.kind == "builtin":
            self.emit(f"# bring builtin: {node.alias}")
        elif node.kind == "idot":
            if node.symbol:
                self.emit(f"# bring {{{node.symbol}}} from {node.path!r} as {node.alias}")
            else:
                self.emit(f"# bring {node.path!r} as {node.alias}")
        elif node.kind == "external":
            if node.lang == "py":
                self.emit(f"try:")
                self.indent += 1
                self.emit(f"import importlib.util as _ilu")
                self.emit(f"_spec = _ilu.spec_from_file_location(\"{node.alias}\", \"{node.path}\")")
                self.emit(f"{node.alias} = _ilu.module_from_spec(_spec)")
                self.emit(f"_spec.loader.exec_module({node.alias})")
                self.indent -= 1
                self.emit("except Exception as _e:")
                self.indent += 1
                self.emit(f'print(f"[bring] WARNING: could not load {node.path!r}: " + str(_e))')
                self.indent -= 1
            elif node.lang == "js":
                self.emit(f"# bring(js) {node.path!r} as {node.alias} — JS interop not supported in compiled output")


# ─────────────────────────────────────────────
#  CLI
# ─────────────────────────────────────────────

BOLD  = "\033[1m"
CYAN  = "\033[96m"
GREEN = "\033[92m"
RED   = "\033[91m"
DIM   = "\033[2m"
RST   = "\033[0m"

def banner(mode: str):
    colour = GREEN if mode == "dev" else CYAN
    print(f"{BOLD}{colour}{'─'*40}{RST}")
    print(f"{BOLD}{colour}  idot  ·  {mode.upper()} mode{RST}")
    print(f"{BOLD}{colour}{'─'*40}{RST}")

def run_file(path: str, mode: str, dump_ast=False, dump_tokens=False, out_py: str = None):
    if not os.path.exists(path):
        print(f"{RED}Error: file not found: {path!r}{RST}")
        sys.exit(1)

    src = open(path).read()
    banner(mode)

    # ── Lex ──────────────────────────────────
    try:
        tokens = Lexer(src).tokenise()
    except LexError as e:
        print(f"{RED}[Lex Error] {e}{RST}")
        sys.exit(1)

    if dump_tokens:
        print(f"\n{DIM}── TOKENS ────────────────────────{RST}")
        for tok in tokens:
            print(f"  {tok}")

    # ── Parse ─────────────────────────────────
    try:
        ast = Parser(tokens).parse()
    except ParseError as e:
        print(f"{RED}[Parse Error] {e}{RST}")
        sys.exit(1)

    if dump_ast:
        print(f"\n{DIM}── AST ───────────────────────────{RST}")
        for node in ast:
            print(f"  {node}")

    # ── Execute / Compile ─────────────────────
    print()
    if mode == "dev":
        print(f"{DIM}[ interpreting... ]{RST}\n")
        try:
            Interpreter().run(ast)
        except RuntimeError_ as e:
            print(f"\n{RED}[Runtime Error] {e}{RST}")
            sys.exit(1)
    else:
        print(f"{DIM}[ compiling to Python... ]{RST}")
        try:
            py_src = Compiler().compile(ast)
        except Exception as e:
            print(f"{RED}[Compile Error] {e}{RST}")
            sys.exit(1)

        if out_py:
            with open(out_py, "w") as f:
                f.write(py_src)
            print(f"{GREEN}✓ Written to {out_py!r}{RST}\n")
        else:
            print(f"{DIM}[ running compiled output ]{RST}\n")
            exec(compile(py_src, "<idot-compiled>", "exec"), {})

    print(f"\n{DIM}{'─'*40}{RST}")


def main():
    ap = argparse.ArgumentParser(
        description="idot — dual-mode language runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
modes:
  dev   interpret directly (fast, great for development)
  prod  compile to Python then run (or save with --out)

examples:
  idot run showcase.idot --mode dev
  idot run showcase.idot --mode prod
  idot run showcase.idot --mode prod --out build/showcase.py
  idot run showcase.idot --mode dev  --dump-tokens --dump-ast
"""
    )
    sub = ap.add_subparsers(dest="cmd")

    r = sub.add_parser("run", help="run an .idot file")
    r.add_argument("file",          help=".idot source file")
    r.add_argument("--mode",        choices=["dev", "prod"], default="dev",
                   help="dev=interpret  prod=compile (default: dev)")
    r.add_argument("--out",         metavar="FILE",
                   help="(prod only) write generated Python to FILE instead of running it")
    r.add_argument("--dump-tokens", action="store_true", help="print token stream")
    r.add_argument("--dump-ast",    action="store_true", help="print AST")

    args = ap.parse_args()

    if args.cmd == "run":
        run_file(
            path        = args.file,
            mode        = args.mode,
            dump_ast    = args.dump_ast,
            dump_tokens = args.dump_tokens,
            out_py      = args.out,
        )
    else:
        ap.print_help()


if __name__ == "__main__":
    main()