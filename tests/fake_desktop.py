"""Fake desktop port: the single test seam. No real screen access."""

from workflow_factory import Lesson, Locator
from workflow_factory.desktop import AppKey, Control, Frame


class FakeDesktop:
    def __init__(
        self, controls, reveals=None, removes=None, now_value="2026-01-01T00:00:00Z",
        app="paint.exe", version="1.0", frame=None, secrets=None,
    ):
        self._secrets = secrets or {}
        self.delivered = []  # (control name, value) the target received; never part of `calls`
        self._frame = frame or Frame()
        self._app_key = AppKey(app, version)
        self._controls = list(controls)
        self._reveals = reveals or {}  # (role, name) -> controls shown after a click
        self._removes = removes or {}  # (role, name) -> controls hidden after a click
        self._now = now_value
        self.clicks = []
        self.typed = []
        self.calls = []  # every action call the apprentice made, in order (names and arguments)

    def find(self, role, name, automation_id=None):
        self.calls.append(("find", role, name, automation_id))
        for c in self._controls:
            if c.role == role and c.name == name:
                if automation_id is None or c.automation_id == automation_id:
                    return c
        return None

    def click(self, control):
        self.calls.append(("click", control.name))
        self.clicks.append(control)
        key = (control.role, control.name)
        gone = self._removes.get(key, [])
        self._controls = [c for c in self._controls if c not in gone]
        self._controls.extend(self._reveals.get(key, []))

    def type_text(self, control, text):
        self.calls.append(("type_text", control.name))
        self.typed.append((control, text))

    def type_secret(self, control, secret_ref):
        self.calls.append(("type_secret", control.name, secret_ref))
        self.delivered.append((control.name, self._secrets[secret_ref]))

    def snapshot(self):
        return tuple(self._controls)

    def app_key(self):
        return self._app_key

    def frame(self):
        return self._frame

    def now(self):
        return self._now


def button(name, automation_id="", readable=True):
    return Control(role="button", name=name, automation_id=automation_id, readable=readable)


def lesson(name, control_name, version="1.0", origin="local", app="paint.exe", **kw):
    return Lesson(
        app=app, version=version, name=name, origin=origin,
        locator=Locator(role="button", name=control_name), **kw,
    )


def field(name):
    return Control(role="textfield", name=name)
