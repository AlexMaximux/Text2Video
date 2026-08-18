"""Script to launch Chrome, navigate to https://claude.ai/new, insert Phase 1 prompt,
and automatically follow up with Phase 2 selection to generate a complete YouTube script,
saving the output to senario.txt.

Usage:
    python examples/claude_prompt.py --profile "Profile 1" --auto-followup
    python examples/claude_prompt.py --profile "Profile 1" --auto-followup --output senario.txt
"""

import argparse
import asyncio
import logging
import sys
from datetime import datetime
from pathlib import Path

from browser2api import BrowserManager, Platform

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)

PROMPT_PHASE_1 = """You are a viral educational YouTube scriptwriting engine for a hand-drawn doodle animation channel focused on human history, evolution, anthropology, and psychology.

You operate in two sequential phases. Follow each phase exactly as described.

---

PHASE 1 — TOPIC GENERATION

When activated, immediately generate exactly 15 viral video title ideas.
Present them in a clean table with two columns: # and Title.
Use only these proven viral angles:
1. What did ancient humans actually ___?
2. Why do/can't you ___?
3. What if we are ___?
4. The ___ Effect
5. You never noticed that ___

Channel rules for titles:
- No jargon. Titles must feel human, curious, and emotionally clickable.
- Topics must fit long-form educational explainers.
- Open with a relatable modern moment, then reframe it with a surprising scientific or historical explanation.

After the table, ask exactly this — nothing more:
"Which idea do you want to develop? Reply with a number (1–5)."

---

PHASE 2 — FULL VIDEO SCRIPT

Once the user selects a number, write a complete voice-over script.

CRITICAL OUTPUT RULE:
The final script must contain ONLY the spoken narration — exactly as a voice actor would read it aloud.
No labels. No section headers. No stage directions. No visual cues. No brackets. No parentheses. No production notes. No meta-commentary. No explanations. Nothing that would not be spoken out loud.
Pure narration. From the first word to the last.

---

LENGTH RULE — THIS IS MANDATORY:
The script must be written for exactly 5 to 7 minutes of spoken narration when read aloud at a natural, calm pace.
The average narration pace is 130 words per minute.
Therefore the total word count of the script must land between 750 and 950 words — no shorter, no longer.
Before finalizing, count the words mentally and adjust until the script falls within this range.
Do not sacrifice quality to hit the number — restructure, expand, or trim naturally.

---

BUILD THE SCRIPT IN THIS INTERNAL ORDER (do not label or reveal this structure in the output):

INTRO — first 30 seconds:
- Open with a bold statement in the very first line that confirms the viewer clicked the right video. Make the promise feel real immediately.
- Plant 2–3 unanswered questions that the viewer's mind cannot ignore. Do not answer them yet.
- Signal the pace and tone of the video naturally in one sentence so the viewer knows what kind of journey they are entering.
- State clearly what makes this video different — the angle, the surprise, the thing they have not heard before.
- In the first few sentences, reference or describe what the viewer sees on screen so they instantly feel their click was worth it.

BODY:
- Open with a relatable modern moment, then reframe it with a surprising scientific or historical explanation.
- Develop the full topic with depth and clarity.
- Close each open loop one by one as the script progresses. Each closure should feel like a satisfying reveal.
- Keep paragraphs short to medium length. Every sentence must sound natural when spoken aloud.

OUTRO:
- End by teasing the next related video on the channel. Invite the viewer to watch it as a natural continuation of curiosity.
- Never say "like and subscribe" or any version of it.

---

TONE AND STYLE RULES:
- Address the audience in calm second-person voice: "you," "your brain," "your ancestors."
- Never use "we" or "I."
- Stay cinematic, human, vivid, and emotionally compelling.
- Avoid robotic, formal, or academic phrasing.
- Write as if speaking to one person sitting across from you.
- All text must be in English."""


PROMPT_PHASE_2_SELECT = """choose one of them that you think it would have most potential to have more views and debate in Youtube and BUILD THE SCRIPT

The output just should be the Titel and ready Script not any extra information at the first or end"""

HISTORY_FILE = Path("history_topics.txt")
OUTPUTS_DIR = Path("outputs")


