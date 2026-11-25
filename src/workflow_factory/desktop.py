"""Desktop port: the single seam for everything that touches the machine."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Control:
    role: str
    name: str
    automation_id: str = ""


class Desktop(Protocol):
    def find(self, role: str, name: str, automation_id: str | None = None) -> Control | None: ...
    def click(self, control: Control) -> None: ...
    def snapshot(self) -> tuple[Control, ...]: ...
    def now(self) -> str: ...
