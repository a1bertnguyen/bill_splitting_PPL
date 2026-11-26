"""
ANTLR 4.9.2 code generation helper for SplitLang.

Usage:
    python parserAnalyzer/run.py gen     # Compile SplitLang.g4 -> CompiledFiles/
    python parserAnalyzer/run.py clean   # Remove generated files
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
GRAMMAR_FILE = BASE_DIR / "SplitLang.g4"
OUTPUT_DIR = BASE_DIR / "CompiledFiles"

JAR_CANDIDATES = [
    BASE_DIR / "antlr4-4.9.2-complete.jar",
    Path(os.environ.get("ANTLR_JAR", "")) if os.environ.get("ANTLR_JAR") else None,
    Path(r"C:\antlr\antlr4-4.9.2-complete.jar"),
]


def find_antlr_jar() -> Path:
    for candidate in JAR_CANDIDATES:
        if candidate and candidate.is_file():
            return candidate
    raise FileNotFoundError(
        "Could not locate antlr4-4.9.2-complete.jar. "
        "Place it in parserAnalyzer/ or C:\\antlr\\ or set ANTLR_JAR."
    )


def generate() -> None:
    jar_path = find_antlr_jar()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    cmd = [
        "java",
        "-jar",
        str(jar_path),
        "-Dlanguage=Python3",
        "-visitor",
        "-no-listener",
        "-Xexact-output-dir",
        "-o",
        str(OUTPUT_DIR),
        str(GRAMMAR_FILE),
    ]
    print("Running:", " ".join(cmd))
    subprocess.run(cmd, check=True)
    init_file = OUTPUT_DIR / "__init__.py"
    if not init_file.exists():
        init_file.write_text("# Auto-generated ANTLR4 package for SplitLang\n", encoding="utf-8")
    print(f"Successfully generated SplitLang lexer/parser/visitor into {OUTPUT_DIR}")


def clean() -> None:
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
        print(f"Removed {OUTPUT_DIR}")
    else:
        print("Nothing to clean.")


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[1] == "gen":
        generate()
        return 0
    if argv[1] == "clean":
        clean()
        return 0
    print("Usage: python parserAnalyzer/run.py [gen|clean]")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
