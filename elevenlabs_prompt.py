"""Script to launch Chrome, navigate to ElevenLabs Text-to-Speech synthesis page,
select specified voice ID (e.g., 2styzLg7OSeuhPP6uQ26), paste the contents of senario.txt,
click 'Generate speech', and save the resulting audio file as Senario.mp3.

Usage:
    python examples/elevenlabs_prompt.py
    python examples/elevenlabs_prompt.py --profile "Profile 1"
    python examples/elevenlabs_prompt.py --voice 2styzLg7OSeuhPP6uQ26 --input senario.txt --output Senario.mp3
"""

import argparse
import asyncio
import base64
import logging
import os
import sys
from pathlib import Path

from browser2api import BrowserManager, Platform

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)

DEFAULT_URL = "https://elevenlabs.io/app/speech-synthesis/text-to-speech"
DEFAULT_VOICE_ID = "2styzLg7OSeuhPP6uQ26"
DEFAULT_OUTPUT = Path("Senario.mp3")


def load_scenario_text(input_path: Path) -> str:
    """Read scenario text from input_path. Fallback to senario01.txt if empty."""
    if input_path.exists():
        content = input_path.read_text(encoding="utf-8").strip()
        if content:
            print(f"[+] Loaded scenario text from '{input_path}' ({len(content)} characters)")
            return content
        else:
            print(f"[!] '{input_path}' exists but is empty.")

    # Fallback check
    fallback_path = input_path.parent / "senario01.txt"
    if fallback_path.exists():
        content = fallback_path.read_text(encoding="utf-8").strip()
        if content:
            print(f"[+] Loaded fallback scenario text from '{fallback_path}' ({len(content)} characters)")
            return content

    raise FileNotFoundError(
        f"Could not find valid non-empty scenario text in '{input_path}' or '{fallback_path}'."
    )


async def select_voice(page, voice_id: str):
    """Attempt to select the voice on ElevenLabs page using voice_id or voice search."""
    print(f"[+] Step 1: Attempting to select voice ID: {voice_id} ...")

    # Selectors for voice picker button on ElevenLabs left panel
    voice_picker_selectors = [
        'button[data-testid*="voice"]',
        'button[aria-label*="voice" i]',
        'button[aria-label*="Voice" i]',
        'div[data-testid*="voice-picker"]',
        'button:has-text("Voice")',
        '[aria-haspopup="dialog"]',
        '[aria-haspopup="listbox"]',
        'button:has(svg)',
    ]

    picker_btn = None
    for sel in voice_picker_selectors:
        try:
            elements = page.locator(sel)
            count = await elements.count()
            for i in range(count):
                elem = elements.nth(i)
                if await elem.is_visible(timeout=1000):
                    txt = (await elem.inner_text()).lower()
                    picker_btn = elem
                    print(f"[+] Found potential voice picker button with selector '{sel}' (text: '{txt[:30]}')")
                    break
            if picker_btn:
                break
        except Exception:
            continue

    if picker_btn:
        try:
            await picker_btn.click()
            await asyncio.sleep(1.5)
        except Exception as e:
            print(f"[!] Failed clicking voice picker button: {e}")

    # Look for search box in voice dropdown/modal
    search_selectors = [
        'input[placeholder*="Search" i]',
        'input[placeholder*="search" i]',
        'input[type="search"]',
        'input[data-testid*="search" i]',
        'input',
    ]

    search_input = None
    for s_sel in search_selectors:
        try:
            s_elem = page.locator(s_sel).first
            if await s_elem.is_visible(timeout=2000):
                search_input = s_elem
                print(f"[+] Found voice search input: '{s_sel}'")
                break
        except Exception:
            continue

    if search_input:
        await search_input.fill(voice_id)
        await asyncio.sleep(1.5)
        print(f"[+] Typed voice ID '{voice_id}' into search box.")

        # Click the first search result / option matching voice
        option_selectors = [
            f'*:has-text("{voice_id}")',
            '[role="option"]',
            'div[data-testid*="voice-item"]',
            'button:has-text("Select")',
            'div.cursor-pointer',
        ]

        selected = False
        for opt_sel in option_selectors:
            try:
                opt = page.locator(opt_sel).first
                if await opt.is_visible(timeout=2000):
                    await opt.click()
                    print(f"[✓] Voice '{voice_id}' selected via option locator '{opt_sel}'")
                    selected = True
                    break
            except Exception:
                continue

        if not selected:
            print("[!] Could not click voice search option automatically. Please select it manually if needed.")
    else:
        print("[!] Voice search input box not found automatically. Please verify voice selection on screen.")


