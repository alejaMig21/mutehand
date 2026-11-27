"""The setup check: what the product needs, in plain words, and one fix for each missing piece. It reads; it installs nothing."""

import subprocess

import pytest

from workflow_factory.checks import run_checks


def found(name):
    return f"C:\\tools\\{name}.exe"


def checks_by_id(data_dir, **kw):
    options = {"which": found, "monitors": lambda: 2, "project_dir": data_dir}
    return {c["id"]: c for c in run_checks(data_dir, **{**options, **kw})}


def test_everything_present_reads_as_ok_with_nothing_to_fix(tmp_path):
    (tmp_path / ".mcp.json").write_text("{}", encoding="utf-8")

    checks = checks_by_id(tmp_path)

    assert {c["id"] for c in checks.values()} == {"agent-desktop", "claude-code", "data-folder", "tutor-connection", "second-monitor"}
    assert all(c["ok"] and c["fix"] is None for c in checks.values())


def test_a_missing_piece_says_what_it_is_for_and_gives_one_plain_fix(tmp_path):
    checks = checks_by_id(tmp_path / "nowhere", which=lambda name: None, project_dir=tmp_path)

    for check_id in ("agent-desktop", "claude-code", "data-folder", "tutor-connection"):
        check = checks[check_id]
        assert not check["ok"] and check["fix"] and check["why"] and check["title"]
    assert "npm install -g agent-desktop" in checks["agent-desktop"]["fix"]
    assert "uv run mutehand" in checks["data-folder"]["fix"]


def test_a_second_monitor_is_wanted_not_required(tmp_path):
    checks = checks_by_id(tmp_path, monitors=lambda: 1)

    assert not checks["second-monitor"]["ok"] and checks["second-monitor"]["optional"] is True
    assert checks["agent-desktop"]["optional"] is False


def test_the_check_installs_nothing_creates_nothing_and_runs_no_program(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("the check must not run a program")

    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    folder = tmp_path / "data"

    run_checks(folder, which=lambda name: None, monitors=lambda: 1, project_dir=tmp_path)

    assert not folder.exists()  # not even the data folder it reports as missing


@pytest.mark.parametrize("check_id", ["agent-desktop", "claude-code"])
def test_a_program_that_is_there_is_not_reported_missing(tmp_path, check_id):
    assert checks_by_id(tmp_path)[check_id]["ok"]
