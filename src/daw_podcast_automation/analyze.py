from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path


class AnalyzeTrackError(RuntimeError):
    pass


@dataclass(frozen=True)
class ProblemWindow:
    start_seconds: float
    end_seconds: float
    duration_seconds: float
    rms_dbfs: float
    delta_db: float
    status: str
    active: bool


@dataclass(frozen=True)
class AnalyzeTrackSummary:
    input_path: Path
    sample_rate_hz: int
    duration_seconds: float
    reference_rms_dbfs: float
    active_window_count: int
    problematic_window_count: int
    report_path: Path


def analyze_track(
    input_path: Path,
    *,
    report_path: Path | None = None,
    window_seconds: float = 0.25,
    delta_db: float = 6.0,
    silence_top_db: float = 35.0,
) -> AnalyzeTrackSummary:
    librosa, np = _load_librosa_stack()

    input_path = input_path.expanduser().resolve()
    if not input_path.exists():
        raise FileNotFoundError(f"No existe el archivo de audio: {input_path}")

    audio, sample_rate_hz = librosa.load(str(input_path), sr=None, mono=True)
    if audio.size == 0:
        raise AnalyzeTrackError(f"El archivo esta vacio: {input_path}")

    hop_length = max(1, int(sample_rate_hz * window_seconds))
    frame_length = max(hop_length * 2, 2048)
    rms = librosa.feature.rms(y=audio, frame_length=frame_length, hop_length=hop_length)[0]
    times = librosa.frames_to_time(range(len(rms)), sr=sample_rate_hz, hop_length=hop_length)
    intervals = librosa.effects.split(audio, top_db=silence_top_db, hop_length=hop_length, frame_length=frame_length)

    active_flags = []
    for center_time in times:
        sample_index = int(center_time * sample_rate_hz)
        active = any(start <= sample_index <= end for start, end in intervals)
        active_flags.append(active)

    rms_dbfs = [20.0 * math.log10(max(float(value), 1e-12)) for value in rms]
    active_rms_values = [value for value, active in zip(rms_dbfs, active_flags) if active]
    if not active_rms_values:
        reference_rms_dbfs = float(sum(rms_dbfs) / len(rms_dbfs))
    else:
        reference_rms_dbfs = float(np.median(active_rms_values))

    windows = []
    for index, center_time in enumerate(times):
        start_seconds = max(0.0, float(center_time) - (window_seconds / 2.0))
        end_seconds = start_seconds + window_seconds
        rms_value = float(rms_dbfs[index])
        active = bool(active_flags[index])
        delta_value = rms_value - reference_rms_dbfs
        status = "ok"
        if active and delta_value <= -abs(delta_db):
            status = "too_quiet"
        elif active and delta_value >= abs(delta_db):
            status = "too_loud"

        windows.append(
            ProblemWindow(
                start_seconds=round(start_seconds, 3),
                end_seconds=round(end_seconds, 3),
                duration_seconds=round(window_seconds, 3),
                rms_dbfs=round(rms_value, 3),
                delta_db=round(delta_value, 3),
                status=status,
                active=active,
            )
        )

    merged_windows = _merge_problem_windows(windows)
    if report_path is None:
        report_path = input_path.with_name(f"{input_path.stem}__analysis.json")
    report_path = report_path.expanduser().resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(
            {
                "input_path": str(input_path),
                "sample_rate_hz": sample_rate_hz,
                "duration_seconds": round(float(len(audio) / sample_rate_hz), 3),
                "reference_rms_dbfs": round(reference_rms_dbfs, 3),
                "window_seconds": window_seconds,
                "delta_db": delta_db,
                "silence_top_db": silence_top_db,
                "vad_status": "pending_future_work",
                "problem_windows": [asdict(item) for item in merged_windows],
            },
            indent=2,
            ensure_ascii=True,
        )
    )

    return AnalyzeTrackSummary(
        input_path=input_path,
        sample_rate_hz=sample_rate_hz,
        duration_seconds=round(float(len(audio) / sample_rate_hz), 3),
        reference_rms_dbfs=round(reference_rms_dbfs, 3),
        active_window_count=sum(1 for item in windows if item.active),
        problematic_window_count=len(merged_windows),
        report_path=report_path,
    )


def _merge_problem_windows(windows: list[ProblemWindow]) -> list[ProblemWindow]:
    problem_windows = [window for window in windows if window.status != "ok"]
    if not problem_windows:
        return []

    merged: list[ProblemWindow] = []
    current = problem_windows[0]
    delta_values = [current.delta_db]
    rms_values = [current.rms_dbfs]

    for window in problem_windows[1:]:
        contiguous = abs(window.start_seconds - current.end_seconds) <= 0.001
        same_status = window.status == current.status
        if contiguous and same_status:
            current = ProblemWindow(
                start_seconds=current.start_seconds,
                end_seconds=window.end_seconds,
                duration_seconds=round(window.end_seconds - current.start_seconds, 3),
                rms_dbfs=current.rms_dbfs,
                delta_db=current.delta_db,
                status=current.status,
                active=True,
            )
            delta_values.append(window.delta_db)
            rms_values.append(window.rms_dbfs)
            continue

        merged.append(
            ProblemWindow(
                start_seconds=current.start_seconds,
                end_seconds=current.end_seconds,
                duration_seconds=current.duration_seconds,
                rms_dbfs=round(sum(rms_values) / len(rms_values), 3),
                delta_db=round(sum(delta_values) / len(delta_values), 3),
                status=current.status,
                active=True,
            )
        )
        current = window
        delta_values = [window.delta_db]
        rms_values = [window.rms_dbfs]

    merged.append(
        ProblemWindow(
            start_seconds=current.start_seconds,
            end_seconds=current.end_seconds,
            duration_seconds=current.duration_seconds,
            rms_dbfs=round(sum(rms_values) / len(rms_values), 3),
            delta_db=round(sum(delta_values) / len(delta_values), 3),
            status=current.status,
            active=True,
        )
    )
    return merged


def _load_librosa_stack():
    try:
        import librosa  # type: ignore
        import numpy as np  # type: ignore
    except ModuleNotFoundError as exc:
        raise AnalyzeTrackError(
            "Faltan dependencias de analisis. Instala con: python3 -m pip install '.[analysis]'"
        ) from exc
    return librosa, np