async def paste_scenario(page, text: str):
    """Find text input box and paste scenario text into it."""
    print("[+] Step 2: Locating Text-to-Speech prompt input box...")

    textarea_selectors = [
        'textarea[placeholder*="text" i]',
        'textarea',
        'div[contenteditable="true"]',
        '[data-testid*="text-to-speech-textarea"]',
        '[data-testid*="textarea"]',
        '[aria-label*="text" i]',
    ]

    input_elem = None
    for sel in textarea_selectors:
        try:
            elem = page.locator(sel).first
            if await elem.is_visible(timeout=3000):
                input_elem = elem
                print(f"[+] Found prompt input box: '{sel}'")
                break
        except Exception:
            continue

    if not input_elem:
        print("[!] Text box not immediately found. Waiting for UI element to appear...")
        for sel in textarea_selectors:
            try:
                elem = page.locator(sel).first
                await elem.wait_for(state="visible", timeout=30000)
                input_elem = elem
                print(f"[+] Found prompt input box after waiting: '{sel}'")
                break
            except Exception:
                continue

    if input_elem:
        await input_elem.focus()
        await asyncio.sleep(0.5)

        # Clear existing text if any (Select All + Backspace)
        await page.keyboard.press("Meta+A" if sys.platform == "darwin" else "Control+A")
        await page.keyboard.press("Backspace")
        await asyncio.sleep(0.3)

        # Insert scenario text
        print(f"[+] Pasting scenario content ({len(text)} characters)...")
        await page.keyboard.insert_text(text)
        print("[✓] Scenario content successfully pasted into ElevenLabs text box!")
    else:
        print("[!] Prompt input box could not be located automatically.")


async def generate_and_download_speech(page, output_path: Path = DEFAULT_OUTPUT, timeout_seconds: int = 180):
    """Click 'Generate speech' button, wait for generation, and download audio as Senario.mp3."""
    print("\n[+] Step 3: Triggering 'Generate speech' and waiting for audio download...")

    audio_bytes = bytearray()
    download_event = asyncio.Event()

    # Network listener to capture audio response directly
    async def handle_response(response):
        try:
            content_type = response.headers.get("content-type", "").lower()
            url = response.url.lower()
            if ("audio/" in content_type or ".mp3" in url or "text-to-speech" in url) and response.status == 200:
                body = await response.body()
                if len(body) > 1000:  # Valid audio file payload
                    audio_bytes.clear()
                    audio_bytes.extend(body)
                    print(f"[+] Intercepted audio payload via network ({len(body):,} bytes)")
                    download_event.set()
        except Exception:
            pass

    page.on("response", lambda resp: asyncio.create_task(handle_response(resp)))

    # Find and click Generate Speech button
    generate_selectors = [
        'button:has-text("Generate speech")',
        'button:has-text("Generate audio")',
        'button:has-text("Generate")',
        'button[data-testid*="generate"]',
        'button[type="submit"]',
    ]

    gen_btn = None
    for sel in generate_selectors:
        try:
            elem = page.locator(sel).first
            if await elem.is_visible(timeout=2000) and await elem.is_enabled(timeout=2000):
                gen_btn = elem
                print(f"[+] Found 'Generate speech' button: '{sel}'")
                break
        except Exception:
            continue

    if not gen_btn:
        print("[!] Searching for any button containing 'Generate' or 'Speech'...")
        buttons = page.locator('button')
        count = await buttons.count()
        for i in range(count):
            btn = buttons.nth(i)
            if await btn.is_visible():
                txt = (await btn.inner_text()).strip().lower()
                if "generate" in txt or "speech" in txt:
                    gen_btn = btn
                    print(f"[+] Found button with text: '{txt}'")
                    break

    if not gen_btn:
        print("[!] 'Generate speech' button not found automatically. Please click Generate manually on screen.")
    else:
        print("[+] Clicking 'Generate speech' button...")
        await gen_btn.click()
        print("[+] Clicked! Waiting for speech generation to complete...")

    # Wait for network intercept or UI Download button
    start_time = asyncio.get_event_loop().time()
    saved = False

    while (asyncio.get_event_loop().time() - start_time) < timeout_seconds:
        # 1. Check network intercepted audio
        if download_event.is_set() and audio_bytes:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(bytes(audio_bytes))
            print(f"[✓] Audio successfully saved to '{output_path}' ({len(audio_bytes):,} bytes) via network stream!")
            saved = True
            break

        # 2. Check UI Download button
        download_selectors = [
            'button[aria-label*="download" i]',
            'button[aria-label*="Download" i]',
            'a[aria-label*="download" i]',
            'button:has-text("Download")',
            'button[data-testid*="download"]',
            'a[download]',
        ]

        for d_sel in download_selectors:
            try:
                d_btn = page.locator(d_sel).first
                if await d_btn.is_visible(timeout=1000) and await d_btn.is_enabled(timeout=1000):
                    print(f"[+] Found UI Download button: '{d_sel}'")
                    try:
                        output_path.parent.mkdir(parents=True, exist_ok=True)
                        async with page.expect_download(timeout=15000) as download_info:
                            await d_btn.click()
                        download = await download_info.value
                        await download.save_as(str(output_path))
                        print(f"[✓] Audio successfully saved to '{output_path}' via UI Download button!")
                        saved = True
                        break
                    except Exception as e:
                        print(f"[!] Download button click notice: {e}")
            except Exception:
                continue

        if saved:
            break

        await asyncio.sleep(2)

    # 3. Fallback: Check audio element src in DOM
    if not saved:
        try:
            audio_elem = page.locator('audio').first
            if await audio_elem.is_visible(timeout=2000):
                src = await audio_elem.get_attribute("src")
                if src:
                    print(f"[+] Found audio element src: {src[:50]}...")
                    base64_data = await page.evaluate("""async (url) => {
                        const response = await fetch(url);
                        const blob = await response.blob();
                        return new Promise((resolve) => {
                            const reader = new FileReader();
                            reader.onloadend = () => resolve(reader.result.split(',')[1]);
                            reader.readAsDataURL(blob);
                        });
                    }""", src)
                    output_path.write_bytes(base64.b64decode(base64_data))
                    print(f"[✓] Audio successfully saved to '{output_path}' via audio element fetch!")
                    saved = True
        except Exception as e:
            print(f"[!] Audio element fallback notice: {e}")

    if not saved:
        print(f"[!] Could not automatically capture audio download within {timeout_seconds} seconds.")
        print(f"[!] If you click Download manually on screen, the file will be downloaded by Chrome.")