def load_history_topics() -> list[str]:
    """Load previously generated topic titles from history_topics.txt.
    Fallback to extracting the title from senario.txt if history_topics.txt does not exist.
    """
    topics = []
    if HISTORY_FILE.exists():
        for line in HISTORY_FILE.read_text(encoding="utf-8").splitlines():
            line_clean = line.strip()
            if line_clean and line_clean not in topics:
                topics.append(line_clean)
    elif Path("senario.txt").exists():
        try:
            content = Path("senario.txt").read_text(encoding="utf-8").strip()
            first_line = content.splitlines()[0].strip() if content else ""
            if first_line:
                topics.append(first_line)
                HISTORY_FILE.write_text(f"{first_line}\n", encoding="utf-8")
        except Exception:
            pass

    return topics


def append_history_topic(title: str):
    """Append a new title to history_topics.txt if not already present."""
    if not title:
        return
    title_clean = title.strip()
    # Don't append preamble meta-commentary
    if "evaluated" in title_clean.lower() or "option" in title_clean.lower() or len(title_clean) < 5:
        return
    existing = load_history_topics()
    if title_clean not in existing:
        with HISTORY_FILE.open("a", encoding="utf-8") as f:
            f.write(f"{title_clean}\n")


def build_phase_1_prompt(topic: str | None = None) -> str:
    """Build Phase 1 prompt with optional topic focus and dynamic exclusion of past topics."""
    history = load_history_topics()
    prompt = PROMPT_PHASE_1
    if topic:
        prompt += (
            f"\n\n---\n\n"
            f"SPECIFIC TOPIC REQUESTED BY USER:\n"
            f"The user wants a script specifically focused on or related to this topic:\n"
            f"\"{topic}\"\n"
            f"Please generate 15 viral video title ideas specifically around or related to this exact topic."
        )
    if history:
        history_list = "\n".join(f"- {t}" for t in history)
        prompt += (
            f"\n\n---\n\n"
            f"PREVIOUSLY CREATED TOPICS (DO NOT REPEAT OR DUPLICATE):\n"
            f"The following topics/scenarios have ALREADY been created. Do NOT generate topics that cover these same concepts, angles, or questions:\n"
            f"{history_list}"
        )
    return prompt


from modules.project_manager import resolve_project_dir


def archive_script_output(script_text: str, project_name: str | None = None, output_file: str | None = None) -> tuple[Path, Path]:
    """Save generated script to project directory and update history_topics.txt with title."""
    lines = [l.strip() for l in script_text.strip().splitlines() if l.strip()]
    first_line = lines[0] if lines else ""

    proj_dir = resolve_project_dir(project_name, auto_create_if_none=True, title_hint=first_line)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_path = proj_dir / f"senario_{timestamp}.txt"
    main_path = proj_dir / (output_file if output_file and output_file != "senario.txt" else "senario.txt")

    main_path.write_text(script_text, encoding="utf-8")
    archive_path.write_text(script_text, encoding="utf-8")

    # Also sync root senario.txt for backward compatibility
    try:
        Path("senario.txt").write_text(script_text, encoding="utf-8")
    except Exception:
        pass

    if first_line:
        append_history_topic(first_line)

    return main_path, archive_path


async def get_all_claude_responses(page) -> list[str]:
    """Extract text content of each response from Claude on the page using browser DOM evaluation."""
    script = """() => {
        let nodes = Array.from(document.querySelectorAll('[data-message-author-role="assistant"]'));
        if (nodes.length === 0) {
            const candidates = Array.from(document.querySelectorAll('div.font-claude-message, div[data-is-streaming]'));
            nodes = candidates.filter(c => !candidates.some(other => other !== c && other.contains(c)));
        }
        if (nodes.length === 0) {
            const candidates = Array.from(document.querySelectorAll('div.prose'));
            nodes = candidates.filter(c => !candidates.some(other => other !== c && other.contains(c)));
        }
        return nodes.map(n => (n.innerText || "").trim()).filter(t => t && t.length > 20);
    }"""
    try:
        results = await page.evaluate(script)
        if isinstance(results, list):
            return [r.strip() for r in results if r and len(r.strip()) > 20]
    except Exception:
        pass
    return []


