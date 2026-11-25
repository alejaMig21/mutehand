import numpy as np
import pytest
from fake_desktop import FakeDesktop, button, lesson
from workflow_factory import Flow, Node, find_lesson, run_flow, save_lesson
from workflow_factory.desktop import Frame

FLOW = Flow(nodes=[Node(id="n1", lesson="open-menu")])


def run_with(taught_frame, current_frame, tmp_path, **lesson_kw):
    user_db = tmp_path / "user.db"
    save_lesson(user_db, lesson("open-menu", "Menu", frame=taught_frame, **lesson_kw))
    desktop = FakeDesktop(controls=[button("Menu")], frame=current_frame)
    result = run_flow(FLOW, desktop=desktop, user_db=user_db)
    return desktop, result


def test_lesson_replays_when_the_current_frame_is_within_tolerance(tmp_path):
    taught = Frame(window_width=1000, window_height=700)
    nearly = Frame(window_width=1010, window_height=695)  # inside the 20 px window tolerance

    desktop, result = run_with(taught, nearly, tmp_path)

    assert [c.name for c in desktop.clicks] == ["Menu"]
    assert result.blocked == {}


def test_change_in_a_masked_field_blocks_replay_and_is_reported_out_of_frame(tmp_path):
    taught, rescaled = Frame(scale=1.25), Frame(scale=1.5)

    desktop, result = run_with(taught, rescaled, tmp_path, mask=("scale", "window_width"))

    assert desktop.clicks == []
    assert result.blocked == {"n1": "out_of_frame"}


def test_change_in_an_unmasked_field_does_not_block_replay(tmp_path):
    taught, dark = Frame(theme="light"), Frame(theme="dark")

    desktop, result = run_with(taught, dark, tmp_path, mask=("scale",))

    assert [c.name for c in desktop.clicks] == ["Menu"]
    assert result.blocked == {}


def test_frame_vector_is_numeric_and_distance_grows_with_difference():
    base = Frame()
    near, far = Frame(window_width=base.window_width + 10), Frame(window_width=base.window_width + 500)

    assert np.issubdtype(base.vector().dtype, np.floating)
    assert base.distance(base) == 0
    assert 0 < base.distance(near) < base.distance(far)


def test_canvas_capture_is_stored_as_a_pixel_array_and_comes_back_identical(tmp_path):
    user_db = tmp_path / "user.db"
    pixels = np.arange(4 * 6 * 3, dtype=np.uint8).reshape(4, 6, 3)
    save_lesson(user_db, lesson("open-menu", "Menu", capture=pixels))

    stored = find_lesson(user_db, None, "paint.exe", "open-menu").capture

    assert stored.dtype == np.uint8 and stored.shape == (4, 6, 3)
    assert np.array_equal(stored, pixels)


def test_a_mask_naming_an_unknown_frame_field_is_rejected_when_the_lesson_is_saved(tmp_path):
    with pytest.raises(ValueError, match="windw_width"):
        save_lesson(tmp_path / "user.db", lesson("open-menu", "Menu", mask=("scale", "windw_width")))


def test_factory_lesson_with_a_frame_is_gated_like_a_local_one(tmp_path):
    factory_db, user_db = tmp_path / "factory.db", tmp_path / "user.db"
    save_lesson(factory_db, lesson("open-menu", "Menu", origin="factory", frame=Frame(scale=1.25),
                                   mask=("scale",)))
    desktop = FakeDesktop(controls=[button("Menu")], frame=Frame(scale=2.0))

    result = run_flow(FLOW, desktop=desktop, user_db=user_db, factory_db=factory_db)

    assert desktop.clicks == []
    assert result.blocked == {"n1": "out_of_frame"}
