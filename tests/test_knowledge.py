import json
import subprocess
import sys

import numpy as np
import pytest

from workflow_factory import (
    Derived,
    Endpoint,
    Flow,
    Locator,
    Node,
    Sensitivity,
    Template,
    build_factory,
    duplicate_flow,
    export_knowledge,
    find_lesson,
    grant_consent,
    import_knowledge,
    list_flows,
    load_flow,
    run_flow,
    save_flow,
    save_lesson,
)
from workflow_factory.desktop import Frame

from fake_desktop import FakeDesktop, button, lesson

TEMPLATE_PIXELS = np.random.default_rng(5).integers(0, 255, (6, 6, 3), dtype=np.uint8)


def rich_lesson():
    """A lesson that uses every optional part, so a round trip proves nothing is dropped."""
    return lesson(
        "drag-to-bin", "Report.docx", action="drag", frame=Frame(scale=1.5, theme="dark"), mask=("scale", "theme"),
        derived=Derived(anchor=Locator("pane", "Desktop"), fx=0.25, fy=0.5),
        template=Template(anchor=Locator("pane", "Canvas"), pixels=TEMPLATE_PIXELS, min_score=0.9, max_attempts=2),
        drag_to=Endpoint(locator=Locator("icon", "Recycle Bin"),
                         derived=Derived(anchor=Locator("pane", "Desktop"), fx=0.9, fy=0.95)),
        capture=TEMPLATE_PIXELS, effect="closed_dialog", precondition="the file is visible")


def source_with_templates():
    return {
        "version": 1,
        "lessons": [{**export_one(lesson("open-menu", "Menu", factory_successes=40)), "origin": "local"}],
        "flows": [{"id": "morning-template", "nodes": [{"id": "a", "lesson": "open-menu"}], "edges": None}],
    }


def export_one(single):
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as folder:
        save_lesson(Path(folder) / "x.db", single)
        return export_knowledge(Path(folder) / "x.db")["lessons"][0]


# --- factory database -------------------------------------------------------------------------------

def test_building_writes_a_factory_database_of_factory_lessons_and_template_flows(tmp_path):
    out = tmp_path / "factory.db"

    build_factory(out, source_with_templates())

    found = find_lesson(tmp_path / "user.db", out, "paint.exe", "open-menu")
    assert found.origin == "factory" and found.factory_successes == 40  # origin forced, counters kept
    assert load_flow(tmp_path / "user.db", out, "morning-template").nodes[0].lesson == "open-menu"


def test_replacing_the_factory_file_leaves_the_user_database_untouched(tmp_path):
    user_db, factory_db = tmp_path / "user.db", tmp_path / "factory.db"
    save_lesson(user_db, lesson("mine", "Mine"))
    save_flow(user_db, Flow(id="my-flow", nodes=[Node("a", "mine")]))
    build_factory(factory_db, source_with_templates())
    before = user_db.read_bytes()

    newer = source_with_templates()
    newer["lessons"][0]["factory_successes"] = 99
    build_factory(factory_db, newer)  # a product update ships a new factory file

    assert user_db.read_bytes() == before
    assert find_lesson(user_db, factory_db, "paint.exe", "open-menu").factory_successes == 99
    assert load_flow(user_db, factory_db, "my-flow") is not None


def test_a_broken_source_leaves_the_existing_factory_file_as_it_was(tmp_path):
    factory_db = tmp_path / "factory.db"
    build_factory(factory_db, source_with_templates())
    before = factory_db.read_bytes()
    broken = source_with_templates()
    broken["lessons"].append({**broken["lessons"][0], "name": "bad", "action": "teleport"})

    with pytest.raises(ValueError):
        build_factory(factory_db, broken)

    assert factory_db.read_bytes() == before


# --- templates ------------------------------------------------------------------------------------------

def test_duplicating_a_template_gives_an_editable_copy_in_the_user_layer(tmp_path):
    user_db, factory_db = tmp_path / "user.db", tmp_path / "factory.db"
    build_factory(factory_db, source_with_templates())

    copy = duplicate_flow(user_db, factory_db, "morning-template", "my-morning")
    save_flow(user_db, Flow(id="my-morning", nodes=[*copy.nodes, Node("b", "open-menu")]))  # the person edits it

    assert [f for f in list_flows(user_db, factory_db)] == [
        {"id": "morning-template", "origin": "factory"}, {"id": "my-morning", "origin": "local"}]
    assert len(load_flow(user_db, factory_db, "my-morning").nodes) == 2
    assert len(load_flow(user_db, factory_db, "morning-template").nodes) == 1  # the template never changes


