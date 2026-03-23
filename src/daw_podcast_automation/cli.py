from __future__ import annotations

import argparse
from pathlib import Path

from .audio import LoudnessMeasurement, correct_loudness, measure_loudness
from .fs import copy_logic_project
from .logic import BounceRequest, bounce_project, open_project_in_logic
from .profiles import get_profile
from .workflow import build_run_plan, discover_logic_projects, resolve_logic_project_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="daw-podcast-automation",
        description="Base CLI para automatizar un flujo de podcast alrededor de Logic Pro.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan = subparsers.add_parser("scan", help="Busca proyectos de Logic Pro.")
    scan.add_argument("--root", type=Path, required=True, help="Ruta a escanear.")

    profile = subparsers.add_parser("profile", help="Muestra un perfil disponible.")
    profile.add_argument("--name", required=True, help="Nombre del perfil.")

    plan = subparsers.add_parser("plan", help="Genera un plan de ejecucion para un proyecto.")
    plan.add_argument("--source", type=Path, required=True, help="Proyecto fuente de Logic.")
    plan.add_argument("--profile", default="podcast-stereo", help="Perfil a usar.")
    plan.add_argument(
        "--output-root",
        type=Path,
        help="Directorio donde vivira la copia de trabajo.",
    )

    measure = subparsers.add_parser("measure", help="Mide loudness de un bounce.")
    measure.add_argument("--input", type=Path, required=True, help="Archivo de audio.")
    measure.add_argument("--profile", default="podcast-stereo", help="Perfil a usar.")
    measure.add_argument("--dual-mono", action="store_true", help="Trata mono como dual mono.")

    correct = subparsers.add_parser("correct", help="Corrige loudness de un bounce.")
    correct.add_argument("--input", type=Path, required=True, help="Archivo de entrada.")
    correct.add_argument("--output", type=Path, required=True, help="Archivo corregido.")
    correct.add_argument("--profile", default="podcast-stereo", help="Perfil a usar.")
    correct.add_argument("--dual-mono", action="store_true", help="Trata mono como dual mono.")

    logic_open = subparsers.add_parser("logic-open", help="Abre un proyecto en Logic Pro.")
    logic_open.add_argument("--source", type=Path, required=True, help="Proyecto de Logic.")
    logic_open.add_argument(
        "--wait-seconds",
        type=float,
        default=6.0,
        help="Tiempo de espera tras abrir Logic.",
    )

    logic_bounce = subparsers.add_parser(
        "logic-bounce",
        help="Abre un proyecto en Logic y dispara un bounce automatizado.",
    )
    logic_bounce.add_argument("--source", type=Path, required=True, help="Proyecto de Logic.")
    logic_bounce.add_argument("--output", type=Path, required=True, help="Bounce de salida.")
    logic_bounce.add_argument(
        "--wait-seconds",
        type=float,
        default=6.0,
        help="Tiempo de espera tras abrir Logic.",
    )
    logic_bounce.add_argument(
        "--timeout-seconds",
        type=int,
        default=900,
        help="Timeout para esperar el archivo bounce.",
    )

    run = subparsers.add_parser(
        "run",
        help="Copia proyecto, genera bounce, mide y corrige loudness.",
    )
    run.add_argument("--source", type=Path, required=True, help="Proyecto fuente de Logic.")
    run.add_argument("--profile", default="podcast-stereo", help="Perfil a usar.")
    run.add_argument(
        "--output-root",
        type=Path,
        help="Directorio donde viviran copia, bounce y salida final.",
    )
    run.add_argument(
        "--wait-seconds",
        type=float,
        default=6.0,
        help="Tiempo de espera tras abrir Logic.",
    )
    run.add_argument(
        "--timeout-seconds",
        type=int,
        default=900,
        help="Timeout para esperar el bounce.",
    )
    run.add_argument("--dual-mono", action="store_true", help="Trata mono como dual mono.")

    return parser


def cmd_scan(root: Path) -> int:
    projects = discover_logic_projects(root)
    if not projects:
        print("No se encontraron proyectos de Logic.")
        return 0

    for project in projects:
        print(f"{project.kind:7}  {project.path}")
    return 0


def cmd_profile(name: str) -> int:
    profile = get_profile(name)
    print(f"name: {profile.name}")
    print(f"integrated_lufs: {profile.integrated_lufs}")
    print(f"true_peak_dbtp: {profile.true_peak_dbtp}")
    print(f"sample_rate_hz: {profile.sample_rate_hz}")
    print(f"channel_mode: {profile.channel_mode}")
    print(f"export_format: {profile.export_format}")
    for note in profile.notes:
        print(f"note: {note}")
    return 0