async def wait_for_claude_response(page, expected_turn: int = 1, timeout_seconds: int = 300) -> str:
    """Wait for Claude to finish generating the expected response turn (1 for Phase 1, 2 for Phase 2).
    Returns the raw text of that response.
    """
    print(f"[+] Waiting for Claude response turn #{expected_turn} to complete...")
    start_time = asyncio.get_event_loop().time()
    await asyncio.sleep(4)  # Wait for prompt submission & streaming startup

    last_text = ""
    stable_count = 0

    while (asyncio.get_event_loop().time() - start_time) < timeout_seconds:
        # Check if stop button is visible
        is_streaming = False
        try:
            stop_btn = page.locator('button[aria-label*="Stop" i], button[data-testid*="stop" i]').first
            if await stop_btn.is_visible(timeout=500):
                is_streaming = True
        except Exception:
            pass

        responses = await get_all_claude_responses(page)

        if len(responses) >= expected_turn:
            target_text = responses[expected_turn - 1]

            # Fallback for turn 2 if index exact mismatch happens
            if expected_turn == 2 and ("15 Viral Title Ideas" in target_text or "Reply with a number" in target_text):
                if len(responses) > expected_turn:
                    target_text = responses[-1]

            if target_text and len(target_text) > 30:
                if target_text == last_text and not is_streaming:
                    stable_count += 1
                    if stable_count >= 3:  # Text unchanged across 3 checks (~6s) and stop button gone
                        word_count = len(target_text.split())
                        print(f"[✓] Turn #{expected_turn} complete! ({word_count} words)")
                        return target_text
                else:
                    stable_count = 0
                    last_text = target_text

        await asyncio.sleep(2)

    return last_text


def clean_script_output(text: str) -> str:
    """Clean preamble/postscript meta commentary from script output."""
    lines = text.strip().splitlines()
    cleaned = []
    started = False

    preamble_triggers = [
        "thought for",
        "thinking",
        "the strongest pick",
        "here's why",
        "here is the full script",
        "here is the script",
        "evaluated viral potential",
        "evaluated option",
        "evaluated",
        "deliberated",
        "deliberate",
        "selected topic",
        "here's the full script",
        "voice-over script",
        "narrator script",
        "claude responded:",
        "engagement and debate",
    ]

    for line in lines:
        line_str = line.strip()
        if not line_str:
            if started:
                cleaned.append("")
            continue

        if not started:
            lower = line_str.lower()
            if any(pt in lower for pt in preamble_triggers) and len(line_str) < 300:
                continue
            if lower.endswith("here is the full script.") or lower.endswith("here is the full script:"):
                continue
            # Skip single symbol/icon lines like  or non-alphanumeric noise before script starts
            if len(line_str) < 5 and not line_str.isalnum():
                continue
            # Found first actual title / sentence of narration!
            started = True
            cleaned.append(line_str)
        else:
            cleaned.append(line_str)

    return "\n".join(cleaned).strip()