async def main():
    parser = argparse.ArgumentParser(description="ElevenLabs TTS Browser Automation & Audio Downloader")
    parser.add_argument(
        "--profile",
        type=str,
        default=None,
        help="Chrome profile directory to use (e.g., 'Profile 1', 'Default')",
    )
    parser.add_argument(
        "--voice",
        type=str,
        default=DEFAULT_VOICE_ID,
        help=f"Voice ID or name to select (default: {DEFAULT_VOICE_ID})",
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=None,
        help="Path to scenario text file (default: senario.txt in project workspace)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help=f"Path to save output audio file (default: voice.mp3 in project workspace)",
    )
    parser.add_argument(
        "--project", "-p",
        type=str,
        default=None,
        help="Project name or directory inside projects/ workspace",
    )
    parser.add_argument(
        "--no-generate",
        action="store_true",
        help="Skip clicking Generate speech automatically",
    )
    parser.add_argument(
        "--keep-open",
        action="store_true",
        help="Keep browser open after downloading audio (by default it closes automatically)",
    )
    args = parser.parse_args()

    from modules.project_manager import resolve_project_dir
    proj_dir = resolve_project_dir(args.project)

    input_file = args.input if args.input else (proj_dir / "senario.txt" if (proj_dir / "senario.txt").exists() else Path("senario.txt"))
    output_file = args.output if args.output else (proj_dir / "voice.mp3")

    # Load text content
    scenario_text = load_scenario_text(input_file)

    bm = BrowserManager()

    try:
        profile_msg = f" using profile '{args.profile}'" if args.profile else ""
        print(f"\n[+] Launching browser for ElevenLabs{profile_msg}...")
        context, page = await bm.launch_for_login(
            Platform.ELEVENLABS,
            profile_directory=args.profile,
        )

        print(f"[+] Navigating to {DEFAULT_URL} ...")
        await page.goto(DEFAULT_URL, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(3)

        # 1. Select voice
        await select_voice(page, args.voice)
        await asyncio.sleep(1)

        # 2. Paste scenario text
        await paste_scenario(page, scenario_text)
        await asyncio.sleep(1)

        # 3. Generate speech & Download audio file
        if not args.no_generate:
            await generate_and_download_speech(page, output_path=output_file)

        # Sync both voice.mp3 and Senario.mp3 inside project folder and root fallback
        try:
            if output_file.exists():
                data = output_file.read_bytes()
                (output_file.parent / "voice.mp3").write_bytes(data)
                (output_file.parent / "Senario.mp3").write_bytes(data)
                Path("Senario.mp3").write_bytes(data)
        except Exception:
            pass

        print("\n" + "=" * 60)
        print(f"[✓] ALL STEPS FINISHED! Audio saved to project workspace: {output_file.resolve()}")

        if args.keep_open:
            print("[+] Keeping browser open (--keep-open active). Press ENTER in terminal to close...")
            print("=" * 60 + "\n")
            await asyncio.get_event_loop().run_in_executor(None, input)
        else:
            print("[+] Automatically closing browser in 2 seconds...")
            print("=" * 60 + "\n")
            await asyncio.sleep(2)

    finally:
        print("[+] Closing browser manager...")
        await bm.close()
        print("[✓] Browser closed successfully.")



if __name__ == "__main__":
    asyncio.run(main())
