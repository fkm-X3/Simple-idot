from __future__ import annotations
import os
from typing import Any, List, Optional
from syntax import (
    TT,
    NumberLit, StringLit, VarRef, Interp, BinOp, InputGet, FnCall,
    LetStmt, AssignStmt, PrintStmt, RepeatStmt, FnDef, BringStmt,
)


class IdotRuntimeError(Exception):
    pass


# ─────────────────────────────────────────────────────────────────────────────
#  ENVIRONMENT  (scoped variable store)
# ─────────────────────────────────────────────────────────────────────────────

class Env:
    def __init__(self, parent: Optional["Env"] = None):
        self.vars:   dict = {}
        self.consts: set  = set()
        self.parent       = parent

    def get(self, name: str) -> Any:
        if name in self.vars:
            return self.vars[name]
        if self.parent:
            return self.parent.get(name)
        raise IdotRuntimeError(f"Undefined variable: {name!r}")

    def set(self, name: str, value: Any, const: bool = False):
        if name in self.consts:
            raise IdotRuntimeError(f"Cannot reassign const: {name!r}")
        self.vars[name] = value
        if const:
            self.consts.add(name)

    def assign(self, name: str, value: Any):
        """Reassign an existing variable (walks up scope chain)."""
        if name in self.vars:
            if name in self.consts:
                raise IdotRuntimeError(f"Cannot reassign const: {name!r}")
            self.vars[name] = value
            return
        if self.parent:
            self.parent.assign(name, value)
            return
        raise IdotRuntimeError(f"Undefined variable: {name!r}")


# ─────────────────────────────────────────────────────────────────────────────
#  INTERPRETER
# ─────────────────────────────────────────────────────────────────────────────

class Interpreter:
    def __init__(self):
        self.global_env = Env()
        self.functions: dict = {}   # name → FnDef node

    def run(self, stmts: List[Any]):
        for stmt in stmts:
            self.exec(stmt, self.global_env)

    # ─── statement execution ─────────────────────────────────────────────────

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
                    parts.append(str(v))
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

        else:
            # Bare expression used as a statement (e.g. implicit return in fn body)
            return self.eval(node, env)

    # ─── expression evaluation ───────────────────────────────────────────────

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
            # Add new operators here (and in parser.py OPS + syntax.py TT)
            if node.op == "+": return l + r
            if node.op == "-": return l - r
            if node.op == "*": return l * r
            if node.op == "/": return l / r
            raise IdotRuntimeError(f"Unknown operator: {node.op!r}")

        if t == FnCall:
            return self.call_fn(node, env)

        raise IdotRuntimeError(f"Cannot evaluate node type: {t.__name__}")

    # ─── function calls ──────────────────────────────────────────────────────

    def call_fn(self, node: FnCall, env: Env) -> Any:
        if node.name not in self.functions:
            raise IdotRuntimeError(f"Undefined function: {node.name!r}")
        fn = self.functions[node.name]
        if len(node.args) != len(fn.params):
            raise IdotRuntimeError(
                f"Function {node.name!r} expects {len(fn.params)} args, got {len(node.args)}"
            )
        fn_env = Env(parent=self.global_env)
        for param, arg in zip(fn.params, node.args):
            fn_env.set(param, self.eval(arg, env))

        result = None
        for stmt in fn.body:
            result = self.exec(stmt, fn_env)
        return result

    # ─── bring / module loading ──────────────────────────────────────────────

    def handle_bring(self, node: BringStmt, env: Env):
        if node.kind == "builtin":
            # Stub — extend here to wire up real built-in modules
            print(f"[bring] builtin module {node.alias!r} loaded (stub)")

        elif node.kind == "idot":
            if not os.path.exists(node.path):
                print(f"[bring] WARNING: {node.path!r} not found — skipping")
                return
            # Parse and run the target file in a fresh interpreter
            from lexer  import Lexer
            from parser import Parser
            src    = open(node.path).read()
            tokens = Lexer(src).tokenise()
            ast    = Parser(tokens).parse()
            sub    = Interpreter()
            sub.run(ast)
            if node.symbol:
                if node.symbol in sub.functions:
                    self.functions[node.alias] = sub.functions[node.symbol]
                else:
                    print(f"[bring] WARNING: symbol {node.symbol!r} not found in {node.path!r}")
            else:
                self.functions.update(sub.functions)
                print(f"[bring] loaded {node.path!r} as {node.alias!r}")

        elif node.kind == "external":
            # Stub — full interop would need subprocess / ctypes / etc.
            print(f"[bring] external {node.lang} file {node.path!r} as {node.alias!r} (stub)")
