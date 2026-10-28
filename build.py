"""Glue the strategy files + trader.py into the ONE file UTEFA accepts, then test it.

Usage:
    python build.py             # writes Team25QuantiFi2026.py and backtests it
    python build.py --no-test   # just writes the file

What it does:
  1. Pastes PARTS together in order (helpers first, Trader last).
  2. Merges everyone's imports into one block at the top and drops the
     `from strategies...` lines (meaningless once everything is in one file).
  3. Stops with an error if two files define the same top-level name, because the
     later one would silently replace the earlier one.
  4. Runs backtest.py on the result so you know it works before uploading.
"""
import argparse
import ast
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
TEAM = "25"
OUT = f"Team{TEAM}QuantiFi2026.py"
PARTS = [
    "strategies/common.py",
    "strategies/core.py",
    "strategies/fruit_lychee.py",
    "strategies/pearls.py",
    "trader.py",
]


def split(path):
    """Read one file and return (imports, body lines, docstring, top-level names)."""
    with open(os.path.join(ROOT, path), encoding="utf-8") as f:
        src = f.read()
    tree = ast.parse(src)
    lines = src.splitlines()
    drop, imports, names, doc = set(), [], [], ""

    for i, node in enumerate(tree.body):
        span = range(node.lineno - 1, node.end_lineno)
        if i == 0 and isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) \
                and isinstance(node.value.value, str):
            doc = node.value.value.strip()
            drop.update(span)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            drop.update(span)
            imports.append(node)
        elif isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            names.append(node.name)
        elif isinstance(node, ast.Assign):
            names += [t.id for t in node.targets if isinstance(t, ast.Name)]
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.append(node.target.id)

    body = [line for n, line in enumerate(lines) if n not in drop]
    return imports, body, doc, names


def merge_imports(nodes):
    """One `import x` / `from m import a, b` line per module, no duplicates."""
    plain, from_ = set(), {}
    for node in nodes:
        if isinstance(node, ast.Import):
            plain.update((a.name, a.asname) for a in node.names)
        elif not (node.module or "").startswith("strategies"):
            from_.setdefault(node.module, set()).update((a.name, a.asname) for a in node.names)

    fmt = lambda name, alias: f"{name} as {alias}" if alias else name
    future = [f"from __future__ import {', '.join(sorted(fmt(*a) for a in from_.pop('__future__')))}"] \
        if "__future__" in from_ else []
    out = future + [f"import {fmt(*a)}" for a in sorted(plain)]
    out += [f"from {m} import {', '.join(sorted(fmt(*a) for a in from_[m]))}" for m in sorted(from_)]
    return out


def build():
    all_imports, sections, defined_in = [], [], {}
    for path in PARTS:
        imports, body, doc, names = split(path)
        all_imports += imports
        for name in names:
            if name in defined_in:
                sys.exit(f"ERROR: `{name}` is defined in both {defined_in[name]} and {path}. "
                         f"Rename one (or move it inside your class).")
            defined_in[name] = path
        header = [f"# {'=' * 76}", f"# {path}"]
        header += [f"# {line}".rstrip() for line in doc.splitlines()]
        header.append(f"# {'=' * 76}")
        sections.append("\n".join(header) + "\n" + "\n".join(body).strip("\n"))

    text = "\n".join(merge_imports(all_imports)) + "\n\n\n" + "\n\n\n".join(sections) + "\n"
    with open(os.path.join(ROOT, OUT), "w", encoding="utf-8") as f:
        f.write(text)
    print(f"Wrote {OUT} ({len(text.splitlines())} lines)", flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--no-test", action="store_true", help="skip the backtest of the built file")
    args = ap.parse_args()
    build()
    if not args.no_test:
        print("Backtesting the built file (this is exactly what UTEFA will run)...\n", flush=True)
        result = subprocess.run([sys.executable, os.path.join(ROOT, "backtest.py"), "--file", OUT], cwd=ROOT)
        if result.returncode != 0:
            sys.exit("ERROR: the built file failed the backtest. Don't upload it.")


if __name__ == "__main__":
    main()
