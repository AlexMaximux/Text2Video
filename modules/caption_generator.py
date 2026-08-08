"""
Word-Highlighted Subtitles Generator & Burn-In Module
Parses word-level Whisper timestamp JSONs, groups words into multi-line caption blocks,
builds ASS subtitle scripts with active word color highlighting, and burns captions onto video files using FFmpeg.
"""

import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union


def hex_to_ass_color(hex_str: str, include_alpha: bool = False, trailing_amp: bool = True) -> str:
    """
    Converts a hex color code (#RRGGBB or RRGGBB) to ASS color format.
    - For inline tags: &HBBGGRR& (include_alpha=False, trailing_amp=True)
    - For V4+ Styles: &H00BBGGRR (include_alpha=True, trailing_amp=False)
    """
    clean_hex = hex_str.strip().lstrip("#").lstrip("&H")
    if len(clean_hex) == 3:
        clean_hex = "".join(c * 2 for c in clean_hex)

    if len(clean_hex) != 6:
        raise ValueError(f"Invalid hex color string: '{hex_str}'")

    r = clean_hex[0:2]
    g = clean_hex[2:4]
    b = clean_hex[4:6]

    amp = "&" if trailing_amp else ""

    if include_alpha:
        return f"&H00{b}{g}{r}{amp}"
    return f"&H{b}{g}{r}{amp}"


def format_ass_time(seconds: float) -> str:
    """Formats float seconds into ASS timestamp format H:MM:SS.cs (centiseconds)."""
    seconds = max(0.0, float(seconds))
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    cs = int(round((seconds - int(seconds)) * 100))
    if cs >= 100:
        s += 1
        cs = 0
        if s >= 60:
            m += 1
            s = 0
            if m >= 60:
                h += 1
                m = 0
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def load_words_json(path: Union[str, Path]) -> List[Dict]:
    """
    Loads and validates word-level timestamp entries from JSON file.
    Returns list of dicts: [{'word': str, 'start': float, 'end': float}, ...]
    """
    json_path = Path(path).resolve()
    if not json_path.is_file():
        raise FileNotFoundError(f"Words JSON file not found: '{path}'")

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError(f"Invalid words JSON format in '{path}': expected a JSON list.")

    valid_words = []
    for idx, item in enumerate(data):
        if not isinstance(item, dict) or "word" not in item or "start" not in item or "end" not in item:
            continue
        valid_words.append({
            "word": str(item["word"]).strip(),
            "start": float(item["start"]),
            "end": float(item["end"])
        })

    if not valid_words:
        raise ValueError(f"No valid word entries found in '{path}'.")

    return valid_words


def group_words_into_lines(
    words: List[Dict],
    max_words_per_line: int = 5,
    max_chars_per_line: int = 28,
    max_lines_per_group: int = 2,
    silence_threshold: float = 1.0
) -> List[Dict]:
    """
    Groups individual words into multi-line caption chunks based on line length limits,
    word count limits, maximum lines per group, and silence gaps.

    Returns list of word group dicts:
    [
      {
        'words': [word_dict, ...],
        'lines': [[word_dict, ...], [word_dict, ...]],
        'start_time': float,
        'end_time': float
      },
      ...
    ]
    """
    if not words:
        return []

    groups = []
    current_group_lines: List[List[Dict]] = []
    current_line: List[Dict] = []
    current_line_chars = 0

    def finalize_group():
        nonlocal current_group_lines, current_line, current_line_chars
        if current_line:
            current_group_lines.append(current_line)
            current_line = []
            current_line_chars = 0

        if current_group_lines:
            all_group_words = [w for line in current_group_lines for w in line]
            groups.append({
                "words": all_group_words,
                "lines": current_group_lines,
                "start_time": all_group_words[0]["start"],
                "end_time": all_group_words[-1]["end"]
            })
            current_group_lines = []

    for i, w in enumerate(words):
        # Check silence gap before current word
        if i > 0:
            prev_end = words[i - 1]["end"]
            if w["start"] - prev_end >= silence_threshold:
                finalize_group()

        word_len = len(w["word"])
        projected_chars = current_line_chars + (1 if current_line else 0) + word_len

        # Check line capacity limits
        line_full = (
            len(current_line) >= max_words_per_line or
            (current_line and projected_chars > max_chars_per_line)
        )

        if line_full:
            current_group_lines.append(current_line)
            current_line = []
            current_line_chars = 0

            # Check if group is full (max lines per group reached)
            if len(current_group_lines) >= max_lines_per_group:
                groups.append({
                    "words": [w_item for line in current_group_lines for w_item in line],
                    "lines": current_group_lines,
                    "start_time": current_group_lines[0][0]["start"],
                    "end_time": current_group_lines[-1][-1]["end"]
                })
                current_group_lines = []

        current_line.append(w)
        current_line_chars += word_len + (1 if len(current_line) > 1 else 0)

    finalize_group()
    return groups


