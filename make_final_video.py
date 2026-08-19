"""CLI script to build final slideshow video with audio and customizable word-highlighted captions.

Usage:
    python make_final_video.py --images-dir output --audio Senario.mp3 --words words.json --add-captions --output final_video.mp4
    python make_final_video.py --images-dir output --audio Senario.mp3 --words words.json --add-captions --font-name "Arial Black" --font-size 48 --highlight-color "#FFD60A" --text-color "#FFFFFF" --position bottom --output final_video.mp4
"""

import argparse
import sys
from pathlib import Path

from modules.pipeline import SlideshowPipeline
from modules.project_manager import resolve_project_dir


def main():
    parser = argparse.ArgumentParser(description="Assemble images, audio, and subtitle captions into a final MP4 video")
    parser.add_argument("--images-dir", type=str, default=None, help="Directory containing generated images (1.png, 2.png, ...)")
    parser.add_argument("--audio", type=str, default=None, help="Audio file path (voice.mp3)")
    parser.add_argument("--transcript", type=str, default=None, help="Timed transcript file path")
    parser.add_argument("--words", type=str, default=None, help="Word-level timestamps JSON file path")
    parser.add_argument("--output", type=str, default=None, help="Output MP4 video file path")
    parser.add_argument("--project", "-p", type=str, default=None, help="Project name or directory inside projects/ workspace")
    parser.add_argument("--add-captions", action="store_true", help="Burn word-highlighted subtitles onto the video")
    
    # Subtitle Customization Flags
    parser.add_argument("--font-name", type=str, default="Arial Black", help="Subtitle font family (e.g., 'Arial Black', 'Impact', 'Montserrat')")
    parser.add_argument("--font-size", type=int, default=None, help="Subtitle font size in px")
    parser.add_argument("--text-color", type=str, default="#FFFFFF", help="Default text color hex (e.g. #FFFFFF)")
    parser.add_argument("--highlight-color", type=str, default="#FFD60A", help="Highlighted active word color hex (e.g. #FFD60A)")
    parser.add_argument("--outline-color", type=str, default="#000000", help="Text outline color hex (e.g. #000000)")
    parser.add_argument("--bg-color", type=str, default=None, help="Text background box color hex if needed")
    parser.add_argument("--position", type=str, choices=["bottom", "middle", "top"], default="bottom", help="Subtitle position")
    parser.add_argument("--on-mismatch", type=str, choices=["pad", "truncate", "ask", "error"], default="pad", help="Mismatch resolution strategy if image count != timestamp count")

    args = parser.parse_args()

    proj_dir = resolve_project_dir(args.project)

    images_dir = Path(args.images_dir) if args.images_dir else (proj_dir / "images" if (proj_dir / "images").exists() else Path("output"))
    audio_path = Path(args.audio) if args.audio else (
        proj_dir / "voice.mp3" if (proj_dir / "voice.mp3").exists() else (
            proj_dir / "Senario.mp3" if (proj_dir / "Senario.mp3").exists() else Path("Senario.mp3")
        )
    )
    transcript_path = Path(args.transcript) if args.transcript else (proj_dir / "transcript.txt" if (proj_dir / "transcript.txt").exists() else Path("transcript.txt"))
    words_path = Path(args.words) if args.words else (proj_dir / "words.json" if (proj_dir / "words.json").exists() else Path("words.json"))
    output_path = Path(args.output) if args.output else (proj_dir / "final_video.mp4")

    style_config = {
        "font_name": args.font_name,
        "font_size": args.font_size,
        "text_color": args.text_color,
        "highlight_color": args.highlight_color,
        "outline_color": args.outline_color,
        "bg_color": args.bg_color,
        "position": args.position,
    }

    print(f"[+] Assembling final video '{output_path}' from images '{images_dir}' and audio '{audio_path}'...")
    pipeline = SlideshowPipeline()
    pipeline.run(
        images_dir=images_dir,
        transcript_path=transcript_path,
        output_path=output_path,
        audio_path=audio_path,
        add_captions=args.add_captions,
        words_json_path=words_path if args.add_captions else None,
        caption_config=style_config,
        on_mismatch=args.on_mismatch,
    )

    print(f"[✓] SUCCESS! Final video generated at: {output_path.resolve()}")


if __name__ == "__main__":
    main()
