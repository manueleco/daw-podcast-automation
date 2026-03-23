from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from .audio import correct_loudness, measure_loudness, probe_audio_stream
from .profiles import PodcastProfile

AUDIO_FILE_EXTENSIONS = {".wav", ".aif", ".aiff", ".caf"}


@dataclass(frozen=True)
class VoiceTrackAdjustment:
    path: str
    matched_pattern: str | None
    channels: int
    sample_rate_hz: int
    integrated_lufs: float
    true_peak_dbtp: float
    target_lufs: float
    adjusted: bool


@dataclass(frozen=True)
class PrepareMixSummary:
    project_path: Path
    analyzed_files: int
    voice_files: int
    adjusted_files: int
    report_path: Path


def prepare_voice_tracks(
    project_path: Path,
    profile: PodcastProfile,
    *,
    loudness_tolerance_db: float = 1.0,
) -> PrepareMixSummary:
    project_path = project_path.expanduser().resolve()
    audio_files = find_project_audio_files(project_path)
    track_profile = build_voice_track_profile(profile)
    adjustments: list[VoiceTrackAdjustment] = []

    voice_files = 0
    adjusted_files = 0

    for audio_file in audio_files:
        matched_pattern = match_voice_track(audio_file, profile.voice_track_patterns)
        if matched_pattern is None:
            continue

        stream_info = probe_audio_stream(audio_file)
        dual_mono = stream_info.channels == 1
        measurement = measure_loudness(audio_file, track_profile, dual_mono=dual_mono)
        should_adjust = abs(track_profile.integrated_lufs - measurement.integrated_lufs) >= loudness_tolerance_db

        if should_adjust:
            tmp_path = audio_file.with_name(f"{audio_file.stem}.__dpa_tmp__{audio_file.suffix}")
            correct_loudness(
                input_path=audio_file,
                output_path=tmp_path,
                profile=track_profile,
                measurement=measurement,
                dual_mono=dual_mono,
                sample_rate_hz=None,
                channel_mode=None,
            )
            tmp_path.replace(audio_file)
            adjusted_files += 1

        adjustments.append(
            VoiceTrackAdjustment(
                path=str(audio_file),
                matched_pattern=matched_pattern,
                channels=stream_info.channels,
                sample_rate_hz=stream_info.sample_rate_hz,
                integrated_lufs=measurement.integrated_lufs,
                true_peak_dbtp=measurement.true_peak_dbtp,
                target_lufs=track_profile.integrated_lufs,
                adjusted=should_adjust,
            )
        )
        voice_files += 1

    report_path = project_path.parent / f"{project_path.stem}__prepare_mix_report.json"
    report_payload = {
        "project_path": str(project_path),
        "voice_track_target_lufs": track_profile.integrated_lufs,
        "voice_track_true_peak_dbtp": track_profile.true_peak_dbtp,
        "adjustments": [asdict(item) for item in adjustments],
    }
    report_path.write_text(json.dumps(report_payload, indent=2, ensure_ascii=True))

    return PrepareMixSummary(
        project_path=project_path,
        analyzed_files=len(audio_files),
        voice_files=voice_files,
        adjusted_files=adjusted_files,
        report_path=report_path,
    )


def find_project_audio_files(project_path: Path) -> list[Path]:
    return sorted(
        path
        for path in project_path.rglob("*")
        if path.is_file() and path.suffix.lower() in AUDIO_FILE_EXTENSIONS and ".__dpa_tmp__" not in path.name
    )


def match_voice_track(path: Path, patterns: tuple[str, ...]) -> str | None:
    candidate = path.stem.lower()
    for pattern in patterns:
        if pattern.lower() in candidate:
            return pattern
    return None


def build_voice_track_profile(profile: PodcastProfile) -> PodcastProfile:
    return PodcastProfile(
        name=f"{profile.name}-voice-track",
        integrated_lufs=profile.voice_track_target_lufs,
        true_peak_dbtp=profile.voice_track_true_peak_dbtp,
        sample_rate_hz=profile.sample_rate_hz,
        channel_mode=profile.channel_mode,
        export_format=profile.export_format,
        voice_track_target_lufs=profile.voice_track_target_lufs,
        voice_track_true_peak_dbtp=profile.voice_track_true_peak_dbtp,
        voice_track_patterns=profile.voice_track_patterns,
        notes=profile.notes,
    )
