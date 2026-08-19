"""Batch image generation script for Google Flow with reference image upload.

Usage:
    python examples/batch_generate_millo.py --prompts prompts.txt --reference millo_reference.jpeg --model nano-banana-2
"""

import argparse
import asyncio
import logging
import re
import shutil
from datetime import datetime
from pathlib import Path

from playwright.async_api import Page

import browser2api.platforms.flow.client as flow_client_module
from browser2api import BrowserManager, Platform
from browser2api.platforms.flow import FlowClient, FlowCount, FlowModel, FlowOrientation
from browser2api.platforms.flow.enums import MODEL_NAMES
from browser2api.types import GenerationStatus

# Monkey-patch _COLLECT_IMAGES_JS in FlowClient to ensure all images in Flow's dense canvas are collected
flow_client_module._COLLECT_IMAGES_JS = """() => {
    const imgs = document.querySelectorAll('img');
    const urls = [];
    for (const img of imgs) {
        const src = img.src || img.getAttribute('src') || '';
        if (src.length > 30) {
            if (src.includes('labs.google/fx/api/')
                || src.includes('googleusercontent.com')
                || src.includes('lh3.google')
                || src.includes('gstatic.com')
                || src.includes('storage.googleapis.com')) {
                urls.push(src);
            }
        }
    }
    return Array.from(new Set(urls));
}"""

async def _robust_ensure_generation_page(self):
    """Ensure the browser is inside a Flow project editor, waiting for listing cards to render."""
    # 1. Check if ANY open page in browser context is already inside a Flow project
    for p in self.context.pages:
        if "labs.google/fx/tools/flow/project/" in p.url:
            self.page = p
            logger.info(f"[Flow] Found active project tab: {p.url}")
            break

    current = self.page.url
    if "labs.google/fx/tools/flow/project/" not in current:
        if "labs.google/fx/tools/flow" not in current:
            try:
                await self.page.goto("https://labs.google/fx/tools/flow", wait_until="domcontentloaded", timeout=60000)
            except Exception as e:
                logger.warning(f"[Flow] Goto warning: {e}")
            await asyncio.sleep(3)

        # Wait up to 20s for project cards or New Project button to appear on listing page
        logger.info("[Flow] On listing page, waiting for project cards to render...")
        for i in range(20):
            try:
                clicked = await self.page.evaluate("""() => {
                    // 1. Look for existing project links
                    for (const a of document.querySelectorAll('a[href*="/project/"]')) {
                        const rect = a.getBoundingClientRect();
                        if (rect.width > 20 && rect.height > 20) {
                            a.click();
                            return 'existing';
                        }
                    }
                    // 2. Look for project cards with data attributes or click handlers
                    for (const el of document.querySelectorAll('div[role="button"], div[class*="card" i], div[class*="project" i]')) {
                        const rect = el.getBoundingClientRect();
                        if (rect.width > 100 && rect.height > 60 && rect.top > 60) {
                            el.click();
                            return 'card';
                        }
                    }
                    // 3. Look for 'New Project' button
                    for (const btn of document.querySelectorAll('button, a, div[role="button"]')) {
                        const text = (btn.textContent || '').trim().toLowerCase();
                        if (text.includes('new project') || text.includes('create project') || text === 'new') {
                            btn.click();
                            return 'new';
                        }
                    }
                    return null;
                }""")
                if clicked:
                    logger.info(f"[Flow] Clicked project card/button ({clicked}) after {i}s")
                    await asyncio.sleep(4)
                    break
            except Exception:
                pass
            await asyncio.sleep(1)

    # Wait until a page with '/project/' is found in context
    for _ in range(25):
        for p in self.context.pages:
            if "labs.google/fx/tools/flow/project/" in p.url:
                self.page = p
                break
        if "labs.google/fx/tools/flow/project/" in self.page.url:
            break
        await asyncio.sleep(1)

    # Dismiss any cookie banner / announcement overlays
    try:
        await self.page.evaluate("""() => {
            const cookie = document.querySelector('#glue-cookie-notification-bar-1, .glue-cookie-notification-bar');
            if (cookie) {
                const btn = cookie.querySelector('button');
                if (btn) btn.click();
                cookie.remove();
            }
            for (const btn of document.querySelectorAll('button')) {
                const text = (btn.textContent || '').trim().toLowerCase();
                if (text === 'dismiss' || text === 'got it' || text === 'i agree' || text === 'accept all') {
                    btn.click();
                }
            }
        }""")
    except Exception:
        pass

    # Now wait for the prompt bar contenteditable to be ready and steady
    for i in range(30):
        try:
            ready = await self.page.evaluate("""() => {
                const ce = document.querySelector('[contenteditable="true"]');
                if (ce) {
                    const r = ce.getBoundingClientRect();
                    return r.width > 50;
                }
                return false;
            }""")
            if ready:
                logger.info(f"[Flow] Prompt input ready after {i}s")
                await asyncio.sleep(1.5)
                break
        except Exception:
            pass
        await asyncio.sleep(1)

