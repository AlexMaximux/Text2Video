"""
OpenAI Whisper Transcriber Module
Handles speech-to-text audio transcription, formatting segments into bracketed transcript files,
and extracting word-level timestamps for future word-highlighted subtitles.
"""
import json
from pathlib import Path
from typing import Dict, List, Union


def check_whisper_installed() -> None:
    """Verifies that the 'openai-whisper' package is installed."""
    try:
        import whisper  # noqa: F401
    except ImportError:
        raise ImportError(
            "The 'openai-whisper' package is not installed.\n"
            "Please install it using:\n"
            "  pip install openai-whisper\n"
            "Note: FFmpeg must also be installed on your system."
        )


def format_timestamp(seconds: float) -> str:
    """Formats float seconds into bracketed timestamp [mm:ss] format."""
    total_sec = max(0, int(round(seconds)))
    minutes = total_sec // 60
    secs = total_sec % 60
    return f"[{minutes:02d}:{secs:02d}]"


def format_segments_as_transcript(segments: List[Dict]) -> str:
    """
    Formats Whisper segment dictionaries into line-by-line bracketed transcript string.
    Example:
      [00:00] Welcome to the automated presentation.
      [00:05] In this section we discuss architecture.
    """
    lines = []
    for seg in segments:
        start_t = seg.get("start", 0.0)
        text = seg.get("text", "").strip()
        if text:
            ts_str = format_timestamp(start_t)
            lines.append(f"{ts_str} {text}")

    return "\n".join(lines) + "\n"


def extract_word_timestamps(segments: List[Dict]) -> List[Dict]:
    """
    Extracts individual word-level timestamps from Whisper segment words lists.
    Returns a list of dicts: [{'word': str, 'start': float, 'end': float}, ...]
    """
    words_list = []
    for seg in segments:
        seg_words = seg.get("words", [])
        for w in seg_words:
            word_str = w.get("word", "").strip()
            if word_str:
                words_list.append({
                    "word": word_str,
                    "start": round(w.get("start", 0.0), 3),
                    "end": round(w.get("end", 0.0), 3)
                })
    return words_list


def transcribe_audio(
    audio_path: Union[str, Path],
    model_size: str = "small"
) -> Dict:
    """
    Transcribes audio file using OpenAI Whisper model.

    Parameters:
      - audio_path: Path to raw audio file (mp3, wav, m4a, etc.)
      - model_size: Whisper model size ('tiny', 'base', 'small', 'medium', 'large')

    Returns dict containing:
      - 'segments': list of sentence-level segment dicts
      - 'words': list of word-level timestamp dicts
      - 'text': full transcribed text
    """
    check_whisper_installed()
    import whisper

    path = Path(audio_path).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Audio file not found for transcription: '{audio_path}'")

    model = whisper.load_model(model_size)
    result = model.transcribe(str(path), word_timestamps=True)

    segments = result.get("segments", [])
    words = extract_word_timestamps(segments)

    return {
        "segments": segments,
        "words": words,
        "text": result.get("text", "").strip()
    }


def save_word_timestamps_json(words: List[Dict], output_json_path: Union[str, Path]) -> Path:
    """Saves word-level timestamps list to JSON file."""
    out_p = Path(output_json_path).resolve()
    out_p.parent.mkdir(parents=True, exist_ok=True)
    out_p.write_text(json.dumps(words, indent=2, ensure_ascii=False), encoding='utf-8')
    return out_p
