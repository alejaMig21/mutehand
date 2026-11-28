"""Fake desktop port: the single test seam. No real screen access."""

import threading
import time
from datetime import UTC, datetime, timedelta

from fake_clipboard import FakeClipboard

from workflow_factory import Locator, Step, save_flow
from workflow_factory.clipboard import backup, restore, set_text
from workflow_factory.desktop import AppKey, Control, DesktopError, Frame
from workflow_factory.flows import with_technology


class FakeDesktop:
    def __init__(
        self, controls, reveals=None, removes=None, seconds_per_action=0, vanish_after=None,
        app="paint.exe", version="1.0", frame=None, secrets=None, captures=None, product_name="",
    ):
        self._captures = captures or {}  # anchor name -> pixel array the fake "screen" shows there
        self._secrets = secrets or {}
        self.delivered = []  # (control name, value) the target received; never part of `calls`
        self._frame = frame or Frame()
        self._app_key = AppKey(app, version, product_name)
        self._controls = list(controls)
        self._reveals = reveals or {}  # (role, name) -> controls shown after a click
        self._removes = removes or {}  # (role, name) -> controls hidden after a click
        self._start = datetime(2026, 1, 1, tzinfo=UTC)
        self._seconds_per_action = seconds_per_action  # the fake clock advances with every action
        self._vanish_after = vanish_after  # after this many clicks every control disappears
        self._actions = 0
        self.click_seconds = 0.0  # how long an action takes, so overlap between threads is observable
        self._busy = threading.Lock()
        self._active = self.max_active = 0  # actions in progress now / the most at the same time
        self.foreground = app  # the process that owns the foreground window
        self.cursor = (0, 0)
        self._last_input = -3600.0  # fake seconds; the user has been idle for a long time
        self._slept = 0.0
        self.slept_total = 0.0
        self.on_action = []  # callables run after every action: tests make the user act here
        self._deferred = []
        self.on_sleep = []  # callables run on every sleep
        self.fail_on = set()  # control names whose click fails with a DesktopError
        self.rendezvous = None  # a Barrier: every action waits for its peers, forcing a real overlap
        self.clicks = []
        self.typed = []
        self.texts = {}  # control name -> the text a read gives
        self.board = FakeClipboard()  # the person's clipboard
        self.pressed = []  # (key, foreground process) for every key sent
        self.page = ""  # what reached the app's own page by keys
        self.elsewhere = ""  # what reached some other window by keys
        self.reads = []  # names of the controls whose text was read
        self.hits = []  # absolute screen points the fake derived internally; the core never sees them
        self.calls = []  # every action call the apprentice made, in order (names and arguments)

    def find(self, role, name, automation_id=None):
        self.calls.append(("find", role, name, automation_id))
        deferred, self._deferred = self._deferred, []
        for hook in deferred:
            hook()
        for c in self._controls:
            if c.role == role and c.name == name:
                if automation_id is None or c.automation_id == automation_id:
                    return c
        return None

    def _acting(self):
        with self._busy:
            self._active += 1
            self.max_active = max(self.max_active, self._active)
        if self.rendezvous is not None:
            self.rendezvous.wait(timeout=2)  # BrokenBarrierError if the peers never run together
        time.sleep(self.click_seconds)
        with self._busy:
            self._active -= 1

    def _after(self):
        """The action is over: our own input counts as input, then tests may make the user act."""
        self._last_input = self._seconds()
        self._deferred = list(self.on_action)  # they fire at the next port call, like a person would

    def click(self, control):
        self._acting()
        if control.name in self.fail_on:
            raise DesktopError(f"cannot click {control.name}")
        self._actions += 1
        if self._vanish_after is not None and self._actions >= self._vanish_after:
            self._controls = []
        self.calls.append(("click", control.name))
        self.clicks.append(control)
        key = (control.role, control.name)
        gone = self._removes.get(key, [])
        self._controls = [c for c in self._controls if c not in gone]
        self._controls.extend(self._reveals.get(key, []))
        self._after()

    def click_at(self, anchor, fx, fy):
        self._acting()
        self.calls.append(("click_at", anchor.name, fx, fy))
        x, y, w, h = anchor.bounds
        self.hits.append((x + fx * w, y + fy * h))
        self.cursor = (int(x + fx * w), int(y + fy * h))
        self._after()

    def drag(self, source, source_point, destination, destination_point):
        self._acting()
        self.calls.append(("drag", source.name, source_point, destination.name, destination_point))
        self._after()

    def capture(self, anchor):
        self.calls.append(("capture", anchor.name))
        return self._captures[anchor.name]

    def type_text(self, control, text):
        self._acting()
        self.calls.append(("type_text", control.name))
        self.typed.append((control, text))
        self._after()

    def clipboard_backup(self):
        self.calls.append(("clipboard_backup",))
        return backup(self.board)

    def clipboard_set(self, text):
        self.calls.append(("clipboard_set",))
        set_text(self.board, text)

    def clipboard_restore(self, saved):
        self.calls.append(("clipboard_restore",))
        return restore(self.board, saved)

    def press_key(self, key):
        """A real key to whichever window is in the foreground, like the person's keyboard."""
        self._acting()
        self.calls.append(("press_key", key))
        self.pressed.append((key, self.foreground))
        typed = {"return": "\n", "space": " "}.get(key, key[6:].upper() if key.startswith("shift+") else key if len(key) == 1 else "")
        if key == "ctrl+v":
            typed = self.board.text() or ""
        if self.foreground == self._app_key.process:
            self.page += typed
        else:
            self.elsewhere += typed
        self._after()

    def read_text(self, control):
        self.calls.append(("read_text", control.name))
        self.reads.append(control.name)
        return self.texts.get(control.name, "")

    def type_secret(self, control, secret_ref):
        self._acting()
        self.calls.append(("type_secret", control.name, secret_ref))
        self.delivered.append((control.name, self._secrets[secret_ref]))
        self._after()

    def snapshot(self):
        return tuple(self._controls)

    def app_key(self):
        return self._app_key

    def frame(self):
        return self._frame

    def _seconds(self):
        return self._actions * self._seconds_per_action + self._slept

    def input_fingerprint(self):
        return (self.cursor, self._last_input)

    def idle_seconds(self):
        return self._seconds() - self._last_input

    def foreground_app(self):
        deferred, self._deferred = self._deferred, []  # what the person did after the last action shows now
        for hook in deferred:
            hook()
        return self.foreground

    def sleep(self, seconds):
        self._slept += seconds
        self.slept_total += seconds
        for hook in list(self.on_sleep):
            hook()

    def screen_changes(self):
        """Whatever was on screen is gone (a dialog closed, the app moved on)."""
        self._controls = []

    def user_acts(self):
        """The person moves the mouse: the cursor shifts and the last-input time is now."""
        self.cursor = (self.cursor[0] + 50, self.cursor[1])
        self._last_input = self._seconds()

    def now(self):
        moment = self._start + timedelta(seconds=self._seconds())
        return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def button(name, automation_id="", readable=True, secure=False):
    return Control(role="button", name=name, automation_id=automation_id, readable=readable, secure=secure)


def step(name, control_name, version="1.0", origin="local", app="paint.exe", **kw):
    return Step(
        app=app, version=version, name=name, origin=origin,
        locator=Locator(role="button", name=control_name), **kw,
    )


def field(name):
    return Control(role="textfield", name=name)


def icon(name, x, y, width, height):
    return Control(role="icon", name=name, bounds=(x, y, width, height))


def pane(name, x, y, width, height):
    return Control(role="pane", name=name, bounds=(x, y, width, height))


def save_flow_on(db, flow, title=None, app=None):
    """Save a flow whose step nodes that name no technology act on `app`."""
    save_flow(db, with_technology(flow, app) if app else flow, title)


def save_flow_paint(db, flow, title=None):
    """`save_flow_on` for the many tests whose steps are all taught on Paint, the stand-in desktop's default."""
    save_flow_on(db, flow, title, "paint.exe")