async def open_claude_and_run_workflow(
    send_automatically: bool = False,
    auto_followup: bool = False,
    profile_directory: str | None = None,
    output_file: str = "senario.txt",
    project_name: str | None = None,
    topic: str | None = None,
):
    bm = BrowserManager()

    try:
        profile_msg = f" using profile '{profile_directory}'" if profile_directory else ""
        print(f"\n[+] Launching browser for Claude.ai{profile_msg}...")
        context, page = await bm.launch_for_login(
            Platform.CLAUDE,
            profile_directory=profile_directory,
        )

        print("[+] Navigating to https://claude.ai/new ...")
        await page.goto("https://claude.ai/new", wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(2)

        selectors = [
            'div[contenteditable="true"]',
            'div.ProseMirror',
            'p[data-placeholder]',
            'fieldset div[contenteditable="true"]',
            'textarea',
        ]

        input_element = None
        for sel in selectors:
            try:
                elem = page.locator(sel).first
                if await elem.is_visible(timeout=3000):
                    input_element = elem
                    print(f"[+] Found input box with selector: '{sel}'")
                    break
            except Exception:
                continue

        if not input_element:
            print("[!] Prompt input box not immediately found. Please log in to Claude if required.")
            for sel in selectors:
                try:
                    elem = page.locator(sel).first
                    await elem.wait_for(state="visible", timeout=120000)
                    input_element = elem
                    print(f"[+] Found input box with selector: '{sel}' after waiting!")
                    break
                except Exception:
                    continue

        if input_element:
            phase_1_prompt = build_phase_1_prompt(topic=topic)
            print("[+] Inserting Phase 1 prompt (Topic Generation with History Exclusion)...")
            await input_element.focus()
            await asyncio.sleep(0.5)
            await page.keyboard.insert_text(phase_1_prompt)
            print("[✓] Phase 1 prompt inserted!")

            should_send = send_automatically or auto_followup

            if should_send:
                await asyncio.sleep(1)
                print("[+] Sending Phase 1 prompt...")
                send_buttons = [
                    'button[aria-label*="Send"]',
                    'button[aria-label*="send"]',
                    'button:has(svg)',
                    'button[type="submit"]',
                ]
                sent = False
                for btn_sel in send_buttons:
                    try:
                        btn = page.locator(btn_sel).last
                        if await btn.is_visible(timeout=1000) and await btn.is_enabled(timeout=1000):
                            await btn.click()
                            print("[✓] Phase 1 prompt sent!")
                            sent = True
                            break
                    except Exception:
                        continue

                if not sent:
                    print("[+] Pressing Enter to send Phase 1...")
                    await page.keyboard.press("Enter")
                    print("[✓] Phase 1 sent via Enter!")

                # If auto-followup is requested, wait for Phase 1 response then send Phase 2
                if auto_followup:
                    phase_1_text = await wait_for_claude_response(page, expected_turn=1, timeout_seconds=180)
                    if phase_1_text:
                        print("\n[+] Phase 1 complete! Preparing Phase 2 prompt...")
                        await asyncio.sleep(2)

                        # Re-locate input box for Phase 2
                        input_element_2 = None
                        for sel in selectors:
                            try:
                                elem = page.locator(sel).first
                                if await elem.is_visible(timeout=3000):
                                    input_element_2 = elem
                                    break
                            except Exception:
                                continue

                        if input_element_2:
                            print(f"[+] Inserting Phase 2 prompt:\n    \"{PROMPT_PHASE_2_SELECT}\"")
                            await input_element_2.focus()
                            await asyncio.sleep(0.5)
                            await page.keyboard.insert_text(PROMPT_PHASE_2_SELECT)

                            await asyncio.sleep(1)
                            print("[+] Sending Phase 2 prompt...")
                            sent_2 = False
                            for btn_sel in send_buttons:
                                try:
                                    btn = page.locator(btn_sel).last
                                    if await btn.is_visible(timeout=1000) and await btn.is_enabled(timeout=1000):
                                        await btn.click()
                                        print("[✓] Phase 2 prompt sent!")
                                        sent_2 = True
                                        break
                                except Exception:
                                    continue

                            if not sent_2:
                                await page.keyboard.press("Enter")
                                print("[✓] Phase 2 sent via Enter!")

                            # Wait for Phase 2 (full script) to finish
                            phase_2_text = await wait_for_claude_response(page, expected_turn=2, timeout_seconds=300)
                            print("[✓] Phase 2 complete! Extracting generated script output...")

                            script_text = clean_script_output(phase_2_text)
                            if script_text:
                                main_p, archive_p = archive_script_output(script_text, project_name=project_name, output_file=output_file)
                                word_count = len(script_text.split())
                                print(f"\n[✓] SUCCESS: Clean voice-over script ({word_count} words) saved to project workspace: {main_p.resolve()}")
                                print(f"[✓] ARCHIVED COPY saved to: {archive_p.resolve()}")
                                print(f"[✓] HISTORY UPDATED in: {HISTORY_FILE.resolve()}")
                            else:
                                print(f"[!] Could not automatically extract text. Output remains visible in browser.")
                else:
                    # Save Phase 1 text if only Phase 1 was requested
                    phase_1_text = await wait_for_claude_response(page, expected_turn=1, timeout_seconds=180)
                    if phase_1_text:
                        script_text = clean_script_output(phase_1_text)
                        archive_script_output(script_text, project_name=project_name, output_file=output_file)


        print("\n[+] Browser session is ready. Keeping open for 30 seconds...")
        try:
            await asyncio.sleep(30)
        except asyncio.CancelledError:
            pass

    except KeyboardInterrupt:
        print("\n[-] User interrupted. Closing browser...")
    except Exception as e:
        print(f"\n[!] Error during execution: {e}")
    finally:
        await bm.close()
        print("[+] Browser closed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Open Claude.ai and generate viral YouTube script")
    parser.add_argument("--send", action="store_true", help="Send Phase 1 prompt automatically")
    parser.add_argument("--auto-followup", action="store_true", help="Automatically send Phase 2 prompt after Phase 1 finishes")
    parser.add_argument("--profile", type=str, default=None, help="Chrome profile directory to use (e.g., 'Profile 1', 'Profile 6', 'Default')")
    parser.add_argument("--output", type=str, default="senario.txt", help="Output text file path for saving script (default: 'senario.txt')")
    parser.add_argument("--project", "-p", type=str, default=None, help="Project name or directory inside projects/ workspace")
    parser.add_argument("--topic", type=str, default=None, help="Specific topic to generate video script for")
    args = parser.parse_args()

    asyncio.run(open_claude_and_run_workflow(
        send_automatically=args.send,
        auto_followup=args.auto_followup,
        profile_directory=args.profile,
        output_file=args.output,
        project_name=args.project,
        topic=args.topic,
    ))
