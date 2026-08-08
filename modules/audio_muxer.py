"""
Audio Muxer Module
Handles validating audio files via ffprobe, measuring audio/video stream durations,
and multiplexing audio streams into video slideshows.

If audio duration (after offset adjustment) is longer than video duration,
freezes the last video frame using FFmpeg's `tpad` filter to match the audio track.
Otherwise, uses fast stream copying (-c:v copy -shortest).
"""
import shutil
import subprocess
from pathlib import Path
from typing import Tuple, Union


def check_ffprobe_installed() -> str:
    """Checks if ffprobe is installed in system PATH."""
    ffprobe_bin = shutil.which("ffprobe")
    if not ffprobe_bin:
        raise EnvironmentError(
            "ffprobe is not installed or not found in system PATH.\n"
            "Please ensure FFmpeg (which includes ffprobe) is installed."
        )
    return ffprobe_bin


def probe_file_duration(file_path: Union[str, Path]) -> float:
    """
    Uses ffprobe to inspect a media file and return its duration in seconds.
    Raises ValueError if the file cannot be probed or is invalid.
    """
    ffprobe_bin = check_ffprobe_installed()
    path = Path(file_path).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Media file not found: '{file_path}'")

    cmd = [
        ffprobe_bin,
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(path)
    ]

    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        out_str = res.stdout.strip()
        if not out_str:
            raise ValueError()
        return float(out_str)
    except Exception as err:
        raise ValueError(f"Invalid media file or unreadable audio/video stream: '{file_path}' ({err})")


def mux_audio(
    video_path: Union[str, Path],
    audio_path: Union[str, Path],
    output_path: Union[str, Path],
    offset: float = 0.0
) -> Tuple[Path, float, float, float, bool, float]:
    """
    Multiplexes audio file into video file.

    - Calculates effective audio duration taking offset into account:
      * offset > 0: effective_audio_dur = audio_duration + offset
      * offset < 0: effective_audio_dur = max(0.0, audio_duration - abs(offset))
      * offset == 0: effective_audio_dur = audio_duration

    - If effective_audio_dur > video_duration:
      Extends the video by freezing the last frame using FFmpeg's `tpad` filter:
      `tpad=stop_mode=clone:stop_duration={extend_by}` with `-c:v libx264`.

    - If video_duration >= effective_audio_dur:
      Uses fast video stream copy (`-c:v copy`) with `-shortest`.

    Returns:
      Tuple of (final_output_path, video_duration, audio_duration, duration_diff, was_extended, extend_by)
    """
    v_path = Path(video_path).resolve()
    a_path = Path(audio_path).resolve()
    out_path = Path(output_path).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # 1. Validate and measure raw durations
    video_duration = probe_file_duration(v_path)
    audio_duration = probe_file_duration(a_path)

    # 2. Calculate effective audio duration based on offset
    if offset > 0:
        effective_audio_dur = audio_duration + offset
    elif offset < 0:
        effective_audio_dur = max(0.0, audio_duration - abs(offset))
    else:
        effective_audio_dur = audio_duration

    duration_diff = abs(video_duration - effective_audio_dur)

    # 3. Build FFmpeg command
    cmd = ["ffmpeg", "-y", "-i", str(v_path)]

    # Always inject offset arguments before audio input file (-i a_path)
    if offset > 0:
        cmd.extend(["-itsoffset", f"{offset:.4f}", "-i", str(a_path)])
    elif offset < 0:
        cmd.extend(["-ss", f"{abs(offset):.4f}", "-i", str(a_path)])
    else:
        cmd.extend(["-i", str(a_path)])

    if effective_audio_dur > video_duration:
        # Video needs to be extended by freezing last frame
        extend_by = effective_audio_dur - video_duration
        was_extended = True
        cmd.extend([
            "-filter_complex", f"[0:v]tpad=stop_mode=clone:stop_duration={extend_by:.4f}[v]",
            "-map", "[v]",
            "-map", "1:a:0",
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "23",
            "-c:a", "aac",
            str(out_path)
        ])
    else:
        # Video is longer or equal to audio: fast stream copy
        extend_by = 0.0
        was_extended = False
        cmd.extend([
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-c:v", "copy",
            "-c:a", "aac",
            "-shortest",
            str(out_path)
        ])

    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg audio muxing failed:\n{result.stderr}")

    return out_path, video_duration, audio_duration, duration_diff, was_extended, extend_by