def cmd_plan(source: Path, profile_name: str, output_root: Path | None) -> int:
    profile = get_profile(profile_name)
    plan = build_run_plan(source_project=source, profile=profile, output_root=output_root)

    print(f"source_project: {plan.source_project}")
    print(f"working_copy: {plan.working_copy}")
    print(f"profile_name: {plan.profile_name}")
    print(f"target_integrated_lufs: {plan.target_integrated_lufs}")
    print(f"target_true_peak_dbtp: {plan.target_true_peak_dbtp}")
    print("steps:")
    for index, step in enumerate(plan.steps, start=1):
        print(f"  {index}. {step}")
    return 0


def cmd_measure(input_path: Path, profile_name: str, dual_mono: bool) -> int:
    profile = get_profile(profile_name)
    measurement = measure_loudness(input_path, profile, dual_mono=dual_mono)
    _print_measurement(measurement)
    return 0


def cmd_correct(input_path: Path, output_path: Path, profile_name: str, dual_mono: bool) -> int:
    profile = get_profile(profile_name)
    measurement = measure_loudness(input_path, profile, dual_mono=dual_mono)
    corrected = correct_loudness(
        input_path=input_path,
        output_path=output_path,
        profile=profile,
        measurement=measurement,
        dual_mono=dual_mono,
    )
    final_measurement = measure_loudness(corrected, profile, dual_mono=dual_mono)
    print(f"corrected_output: {corrected}")
    _print_measurement(final_measurement)
    return 0


def cmd_logic_open(source: Path, wait_seconds: float) -> int:
    opened = open_project_in_logic(source, wait_seconds=wait_seconds)
    print(f"opened_project: {opened}")
    return 0


def cmd_logic_bounce(source: Path, output: Path, wait_seconds: float, timeout_seconds: int) -> int:
    bounced = bounce_project(
        BounceRequest(
            project_path=source,
            output_path=output,
            open_wait_seconds=wait_seconds,
            timeout_seconds=timeout_seconds,
        )
    )
    print(f"bounce_output: {bounced}")
    return 0


def cmd_run(
    source: Path,
    profile_name: str,
    output_root: Path | None,
    wait_seconds: float,
    timeout_seconds: int,
    dual_mono: bool,
) -> int:
    profile = get_profile(profile_name)
    resolved_source = resolve_logic_project_path(source)
    plan = build_run_plan(source_project=resolved_source, profile=profile, output_root=output_root)
    working_copy = copy_logic_project(plan.source_project, plan.working_copy)

    bounce_path = working_copy.parent / f"{working_copy.stem}__bounce.{profile.export_format}"
    corrected_path = working_copy.parent / f"{working_copy.stem}__master.{profile.export_format}"

    bounce_project(
        BounceRequest(
            project_path=working_copy,
            output_path=bounce_path,
            open_wait_seconds=wait_seconds,
            timeout_seconds=timeout_seconds,
        )
    )

    measurement = measure_loudness(bounce_path, profile, dual_mono=dual_mono)
    correct_loudness(
        input_path=bounce_path,
        output_path=corrected_path,
        profile=profile,
        measurement=measurement,
        dual_mono=dual_mono,
    )
    final_measurement = measure_loudness(corrected_path, profile, dual_mono=dual_mono)

    print(f"working_copy: {working_copy}")
    print(f"bounce_output: {bounce_path}")
    print(f"corrected_output: {corrected_path}")
    _print_measurement(final_measurement)
    return 0


def _print_measurement(measurement: LoudnessMeasurement) -> None:
    print(f"input_path: {measurement.input_path}")
    print(f"integrated_lufs: {measurement.integrated_lufs}")
    print(f"loudness_range: {measurement.loudness_range}")
    print(f"true_peak_dbtp: {measurement.true_peak_dbtp}")
    print(f"threshold: {measurement.threshold}")
    print(f"target_offset: {measurement.target_offset}")
    if measurement.output_integrated_lufs is not None:
        print(f"predicted_output_lufs: {measurement.output_integrated_lufs}")
    if measurement.output_true_peak_dbtp is not None:
        print(f"predicted_output_true_peak_dbtp: {measurement.output_true_peak_dbtp}")
    if measurement.normalization_type:
        print(f"normalization_type: {measurement.normalization_type}")


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "scan":
        return cmd_scan(args.root)
    if args.command == "profile":
        return cmd_profile(args.name)
    if args.command == "plan":
        return cmd_plan(args.source, args.profile, args.output_root)
    if args.command == "measure":
        return cmd_measure(args.input, args.profile, args.dual_mono)
    if args.command == "correct":
        return cmd_correct(args.input, args.output, args.profile, args.dual_mono)
    if args.command == "logic-open":
        return cmd_logic_open(args.source, args.wait_seconds)
    if args.command == "logic-bounce":
        return cmd_logic_bounce(args.source, args.output, args.wait_seconds, args.timeout_seconds)
    if args.command == "run":
        return cmd_run(
            source=args.source,
            profile_name=args.profile,
            output_root=args.output_root,
            wait_seconds=args.wait_seconds,
            timeout_seconds=args.timeout_seconds,
            dual_mono=args.dual_mono,
        )

    parser.error(f"Comando no soportado: {args.command}")
    return 2
