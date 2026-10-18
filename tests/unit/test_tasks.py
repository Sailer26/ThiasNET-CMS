"""scripts/tasks.py: npm trovato anche su Windows (npm.cmd), lint solo Python (D-96)."""

from __future__ import annotations

import importlib.util
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
Ran = list[tuple[list[str], dict[str, Any]]]
FAKE_NPM = str(Path("C:/node/npm.cmd"))


def _tasks() -> ModuleType:
    spec = importlib.util.spec_from_file_location("tasks", ROOT / "scripts" / "tasks.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _recorder(ran: Ran) -> Callable[..., int]:
    """Finto `_run`: registra comando e opzioni e risponde 0."""

    def _run(cmd: list[str], **options: Any) -> int:
        ran.append((list(cmd), options))
        return 0

    return _run


def test_lint_is_python_only(monkeypatch: pytest.MonkeyPatch) -> None:
    tasks, ran = _tasks(), Ran()
    monkeypatch.setattr(tasks, "_run", _recorder(ran))
    assert tasks.main(["lint"]) == 0
    assert all("npm" not in " ".join(cmd) for cmd, _ in ran)


def test_admin_commands_use_the_npm_found_on_path(monkeypatch: pytest.MonkeyPatch) -> None:
    tasks, ran = _tasks(), Ran()
    monkeypatch.setattr(tasks.shutil, "which", lambda name: FAKE_NPM)
    monkeypatch.setattr(tasks, "_run", _recorder(ran))
    assert tasks.main(["admin-build"]) == 0
    [(command, options)] = ran
    assert command == [FAKE_NPM, "run", "build"]
    assert options["cwd"] == tasks.ADMIN_DIR


def test_admin_commands_explain_missing_npm(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    tasks = _tasks()
    monkeypatch.setattr(tasks.shutil, "which", lambda name: None)
    assert tasks.main(["admin-test"]) == 1
    assert "Node.js" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("command", "script"),
    [
        ("admin-install", ["ci", "--ignore-scripts"]),
        ("admin-dev", ["run", "dev"]),
        ("admin-test", ["run", "test:coverage"]),
        ("admin-lint", ["run", "lint"]),
    ],
)
def test_admin_command_list(
    monkeypatch: pytest.MonkeyPatch, command: str, script: list[str]
) -> None:
    tasks, ran = _tasks(), Ran()
    monkeypatch.setattr(tasks.shutil, "which", lambda name: "npm")
    monkeypatch.setattr(tasks, "_run", _recorder(ran))
    assert tasks.main([command]) == 0
    assert ran[0][0][1:] == script
