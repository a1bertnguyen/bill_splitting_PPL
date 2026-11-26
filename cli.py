"""
Command-Line Interface (REPL & .split Script Runner) for SplitLang.

Usage:
    python cli.py                              # Start interactive REPL
    python cli.py examples/dinner_demo.split   # Execute a .split script file
    python cli.py examples/dinner_demo.split --inspect  # Show Tokens, Parse Tree, AST
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from controller.Response import SplitLangInterpreter


def print_inspection(res: dict) -> None:
    print("\n--- [Stage 2: Lexer Tokens] ---")
    tok_preview = " ".join(f"{t['type']}({t['text']!r})" for t in res["tokens"])
    print(tok_preview)
    print("\n--- [Stage 3: Parse Tree] ---")
    print(res["parse_tree"])
    print("\n--- [Stage 4: Abstract Syntax Tree (AST)] ---")
    print(res["ast_tree"])
    print("---------------------------------------------\n")


def run_file(script_path: Path, inspect: bool, db_path: str | None) -> int:
    if not script_path.is_file():
        print(f"Error: file not found: {script_path}", file=sys.stderr)
        return 1

    source = script_path.read_text(encoding="utf-8")
    interp = SplitLangInterpreter(db_path=db_path or ":memory:")
    try:
        res = interp.execute(source)
        if inspect:
            print_inspection(res)
        for msg in res["messages"]:
            print(msg)
        return 0 if res["ok"] else 1
    finally:
        interp.close()


def run_repl(inspect: bool, db_path: str | None) -> int:
    interp = SplitLangInterpreter(db_path=db_path)
    show_inspect = inspect
    print("SplitLang Interactive REPL (ANTLR 4.9.2)")
    print("Type 'help' for syntax, ':inspect' to toggle PPL Inspector, ':quit' to exit.")
    print("Tip: For multi-line bill { ... } blocks, braces stay open until matching '}'.\n")

    buffer: list[str] = []
    brace_depth = 0

    try:
        while True:
            grp = interp.ctx.group
            prompt = "... " if brace_depth > 0 else f"splitlang[{grp['name']}:{grp['currency']}]> "
            try:
                line = input(prompt)
            except (EOFError, KeyboardInterrupt):
                print("\nGoodbye!")
                break

            stripped = line.strip()
            if brace_depth == 0:
                if stripped in (":quit", ":exit", "quit", "exit"):
                    print("Goodbye!")
                    break
                if stripped == ":inspect":
                    show_inspect = not show_inspect
                    print(f"PPL Inspector is now {'ON' if show_inspect else 'OFF'}.")
                    continue
                if not stripped:
                    continue

            buffer.append(line)
            brace_depth += line.count("{") - line.count("}")
            if brace_depth > 0:
                continue

            brace_depth = 0
            source = "\n".join(buffer)
            buffer.clear()

            res = interp.execute(source)
            if show_inspect:
                print_inspection(res)
            for msg in res["messages"]:
                print(msg)
    finally:
        interp.close()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="SplitLang Bill-Splitting DSL CLI")
    parser.add_argument("script", nargs="?", help="Optional .split script file to execute")
    parser.add_argument(
        "--inspect",
        action="store_true",
        help="Display Lexer Tokens, Parse Tree, and AST for executed commands",
    )
    parser.add_argument(
        "--db",
        default=None,
        help="Path to SQLite database (defaults to data/splitlang.db in REPL, :memory: for scripts)",
    )
    args = parser.parse_args(argv)

    if args.script:
        return run_file(Path(args.script), inspect=args.inspect, db_path=args.db)
    return run_repl(inspect=args.inspect, db_path=args.db)


if __name__ == "__main__":
    sys.exit(main())
