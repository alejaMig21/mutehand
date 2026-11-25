"""Desktop port: the single seam for everything that touches the machine."""

import zlib
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

import numpy as np


@dataclass(frozen=True)
class Control:
    role: str
    name: str
    automation_id: str = ""
    ref: str = field(default="", compare=False)  # adapter handle, changes per snapshot
    readable: bool = field(default=True, compare=False)  # False: the apprentice cannot perceive it
    bounds: tuple[float, float, float, float] | None = field(default=None, compare=False)  # adapter-side only


FRAME_FIELDS = (
    "window_state", "window_width", "window_height", "resolution_width", "resolution_height",
    "scale", "language", "theme",
)
# ponytail: fixed tolerances (window size may drift 20 px, everything else must match exactly);
# per-lesson tolerances if teaching shows a need.
FRAME_TOLERANCE = np.array([0, 20, 20, 0, 0, 0, 0, 0], dtype=float)


def _code(text: str) -> float:
    return float(zlib.crc32(text.encode()) % 100_000)  # stable numeric stand-in for a label


@dataclass(frozen=True)
class Frame:
    """The exact conditions a lesson was measured in (app and version live in the AppKey)."""

    window_state: str = "normal"
    window_width: int = 1000
    window_height: int = 700
    resolution_width: int = 1920
    resolution_height: int = 1080
    scale: float = 1.25
    language: str = "en-US"
    theme: str = "light"

    def vector(self) -> np.ndarray:
        return np.array(
            [_code(self.window_state), self.window_width, self.window_height,
             self.resolution_width, self.resolution_height, self.scale,
             _code(self.language), _code(self.theme)],
            dtype=float,
        )

    def distance(self, other: "Frame") -> float:
        return float(np.linalg.norm(self.vector() - other.vector()))

    def matches(self, other: "Frame", mask: tuple[str, ...]) -> bool:
        """Within tolerance on every field of the relevance mask; other fields are ignored."""
        picked = [FRAME_FIELDS.index(name) for name in mask]
        gap = np.abs(self.vector() - other.vector())
        return bool(np.all(gap[picked] <= FRAME_TOLERANCE[picked]))


@dataclass(frozen=True)
class AppKey:
    """An app's identity: process name plus executable version."""

    process: str
    version: str


@runtime_checkable
class Desktop(Protocol):
    def find(self, role: str, name: str, automation_id: str | None = None) -> Control | None: ...
    def click(self, control: Control) -> None: ...
    def click_at(self, anchor: Control, fx: float, fy: float) -> None: ...  # fractions of the anchor
    def drag(self, source: Control, source_point: tuple[float, float] | None,
             destination: Control, destination_point: tuple[float, float] | None) -> None: ...
    def capture(self, anchor: Control) -> np.ndarray: ...  # RGB pixels of the anchor's area only
    def type_text(self, control: Control, text: str) -> None: ...
    def type_secret(self, control: Control, secret_ref: str) -> None: ...
    def snapshot(self) -> tuple[Control, ...]: ...
    def app_key(self) -> AppKey: ...
    def frame(self) -> Frame: ...
    def now(self) -> str: ...
