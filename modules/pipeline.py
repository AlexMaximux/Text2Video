"""
Pipeline & Hook Architecture Module
Orchestrates the transcript parsing, timing calculation, pre-processing, rendering,
and post-processing workflow through extensible pipeline hooks.
"""
import os
import tempfile
from pathlib import Path
from typing import Callable, List, Optional, Tuple, Union

from modules.transcript_parser import parse_transcript
from modules.timing_calculator import get_sorted_images, calculate_timings, ImageSegment
from modules.ffmpeg_engine import render_slideshow
from modules.audio_muxer import mux_audio


from modules.caption_generator import generate_captioned_video


class SlideshowPipeline:
    """
    Extensible pipeline for producing slideshow videos from images and transcripts.
    Supports pre-process hooks (image editing), render filter hooks (FFmpeg filters),
    post-process audio hooks (adding audio tracks), and caption burn-in hooks.
    """

    def __init__(self):
        self.pre_process_hooks: List[Callable[[List[ImageSegment]], List[ImageSegment]]] = []
        self.render_filter_hooks: List[Callable[[], List[str]]] = []
        self.audio_hooks: List[Callable[[Path, Path], Path]] = []
        self.caption_hooks: List[Callable[[Path, Path], Path]] = []

    def add_pre_process_hook(self, hook_fn: Callable[[List[ImageSegment]], List[ImageSegment]]) -> None:
        """Adds a hook to modify or process ImageSegments prior to rendering."""
        self.pre_process_hooks.append(hook_fn)

    def add_render_filter_hook(self, hook_fn: Callable[[], List[str]]) -> None:
        """Adds a hook that supplies custom FFmpeg video filters."""
        self.render_filter_hooks.append(hook_fn)

    def add_audio_hook(self, hook_fn: Callable[[Path, Path], Path]) -> None:
        """Adds a post-render audio multiplexing hook."""
        self.audio_hooks.append(hook_fn)

    def add_caption_hook(self, hook_fn: Callable[[Path, Path], Path]) -> None:
        """Adds a post-render caption burn-in hook."""
        self.caption_hooks.append(hook_fn)

    def run(
        self,
        images_dir: Union[str, Path],
        transcript_path: Union[str, Path],
        output_path: Union[str, Path],
        audio_path: Optional[Union[str, Path]] = None,
        audio_offset: float = 0.0,
        keep_temp: bool = False,
        resolution: str = "1920x1080",
        fps: int = 30,
        total_duration: Optional[float] = None,
        fallback_duration: Optional[float] = None,
        on_mismatch: str = "ask",
        mismatch_resolver: Optional[Callable[[int, int], str]] = None,
        add_captions: bool = False,
        words_json_path: Optional[Union[str, Path]] = None,
        caption_config: Optional[dict] = None
    ) -> Tuple[List[ImageSegment], float, Optional[float], float, bool, float]:
        """
        Executes the full pipeline:
        1. Parse transcript for timestamps.
        2. Read and numerically sort images.
        3. Calculate segment timings.
        4. Apply pre-processing hooks.
        5. Render raw video slideshow with FFmpeg engine.
        6. Multiplex audio track if audio_path provided.
        7. Burn word-highlighted captions if add_captions enabled.

        Returns tuple of (segments, video_duration, audio_duration, duration_diff, was_extended, extend_by).
        """
        timestamps = parse_transcript(transcript_path)
        image_paths = get_sorted_images(images_dir)

        # Handle potential mismatch
        if len(timestamps) != len(image_paths) and on_mismatch == "ask" and mismatch_resolver is not None:
            resolved_mode = mismatch_resolver(len(timestamps), len(image_paths))
            on_mismatch = resolved_mode

        segments = calculate_timings(
            timestamps=timestamps,
            image_paths=image_paths,
            total_duration=total_duration,
            fallback_duration=fallback_duration,
            on_mismatch=on_mismatch
        )

        # Apply pre-process hooks
        for hook in self.pre_process_hooks:
            segments = hook(segments)

        # Collect additional render filters
        additional_filters: List[str] = []
        for hook in self.render_filter_hooks:
            additional_filters.extend(hook())

        final_out_path = Path(output_path).resolve()

        # Determine target path for raw video render
        if audio_path:
            if keep_temp:
                raw_video_path = final_out_path.parent / f"{final_out_path.stem}_silent.mp4"
                temp_created = False
            else:
                # Collision-safe temporary file
                with tempfile.NamedTemporaryFile(prefix="slideshow_raw_", suffix=".mp4", delete=False) as tmp:
                    raw_video_path = Path(tmp.name)
                temp_created = True
        else:
            raw_video_path = final_out_path
            temp_created = False

        # Render raw video slideshow using FFmpeg engine
        rendered_video = render_slideshow(
            segments=segments,
            output_path=raw_video_path,
            resolution=resolution,
            fps=fps,
            additional_filters=additional_filters
        )

        v_dur = segments[-1].end_time if segments else 0.0
        a_dur = None
        diff = 0.0
        was_extended = False
        extend_by = 0.0

        # If audio_path is provided, run audio_muxer post-render step
        if audio_path:
            try:
                final_path, v_dur, a_dur, diff, was_extended, extend_by = mux_audio(
                    video_path=rendered_video,
                    audio_path=audio_path,
                    output_path=final_out_path,
                    offset=audio_offset
                )
            finally:
                # Cleanup temp file if created
                if temp_created and raw_video_path.exists():
                    try:
                        os.remove(raw_video_path)
                    except OSError:
                        pass

        # Apply post-process audio hooks if registered
        for hook in self.audio_hooks:
            final_out_path = hook(final_out_path, final_out_path)

        # Burn word-highlighted captions if requested
        if add_captions:
            if not words_json_path or not Path(words_json_path).is_file():
                raise ValueError(
                    "Word captions enabled (--add-captions), but no valid words JSON file was provided. "
                    "Please use --transcribe-audio or specify --words-json."
                )

            res_w, res_h = 1920, 1080
            if isinstance(resolution, str) and "x" in resolution:
                try:
                    w_str, h_str = resolution.lower().split("x")
                    res_w, res_h = int(w_str), int(h_str)
                except ValueError:
                    pass

            if keep_temp:
                uncaptioned_path = final_out_path.parent / f"{final_out_path.stem}_uncaptioned.mp4"
                temp_uncaptioned = False
                os.replace(final_out_path, uncaptioned_path)
            else:
                with tempfile.NamedTemporaryFile(prefix="slideshow_uncaptioned_", suffix=".mp4", delete=False) as tmp:
                    uncaptioned_path = Path(tmp.name)
                temp_uncaptioned = True
                os.replace(final_out_path, uncaptioned_path)

            try:
                generate_captioned_video(
                    video_path=uncaptioned_path,
                    words_json_path=words_json_path,
                    output_path=final_out_path,
                    style_config=caption_config,
                    video_width=res_w,
                    video_height=res_h,
                    keep_temp=keep_temp
                )
            finally:
                if temp_uncaptioned and uncaptioned_path.exists():
                    try:
                        os.remove(uncaptioned_path)
                    except OSError:
                        pass

        # Apply caption hooks if registered
        for hook in self.caption_hooks:
            final_out_path = hook(final_out_path, final_out_path)

        return segments, v_dur, a_dur, diff, was_extended, extend_by

