import pytest

from workflow_factory import cli


def commands(calls):
    def make(name, code=0):
        def handler(argv):
            calls.append((name, list(argv)))
            return code
        return handler

    return {"open": make("open"), "run": make("run", 3), "schedule": make("schedule"),
            "knowledge": make("knowledge"), "mcp": make("mcp")}


def test_no_arguments_opens_the_editor():
    calls = []

    assert cli.main([], commands(calls)) == 0

    assert calls == [("open", [])]


def test_a_command_gets_the_rest_of_the_arguments_and_its_exit_code_is_returned():
    calls = []

    code = cli.main(["run", "--flow", "daily", "--app", "mspaint.exe"], commands(calls))

    assert calls == [("run", ["--flow", "daily", "--app", "mspaint.exe"])]
    assert code == 3


def test_a_handler_that_returns_nothing_means_success():
    assert cli.main(["mcp"], {"mcp": lambda argv: None}) == 0


def test_an_unknown_command_is_refused_and_the_real_ones_are_listed(capsys):
    calls = []

    code = cli.main(["frobnicate"], commands(calls))

    assert code == 2 and calls == []
    err = capsys.readouterr().err
    assert "frobnicate" in err and all(name in err for name in ("run", "schedule", "knowledge", "mcp"))


@pytest.mark.parametrize("flag", ["-h", "--help", "help"])
def test_help_lists_every_command_and_starts_nothing(flag, capsys):
    calls = []

    assert cli.main([flag], commands(calls)) == 0

    out = capsys.readouterr().out
    assert calls == [] and all(name in out for name in ("open", "run", "schedule", "knowledge", "mcp"))


def test_the_installed_command_is_the_front_door():
    import subprocess

    result = subprocess.run(["uv", "run", "--no-sync", "workflow-factory", "--help"], capture_output=True, text=True, timeout=120)

    assert result.returncode == 0, result.stderr
    assert all(name in result.stdout for name in ("open", "run", "schedule", "knowledge", "mcp"))
