"""Small pre-commit style check for example scripts.

Checks:
- Each `engine/examples/*.py` file has a non-empty module docstring.
- If `logging.basicConfig` appears in the file, checks that the file
  also contains a guard `if not logging.getLogger().handlers:` nearby.

This script is intended to be invoked from a pre-commit local hook or
from CI to enforce a consistent examples style.
"""
import ast
import sys
from pathlib import Path


def has_module_docstring(tree: ast.Module) -> bool:
    return bool(ast.get_docstring(tree))


def check_logging_guard(source: str) -> bool:
    # Very small heuristic: require the text pattern "if not logging.getLogger().handlers"
    # somewhere in the file if logging.basicConfig is present.
    if "logging.basicConfig" not in source:
        return True
    return "if not logging.getLogger().handlers" in source


def main() -> int:
    root = Path(__file__).resolve().parents[2] / "engine" / "examples"
    failures = 0
    for p in sorted(root.glob("*.py")):
        src = p.read_text(encoding="utf8")
        try:
            tree = ast.parse(src)
        except Exception as e:
            print(f"ERROR parsing {p}: {e}")
            failures += 1
            continue

        if not has_module_docstring(tree):
            print(f"MISSING DOCSTRING: {p}")
            failures += 1

        if not check_logging_guard(src):
            print(f"MISSING LOGGING GUARD: {p} uses logging.basicConfig without a guard")
            failures += 1

    if failures:
        print(f"Found {failures} example style failures")
        return 2
    print("All examples look good")
    return 0


if __name__ == "__main__":
    sys.exit(main())