def build_ass_subtitle(
    word_groups: List[Dict],
    style_config: Optional[Dict] = None,
    video_width: int = 1920,
    video_height: int = 1080
) -> str:
    """
    Builds a complete ASS (Advanced SubStation Alpha) subtitle script with active-word color highlights.

    style_config keys:
      - font_name (str): Font family (default: "Arial Black")
      - font_size (int): Font size in px (default: ~5% of video_height)
      - highlight_color (str): Hex color for active word (default: "#FFD60A")
      - text_color (str): Hex color for inactive text (default: "#FFFFFF")
      - outline_color (str): Hex color for text outline (default: "#000000")
      - position (str): "bottom", "top", or "middle" (default: "bottom")
      - margin_v (int): Vertical margin in px (default: ~8% of video_height)
    """
    config = style_config or {}
    font_name = config.get("font_name", "Arial Black")

    default_font_size = max(16, int(video_height * 0.05))
    font_size = config.get("font_size") or default_font_size

    highlight_hex = config.get("highlight_color", "#FFD60A")
    text_hex = config.get("text_color", "#FFFFFF")
    outline_hex = config.get("outline_color", "#000000")

    ass_highlight = hex_to_ass_color(highlight_hex, include_alpha=False, trailing_amp=True)
    ass_text = hex_to_ass_color(text_hex, include_alpha=False, trailing_amp=True)
    ass_text_style = hex_to_ass_color(text_hex, include_alpha=True, trailing_amp=False)
    ass_outline_style = hex_to_ass_color(outline_hex, include_alpha=True, trailing_amp=False)

    position = str(config.get("position", "bottom")).lower()
    if position == "top":
        alignment = 8
    elif position == "middle":
        alignment = 5
    else:
        alignment = 2  # bottom-center in ASS numpad notation

    default_margin_v = int(video_height * 0.08)
    margin_v = config.get("margin_v") or config.get("margin_bottom") or default_margin_v

    ass_header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {video_width}
PlayResY: {video_height}
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font_name},{font_size},{ass_text_style},&H00000000,{ass_outline_style},&H80000000,1,0,0,0,100,100,0,0,1,3,0,{alignment},20,20,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    event_lines = []

    for group in word_groups:
        group_words = group["words"]
        group_lines = group["lines"]
        n_words = len(group_words)

        for k, current_w in enumerate(group_words):
            start_t = current_w["start"]
            if k < n_words - 1:
                # Next word in group start time (or current end if next word starts later)
                next_start = group_words[k + 1]["start"]
                end_t = min(next_start, current_w["end"] + 0.5) if next_start >= current_w["start"] else current_w["end"]
            else:
                end_t = current_w["end"]

            if end_t <= start_t:
                end_t = start_t + 0.1

            start_str = format_ass_time(start_t)
            end_str = format_ass_time(end_t)

            # Build multi-line text representation for this active word state
            line_strings = []
            for line in group_lines:
                line_words_rendered = []
                for w in line:
                    word_str = w["word"]
                    if w is current_w:
                        # Highlighted active word
                        rendered = f"{{\\c{ass_highlight}}}{word_str}{{\\c{ass_text}}}"
                    else:
                        rendered = word_str
                    line_words_rendered.append(rendered)
                line_strings.append(" ".join(line_words_rendered))

            dialogue_text = "\\N".join(line_strings)
            dialogue_line = f"Dialogue: 0,{start_str},{end_str},Default,,0,0,0,,{dialogue_text}"
            event_lines.append(dialogue_line)

    return ass_header + "\n".join(event_lines) + "\n"


