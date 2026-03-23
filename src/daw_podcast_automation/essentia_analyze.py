from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path


class EssentiaAnalyzeError(RuntimeError):
    pass


@dataclass(frozen=True)
class EssentiaWindow:
    start_seconds: float
    end_seconds: float
    duration_seconds: float
    active: bool
    rms_dbfs: float
    envelope_mean: float
    envelope_peak: float
    envelope_p95: float
    momentary_lufs: float | None
    short_term_lufs: float | None
    delta_lufs: float | None
    suggested_gain_db: float
    status: str


@dataclass(frozen=True)
class EssentiaQcSummary:
    peak_sample_dbfs: float
    true_peak_dbfs: float
    clipped_sample_count: int
    clipped_sample_ratio: float
    dc_offset: float
    effective_duration_seconds: float
    envelope_peak: float
    envelope_mean: float
    envelope_p95: float


@dataclass(frozen=True)
class EssentiaAnalyzeSummary:
    input_path: Path
    sample_rate_hz: int
    duration_seconds: float
    integrated_lufs: float
    loudness_range: float
    true_peak_dbfs: float
    reference_rms_dbfs: float
    reference_short_term_lufs: float
    active_window_count: int
    problematic_window_count: int
    report_path: Path


@dataclass(frozen=True)
class CompareBackendsSummary:
    input_path: Path
    current_report_path: Path
    essentia_report_path: Path | None
    comparison_report_path: Path
    essentia_available: bool
    recommended_role: str
    decision: str
    installation_note: str | None


