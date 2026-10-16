"""
Mutation runner for the Phase 10 move (FIX-02, research Pitfall 8): break one method at a time, run the tests.

Each listed method of the class keeps its signature and docstring; its body is replaced by a single neutral return
chosen from the return annotation. The method is located with `ast` and only its body lines are spliced, so the
comments and formatting of the rest of the file stay. After each run the original bytes are restored in a `finally`,
and the script exits non-zero when `git diff --quiet -- <file>` reports a change at the end.

Usage (from the repository root, standard library only):

    uv run python mutate.py --file F --class C --methods m1,m2 --out OUT.tsv --tests "<pytest args>"
        [--full-on-survive] [--junit-dir DIR] [--merge] [--note TEXT]

`--full-on-survive` re-runs a survivor of the subset against the full suite (`uv run pytest -x -q`) before it counts
as survived. `--junit-dir` writes `<method>.xml` per run (and `<method>-full.xml` for the full re-run). `--merge`
keeps the rows of OUT.tsv for methods that are not run now and replaces the others in place. `--note` sets the note
column of the rows written now.

The TSV has the columns method, mutant, exit, first_failing, verdict, note. The verdict is `killed` when the test run
fails (exit 1), `survived` when it passes (exit 0) and `error` for any other exit code, which also makes the script
exit non-zero.
"""

from __future__ import annotations

import argparse
import ast
import contextlib
import os
import re
import shlex
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

HEADER = ("method", "mutant", "exit", "first_failing", "verdict", "note")

NEUTRAL_RETURNS: dict[str, str] = {
    "None": "return None",
    "bool": "return False",
    "int": "return 0",
    "takeover.TopicVerdict": "return takeover.TopicVerdict(remove_disabled=False, may_clear=False, rearm=False)",
    "takeover.TakeoverStatus": "return takeover.TakeoverStatus.NOTHING",
}
NEUTRAL_GENERIC_RETURNS: dict[str, str] = {
    "list": "return []",
    "set": "return set()",
    "frozenset": "return frozenset()",
}


class MutationError(Exception):
    """The method cannot be mutated as asked; the script stops."""


def neutral_return(annotation: ast.expr | None, method: str) -> str:
    """Return the neutral return statement for a return annotation, or raise for an annotation without one."""
    text = "None" if annotation is None else ast.unparse(annotation)
    if text in NEUTRAL_RETURNS:
        return NEUTRAL_RETURNS[text]
    base = text.split("[", 1)[0]
    if base in NEUTRAL_GENERIC_RETURNS:
        return NEUTRAL_GENERIC_RETURNS[base]
    msg = f"{method}: no neutral return for the annotation {text!r}"
    raise MutationError(msg)


def find_method(tree: ast.Module, class_name: str, method: str) -> ast.FunctionDef | ast.AsyncFunctionDef:
    """Return the method node of the class; raise when the class or the method is missing."""
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == method:
                    return item
            msg = f"{class_name}.{method} does not exist"
            raise MutationError(msg)
    msg = f"class {class_name} does not exist"
    raise MutationError(msg)


