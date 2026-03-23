from __future__ import annotations

import shutil
from pathlib import Path

from .workflow import get_logic_project_container, resolve_logic_project_path


def copy_logic_project(source: Path, destination: Path) -> Path:
    source = get_logic_project_container(resolve_logic_project_path(source))
    destination = destination.expanduser().resolve()

    if not source.exists():
        raise FileNotFoundError(f"No existe el proyecto fuente: {source}")
    if destination.exists():
        raise FileExistsError(f"La copia de trabajo ya existe: {destination}")

    destination.parent.mkdir(parents=True, exist_ok=True)

    if source.is_dir():
        shutil.copytree(source, destination)
    else:
        shutil.copy2(source, destination)

    return destination