def essentia_analyze_track(
    input_path: Path,
    *,
    report_path: Path | None = None,
    profile_name: str = "podcast-stereo",
    window_seconds: float = 0.25,
    delta_db: float = 6.0,
    silence_top_db: float = 35.0,
    max_gain_db: float = 6.0,
    envelope_attack_ms: float = 10.0,
    envelope_release_ms: float = 1500.0,
) -> EssentiaAnalyzeSummary:
    essentia_standard, np = _load_essentia_stack()

    from .profiles import get_profile

    input_path = input_path.expanduser().resolve()
    if not input_path.exists():
        raise FileNotFoundError(f"No existe el archivo de audio: {input_path}")
    if window_seconds <= 0:
        raise ValueError("`window_seconds` debe ser mayor a 0.")

    profile = get_profile(profile_name)
    audio_loader = essentia_standard.AudioLoader(filename=str(input_path))
    audio, sample_rate_hz, _, _, _, _ = audio_loader()

    mono_audio, stereo_audio = _normalize_audio_arrays(np, audio)
    if mono_audio.size == 0:
        raise EssentiaAnalyzeError(f"El archivo esta vacio: {input_path}")

    envelope = np.asarray(
        essentia_standard.Envelope(
            sampleRate=float(sample_rate_hz),
            attackTime=envelope_attack_ms,
            releaseTime=envelope_release_ms,
        )(mono_audio),
        dtype=np.float32,
    )

    hop_seconds = min(0.1, max(0.02, window_seconds))
    momentary, short_term, integrated, loudness_range = essentia_standard.LoudnessEBUR128(
        sampleRate=float(sample_rate_hz),
        hopSize=float(hop_seconds),
        startAtZero=True,
    )(stereo_audio)

    momentary = np.asarray(momentary, dtype=np.float32)
    short_term = np.asarray(short_term, dtype=np.float32)
    ebu_times = np.arange(len(short_term), dtype=np.float32) * hop_seconds

    peak_locations, oversampled = essentia_standard.TruePeakDetector(version=4)(mono_audio)
    oversampled = np.asarray(oversampled, dtype=np.float32)
    peak_sample = float(np.max(np.abs(mono_audio))) if mono_audio.size else 0.0
    true_peak = float(np.max(np.abs(oversampled))) if oversampled.size else peak_sample
    effective_duration = float(
        essentia_standard.EffectiveDuration(
            sampleRate=float(sample_rate_hz),
            thresholdRatio=0.4,
        )(envelope)
    )

    sample_count = len(mono_audio)
    duration_seconds = round(sample_count / sample_rate_hz, 3)
    samples_per_window = max(1, int(sample_rate_hz * window_seconds))

    rms_windows: list[float] = []
    active_flags: list[bool] = []
    raw_windows: list[dict[str, float | bool | None | str]] = []

    for start_sample in range(0, sample_count, samples_per_window):
        end_sample = min(sample_count, start_sample + samples_per_window)
        window_audio = mono_audio[start_sample:end_sample]
        if window_audio.size == 0:
            continue

        window_envelope = envelope[start_sample:end_sample]
        start_seconds = start_sample / sample_rate_hz
        end_seconds = end_sample / sample_rate_hz
        rms_value = float(np.sqrt(np.mean(np.square(window_audio))))
        rms_dbfs = _dbfs(rms_value)
        rms_windows.append(rms_dbfs)
        raw_windows.append(
            {
                "start_seconds": round(start_seconds, 3),
                "end_seconds": round(end_seconds, 3),
                "duration_seconds": round(end_seconds - start_seconds, 3),
                "rms_dbfs": round(rms_dbfs, 3),
                "envelope_mean": round(float(np.mean(window_envelope)), 6),
                "envelope_peak": round(float(np.max(window_envelope)), 6),
                "envelope_p95": round(float(np.percentile(window_envelope, 95)), 6),
                "momentary_lufs": _aggregate_lufs(np, momentary, ebu_times, start_seconds, end_seconds),
                "short_term_lufs": _aggregate_lufs(np, short_term, ebu_times, start_seconds, end_seconds),
            }
        )

    if not raw_windows:
        raise EssentiaAnalyzeError(f"No se pudieron generar ventanas para: {input_path}")

    max_rms_dbfs = max(item["rms_dbfs"] for item in raw_windows if isinstance(item["rms_dbfs"], float))
    active_threshold = max_rms_dbfs - abs(silence_top_db)

    active_short_term_values: list[float] = []
    active_rms_values: list[float] = []
    for item in raw_windows:
        active = float(item["rms_dbfs"]) >= active_threshold
        active_flags.append(active)
        item["active"] = active
        if active:
            active_rms_values.append(float(item["rms_dbfs"]))
            if item["short_term_lufs"] is not None:
                active_short_term_values.append(float(item["short_term_lufs"]))

    reference_rms_dbfs = float(np.median(active_rms_values)) if active_rms_values else float(np.median(rms_windows))
    reference_short_term_lufs = (
        float(np.median(active_short_term_values))
        if active_short_term_values
        else float(profile.integrated_lufs)
    )

    windows: list[EssentiaWindow] = []
    for item in raw_windows:
        short_term_lufs = _as_optional_float(item["short_term_lufs"])
        if bool(item["active"]) and short_term_lufs is not None:
            raw_gain = reference_short_term_lufs - short_term_lufs
            delta_lufs = round(raw_gain, 3)
        else:
            raw_gain = 0.0
            delta_lufs = None

        suggested_gain_db = round(_clamp(raw_gain, -abs(max_gain_db), abs(max_gain_db)), 3)

        status = "ok"
        if bool(item["active"]) and delta_lufs is not None:
            if delta_lufs >= abs(delta_db):
                status = "too_quiet"
            elif delta_lufs <= -abs(delta_db):
                status = "too_loud"

        windows.append(
            EssentiaWindow(
                start_seconds=float(item["start_seconds"]),
                end_seconds=float(item["end_seconds"]),
                duration_seconds=float(item["duration_seconds"]),
                active=bool(item["active"]),
                rms_dbfs=float(item["rms_dbfs"]),
                envelope_mean=float(item["envelope_mean"]),
                envelope_peak=float(item["envelope_peak"]),
                envelope_p95=float(item["envelope_p95"]),
                momentary_lufs=_as_optional_float(item["momentary_lufs"]),
                short_term_lufs=short_term_lufs,
                delta_lufs=delta_lufs,
                suggested_gain_db=suggested_gain_db,
                status=status,
            )
        )

    qc = EssentiaQcSummary(
        peak_sample_dbfs=round(_dbfs(peak_sample), 3),
        true_peak_dbfs=round(_dbfs(true_peak), 3),
        clipped_sample_count=int(len(peak_locations)),
        clipped_sample_ratio=round((len(peak_locations) / max(len(oversampled), 1)), 8),
        dc_offset=round(float(np.mean(mono_audio)), 8),
        effective_duration_seconds=round(effective_duration, 3),
        envelope_peak=round(float(np.max(envelope)), 6),
        envelope_mean=round(float(np.mean(envelope)), 6),
        envelope_p95=round(float(np.percentile(envelope, 95)), 6),
    )

    if report_path is None:
        report_path = input_path.with_name(f"{input_path.stem}__essentia_analysis.json")
    report_path = report_path.expanduser().resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(
            {
                "backend": "essentia",
                "input_path": str(input_path),
                "sample_rate_hz": int(sample_rate_hz),
                "duration_seconds": duration_seconds,
                "profile_name": profile.name,
                "window_seconds": window_seconds,
                "delta_db": delta_db,
                "silence_top_db": silence_top_db,
                "max_gain_db": max_gain_db,
                "essentia_notes": {
                    "envelope": "Envelope usa rectificacion y filtro asimetrico de ataque/release.",
                    "ebu_r128": "LoudnessEBUR128 entrega momentary, short-term, integrated y LRA sobre señal stereo.",
                    "qc": "QC incluye true peak, clipping potencial, offset DC y duracion efectiva.",
                },
                "overall_loudness": {
                    "integrated_lufs": round(float(integrated), 3),
                    "loudness_range": round(float(loudness_range), 3),
                },
                "references": {
                    "reference_rms_dbfs": round(reference_rms_dbfs, 3),
                    "reference_short_term_lufs": round(reference_short_term_lufs, 3),
                },
                "qc": asdict(qc),
                "windows": [asdict(item) for item in windows],
            },
            indent=2,
            ensure_ascii=True,
        )
    )

    return EssentiaAnalyzeSummary(
        input_path=input_path,
        sample_rate_hz=int(sample_rate_hz),
        duration_seconds=duration_seconds,
        integrated_lufs=round(float(integrated), 3),
        loudness_range=round(float(loudness_range), 3),
        true_peak_dbfs=round(_dbfs(true_peak), 3),
        reference_rms_dbfs=round(reference_rms_dbfs, 3),
        reference_short_term_lufs=round(reference_short_term_lufs, 3),
        active_window_count=sum(1 for item in windows if item.active),
        problematic_window_count=sum(1 for item in windows if item.status in {"too_quiet", "too_loud"}),
        report_path=report_path,
    )