def test_duplicating_refuses_an_existing_name_or_an_unknown_template(tmp_path):
    user_db, factory_db = tmp_path / "user.db", tmp_path / "factory.db"
    build_factory(factory_db, source_with_templates())
    duplicate_flow(user_db, factory_db, "morning-template", "mine")

    with pytest.raises(ValueError, match="already exists"):
        duplicate_flow(user_db, factory_db, "morning-template", "mine")
    with pytest.raises(ValueError, match="no flow"):
        duplicate_flow(user_db, factory_db, "nope", "another")
    with pytest.raises(ValueError, match="letters"):  # an id the editor URLs could never reach
        duplicate_flow(user_db, factory_db, "morning-template", "a/b")


# --- export and import -----------------------------------------------------------------------------------

def test_exporting_then_importing_round_trips_lessons_and_flows_unchanged(tmp_path):
    first, second = tmp_path / "first.db", tmp_path / "second.db"
    save_lesson(first, rich_lesson())
    save_lesson(first, lesson("plain", "Plain"))
    save_flow(first, Flow(id="f", nodes=[Node("a", "plain", exclusive_input=True,
                                              inputs=(("t", "str"),)), Node("b", "drag-to-bin")], edges=[("a", "b")]))

    exported = export_knowledge(first)
    import_knowledge(second, json.loads(json.dumps(exported)))  # through real JSON text, as a file would be

    assert export_knowledge(second) == exported
    again = find_lesson(second, None, "paint.exe", "drag-to-bin")
    assert np.array_equal(again.template.pixels, TEMPLATE_PIXELS) and again.drag_to.derived.fx == 0.9


def test_an_export_holds_no_consents_and_no_secret_values_only_references(tmp_path):
    user_db = tmp_path / "user.db"
    grant_consent(user_db, app="paint.exe", control="Password", action="type_secret")
    save_lesson(user_db, lesson("login", "Password", action="type_secret", secret_ref="login",
                                sensitive=Sensitivity.PASSWORD_FIELD))
    desktop = FakeDesktop(controls=[button("Password")], secrets={"login": "hunter2"})
    run_flow(Flow(id="f", nodes=[Node("a", "login")]), desktop=desktop, user_db=user_db)  # types the secret

    exported = export_knowledge(user_db)
    text = json.dumps(exported)

    assert desktop.delivered == [("Password", "hunter2")]
    assert "hunter2" not in text and exported["lessons"][0]["secret_ref"] == "login"
    assert set(exported) == {"version", "lessons", "flows"}  # no consents section at all


def test_importing_never_grants_a_consent_so_a_sensitive_lesson_stays_blocked(tmp_path):
    source, target = tmp_path / "source.db", tmp_path / "target.db"
    save_lesson(source, lesson("send", "Send", sensitive=Sensitivity.OUTWARD_ACTION))
    grant_consent(source, app="paint.exe", control="Send", action="click")  # consent exists only at the source
    import_knowledge(target, export_knowledge(source))
    desktop = FakeDesktop(controls=[button("Send")])

    result = run_flow(Flow(id="f", nodes=[Node("a", "send")]), desktop=desktop, user_db=target)

    assert result.blocked == {"a": "no_consent"} and desktop.clicks == []


def test_a_bad_import_changes_nothing(tmp_path):
    source = tmp_path / "source.db"
    save_lesson(source, lesson("good", "Good"))
    data = export_knowledge(source)
    data["lessons"].append({**data["lessons"][0], "name": "bad", "action": "teleport"})

    with pytest.raises(ValueError):
        import_knowledge(tmp_path / "target.db", data)

    assert not (tmp_path / "target.db").exists()  # nothing was written, not even the good lesson


def test_an_export_of_another_format_version_is_refused(tmp_path):
    with pytest.raises(ValueError, match="version"):
        import_knowledge(tmp_path / "t.db", {"version": 99, "lessons": [], "flows": []})


# --- command line ------------------------------------------------------------------------------------------

def run_cli(*args):
    return subprocess.run([sys.executable, "-m", "workflow_factory.knowledge", *args], capture_output=True,
                          text=True, timeout=60)


def test_the_command_line_exports_imports_and_builds_the_factory_file(tmp_path):
    user_db, other_db, factory_db = tmp_path / "user.db", tmp_path / "other.db", tmp_path / "factory.db"
    save_lesson(user_db, lesson("open-menu", "Menu"))
    dump = tmp_path / "knowledge.json"

    exported = run_cli("export", "--user-db", str(user_db), "--out", str(dump))
    imported = run_cli("import", "--user-db", str(other_db), str(dump))
    built = run_cli("build-factory", str(dump), str(factory_db))

    assert (exported.returncode, imported.returncode, built.returncode) == (0, 0, 0), \
        exported.stderr + imported.stderr + built.stderr
    assert find_lesson(other_db, None, "paint.exe", "open-menu") is not None
    assert find_lesson(tmp_path / "none.db", factory_db, "paint.exe", "open-menu").origin == "factory"


# --- trust boundary: a file from elsewhere is untrusted input ---------------------------------------------

