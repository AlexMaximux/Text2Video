"""CLI script to generate detailed Google Flow image prompts from transcript.txt using Claude.ai automation.

Usage:
    python generate_image_prompts.py --profile "Profile 1"
    python generate_image_prompts.py --project "Video_01" --profile "Profile 1"
"""

import argparse
import asyncio
import logging
import re
import sys
from pathlib import Path

from browser2api import BrowserManager, Platform
from modules.project_manager import resolve_project_dir

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)

PROMPT_MAKING_SYSTEM_PROMPT = """You are an image-prompt generation engine for a viral educational YouTube doodle animation workflow.

Your job is to convert a timestamped script batch into one detailed text-to-image prompt for every timestamp line.

Important:
The input may be a partial batch of a larger transcript.
It may contain as few as 1 timestamp line or as many as 20 timestamp lines.
You must process the batch exactly as given.
Do not say the transcript is incomplete just because the batch is short.

Each input line usually looks like this:
[00:00] Tonight, when the sun goes down, you're going to flip a switch.
[00:05] Light will flood the room and you won't think twice about it.

You must generate exactly one image prompt for each timestamp line in the batch.
Do not skip any timestamp.
Do not merge timestamps.
Do not summarize.
Do not explain your reasoning.
Do not add commentary before or after the prompts.

CHANNEL VISUAL DNA

Style:
- Hand-drawn 2D doodle cartoon animation
- Flat colors
- Bold black outlines
- Slightly imperfect sketchy marker lines
- Educational YouTube explainer doodle style
- Simple stick figures with large circular heads, dot eyes, expressive thick brows
- Simplified cartoon animals and objects
- Backgrounds must be flat solid colors only
- No gradients
- No shadows
- No textures
- No photorealism
- No 3D

Default visual language:
- White background = neutral / modern / everyday
- Blue sky + green ground = outdoor / nature / evolution
- Solid orange background = fire / ancient ritual / night warmth
- Tan background = cave / desert / prehistoric
- Solid blue background = science / abstract explanation
- Stark white with red text or accents = danger / threat / alarm

On-screen design elements allowed:
- Bold ALL CAPS hand-lettered text at top of frame
- Short labels with black or yellow arrows
- Thought bubbles with text like "?", "WAIT...", "HMMMM", "!"

Aspect ratio:
- Always 16:9

CORE TASK

For each timestamped line in the input:
1. Read the sentence carefully.
2. Translate the meaning into a concrete visual scene.
3. Write one image prompt for that timestamp.
4. Keep prompts in the same chronological order as the input.
5. Hold scenes across consecutive timestamps when the narration is describing the same moment; only adjust expression, pose, framing, or add one new visual element when needed.
6. Make every prompt visually specific:
- who is in the frame
- what they are doing
- facial expression
- what objects are present
- background color
- any on-screen text
- any arrows, labels, or thought bubbles if useful

PROMPT CONSTRUCTION RULES

Every prompt must:
- Begin with its timestamp in this exact format: [00:00]
- Immediately continue with this exact style anchor:
Hand-drawn 2D doodle cartoon animation, flat colors, bold black outlines, slightly imperfect sketchy marker lines,
- End with this exact style lock:
no gradients, no shadows, no textures, no photorealism, no 3D, 16:9 aspect ratio, educational YouTube explainer doodle style.

You must convert abstract narration into concrete visuals.

Use these frame types when appropriate:
- Concept text frame
- Evolution sequence
- Labeled diagram
- Stick figure reaction frame
- Villain personified
- Globe with creatures or objects around it

Do not make every timestamp a completely new scene.
If 2 to 4 consecutive lines describe the same idea, preserve scene continuity.

BACKGROUND COLOR LOGIC

Use background colors intentionally:
- Ancient / prehistoric = tan or dark blue
- Danger / fear / predator / threat = stark white with red warning text, or red-tinted sky
- Discovery / relief / triumph = bright white or yellow
- Science / abstract explanation = solid blue
- Nature / evolution / outdoor = blue sky with green ground
- Fire / ritual / campfire / night gathering = solid orange

OUTPUT FORMAT

Output plain text only.
Do not use markdown headings.
Do not use bullet points.
Do not use code fences.
Do not number the prompts.

Output exactly one prompt per timestamp line in this format:

[00:00] Hand-drawn 2D doodle cartoon animation, flat colors, bold black outlines, slightly imperfect sketchy marker lines, [full scene description], no gradients, no shadows, no textures, no photorealism, no 3D, 16:9 aspect ratio, educational YouTube explainer doodle style.

Insert exactly one blank line between prompts.

VALIDATION RULES

Before producing the final answer, verify all of the following:
- Every input timestamp appears exactly once in the output
- Output order matches input order
- No timestamp is skipped
- No extra timestamps are invented
- Every prompt starts with the timestamp and the exact style anchor
- Every prompt ends with the exact style lock
- Every prompt is visually concrete, not abstract
- Consecutive related lines preserve scene continuity where appropriate

If the input contains no valid timestamp lines, output exactly this sentence and nothing else:

No valid timestamp lines were found. Please provide timestamped lines in the format [MM:SS] Your sentence here.

---

HERE IS THE TIMESTAMPED TRANSCRIPT TO PROCESS:

"""


