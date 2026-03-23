from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from traceback import format_exc


REPO_ROOT = Path(__file__).resolve().parents[2]
LOG_DIR = REPO_ROOT / "runtime-logs"
SESSIONS_DIR = LOG_DIR / "sessions"
GENERAL_LOG_PATH = LOG_DIR / "general.log"
ERROR_LOG_PATH = LOG_DIR / "errors.log"


def ensure_log_dirs() -> None:
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)


def create_session_log_path(process_kind: str) -> Path:
    ensure_log_dirs()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe_kind = "".join(char if char.isalnum() or char in {"-", "_"} else "-" for char in process_kind)
    return SESSIONS_DIR / f"{stamp}__{safe_kind}.log"


def append_general_log(message: str) -> None:
    _append_line(GENERAL_LOG_PATH, message)


def append_error_log(message: str) -> None:
    _append_line(ERROR_LOG_PATH, message)


def append_path_log(path: Path, message: str) -> None:
    _append_line(path, message)


def log_exception(context: str) -> None:
    append_error_log(f"[{context}] {format_exc().rstrip()}")


def _append_line(path: Path, message: str) -> None:
    ensure_log_dirs()
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"{_stamp()} {message.rstrip()}\n")


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
