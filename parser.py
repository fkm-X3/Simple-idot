from __future__ import annotations
from typing import Any, List
from syntax import (
    TT, Token,
    # expression nodes
    NumberLit, StringLit, VarRef, Interp, BinOp, InputGet, FnCall,
    # statement nodes
    LetStmt, AssignStmt, PrintStmt, RepeatStmt, FnDef, BringStmt,
)


class ParseError(Exception):
    pass


class Parser:
    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.pos    = 0

    # ─── token navigation ────────────────────────────────────────────────────

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

    def check(self, *types: TT) -> bool:
        return self.peek().type in types

    # ─── top level ───────────────────────────────────────────────────────────

    def parse(self) -> List[Any]:
        stmts = []
        while not self.check(TT.EOF):
            stmts.append(self.parse_stmt())
        return stmts

    # ─── statements ──────────────────────────────────────────────────────────
    # Add new keyword dispatch here (and implement parse_<keyword> below).

    def parse_stmt(self) -> Any:
        t = self.peek()

        if t.type == TT.LET:        return self.parse_let(const=False)
        if t.type == TT.CONST:      return self.parse_let(const=True)
        if t.type == TT.PRINT:      return self.parse_print()
        if t.type == TT.REPEAT:     return self.parse_repeat()
        if t.type == TT.FN:         return self.parse_fn()
        if t.type == TT.BRING:      return self.parse_bring()
        if t.type == TT.IDENT:      return self.parse_ident_stmt()

        raise ParseError(f"Line {t.line}: unexpected token {t.type.name} ({t.value!r})")

    def parse_let(self, const: bool) -> LetStmt:
        self.advance()                       # consume let / const
        name = self.expect(TT.IDENT).value
        self.expect(TT.EQ)
        value = self.parse_expr()
        return LetStmt(name=name, const=const, value=value)

    def parse_print(self) -> PrintStmt:
        self.advance()                       # consume print
        self.expect(TT.LPAREN)
        args = []
        while not self.check(TT.RPAREN, TT.EOF):
            if self.check(TT.COMMA):
                self.advance()
            elif self.check(TT.INTERP):
                tok = self.advance()
                args.append(Interp(tok.value))
            else:
                args.append(self.parse_expr())
        self.expect(TT.RPAREN)
        return PrintStmt(args=args)

    def parse_repeat(self) -> RepeatStmt:
        self.advance()                       # consume repeat
        count = self.parse_expr()
        self.expect(TT.LBRACE)
        body = []
        while not self.check(TT.RBRACE, TT.EOF):
            body.append(self.parse_stmt())
        self.expect(TT.RBRACE)
        return RepeatStmt(count=count, body=body)

    def parse_fn(self) -> FnDef:
        self.advance()                       # consume fn
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
        tok = self.advance()                 # consume bring (may carry lang tag)

        # bring(py) "file.py" as alias  /  bring(js) "file.js" as alias
        if isinstance(tok.value, tuple) and tok.value[0] == "external":
            lang  = tok.value[1]
            path  = self.expect(TT.STRING).value
            self.expect(TT.AS)
            alias = self.expect(TT.IDENT).value
            return BringStmt(kind="external", lang=lang, path=path, symbol=None, alias=alias)

        # bring {symbol} from "file.idot" as alias
        # {symbol} may arrive as TT.INTERP (from lexer context) or as LBRACE IDENT RBRACE
        symbol = None
        if self.check(TT.INTERP):
            symbol = self.advance().value
        elif self.check(TT.LBRACE):
            self.advance()                   # {
            symbol = self.expect(TT.IDENT).value
            self.expect(TT.RBRACE)           # }

        if symbol is not None:
            self.expect(TT.FROM)
            path  = self.expect(TT.STRING).value
            self.expect(TT.AS)
            alias = self.expect(TT.IDENT).value
            return BringStmt(kind="idot", lang=None, path=path, symbol=symbol, alias=alias)

        # bring "file.idot" as alias
        if self.check(TT.STRING):
            path  = self.advance().value
            self.expect(TT.AS)
            alias = self.expect(TT.IDENT).value
            return BringStmt(kind="idot", lang=None, path=path, symbol=None, alias=alias)

        # bring math  (builtin module)
        if self.check(TT.IDENT):
            name = self.advance().value
            return BringStmt(kind="builtin", lang=None, path=None, symbol=None, alias=name)

        raise ParseError(f"Line {self.peek().line}: malformed bring statement")

    def parse_ident_stmt(self) -> Any:
        name = self.advance().value          # consume identifier

        if self.check(TT.LPAREN):           # function call as statement
            return self.parse_call(name)
        if self.check(TT.EQ):              # reassignment
            self.advance()
            return AssignStmt(name=name, value=self.parse_expr())

        # bare expression (e.g. implicit return value at end of fn body)
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

    # ─── expressions ─────────────────────────────────────────────────────────

    def parse_expr(self) -> Any:
        left = self.parse_primary()
        return self.parse_binop_rhs(left)

    def parse_binop_rhs(self, left: Any) -> Any:
        # Add new infix operators here (and a TT member in syntax.py)
        OPS = {
            TT.PLUS:  "+",
            TT.MINUS: "-",
            TT.STAR:  "*",
            TT.SLASH: "/",
        }
        while self.peek().type in OPS:
            op   = OPS[self.advance().type]
            rhs  = self.parse_primary()
            left = BinOp(op=op, left=left, right=rhs)
        return left

    def parse_primary(self) -> Any:
        t = self.peek()

        if t.type == TT.NUMBER:
            self.advance()
            return NumberLit(t.value)

        if t.type == TT.STRING:
            self.advance()
            return StringLit(t.value)

        if t.type == TT.INTERP:
            self.advance()
            return Interp(t.value)

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

        raise ParseError(
            f"Line {t.line}: unexpected token in expression: {t.type.name} ({t.value!r})"
        )
