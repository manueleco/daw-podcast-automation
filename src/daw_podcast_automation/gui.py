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


REPO_ROOT = Path(__file__).resolve().parents[2]
ASSETS_ROOT = Path(__file__).resolve().parent / "gui_assets"
DEFAULT_OUTPUT_ROOT = Path.home() / "Music" / "DAW Podcast Automation Exports"


class AppBridge:
    def __init__(self) -> None:
        self.window: webview.Window | None = None
        self.process: subprocess.Popen[str] | None = None
        self.lock = threading.Lock()

    def get_initial_state(self) -> dict[str, object]:
        return {
            "profiles": ["podcast-stereo", "podcast-mono"],
            "default_output_root": str(DEFAULT_OUTPUT_ROOT),
            "repo_root": str(REPO_ROOT),
            "python_path": sys.executable,
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
        profile = str(payload.get("profile", "podcast-stereo")).strip()
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
                raise ValueError("Ya hay un proceso en marcha. Espera a que termine antes de lanzar otro.")

            env = os.environ.copy()
            env["PYTHONPATH"] = str(REPO_ROOT / "src")
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
            },
        )

        assert process.stdout is not None
        for raw_line in process.stdout:
            line = raw_line.rstrip("\n")
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

        self._emit_event(
            "onProcessState",
            {
                "status": "success" if return_code == 0 else "error",
                "process_kind": process_kind,
                "return_code": return_code,
                "message": "Proceso terminado." if return_code == 0 else "Proceso terminado con error.",
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


def main() -> int:
    bridge = AppBridge()
    window = webview.create_window(
        "DAW Podcast Automation",
        url=(ASSETS_ROOT / "index.html").as_uri(),
        width=1180,
        height=780,
        min_size=(1040, 700),
        js_api=bridge,
        background_color="#e8ecef",
    )
    bridge.window = window
    webview.start(debug=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
