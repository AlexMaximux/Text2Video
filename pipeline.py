"""Master End-to-End Pipeline script for Text2Video.

Usage:
    python pipeline.py --profile "Profile 1" --voice 2styzLg7OSeuhPP6uQ26 --add-captions --output final_video.mp4
"""

import argparse
import subprocess
import sys
from pathlib import Path


def run_cmd(cmd: str):
    print(f"\n[>>> EXEC] {cmd}")
    res = subprocess.run(cmd, shell=True)
    if res.returncode != 0:
        print(f"[!] Step failed with return code {res.returncode}")
        sys.exit(res.returncode)


from modules.project_manager import resolve_project_dir


def main():
    parser = argparse.ArgumentParser(description="Master End-to-End Text2Video Pipeline")
    parser.add_argument("--profile", type=str, default="Profile 1", help="Chrome profile for automation")
    parser.add_argument("--voice", type=str, default="2styzLg7OSeuhPP6uQ26", help="ElevenLabs Voice ID")
    parser.add_argument("--project", "-p", type=str, default=None, help="Project name or directory inside projects/ workspace")
    parser.add_argument("--add-captions", action="store_true", help="Burn captions into final video")
    parser.add_argument("--font-name", type=str, default="Arial Black", help="Subtitle font family")
    parser.add_argument("--font-size", type=int, default=None, help="Subtitle font size in px")
    parser.add_argument("--text-color", type=str, default="#FFFFFF", help="Subtitle default text color hex")
    parser.add_argument("--highlight-color", type=str, default="#FFD60A", help="Subtitle active word highlight hex")
    parser.add_argument("--position", type=str, choices=["bottom", "middle", "top"], default="bottom", help="Subtitle position")
    parser.add_argument("--skip-images", action="store_true", help="Skip Step 4 image generation")
    parser.add_argument("--output", type=str, default=None, help="Final output video path")
    args = parser.parse_args()

    proj_arg = f'--project "{args.project}"' if args.project else ""

    # Step 1: Script generation via Claude
    run_cmd(f'python claude_prompt.py --profile "{args.profile}" --auto-followup {proj_arg}')

    # Resolve actual project folder created in step 1 or specified
    proj_dir = resolve_project_dir(args.project)
    proj_name = proj_dir.name
    proj_flag = f'--project "{proj_name}"'

    # Step 2: Voiceover generation via ElevenLabs
    run_cmd(f'python elevenlabs_prompt.py --profile "{args.profile}" --voice {args.voice} {proj_flag}')

    # Step 3: Transcription & Word Timestamps
    run_cmd(f'python transcribe_audio.py {proj_flag}')

    # Step 4: Prompt-Making via Claude (generate image_prompts.txt from transcript.txt)
    run_cmd(f'python generate_image_prompts.py --profile "{args.profile}" {proj_flag}')

    # Step 5: Batch Image Generation via Google Flow
    if not args.skip_images:
        run_cmd(f'python batch_generate_millo.py --profile "{args.profile}" {proj_flag}')

    # Step 6: Video assembly
    captions_flag = "--add-captions" if args.add_captions else ""
    font_size_flag = f"--font-size {args.font_size}" if args.font_size else ""
    out_flag = f'--output "{args.output}"' if args.output else ""
    cmd_video = (
        f'python make_final_video.py {proj_flag} {captions_flag} '
        f'--font-name "{args.font_name}" {font_size_flag} --text-color "{args.text_color}" '
        f'--highlight-color "{args.highlight_color}" --position {args.position} {out_flag}'
    )
    run_cmd(cmd_video)

    out_video = Path(args.output) if args.output else (proj_dir / "final_video.mp4")
    print(f"\n[🎉 SUCCESS] End-to-End pipeline complete! Output video: {out_video.resolve()}")


if __name__ == "__main__":
    main()
