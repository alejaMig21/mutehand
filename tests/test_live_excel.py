# ruff: noqa: E501
"""Opt-in live check of the `select` action and of a workbook open in two windows, on an Excel of our own.

It uses the foreground window (a click and Escape go there). That disturbs whoever is working, so it never runs by itself:
set WF_LIVE_EXCEL=1 and be away from the keyboard. Excel must not be running: the helper refuses to touch an instance the
person already has. The workbook is a throw-away file made here.
"""

import os
import subprocess
import time
import zipfile
from pathlib import Path

import pytest

from workflow_factory import Flow, Node, save_step
from workflow_factory.agent_desktop import AgentDesktop
from workflow_factory.flow import run_flow
from workflow_factory.steps import Locator, Step

pytestmark = pytest.mark.live
HELPER = Path.home() / ".claude" / "skills" / "live-testing" / "desktop-window.ps1"
EXCEL = r"C:\Program Files\Microsoft Office\Root\Office16\EXCEL.EXE"
SHEET = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
         '<sheetData><row r="1"><c r="A1" t="inlineStr"><is><t>Item</t></is></c></row></sheetData></worksheet>')
PARTS = {
    "[Content_Types].xml": '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>',
    "_rels/.rels": '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>',
    "xl/workbook.xml": '<?xml version="1.0" encoding="UTF-8"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets></workbook>',
    "xl/_rels/workbook.xml.rels": '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>',
    "xl/worksheets/sheet1.xml": SHEET,
}


def helper(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["powershell", "-NoProfile", "-File", str(HELPER), *args], capture_output=True, text=True, timeout=120)


@pytest.fixture(scope="module")
def our_excel(tmp_path_factory):
    if os.environ.get("WF_LIVE_EXCEL") != "1":
        pytest.skip("opt-in: set WF_LIVE_EXCEL=1 (it uses the foreground window)")
    book = tmp_path_factory.mktemp("excel") / "live_check.xlsx"
    with zipfile.ZipFile(book, "w") as archive:
        for name, text in PARTS.items():
            archive.writestr(name, text)
    launched = helper("launch", "-Exe", f'"{EXCEL}" /e "{book}"')
    if launched.returncode != 0:
        pytest.skip(f"the helper did not start our own Excel (exit {launched.returncode}): {launched.stdout.strip()}")
    pid = int(launched.stdout.split()[-1])
    try:
        desktop = AgentDesktop("EXCEL.EXE")
        for _ in range(40):  # Excel takes a while to show its grid
            try:
                if any(c.role == "cell" for c in desktop.snapshot()):
                    break
            except Exception:  # noqa: BLE001 - not ready yet
                pass
            time.sleep(1)
        else:
            pytest.fail("our Excel never showed its cells")
        yield desktop
    finally:  # our own Excel never outlives the test, whatever happened
        helper("stop", "-ProcessId", str(pid))


def cell_states(desktop, name):
    found = desktop._call(["find", "--app", "EXCEL.EXE", "--role", "cell", "--name", name, "--exact"])
    return found["matches"][0]["states"]


def pick(desktop, tmp_path, cell):
    key = desktop.app_key()
    save_step(tmp_path / "user.db", Step(app=key.process, version=key.version, name=f"pick-{cell}",
                                         locator=Locator("cell", cell), action="select"))
    return run_flow(Flow(id="f", nodes=[Node("p", f"pick-{cell}")]), desktop, tmp_path / "user.db")


def test_select_leaves_the_cell_selected_and_no_editor_open(tmp_path, our_excel):
    result = pick(our_excel, tmp_path, "C3")

    assert result.status == "finished", result.blocked
    assert {"focused", "selected"} <= set(cell_states(our_excel, "C3"))
    assert not any(c.name == "Cell Editor" for c in our_excel.snapshot())


def test_with_the_workbook_open_in_two_windows_a_step_acts_on_the_window_in_front(tmp_path, our_excel):
    view = next(c for c in our_excel.snapshot() if c.role == "tab" and c.name == "View")
    our_excel.click(view)
    time.sleep(1)
    our_excel.click(next(c for c in our_excel.snapshot() if c.name == "New Window"))
    time.sleep(3)
    windows = [w for w in our_excel._windows() if w.get("visible", True)]
    assert len(windows) == 2

    result = pick(our_excel, tmp_path, "D4")

    assert result.status == "finished", result.blocked
    focused = next(w for w in windows if w.get("is_focused"))
    found = our_excel._call(["find", "--app", "EXCEL.EXE", "--role", "cell", "--name", "D4", "--exact"])
    assert any("selected" in m["states"] and focused["title"] in "".join(m["path"]) for m in found["matches"])
