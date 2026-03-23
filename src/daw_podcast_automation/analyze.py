from __future__ import annotations

import json
import math
import re
import subprocess
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path

from .audio import LoudnessError, measure_loudness
from .profiles import get_profile


class AnalyzeTrackError(RuntimeError):
    pass


@dataclass(frozen=True)
class AnalysisWindow:
    start_seconds: float
    end_seconds: float
    duration_seconds: float
    active: bool
    classification: str
    classification_confidence: float
    marker_label: str
    rms_dbfs: float
    momentary_lufs: float | None
    short_term_lufs: float | None
    delta_lufs: float | None
    suggested_gain_db: float
    status: str
    spectral_centroid_hz: float
    spectral_bandwidth_hz: float
    spectral_rolloff_hz: float
    spectral_flatness: float
    zero_crossing_rate: float


@dataclass(frozen=True)
class ContentSegment:
    start_seconds: float
    end_seconds: float
    duration_seconds: float
    active: bool
    classification: str
    marker_label: str
    average_rms_dbfs: float
    average_short_term_lufs: float | None
    average_suggested_gain_db: float
    status: str
    window_count: int


@dataclass(frozen=True)
class MarkerDraft:
    start_seconds: float
    end_seconds: float
    label: str
    classification: str
    confidence: float


@dataclass(frozen=True)
class AutomationPointDraft:
    time_seconds: float
    gain_db: float
    role: str
    classification: str
    label: str


@dataclass(frozen=True)
class AnalyzeTrackSummary:
    input_path: Path
    sample_rate_hz: int
    duration_seconds: float
    integrated_lufs: float
    true_peak_dbtp: float
    reference_rms_dbfs: float
    reference_short_term_lufs: float
    active_window_count: int
    problematic_window_count: int
    speech_segment_count: int
    music_segment_count: int
    marker_count: int
    automation_point_count: int
    report_path: Path


@dataclass(frozen=True)
class _Ebur128Point:
    time_seconds: float
    momentary_lufs: float | None
    short_term_lufs: float | None
    integrated_lufs: float | None
    true_peak_dbfs: float | None


