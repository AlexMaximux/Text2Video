# Text2Video Clean Workspace & Pipeline Guide

## 1. Clean Project Workspace Structure (ساختار پوشه‌ها)

از این پس تمام فایل‌های پروژه داخل پوشه `projects/` به صورت شکیل و مجزا آرشیو می‌شوند:

```text
Text2Video/
├── claude_prompt.py
├── elevenlabs_prompt.py
├── transcribe_audio.py
├── generate_image_prompts.py
├── batch_generate_millo.py
├── make_final_video.py
├── pipeline.py
├── history_topics.txt
│
└── projects/
    └── Video_20260807_1937_WiredToBelong/
        ├── senario.txt           # ۱. متن سناریوی تولیدشده
        ├── voice.mp3             # ۲. ویس ElevenLabs
        ├── transcript.txt        # ۳. متون زمان‌بندی Whisper
        ├── words.json            # ۴. زمان‌بندی کلمه به کلمه زیرنویس
        ├── image_prompts.txt     # ۵. پرامپت‌های تولید عکس (ساخته‌شده با کلاد)
        ├── images/               # ۶. تصاویر ساخت شده Google Flow
        └── final_video.mp4       # ۷. ویدیوی نهایی کامل با زیرنویس
```

---

## 2. Step-by-Step Commands (دستورات تک‌به‌تک)

در هر گام، اسکریپت به صورت خودکار **آخرین پروژه ساخته‌شده** را تشخیص می‌دهد و نیازی به وارد کردن مسیرهای طولانی نیست:

### Step 1: Generate Script via Claude (تولید سناریو و ساخت پوشه جدید پروژه)
python claude_prompt.py --profile "Profile 1" --auto-followup



#if i want to have my own topic 

python claude_prompt.py --profile "Profile 9" --auto-followup --topic "The Evolutionary Mystery of White Skin"

### Step 2: Generate Voiceover via ElevenLabs (تولید گویندگی صوتی در پوشه پروژه)
python elevenlabs_prompt.py --profile "Profile 1" --voice 2styzLg7OSeuhPP6uQ26

### Step 3: Transcribe Audio & Extract Word Timestamps (ترانویسی و زمان‌بندی کلمه‌ای)
python transcribe_audio.py

python transcribe_audio.py \
    --audio /root/abc.mp3 \
    --model medium \
    --output-transcript ./video1/senario.txt \
    --output-words ./video1/words.json \
    --project my_project      # if you have a specific project folder


### Step 4: Generate Image Prompts via Claude (مرحله Prompt-Making در کلاد)
python generate_image_prompts.py --profile "Profile 1"

### Step 5: Batch Generate Images via Google Flow (تولید تصاویر به صورت دسته‌ای)
python batch_generate_millo.py --profile "Profile 1" --reference milo.jpeg --model nano-banana-2 --delay 8.0

### Step 6: Assemble Final Video with Custom Captions (ساخت ویدیوی نهایی)
python make_final_video.py \
  --add-captions \
  --font-name "Arial Black" \
  --font-size 48 \
  --text-color "#FFFFFF" \
  --highlight-color "#FFD60A" \
  --position bottom

---

## 3. Specific Project Commands (اجرا برای یک پروژه خاص)

اگر می‌خواهید روی یک پوشه پروژه مشخص (مثلاً `Video_01`) کار کنید:

```bash
python claude_prompt.py --project "Video_01" --profile "Profile 1" --auto-followup
python elevenlabs_prompt.py --project "Video_01" --profile "Profile 1" --voice 2styzLg7OSeuhPP6uQ26
python transcribe_audio.py --project "Video_01"
python generate_image_prompts.py --project "Video_01" --profile "Profile 1"
python batch_generate_millo.py --project "Video_01" --profile "Profile 1" --reference milo.jpeg --model nano-banana-2 --delay 8.0
python make_final_video.py --project "Video_01" --add-captions
```

---

## 4. Full Master Pipeline (اجرای خودکار یکپارچه تمام ۶ گام)

```bash
python pipeline.py \
  --profile "Profile 1" \
  --voice 2styzLg7OSeuhPP6uQ26 \
  --add-captions \
  --font-name "Arial Black" \
  --highlight-color "#FFD60A"
```
