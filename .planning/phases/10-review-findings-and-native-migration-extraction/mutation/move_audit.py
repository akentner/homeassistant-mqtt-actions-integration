"""
AST audit of the Phase 10 move (FIX-02, D-10, research Pitfall 8): every moved method is the method it was.

The base is the parent of the first `refactor(10-04)` commit. `Manager` is read from `manager.py` at the base with
`git show`, `NativeMigration` from `native_migration.py` in the working tree. For each of the 28 moved methods the
script compares:

- the kind (def or async def) and the decorators
- the docstring
- the multiset of string constants outside the docstring and the `ast.dump` of every f-string
- the ordered `takeover.<name>` calls and the ordered `takeover.<name>` references
- the ordered (LOGGER method, first argument) pairs
- the whole method AST, after the old one is rewritten with exactly the access paths of the move (`self._hass` to
  `self._manager.hass`, the Store save to `self._manager.async_save_now()`, `_async_attempt` to `async_attempt`, ...)

It also checks that Manager at HEAD defines none of the 28 names except the delegators `on_roster_changed` and
`on_discovery_emptied`, that every `@callback` method of NativeMigration is a plain def, and that no moved method that
was a def became an async def. It prints `PASS <name>` or `FAIL <name>: <what differs>` per method, `CHECK ok: ...` or
`FAIL <check>: ...` for the global checks, and exits non-zero on any FAIL.

Usage (from the repository root, standard library only):

    uv run python move_audit.py --base <sha>
"""

from __future__ import annotations

import argparse
import ast
import subprocess
import sys
from collections import Counter
from pathlib import Path

MANAGER = "custom_components/mqtt_actions/manager.py"
MIGRATION = "custom_components/mqtt_actions/native_migration.py"

RENAMES = {
    "_async_native_takeover": "async_takeover",
    "_arm_duplicate_guard": "arm_duplicate_guard",
    "_async_retry_unconfirmed_clears": "async_retry_unconfirmed_clears",
}
MOVED = (
    "_arm_cutover",
    "_on_cutover_due",
    "on_roster_changed",
    "_start_cutover_check",
    "_async_cutover_check",
    "_show_cutover_hint",
    "_clear_cutover_hint",
    "_async_native_takeover",
    "_async_take_over_one",
    "_async_finish_takeover",
    "_async_defer_takeover",
    "_async_retry_unconfirmed_clears",
    "_native_device_ids",
    "_topic_verdict",
    "_ids_that_may_empty_the_topic",
    "_remove_replay_twins",
    "_arm_replay_catch",
    "on_discovery_emptied",
    "_on_replay_catch_due",
    "_async_replay_catch",
    "_rearm_or_log_replay_catch",
    "_async_publish_migrates",
    "_may_clear",
    "_duplicate_guard_ids",
    "_disarm_duplicate_guard",
    "_arm_duplicate_guard",
    "_on_duplicate_registry_updated",
    "_disable_duplicates",
)
DELEGATORS = frozenset({"on_roster_changed", "on_discovery_emptied"})
# Manager member -> the public member of the manager the moved code reads instead
DIRECT = {
    "_hass": "hass",
    "_entry": "entry",
    "_running": "running",
    "_lock": "lock",
    "_publisher": "publisher",
    "_base_topic": "base_topic",
    "_native": "native_state",
    "gateway": "gateway",
    "sync": "sync",
    "mirrors": "mirrors",
    "devices": "devices",
    "presence": "presence",
    "subentry_id_of": "subentry_id_of",
    "is_native": "is_native",
}
NATIVE_SETS = {"_native_pending": "pending", "_native_devices": "devices"}

Function = ast.FunctionDef | ast.AsyncFunctionDef


def _is_self_attr(node: ast.expr, name: str) -> bool:
    return (
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "self"
        and node.attr == name
    )


def _manager_attr(name: str, ctx: ast.expr_context | None = None) -> ast.Attribute:
    owner = ast.Attribute(value=ast.Name(id="self", ctx=ast.Load()), attr="_manager", ctx=ast.Load())
    return ast.Attribute(value=owner, attr=name, ctx=ctx or ast.Load())


class AccessPaths(ast.NodeTransformer):
    """Rewrite an old Manager method with exactly the access-path substitutions of the move, nothing else."""

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.FunctionDef:
        node.name = RENAMES.get(node.name, node.name)
        self.generic_visit(node)
        return node

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.AsyncFunctionDef:
        node.name = RENAMES.get(node.name, node.name)
        self.generic_visit(node)
        return node

    def visit_Call(self, node: ast.Call) -> ast.AST:
        func = node.func
        if (
            isinstance(func, ast.Attribute)
            and func.attr == "async_save"
            and _is_self_attr(func.value, "_store")
            and len(node.args) == 1
            and isinstance(node.args[0], ast.Call)
            and _is_self_attr(node.args[0].func, "_data_to_save")
        ):
            return ast.Call(func=_manager_attr("async_save_now"), args=[], keywords=[])
        if isinstance(func, ast.Name) and func.id == "partial" and node.args:
            if _is_self_attr(node.args[0], "_on_test_message"):
                rest = [self.visit(arg) for arg in node.args[1:]]
                return ast.Call(func=_manager_attr("test_message_handler"), args=rest, keywords=[])
        if _is_self_attr(func, "_schedule_save"):
            return ast.Call(func=_manager_attr("schedule_save"), args=[], keywords=[])
        self.generic_visit(node)
        return node

    def visit_Attribute(self, node: ast.Attribute) -> ast.AST:
        if isinstance(node.value, ast.Name) and node.value.id == "self":
            if node.attr in DIRECT:
                return _manager_attr(DIRECT[node.attr], node.ctx)
            if node.attr in NATIVE_SETS:
                return ast.Attribute(value=_manager_attr("native_state"), attr=NATIVE_SETS[node.attr], ctx=node.ctx)
            if node.attr in RENAMES:
                node.attr = RENAMES[node.attr]
            return node
        self.generic_visit(node)
        return node

    def visit_Name(self, node: ast.Name) -> ast.Name:
        if node.id == "_async_attempt":
            return ast.Name(id="async_attempt", ctx=node.ctx)
        return node


