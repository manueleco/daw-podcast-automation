from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .analyze import AnalyzeTrackError, AnalyzeTrackSummary, analyze_track
from .audio import LoudnessError, LoudnessMeasurement, correct_loudness, measure_loudness
from .essentia_analyze import (
    CompareBackendsSummary,
    EssentiaAnalyzeError,
    EssentiaAnalyzeSummary,
    compare_analysis_backends,
    essentia_analyze_track,
)
from .fs import copy_logic_project
from .logic import (
    BounceRequest,
    LogicAutomationError,
    MarkerCreateRequest,
    bounce_project,
    create_named_marker_at_playhead,
    open_marker_list,
    open_project_in_logic,
)
from .prepare import prepare_voice_tracks
from .profiles import get_profile
from .runtime_logs import (
    append_error_log,
    append_general_log,
    append_path_log,
    create_session_log_path,
    log_exception,
)
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

    logic_marker_list = subparsers.add_parser(
        "logic-marker-list",
        help="Abre el Marker List de un proyecto en Logic Pro.",
    )
    logic_marker_list.add_argument("--source", type=Path, required=True, help="Proyecto de Logic.")
    logic_marker_list.add_argument(
        "--wait-seconds",
        type=float,
        default=6.0,
        help="Tiempo de espera tras abrir Logic.",
    )

    logic_marker_create = subparsers.add_parser(
        "logic-marker-create",
        help="Crea y nombra un marker en la posicion actual del playhead.",
    )
    logic_marker_create.add_argument("--source", type=Path, required=True, help="Proyecto de Logic.")
    logic_marker_create.add_argument("--name", required=True, help="Nombre del marker.")
    logic_marker_create.add_argument(
        "--wait-seconds",
        type=float,
        default=6.0,
        help="Tiempo de espera tras abrir Logic.",
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

    prepare_mix = subparsers.add_parser(
        "prepare-mix",
        help="Clona proyecto y aplica ganancia base a archivos de voz antes del bounce.",
    )
    prepare_mix.add_argument("--source", type=Path, required=True, help="Proyecto fuente de Logic.")
    prepare_mix.add_argument("--profile", default="podcast-stereo", help="Perfil a usar.")
    prepare_mix.add_argument(
        "--output-root",
        type=Path,
        help="Directorio donde vivira la copia de trabajo.",
    )
    prepare_mix.add_argument(
        "--open-in-logic",
        action="store_true",
        help="Abre la copia resultante en Logic Pro al terminar.",
    )

    final_master = subparsers.add_parser(
        "final-master",
        help="Mide y corrige el bounce final para entrega.",
    )
    final_master.add_argument("--input", type=Path, required=True, help="Bounce final de entrada.")
    final_master.add_argument("--output", type=Path, required=True, help="Master final corregido.")
    final_master.add_argument("--profile", default="podcast-stereo", help="Perfil a usar.")
    final_master.add_argument("--dual-mono", action="store_true", help="Trata mono como dual mono.")

    analyze_track_cmd = subparsers.add_parser(
        "analyze-track",
        help="Analiza un audio por ventanas con RMS, short-term loudness y clasificacion por contenido.",
    )
    analyze_track_cmd.add_argument("--input", type=Path, required=True, help="Archivo de audio.")
    analyze_track_cmd.add_argument("--report", type=Path, help="Ruta del JSON de salida.")
    analyze_track_cmd.add_argument("--profile", default="podcast-stereo", help="Perfil a usar.")
    analyze_track_cmd.add_argument(
        "--window-seconds",
        type=float,
        default=0.25,
        help="Tamano de ventana para el analisis.",
    )
    analyze_track_cmd.add_argument(
        "--delta-db",
        type=float,
        default=6.0,
        help="Desviacion en dB sobre la referencia para marcar una ventana.",
    )
    analyze_track_cmd.add_argument(
        "--silence-top-db",
        type=float,
        default=35.0,
        help="Threshold para ignorar silencio de fondo.",
    )
    analyze_track_cmd.add_argument(
        "--min-segment-seconds",
        type=float,
        default=1.0,
        help="Duracion minima para consolidar segmentos y marcadores.",
    )
    analyze_track_cmd.add_argument(
        "--max-gain-db",
        type=float,
        default=6.0,
        help="Limite maximo de ganancia sugerida por segmento.",
    )

    essentia_track_cmd = subparsers.add_parser(
        "essentia-analyze-track",
        help="Analiza un audio con Essentia para RMS, envelope, EBU short-term y QC.",
    )
    essentia_track_cmd.add_argument("--input", type=Path, required=True, help="Archivo de audio.")
    essentia_track_cmd.add_argument("--report", type=Path, help="Ruta del JSON de salida.")
    essentia_track_cmd.add_argument("--profile", default="podcast-stereo", help="Perfil a usar.")
    essentia_track_cmd.add_argument(
        "--window-seconds",
        type=float,
        default=0.25,
        help="Tamano de ventana para el analisis.",
    )
    essentia_track_cmd.add_argument(
        "--delta-db",
        type=float,
        default=6.0,
        help="Desviacion en dB sobre la referencia para marcar una ventana.",
    )
    essentia_track_cmd.add_argument(
        "--silence-top-db",
        type=float,
        default=35.0,
        help="Threshold para ignorar silencio de fondo.",
    )
    essentia_track_cmd.add_argument(
        "--max-gain-db",
        type=float,
        default=6.0,
        help="Limite maximo de ganancia sugerida por ventana.",
    )

    compare_backends_cmd = subparsers.add_parser(
        "compare-analysis-backends",
        help="Compara el backend actual de analisis contra la capa opcional de Essentia.",
    )
    compare_backends_cmd.add_argument("--input", type=Path, required=True, help="Archivo de audio.")
    compare_backends_cmd.add_argument("--profile", default="podcast-stereo", help="Perfil a usar.")
    compare_backends_cmd.add_argument("--current-report", type=Path, help="JSON del backend actual.")
    compare_backends_cmd.add_argument("--essentia-report", type=Path, help="JSON del backend Essentia.")
    compare_backends_cmd.add_argument("--comparison-report", type=Path, help="JSON consolidado de comparacion.")
    compare_backends_cmd.add_argument(
        "--window-seconds",
        type=float,
        default=0.25,
        help="Tamano de ventana para ambos backends.",
    )
    compare_backends_cmd.add_argument(
        "--delta-db",
        type=float,
        default=6.0,
        help="Desviacion en dB sobre la referencia para marcar una ventana.",
    )
    compare_backends_cmd.add_argument(
        "--silence-top-db",
        type=float,
        default=35.0,
        help="Threshold para ignorar silencio de fondo.",
    )
    compare_backends_cmd.add_argument(
        "--min-segment-seconds",
        type=float,
        default=1.0,
        help="Duracion minima para consolidar segmentos del backend actual.",
    )
    compare_backends_cmd.add_argument(
        "--max-gain-db",
        type=float,
        default=6.0,
        help="Limite maximo de ganancia sugerida.",
    )

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
        sample_rate_hz=profile.sample_rate_hz,
        channel_mode=profile.channel_mode,
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


def cmd_logic_marker_list(source: Path, wait_seconds: float) -> int:
    opened = open_marker_list(source, wait_seconds=wait_seconds)
    print(f"opened_marker_list_for: {opened}")
    return 0


def cmd_logic_marker_create(source: Path, name: str, wait_seconds: float) -> int:
    created = create_named_marker_at_playhead(
        MarkerCreateRequest(
            project_path=source,
            name=name,
            open_wait_seconds=wait_seconds,
        )
    )
    print(f"created_marker: {created}")
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
    _emit_stage("prepare-mix", "Clonando proyecto")
    working_copy = copy_logic_project(plan.source_project, plan.working_copy)
    _emit_stage("prepare-mix", "Aplicando ganancia base a voces")
    prepare_summary = prepare_voice_tracks(working_copy, profile)

    bounce_path = working_copy.parent / f"{working_copy.stem}__bounce.{profile.export_format}"
    corrected_path = working_copy.parent / f"{working_copy.stem}__master.{profile.export_format}"

    print(f"prepare_mix_report: {prepare_summary.report_path}")
    print(f"prepare_mix_voice_files: {prepare_summary.voice_files}")
    print(f"prepare_mix_adjusted_files: {prepare_summary.adjusted_files}")

    _emit_stage("plugin-setup", "Pendiente: insercion/configuracion automatica de plugins en Logic aun no implementada")
    _emit_stage("logic-bounce", "Generando bounce en Logic Pro")
    bounce_project(
        BounceRequest(
            project_path=working_copy,
            output_path=bounce_path,
            open_wait_seconds=wait_seconds,
            timeout_seconds=timeout_seconds,
        )
    )

    _emit_stage("final-master", "Midiendo bounce final")
    measurement = measure_loudness(bounce_path, profile, dual_mono=dual_mono)
    _emit_stage("final-master", "Corrigiendo master final")
    correct_loudness(
        input_path=bounce_path,
        output_path=corrected_path,
        profile=profile,
        measurement=measurement,
        dual_mono=dual_mono,
        sample_rate_hz=profile.sample_rate_hz,
        channel_mode=profile.channel_mode,
    )
    final_measurement = measure_loudness(corrected_path, profile, dual_mono=dual_mono)

    print(f"working_copy: {working_copy}")
    print(f"bounce_output: {bounce_path}")
    print(f"corrected_output: {corrected_path}")
    _print_measurement(final_measurement)
    return 0


def cmd_prepare_mix(
    source: Path,
    profile_name: str,
    output_root: Path | None,
    open_in_logic: bool,
) -> int:
    profile = get_profile(profile_name)
    resolved_source = resolve_logic_project_path(source)
    plan = build_run_plan(source_project=resolved_source, profile=profile, output_root=output_root)
    _emit_stage("prepare-mix", "Clonando proyecto")
    working_copy = copy_logic_project(plan.source_project, plan.working_copy)
    _emit_stage("prepare-mix", "Aplicando ganancia base a voces")
    summary = prepare_voice_tracks(working_copy, profile)

    print(f"working_copy: {working_copy}")
    print(f"prepare_mix_report: {summary.report_path}")
    print(f"prepare_mix_analyzed_files: {summary.analyzed_files}")
    print(f"prepare_mix_voice_files: {summary.voice_files}")
    print(f"prepare_mix_adjusted_files: {summary.adjusted_files}")

    if open_in_logic:
        _emit_stage("prepare-mix", "Abriendo copia en Logic Pro")
        open_project_in_logic(working_copy)
        print(f"opened_project: {working_copy}")

    return 0


def cmd_final_master(input_path: Path, output_path: Path, profile_name: str, dual_mono: bool) -> int:
    _emit_stage("final-master", "Midiendo bounce final")
    result = cmd_correct(input_path, output_path, profile_name, dual_mono)
    return result


def cmd_analyze_track(
    input_path: Path,
    report_path: Path | None,
    profile_name: str,
    window_seconds: float,
    delta_db: float,
    silence_top_db: float,
    min_segment_seconds: float,
    max_gain_db: float,
) -> int:
    summary = analyze_track(
        input_path=input_path,
        report_path=report_path,
        profile_name=profile_name,
        window_seconds=window_seconds,
        delta_db=delta_db,
        silence_top_db=silence_top_db,
        min_segment_seconds=min_segment_seconds,
        max_gain_db=max_gain_db,
    )
    _print_analyze_summary(summary)
    return 0


def cmd_essentia_analyze_track(
    input_path: Path,
    report_path: Path | None,
    profile_name: str,
    window_seconds: float,
    delta_db: float,
    silence_top_db: float,
    max_gain_db: float,
) -> int:
    summary = essentia_analyze_track(
        input_path=input_path,
        report_path=report_path,
        profile_name=profile_name,
        window_seconds=window_seconds,
        delta_db=delta_db,
        silence_top_db=silence_top_db,
        max_gain_db=max_gain_db,
    )
    _print_essentia_summary(summary)
    return 0


def cmd_compare_analysis_backends(
    input_path: Path,
    profile_name: str,
    current_report_path: Path | None,
    essentia_report_path: Path | None,
    comparison_report_path: Path | None,
    window_seconds: float,
    delta_db: float,
    silence_top_db: float,
    min_segment_seconds: float,
    max_gain_db: float,
) -> int:
    summary = compare_analysis_backends(
        input_path=input_path,
        comparison_report_path=comparison_report_path,
        current_report_path=current_report_path,
        essentia_report_path=essentia_report_path,
        profile_name=profile_name,
        window_seconds=window_seconds,
        delta_db=delta_db,
        silence_top_db=silence_top_db,
        min_segment_seconds=min_segment_seconds,
        max_gain_db=max_gain_db,
    )
    _print_compare_summary(summary)
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


def _emit_stage(stage_key: str, message: str) -> None:
    print(f"[stage:{stage_key}] {message}", flush=True)


def _print_analyze_summary(summary: AnalyzeTrackSummary) -> None:
    print(f"input_path: {summary.input_path}")
    print(f"sample_rate_hz: {summary.sample_rate_hz}")
    print(f"duration_seconds: {summary.duration_seconds}")
    print(f"integrated_lufs: {summary.integrated_lufs}")
    print(f"true_peak_dbtp: {summary.true_peak_dbtp}")
    print(f"reference_rms_dbfs: {summary.reference_rms_dbfs}")
    print(f"reference_short_term_lufs: {summary.reference_short_term_lufs}")
    print(f"active_window_count: {summary.active_window_count}")
    print(f"problematic_window_count: {summary.problematic_window_count}")
    print(f"speech_segment_count: {summary.speech_segment_count}")
    print(f"music_segment_count: {summary.music_segment_count}")
    print(f"marker_count: {summary.marker_count}")
    print(f"automation_point_count: {summary.automation_point_count}")
    print(f"report_path: {summary.report_path}")


def _print_essentia_summary(summary: EssentiaAnalyzeSummary) -> None:
    print(f"input_path: {summary.input_path}")
    print(f"sample_rate_hz: {summary.sample_rate_hz}")
    print(f"duration_seconds: {summary.duration_seconds}")
    print(f"integrated_lufs: {summary.integrated_lufs}")
    print(f"loudness_range: {summary.loudness_range}")
    print(f"true_peak_dbfs: {summary.true_peak_dbfs}")
    print(f"reference_rms_dbfs: {summary.reference_rms_dbfs}")
    print(f"reference_short_term_lufs: {summary.reference_short_term_lufs}")
    print(f"active_window_count: {summary.active_window_count}")
    print(f"problematic_window_count: {summary.problematic_window_count}")
    print(f"report_path: {summary.report_path}")


def _print_compare_summary(summary: CompareBackendsSummary) -> None:
    print(f"input_path: {summary.input_path}")
    print(f"current_report_path: {summary.current_report_path}")
    print(f"essentia_available: {summary.essentia_available}")
    if summary.essentia_report_path is not None:
        print(f"essentia_report_path: {summary.essentia_report_path}")
    if summary.installation_note:
        print(f"essentia_note: {summary.installation_note}")
    print(f"comparison_report_path: {summary.comparison_report_path}")
    print(f"recommended_role: {summary.recommended_role}")
    print(f"decision: {summary.decision}")


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    session_log_path = create_session_log_path(f"cli-{args.command}")
    append_path_log(session_log_path, f"command={args.command}")
    append_path_log(session_log_path, f"argv={' '.join(sys.argv)}")
    append_general_log(f"[cli] command={args.command} | argv={' '.join(sys.argv)} | session_log={session_log_path}")

    try:
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
        if args.command == "logic-marker-list":
            return cmd_logic_marker_list(args.source, args.wait_seconds)
        if args.command == "logic-marker-create":
            return cmd_logic_marker_create(args.source, args.name, args.wait_seconds)
        if args.command == "run":
            return cmd_run(
                source=args.source,
                profile_name=args.profile,
                output_root=args.output_root,
                wait_seconds=args.wait_seconds,
                timeout_seconds=args.timeout_seconds,
                dual_mono=args.dual_mono,
            )
        if args.command == "prepare-mix":
            return cmd_prepare_mix(args.source, args.profile, args.output_root, args.open_in_logic)
        if args.command == "final-master":
            return cmd_final_master(args.input, args.output, args.profile, args.dual_mono)
        if args.command == "analyze-track":
            return cmd_analyze_track(
                args.input,
                args.report,
                args.profile,
                args.window_seconds,
                args.delta_db,
                args.silence_top_db,
                args.min_segment_seconds,
                args.max_gain_db,
            )
        if args.command == "essentia-analyze-track":
            return cmd_essentia_analyze_track(
                args.input,
                args.report,
                args.profile,
                args.window_seconds,
                args.delta_db,
                args.silence_top_db,
                args.max_gain_db,
            )
        if args.command == "compare-analysis-backends":
            return cmd_compare_analysis_backends(
                args.input,
                args.profile,
                args.current_report,
                args.essentia_report,
                args.comparison_report,
                args.window_seconds,
                args.delta_db,
                args.silence_top_db,
                args.min_segment_seconds,
                args.max_gain_db,
            )
    except (
        AnalyzeTrackError,
        EssentiaAnalyzeError,
        LoudnessError,
        LogicAutomationError,
        FileNotFoundError,
        FileExistsError,
        PermissionError,
        TimeoutError,
        ValueError,
    ) as exc:
        append_path_log(session_log_path, f"error={exc}")
        append_error_log(f"[cli:{args.command}] {exc}")
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except Exception:
        append_path_log(session_log_path, "error=unexpected_exception")
        log_exception(f"cli:{args.command}")
        print("error: Ocurrio un fallo inesperado. Revisa runtime-logs/errors.log.", file=sys.stderr)
        return 1

    parser.error(f"Comando no soportado: {args.command}")
    return 2