def analyze_track(
    input_path: Path,
    *,
    report_path: Path | None = None,
    profile_name: str = "podcast-stereo",
    window_seconds: float = 0.25,
    delta_db: float = 6.0,
    silence_top_db: float = 35.0,
    min_segment_seconds: float = 1.0,
    max_gain_db: float = 6.0,
) -> AnalyzeTrackSummary:
    librosa, np = _load_librosa_stack()

    input_path = input_path.expanduser().resolve()
    if not input_path.exists():
        raise FileNotFoundError(f"No existe el archivo de audio: {input_path}")
    if window_seconds <= 0:
        raise ValueError("`window_seconds` debe ser mayor a 0.")
    if min_segment_seconds <= 0:
        raise ValueError("`min_segment_seconds` debe ser mayor a 0.")

    profile = get_profile(profile_name)
    audio, sample_rate_hz = librosa.load(str(input_path), sr=None, mono=True)
    if audio.size == 0:
        raise AnalyzeTrackError(f"El archivo esta vacio: {input_path}")

    hop_length = max(1, int(sample_rate_hz * window_seconds))
    frame_length = max(hop_length * 2, 2048)

    rms = librosa.feature.rms(y=audio, frame_length=frame_length, hop_length=hop_length)[0]
    zcr = librosa.feature.zero_crossing_rate(
        y=audio,
        frame_length=frame_length,
        hop_length=hop_length,
    )[0]
    centroid = librosa.feature.spectral_centroid(
        y=audio,
        sr=sample_rate_hz,
        n_fft=frame_length,
        hop_length=hop_length,
    )[0]
    bandwidth = librosa.feature.spectral_bandwidth(
        y=audio,
        sr=sample_rate_hz,
        n_fft=frame_length,
        hop_length=hop_length,
    )[0]
    rolloff = librosa.feature.spectral_rolloff(
        y=audio,
        sr=sample_rate_hz,
        n_fft=frame_length,
        hop_length=hop_length,
    )[0]
    flatness = librosa.feature.spectral_flatness(
        y=audio,
        n_fft=frame_length,
        hop_length=hop_length,
    )[0]

    frame_count = min(len(rms), len(zcr), len(centroid), len(bandwidth), len(rolloff), len(flatness))
    if frame_count == 0:
        raise AnalyzeTrackError(f"No se pudieron generar ventanas de analisis para: {input_path}")

    rms = rms[:frame_count]
    zcr = zcr[:frame_count]
    centroid = centroid[:frame_count]
    bandwidth = bandwidth[:frame_count]
    rolloff = rolloff[:frame_count]
    flatness = flatness[:frame_count]

    times = librosa.frames_to_time(range(frame_count), sr=sample_rate_hz, hop_length=hop_length)
    intervals = librosa.effects.split(
        audio,
        top_db=silence_top_db,
        hop_length=hop_length,
        frame_length=frame_length,
    )

    ebur_points = _measure_ebur128_trace(input_path)

    active_flags: list[bool] = []
    provisional_windows: list[dict[str, float | bool | None | str]] = []

    for index, center_time in enumerate(times):
        start_seconds = max(0.0, float(center_time) - (window_seconds / 2.0))
        end_seconds = min(float(len(audio) / sample_rate_hz), start_seconds + window_seconds)
        sample_index = int(center_time * sample_rate_hz)
        active = any(start <= sample_index <= end for start, end in intervals)
        active_flags.append(active)

        rms_dbfs = 20.0 * math.log10(max(float(rms[index]), 1e-12))
        momentary_lufs, short_term_lufs, true_peak_dbfs = _aggregate_ebur_window(
            ebur_points,
            start_seconds=start_seconds,
            end_seconds=end_seconds,
        )
        classification, confidence = _classify_content_window(
            active=active,
            zcr=float(zcr[index]),
            centroid_hz=float(centroid[index]),
            bandwidth_hz=float(bandwidth[index]),
            rolloff_hz=float(rolloff[index]),
            flatness=float(flatness[index]),
        )
        provisional_windows.append(
            {
                "start_seconds": round(start_seconds, 3),
                "end_seconds": round(end_seconds, 3),
                "duration_seconds": round(end_seconds - start_seconds, 3),
                "active": active,
                "classification": classification,
                "classification_confidence": confidence,
                "rms_dbfs": round(rms_dbfs, 3),
                "momentary_lufs": _round_optional(momentary_lufs),
                "short_term_lufs": _round_optional(short_term_lufs),
                "true_peak_dbfs": _round_optional(true_peak_dbfs),
                "spectral_centroid_hz": round(float(centroid[index]), 3),
                "spectral_bandwidth_hz": round(float(bandwidth[index]), 3),
                "spectral_rolloff_hz": round(float(rolloff[index]), 3),
                "spectral_flatness": round(float(flatness[index]), 5),
                "zero_crossing_rate": round(float(zcr[index]), 5),
            }
        )

    smoothed_labels = _smooth_classifications(provisional_windows)
    for record, label in zip(provisional_windows, smoothed_labels):
        record["classification"] = label
        record["marker_label"] = _marker_label(label)

    active_rms_values = [float(record["rms_dbfs"]) for record in provisional_windows if bool(record["active"])]
    reference_rms_dbfs = float(np.median(active_rms_values)) if active_rms_values else float(np.median([float(record["rms_dbfs"]) for record in provisional_windows]))

    all_short_term = _collect_finite_lufs(provisional_windows, active_only=True)
    speech_short_term = _collect_finite_lufs(provisional_windows, active_only=True, classification="speech")
    music_short_term = _collect_finite_lufs(provisional_windows, active_only=True, classification="music")

    reference_short_term_lufs = _median_or_default(np, all_short_term, default=profile.integrated_lufs)
    speech_reference_lufs = _median_or_default(np, speech_short_term, default=reference_short_term_lufs)
    music_reference_lufs = _median_or_default(np, music_short_term, default=reference_short_term_lufs - 1.5)

    windows: list[AnalysisWindow] = []
    for record in provisional_windows:
        classification = str(record["classification"])
        active = bool(record["active"])
        short_term_lufs = _as_optional_float(record["short_term_lufs"])
        if active and classification == "speech" and short_term_lufs is not None:
            raw_gain = speech_reference_lufs - short_term_lufs
        elif active and classification == "music" and short_term_lufs is not None:
            raw_gain = music_reference_lufs - short_term_lufs
        else:
            raw_gain = 0.0

        suggested_gain_db = round(_clamp(raw_gain, -abs(max_gain_db), abs(max_gain_db)), 3)
        delta_lufs = round(raw_gain, 3) if short_term_lufs is not None and active else None

        status = "ok"
        if active and classification in {"speech", "music"} and delta_lufs is not None:
            if delta_lufs >= abs(delta_db):
                status = "too_quiet"
            elif delta_lufs <= -abs(delta_db):
                status = "too_loud"
        elif active and classification == "other":
            status = "review"

        windows.append(
            AnalysisWindow(
                start_seconds=float(record["start_seconds"]),
                end_seconds=float(record["end_seconds"]),
                duration_seconds=float(record["duration_seconds"]),
                active=active,
                classification=classification,
                classification_confidence=float(record["classification_confidence"]),
                marker_label=str(record["marker_label"]),
                rms_dbfs=float(record["rms_dbfs"]),
                momentary_lufs=_as_optional_float(record["momentary_lufs"]),
                short_term_lufs=short_term_lufs,
                delta_lufs=delta_lufs,
                suggested_gain_db=suggested_gain_db,
                status=status,
                spectral_centroid_hz=float(record["spectral_centroid_hz"]),
                spectral_bandwidth_hz=float(record["spectral_bandwidth_hz"]),
                spectral_rolloff_hz=float(record["spectral_rolloff_hz"]),
                spectral_flatness=float(record["spectral_flatness"]),
                zero_crossing_rate=float(record["zero_crossing_rate"]),
            )
        )

    segments = _merge_content_segments(windows)
    filtered_segments = [segment for segment in segments if segment.duration_seconds >= min_segment_seconds]
    markers = _build_markers(filtered_segments)
    automation_points = _build_automation_points(filtered_segments)

    if report_path is None:
        report_path = input_path.with_name(f"{input_path.stem}__analysis.json")
    report_path = report_path.expanduser().resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        measurement = measure_loudness(input_path, profile)
    except LoudnessError as exc:
        raise AnalyzeTrackError(str(exc)) from exc

    report_path.write_text(
        json.dumps(
            {
                "input_path": str(input_path),
                "sample_rate_hz": sample_rate_hz,
                "duration_seconds": round(float(len(audio) / sample_rate_hz), 3),
                "profile_name": profile.name,
                "window_seconds": window_seconds,
                "delta_db": delta_db,
                "silence_top_db": silence_top_db,
                "min_segment_seconds": min_segment_seconds,
                "max_gain_db": max_gain_db,
                "overall_loudness": {
                    "integrated_lufs": measurement.integrated_lufs,
                    "true_peak_dbtp": measurement.true_peak_dbtp,
                    "loudness_range": measurement.loudness_range,
                },
                "references": {
                    "reference_rms_dbfs": round(reference_rms_dbfs, 3),
                    "reference_short_term_lufs": round(reference_short_term_lufs, 3),
                    "speech_reference_short_term_lufs": round(speech_reference_lufs, 3),
                    "music_reference_short_term_lufs": round(music_reference_lufs, 3),
                },
                "classification_notes": {
                    "speech": "Ventanas con rasgos cercanos a dialogo o voz hablada.",
                    "music": "Ventanas con rasgos tonales o espectrales mas musicales.",
                    "other": "Silencio, ruido, mezcla ambigua o material que conviene revisar.",
                },
                "windows": [asdict(item) for item in windows],
                "segments": [asdict(item) for item in filtered_segments],
                "markers": [asdict(item) for item in markers],
                "automation_draft": {
                    "logic_translation_status": "pending_future_work",
                    "volume_points": [asdict(item) for item in automation_points],
                    "strategy": "alinear speech y music por short-term loudness; cerrar loudness final en master",
                },
            },
            indent=2,
            ensure_ascii=True,
        )
    )

    speech_segment_count = sum(1 for item in filtered_segments if item.classification == "speech")
    music_segment_count = sum(1 for item in filtered_segments if item.classification == "music")
    problematic_window_count = sum(1 for item in windows if item.status in {"too_quiet", "too_loud"})

    return AnalyzeTrackSummary(
        input_path=input_path,
        sample_rate_hz=sample_rate_hz,
        duration_seconds=round(float(len(audio) / sample_rate_hz), 3),
        integrated_lufs=measurement.integrated_lufs,
        true_peak_dbtp=measurement.true_peak_dbtp,
        reference_rms_dbfs=round(reference_rms_dbfs, 3),
        reference_short_term_lufs=round(reference_short_term_lufs, 3),
        active_window_count=sum(1 for item in windows if item.active),
        problematic_window_count=problematic_window_count,
        speech_segment_count=speech_segment_count,
        music_segment_count=music_segment_count,
        marker_count=len(markers),
        automation_point_count=len(automation_points),
        report_path=report_path,
    )


