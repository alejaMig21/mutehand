"""Desktop port: the single seam for everything that touches the machine."""

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class Control:
    role: str
    name: str
    automation_id: str = ""
    ref: str = field(default="", compare=False)  # adapter handle, changes per snapshot


@runtime_checkable
class Desktop(Protocol):
    def find(self, role: str, name: str, automation_id: str | None = None) -> Control | None: ...
    def click(self, control: Control) -> None: ...
    def type_text(self, control: Control, text: str) -> None: ...
    def snapshot(self) -> tuple[Control, ...]: ...
    def now(self) -> str: ...
