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

from browser2api import BrowserManager, Platform
from browser2api.platforms.flow import FlowClient, FlowCount, FlowModel, FlowOrientation
from browser2api.platforms.flow.enums import MODEL_NAMES
from browser2api.types import GenerationStatus

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("batch_generate_millo")


def parse_prompts(filepath: str | Path) -> list[tuple[str, str, str]]:
    """Parse prompts file formatted as [MM:SS] prompt text.

    Returns:
        List of (timestamp_key, raw_line_text, prompt_text)
        e.g. [('00-14', '[00:14] Hand-drawn...', 'Hand-drawn...')]
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Prompts file not found: {filepath}")

    prompts: list[tuple[str, str, str]] = []
    pattern = re.compile(r"^\s*\[(\d{2}):(\d{2})\]\s*(.+)$")

    with open(path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line_str = line.strip()
            if not line_str or line_str.startswith("#"):
                continue
            match = pattern.match(line_str)
            if match:
                mm, ss, prompt_text = match.groups()
                # Clean prompt text from LLM span artifacts (e.g. [span_10](start_span)[span_10](end_span))
                clean_prompt = re.sub(r"\[span_\d+\]\(start_span\)|\[span_\d+\]\(end_span\)|\[span_\d+\]", "", prompt_text).strip()
                key = f"{mm}-{ss}"
                raw_line = f"[{mm}:{ss}] {clean_prompt}"
                prompts.append((key, raw_line, clean_prompt))
            else:
                logger.warning(
                    f"Line {line_num} skipped (format must be [MM:SS] prompt): {line_str}"
                )

    return prompts


async def upload_reference_image(page: Page, image_path: str | Path) -> bool:
    """Upload and attach reference image file ('millo_reference.jpeg' / 'milo.jpeg') into Google Flow prompt box.

    1. Checks if reference chip is already attached above prompt box.
    2. Opens Asset Manager via '+' button in prompt bar.
    3. Uploads file if input[type="file"] is present and waits 6s.
    4. Searches 'millo' / 'milo' in Asset Manager search box.
    5. Clicks the matched asset card.
    6. Clicks 'Add to Prompt' button.
    7. Verifies the reference chip is attached above prompt box.
    """
    ref_file = Path(image_path)
    if not ref_file.exists():
        if Path("millo_reference.jpeg").exists():
            ref_file = Path("millo_reference.jpeg")
        elif Path("milo.jpeg").exists():
            ref_file = Path("milo.jpeg")

    ref_abs_path = str(ref_file.resolve())
    ref_name = ref_file.name
    ref_stem = ref_file.stem.lower()

    logger.info(f"[Flow] Ensuring reference asset '{ref_name}' is attached to prompt box...")

    editable = page.locator('[contenteditable="true"]').first
    if await editable.count() == 0:
        logger.warning("[Flow] Could not find contenteditable prompt editor")
        return False

    # Check if chip is already attached above prompt box
    already_attached = await page.evaluate("""() => {
        const ce = document.querySelector('[contenteditable="true"]');
        if (!ce) return false;
        const box = ce.closest('div[class*="dpylNZ"], div[class*="gvAbJD"], form') || ce.parentElement.parentElement;
        const imgs = box.querySelectorAll('img');
        return imgs.length > 0;
    }""")

    if already_attached:
        logger.info("[Flow] Reference chip already attached to prompt box!")
        return True

    # Step 1: Click '+' button near prompt bar
    logger.info("[Flow] Opening Asset Manager via '+' button...")
    plus_btn = page.locator('button.sc-253cad92-0, div.sc-5c3af813-2 button').first
    if await plus_btn.count() > 0:
        await plus_btn.click()
        await asyncio.sleep(1.5)

    # Step 2: Upload local file if input[type="file"] exists
    file_input = page.locator('input[type="file"]').first
    if await file_input.count() > 0:
        try:
            logger.info(f"[Flow] Uploading file via input[type='file'] -> {ref_abs_path}")
            await file_input.set_input_files(ref_abs_path)
            logger.info("[Flow] Waiting 6 seconds for asset upload & processing to complete...")
            await asyncio.sleep(6.0)
        except Exception as e:
            logger.warning(f"[Flow] File input upload notice: {e}")

    # Step 3: Search for 'millo' or 'milo' in Asset Manager search box
    search_term = "millo" if "millo" in ref_stem else "milo"
    logger.info(f"[Flow] Searching '{search_term}' in Asset Manager...")
    search_input = page.locator('input[placeholder*="Search" i], input[type="search"]').first
    if await search_input.count() > 0:
        await search_input.fill(search_term)
        await asyncio.sleep(1.0)

    # Step 4: Click the asset card matching search_term
    logger.info(f"[Flow] Selecting asset card for '{search_term}'...")
    millo_card = page.locator(f'div:has-text("{search_term}"), span:has-text("{search_term}"), img[alt*="{search_term}" i]').first
    if await millo_card.count() > 0:
        await millo_card.click()
        await asyncio.sleep(0.5)

    # Step 5: Click 'Add to Prompt' button
    logger.info("[Flow] Clicking 'Add to Prompt' button...")
    add_btn = page.locator('button:has-text("Add to Prompt")').first
    if await add_btn.count() > 0:
        await add_btn.click()
        logger.info("[Flow] Clicked 'Add to Prompt' successfully!")
        await asyncio.sleep(1.5)

    # Step 6: Verify chip attachment above prompt box
    chip_verified = await page.evaluate("""() => {
        const ce = document.querySelector('[contenteditable="true"]');
        if (!ce) return false;
        const box = ce.closest('div[class*="dpylNZ"], div[class*="gvAbJD"], form') || ce.parentElement.parentElement;
        const imgs = box.querySelectorAll('img');
        return imgs.length > 0;
    }""")

    if chip_verified:
        logger.info("[Flow] MILLO reference image chip verified and attached to prompt box!")
        return True

    logger.warning("[Flow] Chip verification failed after Add to Prompt")
    return False


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

    ref_name = Path(reference_image).name if reference_image else "millo.jpeg"
    model = MODEL_NAMES.get(model_name, FlowModel.NANO_BANANA_2)
    output_dir = Path(output_dir_path).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    bm = BrowserManager()
    try:
        profile_msg = f" using profile '{profile}'" if profile else ""
        logger.info(f"Launching browser{profile_msg}...")
        context, page = await bm.launch_for_login(Platform.FLOW, profile_directory=profile)

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

                # Attach existing reference image chip ('millo.jpeg') before each prompt
                await upload_reference_image(page, ref_name)

                # Generate image (count=1 forced)
                result = await client.generate_images(
                    full_prompt, count=1, timeout_seconds=120
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

    # Resolve prompts file
    if args.prompts:
        prompts_file = Path(args.prompts)
        if not prompts_file.exists() and (proj_dir / args.prompts).exists():
            prompts_file = proj_dir / args.prompts
    elif (proj_dir / "transcript.txt").exists():
        prompts_file = proj_dir / "transcript.txt"
    elif (proj_dir / "image_prompts.txt").exists():
        prompts_file = proj_dir / "image_prompts.txt"
    elif (proj_dir / "prompts.txt").exists():
        prompts_file = proj_dir / "prompts.txt"
    elif Path("transcript.txt").exists():
        prompts_file = Path("transcript.txt")
    elif Path("image_prompts.txt").exists():
        prompts_file = Path("image_prompts.txt")
    else:
        prompts_file = Path("prompts.txt")

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