def _merge_content_segments(windows: list[AnalysisWindow]) -> list[ContentSegment]:
    if not windows:
        return []

    segments: list[ContentSegment] = []
    bucket: list[AnalysisWindow] = [windows[0]]

    for window in windows[1:]:
        previous = bucket[-1]
        contiguous = abs(window.start_seconds - previous.end_seconds) <= 0.001
        same_class = window.classification == previous.classification
        same_status = window.status == previous.status
        if contiguous and same_class and same_status:
            bucket.append(window)
            continue

        segments.append(_build_segment(bucket))
        bucket = [window]

    segments.append(_build_segment(bucket))
    return segments


def _build_segment(windows: list[AnalysisWindow]) -> ContentSegment:
    first = windows[0]
    last = windows[-1]
    average_short_term = _average_optional([window.short_term_lufs for window in windows])
    average_gain = round(sum(window.suggested_gain_db for window in windows) / len(windows), 3)
    return ContentSegment(
        start_seconds=first.start_seconds,
        end_seconds=last.end_seconds,
        duration_seconds=round(last.end_seconds - first.start_seconds, 3),
        active=all(window.active for window in windows),
        classification=first.classification,
        marker_label=first.marker_label,
        average_rms_dbfs=round(sum(window.rms_dbfs for window in windows) / len(windows), 3),
        average_short_term_lufs=_round_optional(average_short_term),
        average_suggested_gain_db=average_gain,
        status=first.status,
        window_count=len(windows),
    )


