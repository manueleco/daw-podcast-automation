from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .profiles import PodcastProfile

LOGIC_PROJECT_SUFFIX = ".logicx"


@dataclass(frozen=True)
class LogicProject:
    path: Path
    kind: str

    @property
    def name(self) -> str:
        return self.path.stem


@dataclass(frozen=True)
class RunPlan:
    source_project: Path
    working_copy: Path
    profile_name: str
    target_integrated_lufs: float
    target_true_peak_dbtp: float
    steps: tuple[str, ...]


def resolve_logic_project_path(source: Path) -> Path:
    source = source.expanduser().resolve()

    if not source.exists():
        raise FileNotFoundError(f"No existe la ruta: {source}")

    if source.name.endswith(LOGIC_PROJECT_SUFFIX):
        return source

    if source.is_dir():
        projects = discover_logic_projects(source)
        if not projects:
            raise FileNotFoundError(
                f"No se encontro ningun proyecto de Logic dentro de: {source}"
            )
        if len(projects) > 1:
            options = "\n".join(str(project.path) for project in projects[:10])
            raise ValueError(
                "La carpeta contiene varios proyectos de Logic. "
                "Pasa la ruta exacta del proyecto.\n"
                f"{options}"
            )
        return projects[0].path

    raise ValueError(f"La ruta no parece un proyecto de Logic: {source}")


def discover_logic_projects(root: Path) -> list[LogicProject]:
    root = root.expanduser().resolve()

    if root.name.endswith(LOGIC_PROJECT_SUFFIX):
        kind = "package" if root.is_dir() else "file"
        return [LogicProject(path=root, kind=kind)]

    if not root.exists():
        raise FileNotFoundError(f"No existe la ruta: {root}")

    projects: list[LogicProject] = []
    for current_root, dirnames, filenames in os.walk(root):
        current_path = Path(current_root)

        package_dirs = sorted(name for name in dirnames if name.endswith(LOGIC_PROJECT_SUFFIX))
        for package_name in package_dirs:
            projects.append(
                LogicProject(
                    path=(current_path / package_name).resolve(),
                    kind="package",
                )
            )

        dirnames[:] = [
            name
            for name in dirnames
            if not name.startswith(".") and not name.endswith(LOGIC_PROJECT_SUFFIX)
        ]

        for filename in sorted(filenames):
            if filename.endswith(LOGIC_PROJECT_SUFFIX):
                projects.append(
                    LogicProject(
                        path=(current_path / filename).resolve(),
                        kind="file",
                    )
                )

    return projects


def build_run_plan(
    source_project: Path,
    profile: PodcastProfile,
    output_root: Path | None = None,
) -> RunPlan:
    source_project = resolve_logic_project_path(source_project)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    base_name = source_project.stem
    suffix = source_project.suffix

    if output_root is None:
        output_root = source_project.parent
    else:
        output_root = output_root.expanduser().resolve()

    working_copy = output_root / f"{base_name}__podcast-pass-{timestamp}{suffix}"

    steps = (
        "Crear copia de trabajo del proyecto de Logic.",
        "Abrir la copia en Logic Pro.",
        f"Aplicar perfil {profile.name}.",
        "Hacer bounce temporal para medicion.",
        "Medir Integrated LUFS y True Peak.",
        "Aplicar correccion final de salida.",
        "Exportar master final listo para distribucion.",
    )

    return RunPlan(
        source_project=source_project,
        working_copy=working_copy,
        profile_name=profile.name,
        target_integrated_lufs=profile.integrated_lufs,
        target_true_peak_dbtp=profile.true_peak_dbtp,
        steps=steps,
    )