FlowClient._ensure_generation_page = _robust_ensure_generation_page

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("batch_generate_millo")


def parse_prompts(filepath: str | Path) -> list[tuple[str, str, str]]:
    """Parse prompts file formatted as [MM:SS] prompt text or line-by-line prompts.

    Returns:
        List of (timestamp_key, raw_line_text, prompt_text)
        e.g. [('00-14', '[00:14] Hand-drawn...', 'Hand-drawn...')]
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Prompts file not found: {filepath}")

    prompts: list[tuple[str, str, str]] = []
    pattern = re.compile(r"^\s*\[(\d{2}):(\d{2})\]\s*(.+)$")

    lines_raw = [l.strip() for l in path.read_text(encoding="utf-8").splitlines() if l.strip() and not l.strip().startswith("#")]

    if not lines_raw:
        return []

    # Check if lines have [MM:SS] timestamp headers
    has_timestamps = any(pattern.match(l) for l in lines_raw)

    if has_timestamps:
        for line_str in lines_raw:
            match = pattern.match(line_str)
            if match:
                mm, ss, prompt_text = match.groups()
                clean_prompt = re.sub(r"\[span_\d+\]\(start_span\)|\[span_\d+\]\(end_span\)|\[span_\d+\]", "", prompt_text).strip()
                key = f"{mm}-{ss}"
                raw_line = f"[{mm}:{ss}] {clean_prompt}"
                prompts.append((key, raw_line, clean_prompt))
    else:
        # Fallback: Prompts don't have [MM:SS] headers directly on lines.
        ts_keys = []
        transcript_path = path.parent / "transcript.txt"
        if not transcript_path.exists():
            transcript_path = Path("transcript.txt")

        if transcript_path.exists():
            for t_line in transcript_path.read_text(encoding="utf-8").splitlines():
                t_match = pattern.match(t_line.strip())
                if t_match:
                    t_mm, t_ss, _ = t_match.groups()
                    ts_keys.append(f"{t_mm}-{t_ss}")

        for idx, prompt_text in enumerate(lines_raw):
            clean_prompt = re.sub(r"\[span_\d+\]\(start_span\)|\[span_\d+\]\(end_span\)|\[span_\d+\]", "", prompt_text).strip()
            if idx < len(ts_keys):
                key = ts_keys[idx]
            else:
                key = f"frame_{idx+1:03d}"

            raw_line = f"[{key.replace('-', ':')}] {clean_prompt}"
            prompts.append((key, raw_line, clean_prompt))

    return prompts


async def upload_reference_image(page: Page, image_path: str | Path) -> bool:
    """Upload and attach reference image file into Google Flow prompt box safely."""
    ref_file = Path(image_path)
    if not ref_file.exists():
        if Path("millo_reference.jpeg").exists():
            ref_file = Path("millo_reference.jpeg")
        elif Path("milo.jpeg").exists():
            ref_file = Path("milo.jpeg")

    ref_abs_path = str(ref_file.resolve())
    ref_name = ref_file.name
    ref_stem = ref_file.stem.lower()

    # 1. Check if chip is already attached above prompt box
    already_attached = await page.evaluate("""() => {
        const ce = document.querySelector('[contenteditable="true"]');
        if (!ce) return false;
        const box = ce.closest('form, div[class*="dpylNZ"], div[class*="gvAbJD"]') || ce.parentElement.parentElement;
        const imgs = box.querySelectorAll('img');
        return imgs.length > 0;
    }""")

    if already_attached:
        logger.info("[Flow] Reference chip already attached to prompt box!")
        return True

    # 2. Try opening Asset Manager and attaching chip
    try:
        plus_btn = page.locator('button.sc-253cad92-0, div.sc-5c3af813-2 button, button:has-text("+")').first
        if await plus_btn.count() > 0 and await plus_btn.is_visible():
            await plus_btn.click()
            await asyncio.sleep(1.5)

            # Upload local file if input[type="file"] exists
            file_input = page.locator('input[type="file"]').first
            if await file_input.count() > 0:
                try:
                    await file_input.set_input_files(ref_abs_path)
                    await asyncio.sleep(4.0)
                except Exception as e:
                    logger.debug(f"[Flow] File input upload note: {e}")

            # Search in Asset Manager
            search_term = "millo" if "millo" in ref_stem else "milo"
            search_input = page.locator('input[placeholder*="Search" i], input[type="search"]').first
            if await search_input.count() > 0:
                await search_input.fill(search_term)
                await asyncio.sleep(1.0)

            # Click matched asset card
            millo_card = page.locator(f'div:has-text("{search_term}"), span:has-text("{search_term}"), img[alt*="{search_term}" i]').first
            if await millo_card.count() > 0:
                await millo_card.click()
                await asyncio.sleep(0.5)

            # Click 'Add to Prompt' button
            add_btn = page.locator('button:has-text("Add to Prompt")').first
            if await add_btn.count() > 0 and await add_btn.is_visible():
                await add_btn.click()
                await asyncio.sleep(1.5)
    except Exception as e:
        logger.warning(f"[Flow] Reference image upload note: {e}")
    finally:
        # Guarantee that any open modal dialog is closed so prompt input is never blocked
        try:
            await page.keyboard.press("Escape")
            await asyncio.sleep(0.3)
        except Exception:
            pass

    return True


async def main(
    prompts_file: str,
    reference_image: str,
    model_name: str,
    output_dir_path: str = "output",
    delay_seconds: float = 8.0,
    profile: str | None = None,
):
    if not Path(prompts_file).exists() and Path("image_prompts.txt").exists():
        logger.info("Defaulting prompts file to 'image_prompts.txt'")
        prompts_file = "image_prompts.txt"

    prompts = parse_prompts(prompts_file)
    if not prompts:
        print("No valid prompts found.")
        return

    ref_name = Path(reference_image).name if reference_image else "milo.jpeg"
    model = MODEL_NAMES.get(model_name, FlowModel.NANO_BANANA_2)
    output_dir = Path(output_dir_path).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    bm = BrowserManager()
    try:
        profile_msg = f" using profile '{profile}'" if profile else ""
        logger.info(f"Launching browser{profile_msg}...")
        context, page = await bm.launch_for_login(Platform.FLOW, profile_directory=profile)

        # Select existing flow page if one is already open in the context
        for p in context.pages:
            if "labs.google" in p.url:
                page = p
                logger.info(f"[Flow] Found active Flow project page: {p.url}")
                break

        client = FlowClient(
            page,
            context,
            output_dir=output_dir,
            model=model,
            orientation=FlowOrientation.LANDSCAPE,
            count=FlowCount.X1,
        )

        total = len(prompts)
        for i, (key, raw_line, prompt_text) in enumerate(prompts, 1):
            target_image = output_dir / f"{key}.jpg"
            target_image_png = output_dir / f"{key}.png"

            if target_image.exists() or target_image_png.exists():
                print(f"⏭ Skipped: {key}.jpg")
                continue

            short_text = prompt_text[:40] + "..." if len(prompt_text) > 40 else prompt_text
            print(f"[{i}/{total}] Generating: {key} → \"{short_text}\"")

            prefix = "Use the reference picture and make the picture according to the instructions below:"
            full_prompt = f"{prefix} {prompt_text}"

            try:
                # Ensure page is inside project editor
                await client._ensure_generation_page()

                # Attach existing reference image chip ('milo.jpeg') before prompt
                await upload_reference_image(client.page, ref_name)

                # Generate image (count=1 forced, timeout=75s)
                result = await client.generate_images(
                    full_prompt, count=1, timeout_seconds=75
                )

                if result.status == GenerationStatus.COMPLETED and result.images:
                    downloaded = result.images[0]
                    if downloaded.local_path and Path(downloaded.local_path).exists():
                        src_file = Path(downloaded.local_path)
                        shutil.move(str(src_file), str(target_image))
                        print(f"  ✓ Saved: {target_image.name}")
                    else:
                        raise RuntimeError("Downloaded file does not exist")
                else:
                    err_msg = result.error or "Generation failed"
                    raise RuntimeError(err_msg)

            except Exception as e:
                err_msg = f"{datetime.now().isoformat()} [{key}] Error: {e}"
                print(f"  ❌ Error on {key}: {e}")
                with open("errors.log", "a", encoding="utf-8") as f:
                    f.write(err_msg + "\n")

            # Pause between requests to prevent rate limiting & let generation complete cleanly
            if i < total:
                print(f"  ⏳ Waiting {delay_seconds}s before next request...")
                await asyncio.sleep(delay_seconds)

    finally:
        await bm.close()


if __name__ == "__main__":
    from modules.project_manager import resolve_project_dir

    parser = argparse.ArgumentParser(
        description="Batch generate images for Millo via Google Flow"
    )
    parser.add_argument("--profile", type=str, default=None, help="Chrome profile directory name (e.g. 'Profile 1')")
    parser.add_argument("--prompts", default=None, help="Path to prompts file")
    parser.add_argument(
        "--reference", default="./milo.jpeg", help="Path to reference image"
    )
    parser.add_argument(
        "--model",
        default="nano-banana-2",
        choices=list(MODEL_NAMES.keys()),
        help="Model to use",
    )
    parser.add_argument("--output-dir", default=None, help="Output directory for generated images")
    parser.add_argument("--project", "-p", default=None, help="Project name or directory inside projects/ workspace")
    parser.add_argument(
        "--delay",
        type=float,
        default=8.0,
        help="Delay in seconds between requests (default: 8.0)",
    )
    args = parser.parse_args()

    proj_dir = resolve_project_dir(args.project)

    # Resolve output_dir (defaults to projects/<ActiveProject>/images)
    output_dir = Path(args.output_dir) if args.output_dir else (proj_dir / "images")

    # Resolve prompts file:
    if args.prompts:
        prompts_file = Path(args.prompts)
        if not prompts_file.exists() and (proj_dir / args.prompts).exists():
            prompts_file = proj_dir / args.prompts
    elif (proj_dir / "image_prompts.txt").exists() and (proj_dir / "image_prompts.txt").stat().st_size > 50:
        prompts_file = proj_dir / "image_prompts.txt"
    elif (proj_dir / "transcript.txt").exists():
        prompts_file = proj_dir / "transcript.txt"
    elif Path("image_prompts.txt").exists() and Path("image_prompts.txt").stat().st_size > 50:
        prompts_file = Path("image_prompts.txt")
    elif Path("transcript.txt").exists():
        prompts_file = Path("transcript.txt")
    else:
        prompts_file = Path("prompts.txt")

    logger.info(f"[Flow] Using picture prompts file: '{prompts_file.resolve()}'")

    # Resolve reference image
    ref_file = Path(args.reference)
    if not ref_file.exists():
        if (proj_dir / "milo.jpeg").exists():
            ref_file = proj_dir / "milo.jpeg"
        elif Path("milo.jpeg").exists():
            ref_file = Path("milo.jpeg")
        elif Path("millo_reference.jpeg").exists():
            ref_file = Path("millo_reference.jpeg")

    asyncio.run(main(prompts_file, ref_file, args.model, output_dir, args.delay, profile=args.profile))
