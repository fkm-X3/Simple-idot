from __future__ import annotations
from typing import List, Optional
from syntax import TT, KEYWORDS, Token


class LexError(Exception):
    pass


class Lexer:
    def __init__(self, source: str):
        self.src    = source
        self.pos    = 0
        self.line   = 1
        self.tokens: List[Token] = []

    # ─── primitives ──────────────────────────────────────────────────────────

    def peek(self, offset: int = 0) -> str:
        p = self.pos + offset
        return self.src[p] if p < len(self.src) else "\0"

    def advance(self) -> str:
        ch = self.src[self.pos]
        self.pos += 1
        if ch == "\n":
            self.line += 1
        return ch

    def skip_whitespace(self):
        while self.pos < len(self.src) and self.src[self.pos] in " \t\r\n":
            self.advance()

    def _last_meaningful(self) -> Optional[Token]:
        """Most recently appended non-comment token (used for context-aware { dispatch)."""
        for tok in reversed(self.tokens):
            if tok.type != TT.COMMENT:
                return tok
        return None

    # ─── comment readers ─────────────────────────────────────────────────────

    def read_header_comment(self) -> Token:
        """/// text ///"""
        self.pos += 3
        start = self.pos
        while self.pos < len(self.src):
            if self.src[self.pos:self.pos + 3] == "///":
                text = self.src[start:self.pos].strip()
                self.pos += 3
                return Token(TT.COMMENT, ("header", text), self.line)
            self.advance()
        raise LexError(f"Unterminated header comment at line {self.line}")

    def read_line_comment(self) -> Token:
        """// text"""
        self.pos += 2
        start = self.pos
        while self.pos < len(self.src) and self.src[self.pos] != "\n":
            self.pos += 1
        return Token(TT.COMMENT, ("line", self.src[start:self.pos].strip()), self.line)

    def read_block_comment(self) -> Token:
        """/* text */"""
        self.pos += 2
        start = self.pos
        while self.pos < len(self.src):
            if self.src[self.pos:self.pos + 2] == "*/":
                text = self.src[start:self.pos].strip()
                self.pos += 2
                return Token(TT.COMMENT, ("block", text), self.line)
            self.advance()
        raise LexError(f"Unterminated block comment at line {self.line}")

    def read_doc_comment(self) -> Token:
        """~ text ~"""
        self.pos += 1
        start = self.pos
        while self.pos < len(self.src):
            if self.src[self.pos] == "~":
                text = self.src[start:self.pos].strip()
                self.pos += 1
                return Token(TT.COMMENT, ("doc", text), self.line)
            self.advance()
        raise LexError(f"Unterminated doc comment at line {self.line}")

    # ─── value readers ───────────────────────────────────────────────────────

    def read_string(self) -> Token:
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

    def read_number(self) -> Token:
        start = self.pos
        while self.pos < len(self.src) and self.src[self.pos] in "0123456789.":
            self.pos += 1
        raw = self.src[start:self.pos]
        val = float(raw) if "." in raw else int(raw)
        return Token(TT.NUMBER, val, self.line)

    def read_ident_or_kw(self) -> Token:
        start = self.pos
        while self.pos < len(self.src) and (self.src[self.pos].isalnum() or self.src[self.pos] == "_"):
            self.pos += 1
        word = self.src[start:self.pos]
        tt   = KEYWORDS.get(word, TT.IDENT)
        return Token(tt, word, self.line)

    def read_interp(self) -> Token:
        """{varname} — only called when we know we're inside a call arg list."""
        line = self.line
        self.pos += 1  # skip {
        start = self.pos
        while self.pos < len(self.src) and self.src[self.pos] != "}":
            self.pos += 1
        name = self.src[start:self.pos].strip()
        self.pos += 1  # skip }
        return Token(TT.INTERP, name, line)

    def read_bring_lang(self) -> str:
        """bring(py) / bring(js) — returns the language tag string."""
        self.pos += 1  # skip (
        start = self.pos
        while self.pos < len(self.src) and self.src[self.pos] != ")":
            self.pos += 1
        lang = self.src[start:self.pos]
        self.pos += 1  # skip )
        return lang

    # ─── main loop ───────────────────────────────────────────────────────────

    def tokenise(self) -> List[Token]:
        while self.pos < len(self.src):
            self.skip_whitespace()
            if self.pos >= len(self.src):
                break

            ch = self.src[self.pos]

            # ── comments ──────────────────────────────────────────────────
            if   ch == "/" and self.peek(1) == "/" and self.peek(2) == "/":
                tok = self.read_header_comment()
            elif ch == "/" and self.peek(1) == "/":
                tok = self.read_line_comment()
            elif ch == "/" and self.peek(1) == "*":
                tok = self.read_block_comment()
            elif ch == "~":
                tok = self.read_doc_comment()

            # ── bring(lang) ───────────────────────────────────────────────
            elif self.src[self.pos:self.pos + 5] == "bring" and self.peek(5) == "(":
                self.pos += 5
                lang = self.read_bring_lang()
                tok  = Token(TT.BRING, ("external", lang), self.line)

            # ── string ────────────────────────────────────────────────────
            elif ch == '"':
                tok = self.read_string()

            # ── number ────────────────────────────────────────────────────
            elif ch.isdigit():
                tok = self.read_number()

            # ── identifier / keyword ──────────────────────────────────────
            elif ch.isalpha() or ch == "_":
                tok = self.read_ident_or_kw()

            # ── { — INTERP when inside call args, LBRACE otherwise ────────
            elif ch == "{":
                last = self._last_meaningful()
                if last and last.type in (TT.COMMA, TT.LPAREN):
                    tok = self.read_interp()
                else:
                    self.pos += 1
                    tok = Token(TT.LBRACE, "{", self.line)

            # ── single-character symbols ───────────────────────────────────
            # Add new operator symbols here (and a matching TT in syntax.py)
            elif ch == "(": self.pos += 1; tok = Token(TT.LPAREN, "(", self.line)
            elif ch == ")": self.pos += 1; tok = Token(TT.RPAREN, ")", self.line)
            elif ch == "}": self.pos += 1; tok = Token(TT.RBRACE, "}", self.line)
            elif ch == "=": self.pos += 1; tok = Token(TT.EQ,     "=", self.line)
            elif ch == ",": self.pos += 1; tok = Token(TT.COMMA,  ",", self.line)
            elif ch == "+": self.pos += 1; tok = Token(TT.PLUS,   "+", self.line)
            elif ch == "-": self.pos += 1; tok = Token(TT.MINUS,  "-", self.line)
            elif ch == "*": self.pos += 1; tok = Token(TT.STAR,   "*", self.line)
            elif ch == "/": self.pos += 1; tok = Token(TT.SLASH,  "/", self.line)

            else:
                raise LexError(f"Unexpected character {ch!r} at line {self.line}")

            # Comments are silently discarded — they never reach the parser
            if tok.type != TT.COMMENT:
                self.tokens.append(tok)

        self.tokens.append(Token(TT.EOF, None, self.line))
        return self.tokens
