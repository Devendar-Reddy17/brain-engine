"""Daemon entry point.

Usage:
    python -m brain.daemon.main --repo-root . --host 127.0.0.1 --port 8765

Starts the FastAPI app via uvicorn, begins watch mode, and logs to
``.brain/daemon.log``.
"""

from __future__ import annotations

import argparse

from brain.config.config_loader import load_config
from brain.core.repo.repo_root import detect_repo_root
from brain.daemon.api import create_app
from brain.daemon.lifecycle import BrainEngine
from brain.utils.logger import configure_logging, get_logger
from brain.utils.paths import daemon_log_path, ensure_brain_dirs


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Local Code Brain daemon")
    parser.add_argument("--repo-root", default=None)
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--no-watch", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    repo_root = detect_repo_root(args.repo_root)
    ensure_brain_dirs(repo_root)
    configure_logging(log_file=str(daemon_log_path(repo_root)))
    log = get_logger("brain.daemon")

    config = load_config(repo_root)
    host = args.host or config.daemon.host
    port = args.port or config.daemon.port

    log.info("Starting Local Code Brain daemon for %s on %s:%d", repo_root, host, port)
    engine = BrainEngine(repo_root)
    if not args.no_watch:
        engine.start_watch()

    app = create_app(engine)

    import uvicorn

    try:
        uvicorn.run(app, host=host, port=port, log_level="warning")
    finally:
        engine.shutdown()


if __name__ == "__main__":
    main()
