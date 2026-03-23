from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from .workflow import resolve_logic_project_path


class LogicAutomationError(RuntimeError):
    pass


@dataclass(frozen=True)
class BounceRequest:
    project_path: Path
    output_path: Path
    open_wait_seconds: float = 6.0
    timeout_seconds: int = 900


def open_project_in_logic(project_path: Path, *, wait_seconds: float = 6.0) -> Path:
    project_path = resolve_logic_project_path(project_path)

    command = ["open", "-a", "Logic Pro", str(project_path)]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise LogicAutomationError(result.stderr.strip() or "No se pudo abrir Logic Pro.")

    time.sleep(wait_seconds)
    return project_path


def activate_logic() -> None:
    script = 'tell application "Logic Pro" to activate'
    _run_osascript(script, require_ui=False)


def bounce_project(request: BounceRequest) -> Path:
    output_path = request.output_path.expanduser().resolve()
    if output_path.exists():
        raise FileExistsError(f"El bounce de salida ya existe: {output_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    open_project_in_logic(request.project_path, wait_seconds=request.open_wait_seconds)

    script = _build_bounce_script(output_path)
    _run_osascript(script, require_ui=True)
    _wait_for_file(output_path, timeout_seconds=request.timeout_seconds)
    return output_path


def _build_bounce_script(output_path: Path) -> str:
    directory = _as_applescript_string(output_path.parent.as_posix())
    filename = _as_applescript_string(output_path.name)
    return f'''
tell application "Logic Pro" to activate
delay 1
tell application "System Events"
    tell process "Logic Pro"
        set frontmost to true
        delay 0.5

        set bounceOpened to false
        repeat with fileMenuName in {{"File", "Archivo"}}
            try
                click menu bar item (contents of fileMenuName) of menu bar 1
                delay 0.2

                repeat with bounceMenuName in {{"Bounce", "Rebotar"}}
                    try
                        click menu item (contents of bounceMenuName) of menu 1 of menu bar item (contents of fileMenuName) of menu bar 1
                        delay 0.2

                        repeat with menuItemName in {{"Project or Section…", "Project or Section...", "Project or Section", "Proyecto o seccion…", "Proyecto o seccion...", "Proyecto o sección…", "Proyecto o sección..."}}
                            try
                                click menu item (contents of menuItemName) of menu 1 of menu item (contents of bounceMenuName) of menu 1 of menu bar item (contents of fileMenuName) of menu bar 1
                                set bounceOpened to true
                                exit repeat
                            end try
                        end repeat
                    end try

                    if bounceOpened is true then
                        exit repeat
                    end if
                end repeat
            end try

            if bounceOpened is true then
                exit repeat
            end if
        end repeat

        if bounceOpened is false then
            key code 53
            delay 0.2
            keystroke "b" using {{command down}}
            delay 1.0
            set bounceOpened to true
        end if

        delay 1.0
        key code 36
        delay 1.0

        keystroke "G" using {{command down, shift down}}
        delay 0.5
        keystroke "{directory}"
        key code 36
        delay 0.5
        keystroke "a" using {{command down}}
        delay 0.2
        keystroke "{filename}"
        delay 0.3
        key code 36
        delay 0.8

        try
            key code 36
        end try
    end tell
end tell
'''.strip()


def _run_osascript(script: str, *, require_ui: bool) -> str:
    command = ["osascript", "-e", script]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode == 0:
        return result.stdout.strip()

    message = result.stderr.strip() or "Fallo de AppleScript."
    if require_ui and ("assistive access" in message.lower() or "-1719" in message):
        raise LogicAutomationError(
            "La automatizacion UI no tiene permisos. Activa Accessibility y Automation para la app que ejecute este script y vuelve a probar."
        )
    if require_ui and ("not allowed to send keystrokes" in message.lower() or "(1002)" in message):
        raise LogicAutomationError(
            "macOS esta bloqueando el envio de keystrokes. Activa Accessibility para Terminal y para DAW Podcast Automation.app, y si hace falta Input Monitoring para Terminal. Luego vuelve a abrir la app."
        )
    raise LogicAutomationError(message)


def _wait_for_file(path: Path, *, timeout_seconds: int, poll_interval: float = 1.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    previous_size = -1
    stable_checks = 0

    while time.monotonic() < deadline:
        if path.exists():
            size = path.stat().st_size
            if size > 0 and size == previous_size:
                stable_checks += 1
            else:
                stable_checks = 0
            previous_size = size
            if stable_checks >= 2:
                return
        time.sleep(poll_interval)

    raise TimeoutError(f"Timeout esperando el bounce: {path}")


def _as_applescript_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')
