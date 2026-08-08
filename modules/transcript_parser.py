"""
Transcript Parser Module
Extracts timestamp markers from text files using flexible regex matching.
"""
import re
from pathlib import Path
from typing import List, Union


def parse_timestamp_str(timestamp_str: str) -> float:
    """
    Converts a timestamp string (e.g., '0:05', '01:23', '01:02:03', '0:15.50')
    into total seconds as a float.
    """
    parts = timestamp_str.strip().split(':')
    if len(parts) == 1:
        # Seconds only
        return float(parts[0])
    elif len(parts) == 2:
        # Minutes:Seconds
        minutes = float(parts[0])
        seconds = float(parts[1])
        return minutes * 60.0 + seconds
    elif len(parts) == 3:
        # Hours:Minutes:Seconds
        hours = float(parts[0])
        minutes = float(parts[1])
        seconds = float(parts[2])
        return hours * 3600.0 + minutes * 60.0 + seconds
    else:
        raise ValueError(f"Invalid timestamp format: '{timestamp_str}'")


def parse_transcript(input_source: Union[str, Path]) -> List[float]:
    """
    Parses a transcript file path or transcript content string and extracts all timestamps in seconds.
    Timestamps are expected inside brackets, e.g. [0:05], [01:20], [01:05:30.5].

    Returns a sorted list of timestamps in seconds.
    """
    content = ""
    if isinstance(input_source, Path):
        content = input_source.read_text(encoding='utf-8')
    elif isinstance(input_source, str):
        path = Path(input_source)
        if path.is_file():
            content = path.read_text(encoding='utf-8')
        else:
            content = input_source

    # Pattern matches bracketed timestamps like [0:05], [00:12:34], [1:02.500]
    pattern = r'\[(\d{1,2}(?::\d{1,2})+(?:\.\d+)?)\]'
    matches = re.findall(pattern, content)

    if not matches:
        raise ValueError("No valid timestamps found in transcript.")

    timestamps = [parse_timestamp_str(m) for m in matches]
    # Return sorted timestamps
    timestamps.sort()
    return timestamps
