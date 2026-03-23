from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from pathlib import Path

try:
    import webview  # type: ignore
except ModuleNotFoundError as exc:  # pragma: no cover - runtime dependency
    raise SystemExit(
        "Falta la dependencia de UI. Instala con: .venv/bin/python -m pip install pywebview"
    ) from exc

from .runtime_logs import (
    ERROR_LOG_PATH,
    GENERAL_LOG_PATH,
    append_error_log,
    append_general_log,
    create_session_log_path,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
ASSETS_ROOT = Path(__file__).resolve().parent / "gui_assets"
DEFAULT_OUTPUT_ROOT = Path.home() / "Music" / "Logic Podcast Automation Exports"


class AppBridge:
    def __init__(self) -> None:
        self.window: webview.Window | None = None
        self.process: subprocess.Popen[str] | None = None
        self.session_log_path: Path | None = None
        self.lock = threading.Lock()

    def get_initial_state(self) -> dict[str, object]:
        return {
            "profiles": ["podcast-stereo", "podcast-mono"],
            "default_profile": "podcast-stereo",
            "default_output_root": str(DEFAULT_OUTPUT_ROOT),
            "repo_root": str(REPO_ROOT),
            "python_path": sys.executable,
            "python_label": f"Python {sys.version_info.major}.{sys.version_info.minor}",
            "general_log_path": str(GENERAL_LOG_PATH),
            "error_log_path": str(ERROR_LOG_PATH),
            "plugin_setup_ready": False,
        }

    def pick_logic_project(self) -> str | None:
        self._require_window()
        result = self.window.create_file_dialog(  # type: ignore[union-attr]
            webview.OPEN_DIALOG,
            allow_multiple=False,
            directory=str(Path.home()),
            file_types=("Logic Project (*.logicx)",),
        )
        if result:
            return str(result[0])

        result = self.window.create_file_dialog(  # type: ignore[union-attr]
            webview.FOLDER_DIALOG,
            allow_multiple=False,
            directory=str(Path.home()),
        )
        if result:
            return str(result[0])
        return None

    def pick_output_folder(self) -> str | None:
        self._require_window()
        result = self.window.create_file_dialog(  # type: ignore[union-attr]
            webview.FOLDER_DIALOG,
            allow_multiple=False,
            directory=str(DEFAULT_OUTPUT_ROOT.parent),
        )
        if result:
            return str(result[0])
        return None

    def pick_audio_track(self) -> str | None:
        self._require_window()
        result = self.window.create_file_dialog(  # type: ignore[union-attr]
            webview.OPEN_DIALOG,
            allow_multiple=False,
            directory=str(Path.home()),
            file_types=(
                "Audio Files (*.wav;*.aif;*.aiff;*.caf;*.mp3)",
            ),
        )
        if result:
            return str(result[0])
        return None

    def run_session(self, payload: dict[str, object]) -> dict[str, object]:
        source = str(payload.get("source", "")).strip()
        output_root = str(payload.get("output_root", "")).strip()
        profile = str(payload.get("profile", "podcast-stereo")).strip() or "podcast-stereo"
        mode = str(payload.get("mode", "run")).strip()

        if not source:
            raise ValueError("Selecciona un proyecto de Logic antes de ejecutar.")
        if not output_root:
            raise ValueError("Selecciona una carpeta de salida.")
        if mode not in {"run", "prepare-mix"}:
            raise ValueError(f"Modo no soportado: {mode}")

        command = [
            sys.executable,
            "-m",
            "daw_podcast_automation",
            mode,
            "--source",
            source,
            "--profile",
            profile,
            "--output-root",
            output_root,
        ]
        if mode == "prepare-mix" and bool(payload.get("open_in_logic", False)):
            command.append("--open-in-logic")

        return self._spawn_command(command, process_kind=mode)

    def analyze_audio_track(self, payload: dict[str, object]) -> dict[str, object]:
        source = str(payload.get("source", "")).strip()
        report = str(payload.get("report", "")).strip()
        profile = str(payload.get("profile", "podcast-stereo")).strip() or "podcast-stereo"
        window_seconds = str(payload.get("window_seconds", "0.25")).strip()
        delta_db = str(payload.get("delta_db", "6.0")).strip()
        silence_top_db = str(payload.get("silence_top_db", "35.0")).strip()

        if not source:
            raise ValueError("Selecciona un archivo de audio para analizar.")
        if not report:
            report = str(Path(source).with_name(f"{Path(source).stem}__analysis.json"))

        command = [
            sys.executable,
            "-m",
            "daw_podcast_automation",
            "analyze-track",
            "--input",
            source,
            "--report",
            report,
            "--profile",
            profile,
            "--window-seconds",
            window_seconds,
            "--delta-db",
            delta_db,
            "--silence-top-db",
            silence_top_db,
        ]
        return self._spawn_command(command, process_kind="analyze-track")

    def open_path(self, path: str) -> None:
        if not path:
            return
        subprocess.run(["open", path], check=False)

    def _spawn_command(self, command: list[str], *, process_kind: str) -> dict[str, object]:
        self._require_window()
        with self.lock:
            if self.process is not None and self.process.poll() is None:
                append_error_log(f"[gui] Intento de lanzar `{process_kind}` con otro proceso en marcha.")
                raise ValueError("Ya hay un proceso en marcha. Espera a que termine antes de lanzar otro.")

            env = os.environ.copy()
            env["PYTHONPATH"] = str(REPO_ROOT / "src")
            self.session_log_path = create_session_log_path(process_kind)
            append_general_log(
                f"[gui] Lanzando `{process_kind}` | session_log={self.session_log_path} | command={' '.join(command)}"
            )
            self.process = subprocess.Popen(
                command,
                cwd=REPO_ROOT,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )

        threading.Thread(
            target=self._stream_process_output,
            args=(self.process, process_kind),
            daemon=True,
        ).start()
        return {"started": True}

    def _stream_process_output(
        self,
        process: subprocess.Popen[str],
        process_kind: str,
    ) -> None:
        self._emit_event(
            "onProcessState",
            {
                "status": "running",
                "process_kind": process_kind,
                "message": "Proceso en marcha.",
                "session_log_path": str(self.session_log_path) if self.session_log_path is not None else "",
            },
        )

        assert process.stdout is not None
        for raw_line in process.stdout:
            line = raw_line.rstrip("\n")
            self._append_session_line(process_kind, line)
            self._emit_event(
                "onProcessLine",
                {
                    "line": line,
                    "process_kind": process_kind,
                },
            )

        return_code = process.wait()
        with self.lock:
            self.process = None
            session_log_path = self.session_log_path
            self.session_log_path = None

        append_general_log(
            f"[gui] `{process_kind}` termino con return_code={return_code} | session_log={session_log_path}"
        )
        if return_code != 0:
            append_error_log(
                f"[gui] `{process_kind}` termino con error. return_code={return_code} | session_log={session_log_path}"
            )

        self._emit_event(
            "onProcessState",
            {
                "status": "success" if return_code == 0 else "error",
                "process_kind": process_kind,
                "return_code": return_code,
                "message": "Proceso terminado." if return_code == 0 else "Proceso terminado con error.",
                "session_log_path": str(session_log_path) if session_log_path is not None else "",
            },
        )

    def _emit_event(self, event_name: str, payload: dict[str, object]) -> None:
        if self.window is None:
            return
        script = f"window.{event_name}({json.dumps(payload, ensure_ascii=True)});"
        self.window.evaluate_js(script)

    def _require_window(self) -> None:
        if self.window is None:
            raise RuntimeError("La ventana de la app no esta inicializada.")

    def _append_session_line(self, process_kind: str, line: str) -> None:
        if self.session_log_path is not None:
            with self.session_log_path.open("a", encoding="utf-8") as handle:
                handle.write(f"{line}\n")
        append_general_log(f"[{process_kind}] {line}")
        if line.startswith("error:") or "Traceback" in line:
            append_error_log(f"[{process_kind}] {line}")


def main() -> int:
    append_general_log("[gui] Abriendo Logic Podcast Automation.")
    bridge = AppBridge()
    window = webview.create_window(
        "Logic Podcast Automation",
        url=(ASSETS_ROOT / "index.html").as_uri(),
        width=1100,
        height=760,
        min_size=(820, 620),
        js_api=bridge,
        background_color="#86b8ff",
    )
    bridge.window = window
    webview.start(debug=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
