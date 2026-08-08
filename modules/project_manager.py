"""Project Workspace Manager Module
Handles creation and resolution of dedicated project output directories under projects/
"""

import re
from datetime import datetime
from pathlib import Path
from typing import Optional

PROJECTS_DIR = Path("projects")


def slugify(text: str, max_words: int = 4) -> str:
    """Convert title string into clean folder name slug."""
    text_clean = re.sub(r"[^\w\s-]", "", text).strip()
    words = text_clean.split()[:max_words]
    slug = "_".join(words)
    return slug or "Scenario"


def get_projects_dir() -> Path:
    """Ensure projects/ base directory exists and return it."""
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    return PROJECTS_DIR.resolve()


def create_new_project_dir(project_name: Optional[str] = None, title_hint: Optional[str] = None) -> Path:
    """Create a new project directory inside projects/."""
    base_dir = get_projects_dir()

    if project_name:
        clean_name = re.sub(r"[^\w\s-]", "", project_name).strip().replace(" ", "_")
        proj_path = base_dir / clean_name
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        slug = slugify(title_hint) if title_hint else "Scenario"
        proj_path = base_dir / f"Video_{timestamp}_{slug}"

    proj_path.mkdir(parents=True, exist_ok=True)
    return proj_path.resolve()


def get_latest_project_dir() -> Path:
    """Find the most recently modified project directory inside projects/."""
    base_dir = get_projects_dir()
    subdirs = [p for p in base_dir.iterdir() if p.is_dir() and not p.name.startswith(".")]
    if subdirs:
        subdirs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return subdirs[0].resolve()

    # Fallback if no project folder exists yet
    return create_new_project_dir(title_hint="Default")


def resolve_project_dir(
    project_arg: Optional[str] = None,
    auto_create_if_none: bool = False,
    title_hint: Optional[str] = None
) -> Path:
    """Resolve active project directory."""
    if project_arg:
        base_dir = get_projects_dir()
        proj_path = base_dir / project_arg
        proj_path.mkdir(parents=True, exist_ok=True)
        return proj_path.resolve()

    if auto_create_if_none:
        return create_new_project_dir(title_hint=title_hint)

    return get_latest_project_dir()