def compare_analysis_backends(
    input_path: Path,
    *,
    comparison_report_path: Path | None = None,
    current_report_path: Path | None = None,
    essentia_report_path: Path | None = None,
    profile_name: str = "podcast-stereo",
    window_seconds: float = 0.25,
    delta_db: float = 6.0,
    silence_top_db: float = 35.0,
    min_segment_seconds: float = 1.0,
    max_gain_db: float = 6.0,
) -> CompareBackendsSummary:
    from .analyze import analyze_track

    input_path = input_path.expanduser().resolve()
    if comparison_report_path is not None:
        comparison_report_path = comparison_report_path.expanduser().resolve()
        if current_report_path is None:
            current_report_path = comparison_report_path.with_name(
                f"{comparison_report_path.stem}__current.json"
            )
        if essentia_report_path is None:
            essentia_report_path = comparison_report_path.with_name(
                f"{comparison_report_path.stem}__essentia.json"
            )

    current_summary = analyze_track(
        input_path=input_path,
        report_path=current_report_path,
        profile_name=profile_name,
        window_seconds=window_seconds,
        delta_db=delta_db,
        silence_top_db=silence_top_db,
        min_segment_seconds=min_segment_seconds,
        max_gain_db=max_gain_db,
    )
    essentia_summary: EssentiaAnalyzeSummary | None = None
    essentia_error: str | None = None
    try:
        essentia_summary = essentia_analyze_track(
            input_path=input_path,
            report_path=essentia_report_path,
            profile_name=profile_name,
            window_seconds=window_seconds,
            delta_db=delta_db,
            silence_top_db=silence_top_db,
            max_gain_db=max_gain_db,
        )
    except EssentiaAnalyzeError as exc:
        essentia_error = str(exc)

    if comparison_report_path is None:
        comparison_report_path = input_path.with_name(f"{input_path.stem}__analysis_compare.json")
    comparison_report_path = comparison_report_path.expanduser().resolve()
    comparison_report_path.parent.mkdir(parents=True, exist_ok=True)

    if essentia_summary is None:
        recommendation = {
            "recommended_role": "secondary_backend",
            "decision": "keep_librosa_as_primary_until_manual_essentia_setup",
            "reasons": [
                "El backend actual ya cubre clasificacion, segmentos, marcadores y automation draft.",
                "Essentia fallo como dependencia nativa en este Mac, asi que no conviene volverlo ruta critica.",
                "Si luego queda estable por instalacion manual, puede sumar envelope, QC y otra lectura EBU short-term.",
            ],
        }
        comparison = None
        essentia_backend = {
            "status": "unavailable",
            "error": essentia_error,
        }
    else:
        recommendation = {
            "recommended_role": "secondary_backend",
            "decision": "keep_librosa_as_primary_for_now",
            "reasons": [
                "El backend actual ya cubre clasificacion, segmentos, marcadores y automation draft.",
                "Essentia aporta envelope y QC utiles, y una via alternativa para EBU short-term.",
                "Hasta validar Essentia en tus audios reales y en macOS, conviene mantenerlo opcional.",
            ],
        }
        comparison = {
            "reference_rms_dbfs_delta": round(
                essentia_summary.reference_rms_dbfs - current_summary.reference_rms_dbfs,
                3,
            ),
            "reference_short_term_lufs_delta": round(
                essentia_summary.reference_short_term_lufs - current_summary.reference_short_term_lufs,
                3,
            ),
            "integrated_lufs_delta": round(
                essentia_summary.integrated_lufs - current_summary.integrated_lufs,
                3,
            ),
            "problematic_window_count_delta": (
                essentia_summary.problematic_window_count - current_summary.problematic_window_count
            ),
        }
        essentia_backend = {
            "status": "available",
            "integrated_lufs": essentia_summary.integrated_lufs,
            "true_peak_dbfs": essentia_summary.true_peak_dbfs,
            "reference_rms_dbfs": essentia_summary.reference_rms_dbfs,
            "reference_short_term_lufs": essentia_summary.reference_short_term_lufs,
            "problematic_window_count": essentia_summary.problematic_window_count,
            "report_path": str(essentia_summary.report_path),
        }

    comparison_report_path.write_text(
        json.dumps(
            {
                "input_path": str(input_path),
                "profile_name": profile_name,
                "analysis_scope": {
                    "window_seconds": window_seconds,
                    "delta_db": delta_db,
                    "silence_top_db": silence_top_db,
                    "min_segment_seconds": min_segment_seconds,
                    "max_gain_db": max_gain_db,
                },
                "current_report_path": str(current_summary.report_path),
                "essentia_report_path": str(essentia_summary.report_path) if essentia_summary is not None else None,
                "essentia_available": essentia_summary is not None,
                "essentia_installation_note": essentia_error,
                "comparison": comparison,
                "current_backend": {
                    "backend_name": "librosa_ffmpeg",
                    "integrated_lufs": current_summary.integrated_lufs,
                    "true_peak_dbtp": current_summary.true_peak_dbtp,
                    "reference_rms_dbfs": current_summary.reference_rms_dbfs,
                    "reference_short_term_lufs": current_summary.reference_short_term_lufs,
                    "problematic_window_count": current_summary.problematic_window_count,
                    "marker_count": current_summary.marker_count,
                    "automation_point_count": current_summary.automation_point_count,
                    "report_path": str(current_summary.report_path),
                },
                "essentia_backend": essentia_backend,
                "recommendation": recommendation,
            },
            indent=2,
            ensure_ascii=True,
        )
    )

    return CompareBackendsSummary(
        input_path=input_path,
        current_report_path=current_summary.report_path,
        essentia_report_path=essentia_summary.report_path if essentia_summary is not None else None,
        comparison_report_path=comparison_report_path,
        essentia_available=essentia_summary is not None,
        recommended_role=recommendation["recommended_role"],
        decision=recommendation["decision"],
        installation_note=essentia_error,
    )


