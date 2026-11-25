"""Fake desktop port: the single test seam. No real screen access."""

from datetime import UTC, datetime, timedelta

from workflow_factory import Lesson, Locator
from workflow_factory.desktop import AppKey, Control, Frame


class FakeDesktop:
    def __init__(
        self, controls, reveals=None, removes=None, seconds_per_action=0, vanish_after=None,
        app="paint.exe", version="1.0", frame=None, secrets=None, captures=None,
    ):
        self._captures = captures or {}  # anchor name -> pixel array the fake "screen" shows there
        self._secrets = secrets or {}
        self.delivered = []  # (control name, value) the target received; never part of `calls`
        self._frame = frame or Frame()
        self._app_key = AppKey(app, version)
        self._controls = list(controls)
        self._reveals = reveals or {}  # (role, name) -> controls shown after a click
        self._removes = removes or {}  # (role, name) -> controls hidden after a click
        self._start = datetime(2026, 1, 1, tzinfo=UTC)
        self._seconds_per_action = seconds_per_action  # the fake clock advances with every action
        self._vanish_after = vanish_after  # after this many clicks every control disappears
        self._actions = 0
        self.clicks = []
        self.typed = []
        self.hits = []  # absolute screen points the fake derived internally; the core never sees them
        self.calls = []  # every action call the apprentice made, in order (names and arguments)

    def find(self, role, name, automation_id=None):
        self.calls.append(("find", role, name, automation_id))
        for c in self._controls:
            if c.role == role and c.name == name:
                if automation_id is None or c.automation_id == automation_id:
                    return c
        return None

    def click(self, control):
        self._actions += 1
        if self._vanish_after is not None and self._actions >= self._vanish_after:
            self._controls = []
        self.calls.append(("click", control.name))
        self.clicks.append(control)
        key = (control.role, control.name)
        gone = self._removes.get(key, [])
        self._controls = [c for c in self._controls if c not in gone]
        self._controls.extend(self._reveals.get(key, []))

    def click_at(self, anchor, fx, fy):
        self.calls.append(("click_at", anchor.name, fx, fy))
        x, y, w, h = anchor.bounds
        self.hits.append((x + fx * w, y + fy * h))

    def drag(self, source, source_point, destination, destination_point):
        self.calls.append(("drag", source.name, source_point, destination.name, destination_point))

    def capture(self, anchor):
        self.calls.append(("capture", anchor.name))
        return self._captures[anchor.name]

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
        moment = self._start + timedelta(seconds=self._actions * self._seconds_per_action)
        return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def button(name, automation_id="", readable=True, secure=False):
    return Control(role="button", name=name, automation_id=automation_id, readable=readable, secure=secure)


def lesson(name, control_name, version="1.0", origin="local", app="paint.exe", **kw):
    return Lesson(
        app=app, version=version, name=name, origin=origin,
        locator=Locator(role="button", name=control_name), **kw,
    )


def field(name):
    return Control(role="textfield", name=name)


def icon(name, x, y, width, height):
    return Control(role="icon", name=name, bounds=(x, y, width, height))


def pane(name, x, y, width, height):
    return Control(role="pane", name=name, bounds=(x, y, width, height))
