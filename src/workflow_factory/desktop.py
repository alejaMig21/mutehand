"""Desktop port: the single seam for everything that touches the machine."""

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class Control:
    role: str
    name: str
    automation_id: str = ""
    ref: str = field(default="", compare=False)  # adapter handle, changes per snapshot


@dataclass(frozen=True)
class AppKey:
    """An app's identity: process name plus executable version."""

    process: str
    version: str


@runtime_checkable
class Desktop(Protocol):
    def find(self, role: str, name: str, automation_id: str | None = None) -> Control | None: ...
    def click(self, control: Control) -> None: ...
    def type_text(self, control: Control, text: str) -> None: ...
    def snapshot(self) -> tuple[Control, ...]: ...
    def app_key(self) -> AppKey: ...
    def now(self) -> str: ...
