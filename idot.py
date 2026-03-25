#Usage:
#  python idot.py run <file.idot> --mode dev
#  python idot.py run <file.idot> --mode prod
#  python idot.py run <file.idot> --mode prod --out build/out.py
#  python idot.py run <file.idot> --mode dev  --dump-tokens --dump-ast

import sys
import os
import argparse

from lexer       import Lexer,       LexError
from parser      import Parser,      ParseError
from interpreter import Interpreter, IdotRuntimeError
from compiler    import Compiler,    CompileError

BOLD  = "\033[1m"
CYAN  = "\033[96m"
GREEN = "\033[92m"
RED   = "\033[91m"
DIM   = "\033[2m"
RST   = "\033[0m"


def banner(mode: str):
    colour = GREEN if mode == "dev" else CYAN
    print(f"{BOLD}{colour}{'─' * 40}{RST}")
    print(f"{BOLD}{colour}  idot  ·  {mode.upper()} mode{RST}")
    print(f"{BOLD}{colour}{'─' * 40}{RST}")


def run_file(path: str, mode: str, dump_ast=False, dump_tokens=False, out_py: str = None):
    if not os.path.exists(path):
        print(f"{RED}Error: file not found: {path!r}{RST}")
        sys.exit(1)

    src = open(path).read()
    banner(mode)

    try:
        tokens = Lexer(src).tokenise()
    except LexError as e:
        print(f"{RED}[Lex Error] {e}{RST}")
        sys.exit(1)

    if dump_tokens:
        print(f"\n{DIM}── TOKENS ──────────────────────────{RST}")
        for tok in tokens:
            print(f"  {tok}")

    try:
        ast = Parser(tokens).parse()
    except ParseError as e:
        print(f"{RED}[Parse Error] {e}{RST}")
        sys.exit(1)

    if dump_ast:
        print(f"\n{DIM}── AST ──────────────────────────────{RST}")
        for node in ast:
            print(f"  {node}")

    print()

    if mode == "dev":
        print(f"{DIM}[ interpreting... ]{RST}\n")
        try:
            Interpreter().run(ast)
        except IdotRuntimeError as e:
            print(f"\n{RED}[Runtime Error] {e}{RST}")
            sys.exit(1)
    else:
        print(f"{DIM}[ compiling to Python... ]{RST}")
        try:
            py_src = Compiler().compile(ast)
        except CompileError as e:
            print(f"{RED}[Compile Error] {e}{RST}")
            sys.exit(1)

        if out_py:
            os.makedirs(os.path.dirname(out_py) or ".", exist_ok=True)
            with open(out_py, "w") as f:
                f.write(py_src)
            print(f"{GREEN}✓ Written to {out_py!r}{RST}\n")
        else:
            print(f"{DIM}[ running compiled output ]{RST}\n")
            exec(compile(py_src, "<idot-compiled>", "exec"), {})

    print(f"\n{DIM}{'─' * 40}{RST}")


def main():
    ap = argparse.ArgumentParser(
        description="idot — dual-mode language runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
modes:
  dev   interpret directly (fast, great for development)
  prod  compile to Python then run (or save with --out)

examples:
  python3 idot.py run showcase.idot --mode dev
  python3 idot.py run showcase.idot --mode prod
  python3 idot.py run showcase.idot --mode prod --out build/showcase.py
  python3 idot.py run showcase.idot --mode dev  --dump-tokens --dump-ast
""",
    )
    sub = ap.add_subparsers(dest="cmd")

    r = sub.add_parser("run", help="run an .idot file")
    r.add_argument("file",          help=".idot source file")
    r.add_argument("--mode",        choices=["dev", "prod"], default="dev",
                   help="dev=interpret  prod=compile  (default: dev)")
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
