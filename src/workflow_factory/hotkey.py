"""Global emergency hotkey (Windows RegisterHotKey): one press stops every running flow.

The listener thread owns the hotkey and a message loop; it only calls back when Windows delivers
WM_HOTKEY. `simulate_press` posts that same message to the thread, so tests never send keyboard input.
"""

import ctypes
import threading
from collections.abc import Callable
from ctypes import wintypes

WM_HOTKEY, WM_QUIT, WM_USER, PM_NOREMOVE = 0x0312, 0x0012, 0x0400, 0x0000
MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_NOREPEAT = 0x0001, 0x0002, 0x0004, 0x4000
VK_F12 = 0x7B
HOTKEY_ID = 0x5744  # arbitrary id of this process' hotkey


class EmergencyHotkey:
    """Ctrl+Alt+Shift+F12 by default."""

    def __init__(self, callback: Callable[[], None], modifiers: int = MOD_CONTROL | MOD_ALT | MOD_SHIFT,
                 key: int = VK_F12):
        self._callback, self._modifiers, self._key = callback, modifiers, key
        self._thread = threading.Thread(target=self._run, name="emergency-hotkey", daemon=True)
        self._ready = threading.Event()
        self._registered = False
        self._thread_id = 0

    def start(self) -> None:
        self._thread.start()
        self._ready.wait(timeout=5)
        if not self._registered:
            raise RuntimeError("the emergency hotkey could not be registered (is another app using it?)")

    def stop(self) -> None:
        if self._thread_id:
            ctypes.windll.user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
        self._thread.join(timeout=5)

    def simulate_press(self) -> None:
        ctypes.windll.user32.PostThreadMessageW(self._thread_id, WM_HOTKEY, HOTKEY_ID, 0)

    def _run(self) -> None:
        user32 = ctypes.windll.user32
        self._thread_id = ctypes.windll.kernel32.GetCurrentThreadId()
        message = wintypes.MSG()
        user32.PeekMessageW(ctypes.byref(message), None, WM_USER, WM_USER, PM_NOREMOVE)  # create the queue
        self._registered = bool(user32.RegisterHotKey(None, HOTKEY_ID, self._modifiers | MOD_NOREPEAT, self._key))
        self._ready.set()
        if not self._registered:
            return
        try:
            while user32.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
                if message.message == WM_HOTKEY:
                    self._callback()
        finally:
            user32.UnregisterHotKey(None, HOTKEY_ID)
