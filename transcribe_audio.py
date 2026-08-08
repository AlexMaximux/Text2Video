"""CLI script to transcribe audio into timed script (transcript.txt) and word-level timestamps (words.json).

Usage:
    python transcribe_audio.py --audio Senario.mp3
    python transcribe_audio.py --audio Senario.mp3 --output-transcript transcript.txt --output-words words.json
"""

import argparse
import json
import sys
from pathlib import Path

from modules.project_manager import resolve_project_dir
from modules.transcriber import transcribe_audio, format_segments_as_transcript


def main():
    parser = argparse.ArgumentParser(description="Transcribe audio file using Whisper to generate transcript.txt and words.json")
    parser.add_argument("--audio", type=str, default=None, help="Input audio file path (e.g. voice.mp3)")
    parser.add_argument("--model", type=str, default="base", help="Whisper model size (tiny, base, small, medium, large)")
    parser.add_argument("--output-transcript", type=str, default=None, help="Output transcript text file path")
    parser.add_argument("--output-words", type=str, default=None, help="Output word timestamps JSON file path")
    parser.add_argument("--project", "-p", type=str, default=None, help="Project name or directory inside projects/ workspace")
    args = parser.parse_args()

    proj_dir = resolve_project_dir(args.project)

    if args.audio:
        audio_path = Path(args.audio)
    elif (proj_dir / "voice.mp3").exists():
        audio_path = proj_dir / "voice.mp3"
    elif (proj_dir / "Senario.mp3").exists():
        audio_path = proj_dir / "Senario.mp3"
    else:
        audio_path = Path("Senario.mp3")

    if not audio_path.is_file():
        print(f"[!] Error: Audio file not found at '{audio_path}'")
        sys.exit(1)

    out_transcript = Path(args.output_transcript) if args.output_transcript else (proj_dir / "transcript.txt")
    out_words = Path(args.output_words) if args.output_words else (proj_dir / "words.json")

    print(f"[+] Transcribing '{audio_path}' using Whisper ({args.model} model)...")
    res = transcribe_audio(audio_path, model_size=args.model)

    transcript_text = format_segments_as_transcript(res["segments"])
    out_transcript.write_text(transcript_text, encoding="utf-8")
    out_words.write_text(json.dumps(res["words"], ensure_ascii=False, indent=2), encoding="utf-8")

    # Sync fallback root files for backward compatibility
    try:
        Path("transcript.txt").write_text(transcript_text, encoding="utf-8")
        Path("words.json").write_text(json.dumps(res["words"], ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass

    print(f"[✓] Transcript saved to: {out_transcript.resolve()}")
    print(f"[✓] Word timestamps saved to: {out_words.resolve()}")


if __name__ == "__main__":
    main()
