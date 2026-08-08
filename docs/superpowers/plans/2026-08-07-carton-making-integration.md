# Carton-Making Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Port full audio-to-video, Whisper transcription, word-level subtitle generation (with customizable fonts, colors, size, background, position), and FFmpeg video rendering pipeline from `Video making by pic` into `Text2Video`.

**Architecture:** Create `modules/` package in `Text2Video` containing `transcriber.py`, `transcript_parser.py`, `timing_calculator.py`, `caption_generator.py`, `ffmpeg_engine.py`, `audio_muxer.py`, and `pipeline.py`. Provide standalone CLI tools `transcribe_audio.py` and `make_final_video.py`, as well as master end-to-end `pipeline.py`.

**Tech Stack:** Python 3.13, `openai-whisper` / `whisper-timestamped`, `ffmpeg`, `pathlib`, `json`, `subprocess`

## Global Constraints
- Keep existing `claude_prompt.py`, `elevenlabs_prompt.py`, and `batch_generate_millo.py` intact.
- All CLI scripts must support `--help` and clean error handling.
- Subtitle generator must support custom font family, font size, text color, highlight color, outline color, background color, and alignment.

---

### Task 1: Copy and Adapt Core Modules into `Text2Video/modules/`

**Files:**
- Create: `modules/__init__.py`
- Create: `modules/transcriber.py`
- Create: `modules/transcript_parser.py`
- Create: `modules/timing_calculator.py`
- Create: `modules/caption_generator.py`
- Create: `modules/ffmpeg_engine.py`
- Create: `modules/audio_muxer.py`
- Create: `modules/pipeline.py`

**Interfaces:**
- Consumes: Audio MP3, images directory, word timestamps JSON
- Produces: `transcribe_audio_file(audio_path) -> (transcript_str, words_list)`, `build_ass_subtitle(words_list, style_config) -> ass_content_str`, `generate_slideshow_with_captions(...) -> output_mp4`

- [ ] **Step 1: Copy module files from `/Users/nersibayat/Desktop/Programing/github/Video making by pic/modules` to `Text2Video/modules/`**

Copy all python files from `/Users/nersibayat/Desktop/Programing/github/Video making by pic/modules` into `/Users/nersibayat/Desktop/Programing/New - Claude 2026/Browser2API/Text2Video/modules/`.

- [ ] **Step 2: Verify modules import cleanly**

Run:
```bash
python -c "import modules.transcriber, modules.caption_generator, modules.ffmpeg_engine, modules.timing_calculator; print('Modules imported successfully!')"
```
Expected: `Modules imported successfully!`

---

### Task 2: Create `transcribe_audio.py` CLI Tool

**Files:**
- Create: `transcribe_audio.py`

**Interfaces:**
- Consumes: Audio MP3 path
- Produces: `transcript.txt` and `words.json`

- [ ] **Step 1: Write `transcribe_audio.py` CLI script**

```python
"""CLI script to transcribe audio into timed script (transcript.txt) and word-level timestamps (words.json).

Usage:
    python transcribe_audio.py --audio Senario.mp3
    python transcribe_audio.py --audio Senario.mp3 --output-transcript transcript.txt --output-words words.json
"""

import argparse
import sys
from pathlib import Path

from modules.transcriber import transcribe_audio_file


def main():
    parser = argparse.ArgumentParser(description="Transcribe audio file using Whisper to generate transcript.txt and words.json")
    parser.add_argument("--audio", type=str, required=True, help="Input audio file path (e.g. Senario.mp3)")
    parser.add_argument("--model", type=str, default="base", help="Whisper model size (tiny, base, small, medium, large)")
    parser.add_argument("--output-transcript", type=str, default="transcript.txt", help="Output transcript text file path")
    parser.add_argument("--output-words", type=str, default="words.json", help="Output word timestamps JSON file path")
    args = parser.parse_args()

    audio_path = Path(args.audio)
    if not audio_path.is_file():
        print(f"[!] Error: Audio file not found at '{audio_path}'")
        sys.exit(1)

    print(f"[+] Transcribing '{audio_path}' using Whisper ({args.model} model)...")
    res = transcribe_audio_file(audio_path, model_name=args.model)

    out_transcript = Path(args.output_transcript)
    out_words = Path(args.output_words)

    out_transcript.write_text(res["transcript_text"], encoding="utf-8")
    import json
    out_words.write_text(json.dumps(res["words"], ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[✓] Transcript saved to: {out_transcript.resolve()}")
    print(f"[✓] Word timestamps saved to: {out_words.resolve()}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Test `transcribe_audio.py --help`**

Run:
```bash
python transcribe_audio.py --help
```
Expected: Displays CLI help options cleanly.

---

### Task 3: Create `make_final_video.py` CLI Tool with Full Subtitle Customization

**Files:**
- Create: `make_final_video.py`

**Interfaces:**
- Consumes: `--images-dir`, `--audio`, `--transcript`, `--words`, subtitle styling flags (`--font-name`, `--font-size`, `--text-color`, `--highlight-color`, `--outline-color`, `--bg-color`, `--position`)
- Produces: Final synchronized MP4 video with burned ASS captions.

- [ ] **Step 1: Write `make_final_video.py` CLI script**

```python
"""CLI script to build final slideshow video with audio and customizable word-highlighted captions.

Usage:
    python make_final_video.py --images-dir images --audio Senario.mp3 --words words.json --add-captions --output final.mp4
    python make_final_video.py --images-dir images --audio Senario.mp3 --words words.json --add-captions --font-name "Impact" --font-size 48 --highlight-color "#FFD60A" --text-color "#FFFFFF" --output final.mp4
"""

