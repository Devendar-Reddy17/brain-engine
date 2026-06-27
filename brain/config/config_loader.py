"""Load, merge, and persist ``.brain/config.yml``.

Loading is tolerant: missing files or partial configs are merged onto the
defaults so callers always receive a fully-populated :class:`BrainConfig`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from brain.config.default_config import BrainConfig, default_config
from brain.utils.errors import ConfigError
from brain.utils.logger import get_logger
from brain.utils.paths import config_path, ensure_brain_dirs

log = get_logger(__name__)


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge ``override`` onto ``base`` (override wins)."""

    result = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config(repo_root: str | Path) -> BrainConfig:
    """Load config for ``repo_root``, merging onto defaults.

    If no config file exists, defaults are returned (nothing is written).
    """

    path = config_path(repo_root)
    base = default_config().model_dump()

    if not path.exists():
        log.debug("No config at %s; using defaults", path)
        return BrainConfig.model_validate(base)

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:  # pragma: no cover - defensive
        raise ConfigError(f"Failed to parse {path}", detail=str(exc)) from exc

    if not isinstance(raw, dict):
        raise ConfigError(f"Config at {path} must be a mapping")

    merged = _deep_merge(base, raw)
    try:
        return BrainConfig.model_validate(merged)
    except Exception as exc:  # pragma: no cover - defensive
        raise ConfigError(f"Invalid config at {path}", detail=str(exc)) from exc


def write_config(repo_root: str | Path, config: BrainConfig | None = None) -> Path:
    """Write config to ``.brain/config.yml``, creating dirs as needed.

    If ``config`` is None, write the default configuration.
    """

    ensure_brain_dirs(repo_root)
    path = config_path(repo_root)
    cfg = config or default_config()
    data = cfg.model_dump()
    path.write_text(
        yaml.safe_dump(data, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )
    log.info("Wrote config to %s", path)
    return path


def config_exists(repo_root: str | Path) -> bool:
    return config_path(repo_root).exists()