def _build_markers(segments: list[ContentSegment]) -> list[MarkerDraft]:
    markers: list[MarkerDraft] = []
    for segment in segments:
        if not segment.active or segment.classification not in {"speech", "music"}:
            continue
        markers.append(
            MarkerDraft(
                start_seconds=segment.start_seconds,
                end_seconds=segment.end_seconds,
                label=segment.marker_label,
                classification=segment.classification,
                confidence=0.75 if segment.classification == "speech" else 0.7,
            )
        )
    return markers


def _build_automation_points(segments: list[ContentSegment]) -> list[AutomationPointDraft]:
    points: list[AutomationPointDraft] = []
    for segment in segments:
        if not segment.active or segment.classification not in {"speech", "music"}:
            continue
        if abs(segment.average_suggested_gain_db) < 1.0:
            continue
        points.append(
            AutomationPointDraft(
                time_seconds=round(segment.start_seconds, 3),
                gain_db=segment.average_suggested_gain_db,
                role="segment_start",
                classification=segment.classification,
                label=segment.marker_label,
            )
        )
        points.append(
            AutomationPointDraft(
                time_seconds=round(segment.end_seconds, 3),
                gain_db=segment.average_suggested_gain_db,
                role="segment_end",
                classification=segment.classification,
                label=segment.marker_label,
            )
        )
    return points


def _aggregate_ebur_window(
    points: list[_Ebur128Point],
    *,
    start_seconds: float,
    end_seconds: float,
) -> tuple[float | None, float | None, float | None]:
    selected = [point for point in points if start_seconds <= point.time_seconds < end_seconds]
    if not selected and points:
        closest = min(points, key=lambda item: abs(item.time_seconds - start_seconds))
        selected = [closest]

    momentary_values = [item.momentary_lufs for item in selected if item.momentary_lufs is not None]
    short_term_values = [item.short_term_lufs for item in selected if item.short_term_lufs is not None]
    true_peak_values = [item.true_peak_dbfs for item in selected if item.true_peak_dbfs is not None]

    momentary = _average_optional(momentary_values)
    short_term = _average_optional(short_term_values)
    if short_term is None:
        short_term = momentary
    true_peak = max(true_peak_values) if true_peak_values else None
    return momentary, short_term, true_peak


