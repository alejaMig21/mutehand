"""A stand-in for subprocess.run that behaves like the few schtasks calls this product makes, keeping tasks in memory.

It also holds a task the person made themselves, which the product must never list or remove.
"""

import subprocess
from xml.sax.saxutils import escape

FOREIGN = "\\Microsoft\\Windows\\Defrag\\ScheduledDefrag"


class FakeScheduler:
    def __init__(self):
        self.tasks: dict[str, dict] = {FOREIGN: {"command": "defrag.exe", "arguments": "/C", "at": "01:00"}}
        self.calls: list[list[str]] = []

    def __call__(self, args, **kwargs):
        self.calls.append(list(args))
        assert kwargs.get("shell") is not True
        verb = args[1]
        name = args[args.index("/TN") + 1] if "/TN" in args else None
        if verb == "/Create":
            command = args[args.index("/TR") + 1]
            exe, _, arguments = command.partition('" ')
            self.tasks["\\" + name] = {"command": exe.lstrip('"'), "arguments": arguments, "at": args[args.index("/ST") + 1]}
            return self._done(args)
        if verb == "/Delete":
            self.tasks.pop("\\" + name, None)
            return self._done(args)
        if verb == "/Query" and "/XML" in args:
            task = self.tasks.get("\\" + name)
            if task is None:
                return self._done(args, 1, err="ERROR: The system cannot find the file specified.")
            xml = (f'<?xml version="1.0" encoding="UTF-16"?><Task xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">'
                   f'<Triggers><CalendarTrigger><StartBoundary>2026-01-01T{task["at"]}:00</StartBoundary></CalendarTrigger></Triggers>'
                   f'<Actions><Exec><Command>{escape(task["command"])}</Command><Arguments>{escape(task["arguments"])}</Arguments>'
                   "</Exec></Actions></Task>")
            return self._done(args, out=xml)
        if verb == "/Query":
            return self._done(args, out="".join(f'"{n}","N/A","Ready"\n' for n in self.tasks))
        raise AssertionError(f"unexpected schtasks call {args}")

    @staticmethod
    def _done(args, code=0, out="", err=""):
        return subprocess.CompletedProcess(args, code, stdout=out, stderr=err)
