# 🎬 Text2Video Automation Suite

> **End-to-End Automated Pipeline for AI Video & Content Creation**  
> Streamline your YouTube, TikTok, and social media production from raw topic generation to voice synthesis and visual asset generation using automated browser interactions.

---

## 📌 Overview

**Text2Video** is an automated content production pipeline powered by Browser2API and Playwright. It automates three major stages of AI video production:

1. 📝 **Script Generation** (`claude_prompt.py`)  
   Generates viral educational video topics and complete narrator-ready voice-over scripts using Claude AI.
2. 🎙️ **Voice-Over Synthesis** (`elevenlabs_prompt.py`)  
   Automates ElevenLabs Text-to-Speech web interface to select custom voices (e.g. `2styzLg7OSeuhPP6uQ26`), insert script text, trigger generation, and automatically download the `Senario.mp3` audio file.
3. 🖼️ **Visual Asset Generation** (`batch_generate_millo.py`)  
   Batch generates AI images and video assets on Google Flow using custom prompts and reference images.

---

## 📁 Directory Structure

```text
Text2Video/
├── claude_prompt.py          # Phase 1 & 2 Script Generator (Claude.ai)
├── elevenlabs_prompt.py      # Voice Synthesis & Audio Downloader (ElevenLabs)
├── batch_generate_millo.py   # Batch Image/Visual Generator (Google Flow)
└── README.md                 # Project Documentation
```

---

## ⚡ Quick Start Guide

### 1️⃣ Requirements & Prerequisites

Ensure Python 3.10+ and Playwright are installed:

```bash
pip install -r requirements.txt
playwright install chromium
```

Ensure Chrome browser is installed if using `--profile` with persistent user logins.

---

### 2️⃣ Step-by-Step Workflow

#### Step 1: Generate Script with Claude (`claude_prompt.py`)
Launches Claude.ai, executes Phase 1 (viral topic ideas) and Phase 2 (narration script), saving the output script to `senario.txt`.

```bash
python Text2Video/claude_prompt.py --profile "Profile 1" --auto-followup --output senario.txt
```

#### Step 2: Synthesize Voice with ElevenLabs (`elevenlabs_prompt.py`)
Launches ElevenLabs Text-to-Speech page, selects voice ID `2styzLg7OSeuhPP6uQ26`, inputs text from `senario.txt`, clicks **Generate speech**, and downloads `Senario.mp3`. Automatically closes the browser when complete.

```bash
python Text2Video/elevenlabs_prompt.py --profile "Profile 1" --voice 2styzLg7OSeuhPP6uQ26 --input senario.txt --output Senario.mp3
```

#### Step 3: Batch Generate Visual Assets (`batch_generate_millo.py`)
Batch generates images/video frames for each timestamp in your video using Google Flow with reference image support.

```bash
python Text2Video/batch_generate_millo.py --prompts image_prompts.txt --reference millo_reference.jpeg --model nano-banana-2
```

---

## ⚙️ CLI Reference

### 🎙️ `elevenlabs_prompt.py`

| Flag | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `--profile` | `str` | `None` | Chrome profile directory to maintain logged-in ElevenLabs session (e.g. `"Profile 1"`, `"Default"`). |
| `--voice` | `str` | `2styzLg7OSeuhPP6uQ26` | Voice ID or Voice Name to search and select on ElevenLabs. |
| `--input` | `Path` | `senario.txt` | File path containing narration scenario text. |
| `--output` | `Path` | `Senario.mp3` | File path to save generated MP3 audio file. |
| `--keep-open` | `flag` | `False` | Keep browser open after downloading audio (by default browser closes automatically). |
| `--no-generate` | `flag` | `False` | Skip automatic generation click. |

---

### 📝 `claude_prompt.py`

| Flag | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `--profile` | `str` | `None` | Chrome profile directory to use for Claude session. |
| `--auto-followup` | `flag` | `False` | Automatically send Phase 2 script request after Phase 1 finishes. |
| `--output` | `str` | `senario.txt` | Destination file path for generated script text. |

---

### 🖼️ `batch_generate_millo.py`

| Flag | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `--prompts` | `Path` | Required | Text file formatted with timestamped prompts (e.g. `[00:15] prompt text`). |
| `--reference` | `Path` | Optional | Reference image file path to upload for consistent character style. |
| `--model` | `str` | `nano-banana-2` | Target model name on Google Flow. |
| `--output-dir` | `Path` | `./output` | Output directory for downloaded images/assets. |

---

## 📄 License & Notes

Developed as part of the **Browser2API** automation framework.
python make_final_video.py --project "Video_20260807_174256_The_phone_busses"   --add-captions --font-size 80 
# گام ۱: ساخت سناریو در کلاد
python claude_prompt.py --profile "Profile 1" --auto-followup

# گام ۲: ساخت ویس ElevenLabs
python elevenlabs_prompt.py --profile "Profile 1" --voice 2styzLg7OSeuhPP6uQ26

# گام ۳: ترانویسی Whisper (ساخت transcript.txt و words.json)
python transcribe_audio.py

# گام ۴ (جدید): مرحله Prompt-Making در کلاد (ساخت image_prompts.txt)
python generate_image_prompts.py --profile "Profile 1"

# گام ۵: ساخت تصاویر در Google Flow
python batch_generate_millo.py --reference milo.jpeg --model nano-banana-2 --delay 8.0

# گام ۶: ساخت ویدیوی نهایی با زیرنویس
python make_final_video.py --add-captions


python generate_image_prompts.py --project "Video_20260807_174256_The_phone_busses" --profile "Profile 1"


python batch_generate_millo.py --project "Video_20260807_174256_The_phone_busses"


python batch_generate_millo.py \
  --project "Video_20260807_174256_The_phone_busses" \
  --prompts transcript.txt \
  --reference milo.jpeg \
  --model nano-banana-2 \
  --delay 8.0



python batch_generate_millo.py --project "Video_01" --prompts image_prompts.txt --reference milo.jpeg --model nano-banana-2 --delay 8.0