def _load_essentia_stack():
    try:
        import essentia.standard as essentia_standard  # type: ignore
        import numpy as np  # type: ignore
    except ModuleNotFoundError as exc:
        raise EssentiaAnalyzeError(
            "Essentia no esta disponible en este entorno. En macOS suele requerir instalacion manual. Referencia oficial: https://essentia.upf.edu/installing.html"
        ) from exc
    return essentia_standard, np


def _normalize_audio_arrays(np, audio):
    array = np.asarray(audio, dtype=np.float32)
    if array.ndim == 1:
        mono = array
        stereo = np.stack((array, array), axis=1)
        return mono, stereo

    if array.ndim != 2:
        raise EssentiaAnalyzeError(f"Formato de audio inesperado desde Essentia: shape={array.shape}")

    if array.shape[1] == 2:
        stereo = array
    elif array.shape[0] == 2:
        stereo = array.T
    elif array.shape[1] == 1:
        stereo = np.repeat(array, 2, axis=1)
    elif array.shape[0] == 1:
        stereo = np.repeat(array.T, 2, axis=1)
    else:
        raise EssentiaAnalyzeError(f"No se pudo normalizar el audio stereo: shape={array.shape}")

    mono = stereo.mean(axis=1)
    return mono.astype(np.float32), stereo.astype(np.float32)


def _aggregate_lufs(np, values, times, start_seconds: float, end_seconds: float) -> float | None:
    if values.size == 0:
        return None
    mask = (times >= start_seconds) & (times < end_seconds)
    selected = values[mask]
    finite = selected[np.isfinite(selected)]
    finite = finite[finite > -99.0]
    if finite.size == 0:
        nearest_index = int(np.argmin(np.abs(times - start_seconds)))
        candidate = float(values[nearest_index])
        if not math.isfinite(candidate) or candidate <= -99.0:
            return None
        return round(candidate, 3)
    return round(float(np.mean(finite)), 3)


def _dbfs(value: float) -> float:
    return 20.0 * math.log10(max(abs(value), 1e-12))


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def _as_optional_float(value: object) -> float | None:
    if value is None:
        return None
    return float(value)
