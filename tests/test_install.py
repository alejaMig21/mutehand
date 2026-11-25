import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INSTALLER = ROOT / "installer" / "install.ps1"


def run_installer(desktop, start_menu, python=None):
    command = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(INSTALLER),
               "-DesktopDir", str(desktop), "-StartMenuDir", str(start_menu)]
    if python:
        command += ["-Python", str(python)]
    return subprocess.run(command, capture_output=True, text=True, timeout=120)


def read_shortcut(path):
    script = (f"$s = (New-Object -ComObject WScript.Shell).CreateShortcut('{path}'); "
              "$s.TargetPath; $s.Arguments; $s.WorkingDirectory")
    out = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True, timeout=60)
    return out.stdout.strip().splitlines()


def test_the_installer_makes_one_windowless_shortcut_on_the_desktop_and_in_the_start_menu(tmp_path):
    desktop, start_menu = tmp_path / "Desktop", tmp_path / "Programs"
    desktop.mkdir(), start_menu.mkdir()

    result = run_installer(desktop, start_menu)

    assert result.returncode == 0, result.stderr
    for folder in (desktop, start_menu):
        target, arguments, workdir = read_shortcut(folder / "Workflow Factory.lnk")
        assert target.lower().endswith("pythonw.exe")  # no console window
        assert arguments == "-m workflow_factory.app"
        assert Path(workdir) == ROOT


def test_the_installer_is_safe_to_run_twice(tmp_path):
    desktop, start_menu = tmp_path / "Desktop", tmp_path / "Programs"
    desktop.mkdir(), start_menu.mkdir()

    assert run_installer(desktop, start_menu).returncode == 0
    assert run_installer(desktop, start_menu).returncode == 0
    assert [p.name for p in desktop.iterdir()] == ["Workflow Factory.lnk"]


def test_the_installer_says_what_to_do_when_the_environment_is_missing(tmp_path):
    desktop, start_menu = tmp_path / "Desktop", tmp_path / "Programs"
    desktop.mkdir(), start_menu.mkdir()

    result = run_installer(desktop, start_menu, python=tmp_path / "nowhere" / "pythonw.exe")

    assert result.returncode == 1
    assert "uv sync" in result.stdout + result.stderr
    assert list(desktop.iterdir()) == []  # nothing half made
