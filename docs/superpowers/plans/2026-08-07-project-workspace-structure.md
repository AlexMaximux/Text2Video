# Project Workspace Structure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement centralized project workspace management (`modules/project_manager.py`) so all scripts automatically store their inputs and outputs cleanly in self-contained directories under `projects/`.

**Architecture:** Create `modules/project_manager.py` with `resolve_project_dir()`, `create_new_project_dir()`, and `get_latest_project_dir()`. Update `claude_prompt.py`, `elevenlabs_prompt.py`, `transcribe_audio.py`, `make_final_video.py`, and `pipeline.py` to support `--project` CLI flag and default to active project directories.

**Tech Stack:** Python 3.13, `pathlib.Path`, `re`, `datetime`

## Global Constraints
- Preserve existing CLI flags and add `--project` / `-p` option across all tools.
- Auto-detect latest active project directory if `--project` is omitted in downstream scripts.
- Ensure all created directories and files use UTF-8 and proper path resolution.

---

### Task 1: Create `modules/project_manager.py` Module

**Files:**
- Create: `modules/project_manager.py`
- Modify: `modules/__init__.py`

**Interfaces:**
- Consumes: `project_name` (optional), `title_hint` (optional)
- Produces: `resolve_project_dir(...) -> Path`, `get_latest_project_dir() -> Path`, `create_new_project_dir(...) -> Path`

- [ ] **Step 1: Write `modules/project_manager.py`**

```python
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
    return slug or "Untitled"


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
```

- [ ] **Step 2: Test `project_manager.py` functions via python one-liner**

Run:
```bash
python -c "from modules.project_manager import resolve_project_dir, get_latest_project_dir; print('Resolved Latest:', get_latest_project_dir())"
```
Expected: Prints resolved latest project directory inside `projects/`.

---

### Task 2: Integrate `project_manager` into `claude_prompt.py` and `elevenlabs_prompt.py`

**Files:**
- Modify: `claude_prompt.py`
- Modify: `elevenlabs_prompt.py`

- [ ] **Step 1: Update `claude_prompt.py` to accept `--project` and output to project workspace**

Update `archive_script_output` and CLI arguments in `claude_prompt.py` to use `resolve_project_dir(args.project, auto_create_if_none=True, title_hint=first_line)`.

- [ ] **Step 2: Update `elevenlabs_prompt.py` to accept `--project` and use project input/output defaults**

Add `--project` flag to `elevenlabs_prompt.py`. Default input `project_dir / "senario.txt"` -> default output `project_dir / "voice.mp3"`.

- [ ] **Step 3: Verify CLI help for `claude_prompt.py` and `elevenlabs_prompt.py`**

Run:
```bash
python claude_prompt.py --help
python elevenlabs_prompt.py --help
```
Expected: Shows `--project` option in help output.

---

### Task 3: Integrate `project_manager` into `transcribe_audio.py`, `make_final_video.py`, and `pipeline.py`

**Files:**
- Modify: `transcribe_audio.py`
- Modify: `make_final_video.py`
- Modify: `pipeline.py`
- Modify: `myOwnreadme.mt`

- [ ] **Step 1: Update `transcribe_audio.py` to use `--project`**

Add `--project` flag to `transcribe_audio.py`. Default audio `project_dir / "voice.mp3"`, transcript `project_dir / "transcript.txt"`, words `project_dir / "words.json"`.

- [ ] **Step 2: Update `make_final_video.py` to use `--project`**

Add `--project` flag to `make_final_video.py`. Default images `project_dir / "images"`, audio `project_dir / "voice.mp3"`, transcript `project_dir / "transcript.txt"`, words `project_dir / "words.json"`, output `project_dir / "final_video.mp4"`.

- [ ] **Step 3: Update `pipeline.py` to use `--project`**

Add `--project` flag to `pipeline.py`. Passes `--project` to all underlying scripts.

- [ ] **Step 4: Update `myOwnreadme.mt` documentation**

Update `myOwnreadme.mt` with clean project workspace commands.
