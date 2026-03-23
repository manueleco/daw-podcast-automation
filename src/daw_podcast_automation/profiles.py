from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PodcastProfile:
    name: str
    integrated_lufs: float
    true_peak_dbtp: float
    sample_rate_hz: int
    channel_mode: str
    export_format: str
    voice_track_target_lufs: float
    voice_track_true_peak_dbtp: float
    voice_track_patterns: tuple[str, ...]
    notes: tuple[str, ...] = ()


DEFAULT_PROFILES: dict[str, PodcastProfile] = {
    "podcast-stereo": PodcastProfile(
        name="podcast-stereo",
        integrated_lufs=-16.0,
        true_peak_dbtp=-1.0,
        sample_rate_hz=48_000,
        channel_mode="stereo",
        export_format="wav",
        voice_track_target_lufs=-20.0,
        voice_track_true_peak_dbtp=-3.0,
        voice_track_patterns=("voz", "voice", "host", "guest", "isa", "mic"),
        notes=(
            "Perfil base para plataformas de streaming y podcast.",
            "Pensado para voz hablada con musica ligera o stingers.",
        ),
    ),
    "podcast-mono": PodcastProfile(
        name="podcast-mono",
        integrated_lufs=-19.0,
        true_peak_dbtp=-1.0,
        sample_rate_hz=48_000,
        channel_mode="mono",
        export_format="wav",
        voice_track_target_lufs=-20.0,
        voice_track_true_peak_dbtp=-3.0,
        voice_track_patterns=("voz", "voice", "host", "guest", "isa", "mic"),
        notes=(
            "Perfil base para episodios solo voz en mono.",
            "Mantiene margen de pico para codificacion y distribucion.",
        ),
    ),
}


def get_profile(name: str) -> PodcastProfile:
    try:
        return DEFAULT_PROFILES[name]
    except KeyError as exc:
        available = ", ".join(sorted(DEFAULT_PROFILES))
        raise KeyError(f"Perfil desconocido: {name}. Disponibles: {available}") from exc