def mutate_source(source: str, class_name: str, method: str) -> tuple[str, str]:
    """Return the mutated source and the mutant statement; the body after the docstring becomes one return."""
    node = find_method(ast.parse(source), class_name, method)
    statement = neutral_return(node.returns, method)
    body = node.body
    if (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
    ):
        body = body[1:]
    if not body:
        msg = f"{class_name}.{method} has no body after its docstring"
        raise MutationError(msg)
    lines = source.splitlines(keepends=True)
    first = body[0]
    start = first.lineno - 1
    # A decorated nested definition starts at its first decorator; comments above the first statement stay
    if isinstance(first, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and first.decorator_list:
        start = first.decorator_list[0].lineno - 1
    end = node.end_lineno
    assert end is not None  # noqa: S101
    indent = " " * first.col_offset
    mutated = "".join([*lines[:start], f"{indent}{statement}\n", *lines[end:]])
    ast.parse(mutated)  # the mutant must still be valid Python
    return mutated, statement


def first_failing(junit: Path | None, output: str) -> str:
    """Return the id of the first failing or erroring test, from the JUnit report or else the pytest summary."""
    if junit is not None and junit.exists():
        with contextlib.suppress(ET.ParseError):
            for case in ET.parse(junit).getroot().iter("testcase"):
                if case.find("failure") is not None or case.find("error") is not None:
                    module = case.get("classname", "").replace(".", "/")
                    return f"{module}.py::{case.get('name', '')}"
    match = re.search(r"^(?:FAILED|ERROR) (\S+)", output, re.MULTILINE)
    return match.group(1) if match else ""


def run_tests(args: list[str], junit: Path | None) -> tuple[int, str]:
    """Run pytest with these arguments under uv; return the exit code and the combined output."""
    command = ["uv", "run", "pytest", *args]
    if junit is not None:
        command.append(f"--junitxml={junit}")
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    result = subprocess.run(command, capture_output=True, text=True, env=env, check=False)  # noqa: S603
    return result.returncode, result.stdout + result.stderr


def read_rows(path: Path) -> dict[str, list[str]]:
    """Return the existing rows of a TSV, keyed by method, without the header."""
    if not path.exists():
        return {}
    rows: dict[str, list[str]] = {}
    for line in path.read_text().splitlines()[1:]:
        if line.strip():
            cells = line.split("\t")
            rows[cells[0]] = cells + [""] * (len(HEADER) - len(cells))
    return rows


def write_rows(path: Path, rows: dict[str, list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "\t".join(HEADER) + "\n" + "".join("\t".join(cells) + "\n" for cells in rows.values())
    path.write_text(text)


def git_clean(file: Path) -> bool:
    return subprocess.run(["git", "diff", "--quiet", "--", str(file)], check=False).returncode == 0  # noqa: S607


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--file", required=True, type=Path)
    parser.add_argument("--class", dest="class_name", required=True)
    parser.add_argument("--methods", required=True, help="comma-separated method names")
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--tests", required=True, help="pytest arguments of the subset, as one string")
    parser.add_argument("--full-on-survive", action="store_true")
    parser.add_argument("--junit-dir", type=Path)
    parser.add_argument("--merge", action="store_true")
    parser.add_argument("--note", default="")
    args = parser.parse_args()

    methods = [name.strip() for name in args.methods.split(",") if name.strip()]
    if not git_clean(args.file):
        print(f"{args.file} differs from git before the first mutant; refusing to run", file=sys.stderr)
        return 2
    original = args.file.read_bytes()
    source = original.decode()
    # Fail before any run when a method is missing or has an annotation without a neutral return
    mutants = {method: mutate_source(source, args.class_name, method) for method in methods}
    if args.junit_dir is not None:
        args.junit_dir.mkdir(parents=True, exist_ok=True)

    rows = read_rows(args.out) if args.merge else {}
    errors = 0
    with tempfile.TemporaryDirectory() as scratch:
        for method in methods:
            mutated, statement = mutants[method]
            junit_dir = args.junit_dir if args.junit_dir is not None else Path(scratch)
            junit = junit_dir / f"{method}.xml"
            try:
                args.file.write_text(mutated)
                code, output = run_tests(shlex.split(args.tests), junit)
                failing = first_failing(junit, output) if code else ""
                if code == 0 and args.full_on_survive:
                    full_junit = junit_dir / f"{method}-full.xml"
                    code, output = run_tests(["-x", "-q"], full_junit)
                    failing = f"full: {first_failing(full_junit, output)}" if code else ""
            finally:
                args.file.write_bytes(original)
            verdict = {0: "survived", 1: "killed"}.get(code, "error")
            if verdict == "error":
                errors += 1
                tail = " | ".join(output.strip().splitlines()[-3:])
                failing = failing or tail
            rows[method] = [method, statement, str(code), failing, verdict, args.note]
            print(f"{method}\t{verdict}\t{failing}", flush=True)
            write_rows(args.out, rows)

    if not git_clean(args.file):
        print(f"{args.file} still differs from git after the run", file=sys.stderr)
        return 1
    return 1 if errors else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except MutationError as err:
        print(f"error: {err}", file=sys.stderr)
        sys.exit(2)
