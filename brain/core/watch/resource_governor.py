"""Opportunistic resource governor.

Indexing must not slow the IDE or builds. The governor reports whether work
should pause based on system CPU, memory, battery, and build activity. Uses
``psutil`` when available; otherwise it degrades gracefully (never blocks).
"""

from __future__ import annotations

from brain.config.default_config import IndexingSection
from brain.utils.logger import get_logger

log = get_logger(__name__)

try:
    import psutil  # type: ignore
    _HAS_PSUTIL = True
except Exception:  # pragma: no cover
    psutil = None  # type: ignore
    _HAS_PSUTIL = False

_BUILD_PROCESS_HINTS = ("gradle", "mvn", "maven", "javac", "webpack", "vite", "tsc")


class ResourceGovernor:
    def __init__(self, config: IndexingSection) -> None:
        self.config = config

    def should_pause(self) -> tuple[bool, str]:
        if not _HAS_PSUTIL:
            return (False, "")

        try:
            cpu = psutil.cpu_percent(interval=0.0)
            if cpu and cpu > self.config.pause_when_system_cpu_above:
                return (True, f"system CPU {cpu:.0f}% > {self.config.pause_when_system_cpu_above}%")

            mem_used_mb = (psutil.virtual_memory().used) / (1024 * 1024)
            if mem_used_mb > self.config.pause_when_memory_above_mb:
                return (True, f"memory {mem_used_mb:.0f}MB > {self.config.pause_when_memory_above_mb}MB")

            if self.config.pause_when_on_battery and self._on_battery():
                return (True, "running on battery")

            if self.config.pause_during_build and self._build_running():
                return (True, "build in progress")
        except Exception as exc:  # pragma: no cover
            log.debug("resource check failed: %s", exc)

        return (False, "")

    def _on_battery(self) -> bool:
        try:
            battery = psutil.sensors_battery()
        except Exception:
            return False
        return bool(battery is not None and not battery.power_plugged)

    def _build_running(self) -> bool:
        try:
            for proc in psutil.process_iter(["name"]):
                name = (proc.info.get("name") or "").lower()
                if any(hint in name for hint in _BUILD_PROCESS_HINTS):
                    return True
        except Exception:
            return False
        return False
