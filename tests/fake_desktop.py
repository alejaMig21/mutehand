"""Fake desktop port: the single test seam. No real screen access."""

from workflow_factory import Lesson, Locator
from workflow_factory.desktop import AppKey, Control, Frame


class FakeDesktop:
    def __init__(
        self, controls, reveals=None, removes=None, now_value="2026-01-01T00:00:00Z",
        app="paint.exe", version="1.0", frame=None,
    ):
        self._frame = frame or Frame()
        self._app_key = AppKey(app, version)
        self._controls = list(controls)
        self._reveals = reveals or {}  # (role, name) -> controls shown after a click
        self._removes = removes or {}  # (role, name) -> controls hidden after a click
        self._now = now_value
        self.clicks = []
        self.typed = []

    def find(self, role, name, automation_id=None):
        for c in self._controls:
            if c.role == role and c.name == name:
                if automation_id is None or c.automation_id == automation_id:
                    return c
        return None

    def click(self, control):
        self.clicks.append(control)
        key = (control.role, control.name)
        gone = self._removes.get(key, [])
        self._controls = [c for c in self._controls if c not in gone]
        self._controls.extend(self._reveals.get(key, []))

    def type_text(self, control, text):
        self.typed.append((control, text))

    def snapshot(self):
        return tuple(self._controls)

    def app_key(self):
        return self._app_key

    def frame(self):
        return self._frame

    def now(self):
        return self._now


def button(name, automation_id=""):
    return Control(role="button", name=name, automation_id=automation_id)


def lesson(name, control_name, version="1.0", origin="local", app="paint.exe", **kw):
    return Lesson(
        app=app, version=version, name=name, origin=origin,
        locator=Locator(role="button", name=control_name), **kw,
    )