async def wait_for_response(page, timeout_seconds: int = 180) -> str:
    """Wait for Claude's response generation to finish."""
    start = asyncio.get_event_loop().time()
    last_text = ""

    while (asyncio.get_event_loop().time() - start) < timeout_seconds:
        content_loc = page.locator('div[class*="font-claude-message"], div.grid-cols-1, div[data-is-streaming="false"]').last
        if await content_loc.count() > 0:
            current_text = await content_loc.inner_text()
            if current_text and current_text == last_text and len(current_text) > 100:
                is_streaming = await page.evaluate("""() => {
                    const btn = document.querySelector('button[aria-label*="Stop"], button[data-testid*="stop"]');
                    return !!btn;
                }""")
                if not is_streaming:
                    return current_text
            last_text = current_text
        await asyncio.sleep(3)

    return last_text


def clean_prompt_output(text: str) -> str:
    """Clean markdown code fences or preambles from image prompt output."""
    lines = text.strip().splitlines()
    cleaned = []
    for line in lines:
        line_str = line.strip()
        if line_str.startswith("```") or line_str.endswith("```"):
            continue
        if cleaned or line_str.startswith("["):
            cleaned.append(line_str)
    return "\n".join(cleaned).strip()


async def generate_image_prompts(profile: str, input_file: Path, output_file: Path):
    """Launch Claude.ai and submit transcript to produce image_prompts.txt."""
    if not input_file.exists():
        print(f"[!] Error: Transcript file not found at '{input_file}'")
        sys.exit(1)

    transcript_text = input_file.read_text(encoding="utf-8").strip()
    if not transcript_text:
        print(f"[!] Error: Transcript file '{input_file}' is empty!")
        sys.exit(1)

    full_prompt = PROMPT_MAKING_SYSTEM_PROMPT + transcript_text

    bm = BrowserManager()
    print(f"[+] Launching browser for Claude.ai using profile '{profile}'...")
    context, page = await bm.launch_for_login(Platform.CLAUDE, profile_directory=profile)

    try:
        print("[+] Navigating to https://claude.ai/new ...")
        await page.goto("https://claude.ai/new", wait_until="domcontentloaded")
        await asyncio.sleep(4)

        input_box = page.locator('div[contenteditable="true"]').first
        if await input_box.count() == 0:
            print("[!] Could not locate Claude prompt input box.")
            sys.exit(1)

        print(f"[+] Inserting Prompt-Making request ({len(full_prompt):,} characters)...")
        await input_box.click()
        await page.keyboard.insert_text(full_prompt)
        await asyncio.sleep(1)

        print("[+] Sending Prompt-Making request...")
        await page.keyboard.press("Enter")
        await asyncio.sleep(2)

        print("[+] Waiting for Claude's image prompt generation to complete...")
        raw_output = await wait_for_response(page, timeout_seconds=180)

        cleaned_output = clean_prompt_output(raw_output)

        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(cleaned_output, encoding="utf-8")

        # Sync fallback root image_prompts.txt for backward compatibility
        try:
            Path("image_prompts.txt").write_text(cleaned_output, encoding="utf-8")
        except Exception:
            pass

        print(f"[✓] SUCCESS! Image prompts saved to project workspace: {output_file.resolve()}")

    finally:
        await bm.close()


def main():
    parser = argparse.ArgumentParser(description="Generate image prompts from transcript via Claude.ai")
    parser.add_argument("--profile", type=str, default="Profile 1", help="Chrome profile name")
    parser.add_argument("--input", type=str, default=None, help="Input transcript file path")
    parser.add_argument("--output", type=str, default=None, help="Output image_prompts.txt path")
    parser.add_argument("--project", "-p", type=str, default=None, help="Project workspace directory")
    args = parser.parse_args()

    proj_dir = resolve_project_dir(args.project)
    input_file = Path(args.input) if args.input else (proj_dir / "transcript.txt")
    output_file = Path(args.output) if args.output else (proj_dir / "image_prompts.txt")

    asyncio.run(generate_image_prompts(args.profile, input_file, output_file))


if __name__ == "__main__":
    main()
