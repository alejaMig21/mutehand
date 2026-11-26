"""An in-memory stand-in for the Windows clipboard, with the few facts the product depends on."""

CF_UNICODETEXT, CF_HDROP, CF_DIB, CF_BITMAP = 13, 15, 8, 2
HTML_FORMAT, DROP_EFFECT = 49000, 49001
NAMES = {CF_UNICODETEXT: "text", CF_HDROP: "files", CF_DIB: "image", CF_BITMAP: "bitmap handle",
         HTML_FORMAT: "HTML Format", DROP_EFFECT: "Preferred DropEffect"}


class FakeClipboard:
    """formats() / get() / set_all() / name(): what clipboard.py needs from a backend."""

    def __init__(self, items: dict[int, bytes] | None = None, unreadable: tuple[int, ...] = ()):
        self.items = dict(items or {})
        self.unreadable = set(unreadable)  # formats that exist but give no bytes (a handle, delayed rendering)
        self.writes = 0

    def formats(self) -> list[int]:
        return list(self.items)

    def get(self, fmt: int) -> bytes | None:
        return None if fmt in self.unreadable else self.items.get(fmt)

    def set_all(self, items: dict[int, bytes]) -> None:
        self.items = dict(items)
        self.unreadable = set()
        self.writes += 1

    def name(self, fmt: int) -> str:
        return NAMES.get(fmt, f"format {fmt}")

    def text(self) -> str | None:
        raw = self.items.get(CF_UNICODETEXT)
        return None if raw is None else raw.decode("utf-16-le").rstrip("\x00")