def _measure_ebur128_trace(input_path: Path) -> list[_Ebur128Point]:
    command = [
        "ffmpeg",
        "-hide_banner",
        "-nostats",
        "-i",
        str(input_path),
        "-filter_complex",
        "ebur128=peak=true",
        "-f",
        "null",
        "-",
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise AnalyzeTrackError(result.stderr.strip() or "No se pudo generar traza de loudness.")

    pattern = re.compile(
        r"t:\s*(?P<time>-?\d+(?:\.\d+)?)\s+TARGET:.*?"
        r"M:\s*(?P<m>-?\d+(?:\.\d+)?)\s+"
        r"S:\s*(?P<s>-?\d+(?:\.\d+)?)\s+"
        r"I:\s*(?P<i>-?\d+(?:\.\d+)?)\s+LUFS.*?"
        r"TPK:\s*(?P<tpk>-?\d+(?:\.\d+)?)\s+dBFS"
    )

    points: list[_Ebur128Point] = []
    for line in result.stderr.splitlines():
        match = pattern.search(line)
        if not match:
            continue
        points.append(
            _Ebur128Point(
                time_seconds=float(match.group("time")),
                momentary_lufs=_normalize_lufs(match.group("m")),
                short_term_lufs=_normalize_lufs(match.group("s")),
                integrated_lufs=_normalize_lufs(match.group("i")),
                true_peak_dbfs=float(match.group("tpk")),
            )
        )

    if not points:
        raise AnalyzeTrackError("No se pudo parsear la traza ebur128 de ffmpeg.")
    return points


def _classify_content_window(
    *,
    active: bool,
    zcr: float,
    centroid_hz: float,
    bandwidth_hz: float,
    rolloff_hz: float,
    flatness: float,
) -> tuple[str, float]:
    if not active:
        return "other", 0.95

    speech_score = 0
    music_score = 0
    other_score = 0

    if 120.0 <= centroid_hz <= 3800.0:
        speech_score += 1
    if 250.0 <= bandwidth_hz <= 2600.0:
        speech_score += 1
    if 0.02 <= zcr <= 0.18:
        speech_score += 1
    if flatness <= 0.22:
        speech_score += 1
    if rolloff_hz <= 5500.0:
        speech_score += 1

    if centroid_hz >= 650.0:
        music_score += 1
    if bandwidth_hz >= 1300.0:
        music_score += 1
    if rolloff_hz >= 2500.0:
        music_score += 1
    if flatness <= 0.35:
        music_score += 1
    if zcr <= 0.24:
        music_score += 1

    if flatness >= 0.3:
        other_score += 1
    if zcr >= 0.22:
        other_score += 1
    if centroid_hz >= 4200.0 or bandwidth_hz >= 3600.0:
        other_score += 1
    if rolloff_hz >= 7000.0:
        other_score += 1

    scores = {
        "speech": speech_score,
        "music": music_score,
        "other": other_score,
    }
    label = max(scores, key=scores.get)
    ordered_scores = sorted(scores.values(), reverse=True)
    best_score = ordered_scores[0]
    runner_up = ordered_scores[1] if len(ordered_scores) > 1 else 0

    if best_score < 3:
        return "other", 0.45
    if label == "speech" and speech_score < music_score + 1:
        label = "other"
    elif label == "music" and music_score < speech_score + 1:
        label = "other"

    confidence = max(0.45, min(0.95, 0.5 + ((best_score - runner_up) * 0.15)))
    return label, round(confidence, 3)


def _smooth_classifications(records: list[dict[str, float | bool | None | str]]) -> list[str]:
    labels = [str(record["classification"]) for record in records]
    smoothed: list[str] = []
    for index, record in enumerate(records):
        if not bool(record["active"]):
            smoothed.append("other")
            continue

        neighborhood = labels[max(0, index - 1) : min(len(labels), index + 2)]
        counts = Counter(neighborhood)
        winner, winner_count = counts.most_common(1)[0]
        if winner_count >= 2:
            smoothed.append(winner)
        else:
            smoothed.append(labels[index])
    return smoothed


def _collect_finite_lufs(
    records: list[dict[str, float | bool | None | str]],
    *,
    active_only: bool,
    classification: str | None = None,
) -> list[float]:
    values: list[float] = []
    for record in records:
        if active_only and not bool(record["active"]):
            continue
        if classification is not None and str(record["classification"]) != classification:
            continue
        short_term = _as_optional_float(record["short_term_lufs"])
        if short_term is not None:
            values.append(short_term)
    return values


def _marker_label(classification: str) -> str:
    if classification == "speech":
        return "Dialogo"
    if classification == "music":
        return "Musica"
    return "Otro"


def _load_librosa_stack():
    try:
        import librosa  # type: ignore
        import numpy as np  # type: ignore
    except ModuleNotFoundError as exc:
        raise AnalyzeTrackError(
            "Faltan dependencias de analisis. Instala con: python3 -m pip install '.[analysis]'"
        ) from exc
    return librosa, np


def _normalize_lufs(value: str) -> float | None:
    numeric = float(value)
    if numeric <= -99.0:
        return None
    return numeric


def _average_optional(values: list[float | None]) -> float | None:
    finite_values = [float(item) for item in values if item is not None]
    if not finite_values:
        return None
    return sum(finite_values) / len(finite_values)


def _median_or_default(np, values: list[float], *, default: float) -> float:
    if not values:
        return float(default)
    return float(np.median(values))


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def _round_optional(value: float | None) -> float | None:
    if value is None:
        return None
    return round(float(value), 3)


def _as_optional_float(value: object) -> float | None:
    if value is None:
        return None
    return float(value)
