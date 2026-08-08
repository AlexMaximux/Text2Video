# Carton-Making Integration into Text2Video Design Document

**Date:** 2026-08-07  
**Status:** Approved by User  
**Goal:** Port full capabilities from Carton-making (`Video making by pic`) into `Text2Video`. This includes Whisper audio transcription, word-level JSON timestamp generation, dynamic image slide timing, ASS/SRT word-highlighted subtitle generation (with configurable font, colors, background, size, and position), FFmpeg video rendering, and a master end-to-end pipeline script.

---

## 1. Architecture & Component Scope

### 1.1 `modules/` Package Porting
Port and refine the following modules from `Carton-making`:
- `modules/__init__.py`: Package initialization.
- `modules/transcriber.py`: Uses Whisper (`openai-whisper` or `whisper-timestamped`) to transcribe audio (`Senario.mp3`), generating `transcript.txt` and `words.json` with word-level timestamps.
- `modules/transcript_parser.py`: Parses timestamps from `transcript.txt` for image timing.
- `modules/timing_calculator.py`: Calculates display duration for each image based on transcript timestamps and total audio duration.
- `modules/caption_generator.py`: Converts `words.json` into animated ASS word-highlighted subtitles with custom font, size, text color, highlight color, background/outline color, and alignment options.
- `modules/ffmpeg_engine.py`: Uses FFmpeg to build slideshow videos, overlay ASS subtitles, and burn captions.
- `modules/audio_muxer.py`: Merges rendered video track with the original audio track (`Senario.mp3`).
- `modules/pipeline.py`: Low-level video assembly orchestrator.

### 1.2 Top-Level CLI Commands in `Text2Video`
1. `claude_prompt.py`: Script generation -> `senario.txt`.
2. `elevenlabs_prompt.py`: Voice generation -> `Senario.mp3`.
3. `transcribe_audio.py` [NEW]: Audio transcription -> `transcript.txt` and `words.json`.
4. `batch_generate_millo.py`: Image generation -> `./images/`.
5. `make_final_video.py` [NEW]: Assembles final MP4 video from images + audio + transcript + words JSON, with full subtitle styling options:
   - `--font-name` (default: "Arial Black")
   - `--font-size` (default: auto ~5% video height)
   - `--text-color` (default: "#FFFFFF")
   - `--highlight-color` (default: "#FFD60A")
   - `--outline-color` (default: "#000000")
   - `--bg-color` / `--back-color` (default: transparent / outline)
   - `--position` ("bottom", "middle", "top")
6. `pipeline.py` [NEW]: Master end-to-end runner that executes all steps automatically.

---

## 2. Dependencies & Requirements
Update `requirements.txt` to include:
- `browser2api`
- `playwright`
- `openai-whisper` or `whisper-timestamped`
- `torch` / `torchaudio`
- `ffmpeg-python` (and system `ffmpeg` binary)

---

## 3. Verification Plan
- Unit test for `transcriber.py` and `caption_generator.py` with mock word timestamps.
- Dry run test for `make_final_video.py --help` verifying all subtitle styling flags (`--font-name`, `--font-size`, `--text-color`, `--highlight-color`, `--outline-color`, `--bg-color`, `--position`).
- Update `myOwnreadme.mt` with full command examples.
