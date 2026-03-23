from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .profiles import PodcastProfile


class LoudnessError(RuntimeError):
    pass


@dataclass(frozen=True)
class LoudnessMeasurement:
    input_path: Path
    integrated_lufs: float
    loudness_range: float
    true_peak_dbtp: float
    threshold: float
    target_offset: float
    output_integrated_lufs: float | None = None
    output_true_peak_dbtp: float | None = None
    normalization_type: str | None = None


def measure_loudness(
    input_path: Path,
    profile: PodcastProfile,
    *,
    loudness_range_target: float = 11.0,
    dual_mono: bool = False,
) -> LoudnessMeasurement:
    input_path = input_path.expanduser().resolve()
    if not input_path.exists():
        raise FileNotFoundError(f"No existe el archivo de audio: {input_path}")

    filter_expr = (
        f"loudnorm=I={profile.integrated_lufs}:"
        f"LRA={loudness_range_target}:"
        f"TP={profile.true_peak_dbtp}:"
        f"dual_mono={'true' if dual_mono else 'false'}:"
        "print_format=json"
    )

    command = [
        "ffmpeg",
        "-hide_banner",
        "-i",
        str(input_path),
        "-af",
        filter_expr,
        "-f",
        "null",
        "-",
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise LoudnessError(result.stderr.strip() or "No se pudo medir loudness con ffmpeg.")

    payload = _extract_json_payload(result.stderr)
    return LoudnessMeasurement(
        input_path=input_path,
        integrated_lufs=float(payload["input_i"]),
        loudness_range=float(payload["input_lra"]),
        true_peak_dbtp=float(payload["input_tp"]),
        threshold=float(payload["input_thresh"]),
        target_offset=float(payload["target_offset"]),
        output_integrated_lufs=float(payload["output_i"]),
        output_true_peak_dbtp=float(payload["output_tp"]),
        normalization_type=payload.get("normalization_type"),
    )


def correct_loudness(
    input_path: Path,
    output_path: Path,
    profile: PodcastProfile,
    measurement: LoudnessMeasurement,
    *,
    loudness_range_target: float = 11.0,
    dual_mono: bool = False,
) -> Path:
    input_path = input_path.expanduser().resolve()
    output_path = output_path.expanduser().resolve()

    if not input_path.exists():
        raise FileNotFoundError(f"No existe el archivo de audio: {input_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    filter_expr = (
        f"loudnorm=I={profile.integrated_lufs}:"
        f"LRA={loudness_range_target}:"
        f"TP={profile.true_peak_dbtp}:"
        f"measured_I={measurement.integrated_lufs}:"
        f"measured_LRA={measurement.loudness_range}:"
        f"measured_TP={measurement.true_peak_dbtp}:"
        f"measured_thresh={measurement.threshold}:"
        f"offset={measurement.target_offset}:"
        f"dual_mono={'true' if dual_mono else 'false'}:"
        "linear=true:print_format=summary"
    )

    command = [
        "ffmpeg",
        "-hide_banner",
        "-y",
        "-i",
        str(input_path),
        "-af",
        filter_expr,
        "-ar",
        str(profile.sample_rate_hz),
        "-ac",
        "1" if profile.channel_mode == "mono" else "2",
    ]

    if output_path.suffix.lower() == ".wav":
        command.extend(["-c:a", "pcm_s24le"])

    command.append(str(output_path))

    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise LoudnessError(result.stderr.strip() or "No se pudo corregir loudness con ffmpeg.")

    return output_path


def _extract_json_payload(stderr: str) -> dict[str, str]:
    start = stderr.rfind("{")
    end = stderr.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise LoudnessError("ffmpeg no devolvio un bloque JSON de loudnorm.")

    try:
        payload = json.loads(stderr[start : end + 1])
    except json.JSONDecodeError as exc:
        raise LoudnessError("No se pudo parsear la salida JSON de loudnorm.") from exc

    return payload