def check_ffmpeg_subtitles_supported() -> None:
    """
    Verifies that FFmpeg is installed and has the 'subtitles' (libass) filter enabled.
    Raises EnvironmentError with installation instructions if missing.
    """
    try:
        res = subprocess.run(["ffmpeg", "-filters"], capture_output=True, text=True)
        has_subtitles = False
        if res.returncode == 0:
            for line in res.stdout.splitlines():
                parts = line.strip().split()
                if len(parts) >= 2 and parts[1] in ("subtitles", "ass"):
                    has_subtitles = True
                    break
        if not has_subtitles:
            raise EnvironmentError(
                "Your installed FFmpeg build does not support subtitle burning (`subtitles`/`ass` filter with `libass` is missing).\n\n"
                "To enable subtitle burning:\n"
                "  - On macOS (Homebrew):\n"
                "      brew unlink ffmpeg\n"
                "      brew tap homebrew-ffmpeg/ffmpeg\n"
                "      brew install homebrew-ffmpeg/ffmpeg/ffmpeg\n"
                "  - On Ubuntu / Linux:\n"
                "      sudo apt update && sudo apt install ffmpeg\n"
            )
    except FileNotFoundError:
        raise EnvironmentError("FFmpeg is not installed or not found in system PATH.")


def burn_captions(
    video_path: Union[str, Path],
    ass_path: Union[str, Path],
    output_path: Union[str, Path]
) -> Path:
    """
    Burns ASS subtitles onto the video file using FFmpeg subtitles filter.
    Re-encodes video stream using libx264 and copies audio stream.
    """
    check_ffmpeg_subtitles_supported()

    in_video = Path(video_path).resolve()
    in_ass = Path(ass_path).resolve()
    out_video = Path(output_path).resolve()

    if not in_video.is_file():
        raise FileNotFoundError(f"Source video not found for caption burn-in: '{video_path}'")
    if not in_ass.is_file():
        raise FileNotFoundError(f"Subtitle ASS file not found for caption burn-in: '{ass_path}'")

    out_video.parent.mkdir(parents=True, exist_ok=True)

    # Format path for FFmpeg filter argument escaping
    escaped_ass = (
        str(in_ass)
        .replace("\\", "/")
        .replace("'", "'\\''")
        .replace(":", "\\:")
        .replace("[", "\\[")
        .replace("]", "\\]")
        .replace(",", "\\,")
    )

    cmd = [
        "ffmpeg",
        "-y",
        "-i", str(in_video),
        "-vf", f"subtitles=filename={escaped_ass}",
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "18",
        "-c:a", "copy",
        str(out_video)
    ]

    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"FFmpeg caption burn-in failed with return code {result.returncode}.\n"
            f"Error log:\n{result.stderr}"
        )

    return out_video


def generate_captioned_video(
    video_path: Union[str, Path],
    words_json_path: Union[str, Path],
    output_path: Union[str, Path],
    style_config: Optional[Dict] = None,
    video_width: int = 1920,
    video_height: int = 1080,
    keep_temp: bool = False
) -> Path:
    """
    Orchestrates word caption loading, ASS script creation, and FFmpeg caption burn-in.
    Manages temporary .ass file lifecycle.
    """
    words = load_words_json(words_json_path)

    max_words = style_config.get("max_words_per_line", 5) if style_config else 5
    word_groups = group_words_into_lines(words, max_words_per_line=max_words)

    ass_content = build_ass_subtitle(
        word_groups=word_groups,
        style_config=style_config,
        video_width=video_width,
        video_height=video_height
    )

    out_path = Path(output_path).resolve()

    if keep_temp:
        ass_file_path = out_path.parent / f"{out_path.stem}_captions.ass"
        with open(ass_file_path, "w", encoding="utf-8") as f:
            f.write(ass_content)
        temp_created = False
    else:
        with tempfile.NamedTemporaryFile(mode="w", prefix="captions_", suffix=".ass", delete=False, encoding="utf-8") as tmp:
            tmp.write(ass_content)
            ass_file_path = Path(tmp.name)
        temp_created = True

    try:
        final_video = burn_captions(
            video_path=video_path,
            ass_path=ass_file_path,
            output_path=out_path
        )
    finally:
        if temp_created and ass_file_path.exists():
            try:
                os.remove(ass_file_path)
            except OSError:
                pass

    return final_video