def exported_lesson(tmp_path, **kw):
    save_lesson(tmp_path / "source.db", lesson("send-it", "Send", **kw))
    return export_knowledge(tmp_path / "source.db")


def test_the_consent_gate_also_covers_an_imported_lesson_that_forgot_its_sensitive_label(tmp_path):
    data = exported_lesson(tmp_path)  # a "Send" button with sensitive = null
    import_knowledge(tmp_path / "target.db", data)
    desktop = FakeDesktop(controls=[button("Send")])

    result = run_flow(Flow(id="f", nodes=[Node("a", "send-it")]), desktop=desktop, user_db=tmp_path / "target.db")

    assert result.blocked == {"a": "no_consent"} and desktop.clicks == []


def test_importing_resets_trust_a_file_cannot_ship_counters_or_a_trusted_status(tmp_path):
    from workflow_factory import lesson_report

    data = exported_lesson(tmp_path)
    data["lessons"][0].update(factory_successes=1000, factory_failures=0, status="trusted")
    import_knowledge(tmp_path / "target.db", data)

    stored = find_lesson(tmp_path / "target.db", None, "paint.exe", "send-it")
    report = lesson_report(tmp_path / "target.db", stored)

    assert (report["successes"], report["state"]) == (0, "suspect")


def test_importing_refuses_to_replace_what_the_person_already_has_unless_told_to(tmp_path):
    user_db = tmp_path / "user.db"
    save_lesson(user_db, lesson("send-it", "Mine", effect="revealed"))
    save_flow(user_db, Flow(id="f", nodes=[Node("a", "send-it")]))
    data = exported_lesson(tmp_path)
    data["flows"] = [{"id": "f", "nodes": [{"id": "z", "lesson": "send-it"}], "edges": None}]

    with pytest.raises(ValueError, match="already exists"):
        import_knowledge(user_db, data)
    assert find_lesson(user_db, None, "paint.exe", "send-it").locator.name == "Mine"  # nothing replaced

    import_knowledge(user_db, data, overwrite=True)
    assert find_lesson(user_db, None, "paint.exe", "send-it").locator.name == "Send"
    assert [n.id for n in load_flow(user_db, None, "f").nodes] == ["z"]


@pytest.mark.parametrize("broken", [
    [],
    {"version": 1, "lessons": [], "flows": [{"id": "f", "nodes": [{"bogus": 1}], "edges": None}]},
    {"version": 1, "lessons": [], "flows": [{"id": "f", "nodes": [1], "edges": None}]},
    {"version": 1, "lessons": [], "flows": [{"id": "../x", "nodes": [], "edges": None}]},
    {"version": 1, "lessons": ["not a lesson"], "flows": []},
], ids=["list", "unknown node key", "node not an object", "bad flow id", "lesson not an object"])
def test_malformed_files_are_a_clear_error_never_a_traceback(tmp_path, broken):
    with pytest.raises(ValueError):
        import_knowledge(tmp_path / "t.db", broken)


def test_a_pixel_array_that_declares_an_absurd_size_is_refused_before_it_is_allocated(tmp_path):
    import base64
    import struct

    data = exported_lesson(tmp_path)
    header = "{'descr': '|u1', 'fortran_order': False, 'shape': (900000, 900000, 3), }"
    header += " " * (-(10 + len(header) + 1) % 64) + "\n"  # a real .npy header: 11 petabytes of pixels, 100 bytes of file
    blob = b"\x93NUMPY\x01\x00" + struct.pack("<H", len(header)) + header.encode()
    data["lessons"][0]["capture"] = base64.b64encode(blob).decode()

    with pytest.raises(ValueError, match="too large"):
        import_knowledge(tmp_path / "t.db", data)


def test_an_empty_relevance_mask_survives_the_round_trip(tmp_path):
    first, second = tmp_path / "a.db", tmp_path / "b.db"
    save_lesson(first, lesson("any-frame", "Menu", mask=()))

    import_knowledge(second, export_knowledge(first))

    assert find_lesson(second, None, "paint.exe", "any-frame").mask == ()


def test_a_lesson_the_person_rejected_stays_rejected_after_export_and_import(tmp_path):
    from workflow_factory import lesson_report, reject_lesson

    first, second = tmp_path / "a.db", tmp_path / "b.db"
    save_lesson(first, lesson("bad-idea", "Menu"))
    reject_lesson(first, "paint.exe", "bad-idea")

    import_knowledge(second, export_knowledge(first))

    assert lesson_report(second, find_lesson(second, None, "paint.exe", "bad-idea"))["state"] == "rejected"


def test_building_the_factory_from_an_empty_source_gives_a_valid_empty_file(tmp_path):
    out = tmp_path / "factory.db"

    build_factory(out, {"version": 1, "lessons": [], "flows": []})

    assert out.exists() and find_lesson(tmp_path / "u.db", out, "paint.exe", "anything") is None
    assert list_flows(tmp_path / "u.db", out) == []