import argparse
import sys
from pathlib import Path

from modules.pipeline import run_video_pipeline


def main():
    parser = argparse.ArgumentParser(description="Assemble images, audio, and subtitle captions into a final MP4 video")
    parser.add_argument("--images-dir", type=str, required=True, help="Directory containing generated images (1.png, 2.png, ...)")
    parser.add_argument("--audio", type=str, required=True, help="Audio file path (Senario.mp3)")
    parser.add_argument("--transcript", type=str, default="transcript.txt", help="Timed transcript file path")
    parser.add_argument("--words", type=str, default="words.json", help="Word-level timestamps JSON file path")
    parser.add_argument("--output", type=str, default="final_video.mp4", help="Output MP4 video file path")
    parser.add_argument("--add-captions", action="store_true", help="Burn word-highlighted subtitles onto the video")
    
    # Subtitle Customization Flags
    parser.add_argument("--font-name", type=str, default="Arial Black", help="Subtitle font family (e.g., 'Arial Black', 'Impact', 'Montserrat')")
    parser.add_argument("--font-size", type=int, default=None, help="Subtitle font size in px")
    parser.add_argument("--text-color", type=str, default="#FFFFFF", help="Default text color hex (e.g. #FFFFFF)")
    parser.add_argument("--highlight-color", type=str, default="#FFD60A", help="Highlighted active word color hex (e.g. #FFD60A)")
    parser.add_argument("--outline-color", type=str, default="#000000", help="Text outline color hex (e.g. #000000)")
    parser.add_argument("--bg-color", type=str, default=None, help="Text background box color hex if needed")
    parser.add_argument("--position", type=str, choices=["bottom", "middle", "top"], default="bottom", help="Subtitle position")

    args = parser.parse_args()

    style_config = {
        "font_name": args.font_name,
        "font_size": args.font_size,
        "text_color": args.text_color,
        "highlight_color": args.highlight_color,
        "outline_color": args.outline_color,
        "bg_color": args.bg_color,
        "position": args.position,
    }

    print(f"[+] Assembling final video '{args.output}' from images '{args.images_dir}' and audio '{args.audio}'...")
    res = run_video_pipeline(
        images_dir=args.images_dir,
        audio_file=args.audio,
        transcript_file=args.transcript,
        words_json=args.words if args.add_captions else None,
        output_file=args.output,
        add_captions=args.add_captions,
        style_config=style_config,
    )

    print(f"[✓] SUCCESS! Final video generated at: {Path(args.output).resolve()}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Test `make_final_video.py --help`**

Run:
```bash
python make_final_video.py --help
```
Expected: Displays all options including font, color, background, and position flags cleanly.

---

### Task 4: Create Master Pipeline Runner `pipeline.py` and Update Documentation

**Files:**
- Create: `pipeline.py`
- Modify: `myOwnreadme.mt`
- Modify: `requirements.txt`

- [ ] **Step 1: Create master end-to-end `pipeline.py`**

```python
"""Master End-to-End Pipeline script for Text2Video.

Usage:
    python pipeline.py --profile "Profile 1" --voice 2styzLg7OSeuhPP6uQ26 --add-captions --output final_video.mp4
"""

import argparse
import asyncio
import subprocess
import sys
from pathlib import Path


def run_cmd(cmd: str):
    print(f"\n[>>> EXEC] {cmd}")
    res = subprocess.run(cmd, shell=True)
    if res.returncode != 0:
        print(f"[!] Step failed with return code {res.returncode}")
        sys.exit(res.returncode)


def main():
    parser = argparse.ArgumentParser(description="Master End-to-End Text2Video Pipeline")
    parser.add_argument("--profile", type=str, default="Profile 1", help="Chrome profile for automation")
    parser.add_argument("--voice", type=str, default="2styzLg7OSeuhPP6uQ26", help="ElevenLabs Voice ID")
    parser.add_argument("--add-captions", action="store_true", help="Burn captions into final video")
    parser.add_argument("--output", type=str, default="final_video.mp4", help="Final output video path")
    args = parser.parse_args()

    # Step 1: Script generation via Claude
    run_cmd(f'python claude_prompt.py --profile "{args.profile}" --auto-followup')

    # Step 2: Voiceover generation via ElevenLabs
    run_cmd(f'python elevenlabs_prompt.py --profile "{args.profile}" --voice {args.voice} --input senario.txt --output Senario.mp3')

    # Step 3: Transcription & Word Timestamps
    run_cmd('python transcribe_audio.py --audio Senario.mp3 --output-transcript transcript.txt --output-words words.json')

    # Step 4: Video assembly
    captions_flag = "--add-captions" if args.add_captions else ""
    run_cmd(f'python make_final_video.py --images-dir output --audio Senario.mp3 --transcript transcript.txt --words words.json {captions_flag} --output {args.output}')

    print(f"\n[🎉 SUCCESS] End-to-End pipeline complete! Output video: {Path(args.output).resolve()}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Update `myOwnreadme.mt` with all pipeline commands**

Add the full step-by-step and master pipeline commands to `myOwnreadme.mt`.

- [ ] **Step 3: Update `requirements.txt`**

Add `openai-whisper` and `torch` to `requirements.txt`.
