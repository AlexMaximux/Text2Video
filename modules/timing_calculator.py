"""
Timing Calculator Module
Handles numerical sorting of image files, mapping timestamps to image sequences,
and calculating individual image display durations.
"""
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple, Union


class MismatchWarning(Exception):
    """Raised when timestamp count and image count do not match."""
    def __init__(self, timestamps_count: int, images_count: int):
        self.timestamps_count = timestamps_count
        self.images_count = images_count
        super().__init__(
            f"Mismatch detected: {timestamps_count} timestamp(s) vs {images_count} image(s)."
        )


@dataclass
class ImageSegment:
    image_path: str
    start_time: float
    duration: float

    @property
    def end_time(self) -> float:
        return self.start_time + self.duration


def extract_numerical_key(file_path: Union[str, Path]) -> Tuple[int, str]:
    """
    Extracts numerical value from filename stem for numeric sorting.
    Returns (number, original_stem) tuple so files without numbers sort lexically.
    """
    stem = Path(file_path).stem
    digits = re.findall(r'\d+', stem)
    if digits:
        # Use the first block of digits for numerical sorting
        return (int(digits[0]), stem)
    return (99999999, stem)


def get_sorted_images(images_dir: Union[str, Path]) -> List[Path]:
    """
    Finds all images (.jpg, .jpeg, .png) in directory and sorts them by numerical filename value.
    """
    dir_path = Path(images_dir)
    if not dir_path.is_dir():
        raise FileNotFoundError(f"Images directory not found: '{images_dir}'")

    valid_extensions = {'.jpg', '.jpeg', '.png'}
    image_files = [
        f for f in dir_path.iterdir()
        if f.is_file() and f.suffix.lower() in valid_extensions
    ]

    if not image_files:
        raise FileNotFoundError(f"No valid image files (.jpg, .jpeg, .png) found in '{images_dir}'")

    image_files.sort(key=extract_numerical_key)
    return image_files


def calculate_timings(
    timestamps: List[float],
    image_paths: List[Union[str, Path]],
    total_duration: Optional[float] = None,
    fallback_duration: Optional[float] = None,
    on_mismatch: str = "ask"
) -> List[ImageSegment]:
    """
    Maps timestamps to image paths and calculates durations for each segment.

    Parameters:
      - timestamps: List of timestamps in seconds.
      - image_paths: List of image file paths (should be numerically sorted).
      - total_duration: Optional total duration fallback for the last image.
      - fallback_duration: Optional specific fallback duration for the last image.
      - on_mismatch: Action when len(timestamps) != len(image_paths): 'ask', 'truncate', or 'error'.
    """
    n_stamps = len(timestamps)
    n_images = len(image_paths)

    if n_stamps == 0 or n_images == 0:
        raise ValueError("Both timestamps and image_paths must be non-empty.")

    if n_stamps != n_images:
        if on_mismatch == "error":
            raise ValueError(f"Timestamp count ({n_stamps}) does not match image count ({n_images}).")
        elif on_mismatch == "ask":
            raise MismatchWarning(timestamps_count=n_stamps, images_count=n_images)
        elif on_mismatch in ("truncate", "adapt", "ignore"):
            k = min(n_stamps, n_images)
            timestamps = timestamps[:k]
            image_paths = image_paths[:k]
        elif on_mismatch in ("pad", "repeat", "stretch"):
            if n_images < n_stamps:
                last_img = image_paths[-1]
                image_paths = list(image_paths) + [last_img] * (n_stamps - n_images)
            else:
                k = min(n_stamps, n_images)
                timestamps = timestamps[:k]
                image_paths = image_paths[:k]
        else:
            raise ValueError(f"Invalid on_mismatch mode: '{on_mismatch}'")

    segments: List[ImageSegment] = []
    k = len(timestamps)

    for i in range(k):
        img_path = str(Path(image_paths[i]).resolve())
        start_t = timestamps[i]

        if i < k - 1:
            dur = timestamps[i + 1] - start_t
            if dur <= 0:
                raise ValueError(
                    f"Invalid non-positive duration ({dur}s) between timestamp {i} ({timestamps[i]}s) "
                    f"and timestamp {i+1} ({timestamps[i+1]}s)."
                )
        else:
            # Last image duration logic
            if total_duration is not None and total_duration > start_t:
                dur = total_duration - start_t
            elif fallback_duration is not None and fallback_duration > 0:
                dur = fallback_duration
            elif k > 1:
                # Use duration of previous segment
                dur = timestamps[-1] - timestamps[-2]
            else:
                dur = 3.0

        segments.append(ImageSegment(image_path=img_path, start_time=start_t, duration=dur))

    return segments
