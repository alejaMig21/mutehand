"""The person's clipboard is backed up before a paste and put back after, and the step says what it could not put back."""

from fake_clipboard import CF_BITMAP, CF_DIB, CF_HDROP, CF_UNICODETEXT, DROP_EFFECT, HTML_FORMAT, FakeClipboard

from workflow_factory.clipboard import backup, restore, set_text


def text_bytes(value: str) -> bytes:
    return value.encode("utf-16-le") + b"\x00\x00"


def test_a_text_clipboard_is_put_back_exactly_after_a_paste():
    board = FakeClipboard({CF_UNICODETEXT: text_bytes("my own copied words")})
    saved = backup(board)

    set_text(board, "the text we paste")
    assert board.text() == "the text we paste"
    lost = restore(board, saved)

    assert board.text() == "my own copied words" and lost == ()


def test_rich_formats_files_and_the_copy_or_cut_flag_are_all_kept_because_their_bytes_are_copied_as_they_are():
    items = {CF_UNICODETEXT: text_bytes("x"), HTML_FORMAT: b"<b>x</b>", CF_HDROP: b"\x14\x00paths", DROP_EFFECT: b"\x02\x00\x00\x00",
             CF_DIB: b"pixels"}
    board = FakeClipboard(items)
    saved = backup(board)

    set_text(board, "marker")
    lost = restore(board, saved)

    assert board.items == items and lost == ()  # byte for byte, including the cut flag


def test_a_format_that_gives_no_bytes_is_named_as_not_restored_not_silently_dropped():
    board = FakeClipboard({CF_UNICODETEXT: text_bytes("x"), CF_BITMAP: b"handle"}, unreadable=(CF_BITMAP,))
    saved = backup(board)

    set_text(board, "marker")
    lost = restore(board, saved)

    assert lost == ("bitmap handle",) and board.text() == "x" and CF_BITMAP not in board.items


def test_an_empty_clipboard_is_left_empty_not_filled_with_our_marker():
    board = FakeClipboard()
    saved = backup(board)

    set_text(board, "marker")
    lost = restore(board, saved)

    assert board.items == {} and lost == ()


def test_the_pasted_text_replaces_everything_so_nothing_of_the_old_content_can_be_pasted_by_mistake():
    board = FakeClipboard({CF_UNICODETEXT: text_bytes("old"), HTML_FORMAT: b"<i>old</i>"})

    set_text(board, "new")

    assert list(board.items) == [CF_UNICODETEXT] and board.text() == "new"
