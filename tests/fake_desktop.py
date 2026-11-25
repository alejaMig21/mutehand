"""Fake desktop port: the single test seam. No real screen access."""

from workflow_factory.desktop import Control


class FakeDesktop:
    def __init__(self, controls, reveals=None, removes=None, now_value="2026-01-01T00:00:00Z"):
        self._controls = list(controls)
        self._reveals = reveals or {}  # (role, name) -> controls shown after a click
        self._removes = removes or {}  # (role, name) -> controls hidden after a click
        self._now = now_value
        self.clicks = []

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

    def snapshot(self):
        return tuple(self._controls)

    def now(self):
        return self._now


def button(name, automation_id=""):
    return Control(role="button", name=name, automation_id=automation_id)
