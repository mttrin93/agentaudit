"""The wall: `backend/mcp/` reaches no bench module.

[ADR-0100](../../docs/adr/0100-the-mcp-server-has-no-privilege-the-console-lacks.md)
states the wall absolutely, and it is held here at import level rather than by
review, on the reasoning `test_throwaway_checkout.py` and `test_proving.py`
already use for `throwaway.py` and `proving.py`: a wall nobody can see from the
file they are editing is a wall somebody widens by accident.

**Relative imports are resolved, not skipped.** `from ..bench.judge import
Finding` inside `backend/mcp/` is the same widening as the dotted form and reads
in a diff like package-local tidiness, so it is the form most likely to slip a
reviewer who was thinking about a tool description. The wall is worth little if
the accidental spelling is the one it cannot see.
"""

from __future__ import annotations

import ast
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "backend" / "mcp"


def _containing_package(source: pathlib.Path) -> tuple[str, ...]:
    """The dotted package a file lives in, as parts — `backend.mcp` for all of these."""
    return source.resolve().relative_to(ROOT).parts[:-1]


def _imported_modules(source: pathlib.Path) -> set[str]:
    """Every module this file imports, as an absolute dotted name.

    Relative forms are resolved against the containing package rather than skipped.
    """
    tree = ast.parse(source.read_text(encoding="utf-8"))
    package = _containing_package(source)
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0:
                if node.module:
                    names.add(node.module)
                continue
            base = package[: len(package) - node.level + 1]
            names.add(".".join((*base, node.module) if node.module else base))
    return names


def test_the_mcp_package_imports_no_bench_module() -> None:
    offenders = {
        source.name: sorted(
            name
            for name in _imported_modules(source)
            if name == "backend.bench" or name.startswith("backend.bench.")
        )
        for source in PACKAGE.rglob("*.py")
    }
    assert {name: found for name, found in offenders.items() if found} == {}