def _methods(source: str, class_name: str) -> dict[str, Function]:
    for node in ast.parse(source).body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return {item.name: item for item in node.body if isinstance(item, Function)}
    msg = f"class {class_name} not found"
    raise SystemExit(msg)


def _in_order(nodes: list[ast.AST]) -> list[ast.AST]:
    return sorted(nodes, key=lambda node: (node.lineno, node.col_offset))


def _docstring_node(fn: Function) -> ast.AST | None:
    first = fn.body[0] if fn.body else None
    if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
        return first.value
    return None


def _strings(fn: Function) -> Counter[str]:
    skip = _docstring_node(fn)
    return Counter(
        node.value
        for node in ast.walk(fn)
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and node is not skip
    )


def _fstrings(fn: Function) -> list[str]:
    return [ast.dump(node) for node in _in_order([n for n in ast.walk(fn) if isinstance(n, ast.JoinedStr)])]


def _module_refs(fn: Function, module: str, *, calls_only: bool) -> list[str]:
    if calls_only:
        nodes = [
            node.func
            for node in ast.walk(fn)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == module
        ]
    else:
        nodes = [
            node
            for node in ast.walk(fn)
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == module
        ]
    return [node.attr for node in _in_order(nodes)]


def _log_calls(fn: Function) -> list[tuple[str, str]]:
    calls = [
        node
        for node in ast.walk(fn)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "LOGGER"
    ]
    return [(call.func.attr, ast.unparse(call.args[0]) if call.args else "") for call in _in_order(calls)]


def _decorators(fn: Function) -> list[str]:
    return [ast.unparse(decorator) for decorator in fn.decorator_list]


def _kind(fn: Function) -> str:
    return "async def" if isinstance(fn, ast.AsyncFunctionDef) else "def"


def compare(old: Function, new: Function) -> list[str]:
    """Return what differs between the old Manager method and the moved one; empty when nothing does."""
    differs: list[str] = []
    checks = (
        ("kind", _kind),
        ("decorators", _decorators),
        ("docstring", ast.get_docstring),
        ("strings", _strings),
        ("f-strings", _fstrings),
        ("takeover calls", lambda fn: _module_refs(fn, "takeover", calls_only=True)),
        ("takeover refs", lambda fn: _module_refs(fn, "takeover", calls_only=False)),
        ("LOGGER calls", _log_calls),
    )
    for label, read in checks:
        before, after = read(old), read(new)
        if before != after:
            differs.append(f"{label} {before!r} != {after!r}")
    rewritten = AccessPaths().visit(ast.parse(ast.unparse(old)).body[0])
    if ast.dump(rewritten) != ast.dump(new):
        differs.append("the method AST differs beyond the access paths of the move")
    return differs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base", required=True, help="the parent of the first refactor(10-04) commit")
    args = parser.parse_args()
    base_source = subprocess.run(  # noqa: S603
        ["git", "show", f"{args.base}:{MANAGER}"],  # noqa: S607
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    old = _methods(base_source, "Manager")
    new = _methods(Path(MIGRATION).read_text(), "NativeMigration")
    head = _methods(Path(MANAGER).read_text(), "Manager")
    failed = False
    for name in MOVED:
        target = RENAMES.get(name, name)
        if name not in old:
            print(f"FAIL {name}: not defined in Manager at the base")
            failed = True
            continue
        if target not in new:
            print(f"FAIL {name}: NativeMigration does not define {target}")
            failed = True
            continue
        if differs := compare(old[name], new[target]):
            print(f"FAIL {name}: {'; '.join(differs)}")
            failed = True
        else:
            print(f"PASS {name}" + (f" -> {target}" if target != name else ""))
    left = sorted(name for name in MOVED if name in head and name not in DELEGATORS)
    if left:
        print(f"FAIL manager-left: Manager at HEAD still defines {left}")
        failed = True
    else:
        print("CHECK ok: Manager at HEAD defines none of the moved names except the two delegators")
    async_callbacks = sorted(
        name for name, fn in new.items() if isinstance(fn, ast.AsyncFunctionDef) and "callback" in _decorators(fn)
    )
    if async_callbacks:
        print(f"FAIL callback-kind: @callback methods that are async def: {async_callbacks}")
        failed = True
    else:
        print("CHECK ok: every @callback method of NativeMigration is a plain def")
    became_async = sorted(
        name
        for name in MOVED
        if name in old
        and isinstance(old[name], ast.FunctionDef)
        and isinstance(new.get(RENAMES.get(name, name)), ast.AsyncFunctionDef)
    )
    if became_async:
        print(f"FAIL def-to-async: {became_async}")
        failed = True
    else:
        print("CHECK ok: no moved def became an async def")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
