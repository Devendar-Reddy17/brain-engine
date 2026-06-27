"""Debounce bursts of file changes.

Resets a single timer each time a change arrives; once the repo has been quiet
for ``delay_ms`` the registered callback fires once. Thread-safe.
"""

from __future__ import annotations

import threading
from typing import Callable


class Debouncer:
    def __init__(self, delay_ms: int, callback: Callable[[], None]) -> None:
        self.delay_s = max(0.0, delay_ms / 1000.0)
        self.callback = callback
        self._timer: threading.Timer | None = None
        self._lock = threading.Lock()

    def trigger(self) -> None:
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
            self._timer = threading.Timer(self.delay_s, self._fire)
            self._timer.daemon = True
            self._timer.start()

    def _fire(self) -> None:
        with self._lock:
            self._timer = None
        self.callback()

    def cancel(self) -> None:
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None
