# Topic Deduplication and Scenario Archiving Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement topic history tracking and automatic script archiving in `claude_prompt.py` to prevent Claude from generating repetitive topics and keep a full archive of generated video scripts.

**Architecture:** Add helper functions in `claude_prompt.py` (`load_history_topics`, `append_history_topic`, `archive_script_output`) to load past titles from `history_topics.txt` (or fallback to existing `senario.txt`), inject them into `PROMPT_PHASE_1`, archive generated scripts to `outputs/senario_YYYYMMDD_HHMMSS.txt`, and update `history_topics.txt`.

**Tech Stack:** Python 3.13, `pathlib.Path`, `datetime`, `asyncio`, `browser2api`

## Global Constraints

- Preserve all existing CLI arguments and functionality of `claude_prompt.py`.
- Continue writing/updating `senario.txt` as the default output file for backward compatibility.
- Ensure proper UTF-8 encoding when reading/writing text files.

---

### Task 1: Add History Helper Functions and Output Archiving to `claude_prompt.py`

**Files:**
- Modify: `claude_prompt.py`

**Interfaces:**
- Consumes: `history_topics.txt`, `senario.txt`
- Produces: `load_history_topics() -> list[str]`, `append_history_topic(title: str)`, `archive_script_output(script_text: str, output_file: str) -> tuple[Path, Path]`

- [ ] **Step 1: Write helper functions for topic history and script archiving in `claude_prompt.py`**

Add the following functions to `claude_prompt.py`:

```python
from datetime import datetime

HISTORY_FILE = Path("history_topics.txt")
OUTPUTS_DIR = Path("outputs")


def load_history_topics() -> list[str]:
    """Load previously generated topic titles from history_topics.txt.
    Fallback to extracting the title from senario.txt if history_topics.txt does not exist.
    """
    topics = []
    if HISTORY_FILE.exists():
        for line in HISTORY_FILE.read_text(encoding="utf-8").splitlines():
            line_clean = line.strip()
            if line_clean and line_clean not in topics:
                topics.append(line_clean)
    elif Path("senario.txt").exists():
        try:
            content = Path("senario.txt").read_text(encoding="utf-8").strip()
            first_line = content.splitlines()[0].strip() if content else ""
            if first_line:
                topics.append(first_line)
                # Seed history file
                HISTORY_FILE.write_text(f"{first_line}\n", encoding="utf-8")
        except Exception:
            pass

    return topics


def append_history_topic(title: str):
    """Append a new title to history_topics.txt if not already present."""
    if not title:
        return
    existing = load_history_topics()
    if title not in existing:
        with HISTORY_FILE.open("a", encoding="utf-8") as f:
            f.write(f"{title}\n")


def build_phase_1_prompt() -> str:
    """Build Phase 1 prompt with dynamic exclusion of past topics."""
    history = load_history_topics()
    prompt = PROMPT_PHASE_1
    if history:
        history_list = "\n".join(f"- {topic}" for topic in history)
        prompt += f"\n\n---\n\nPREVIOUSLY CREATED TOPICS (DO NOT REPEAT OR DUPLICATE):\nThe following topics/scenarios have ALREADY been created. Do NOT generate topics that cover these same concepts, angles, or questions:\n{history_list}"
    return prompt


def archive_script_output(script_text: str, output_file: str = "senario.txt") -> tuple[Path, Path]:
    """Save generated script to output_file and archive a timestamped copy in outputs/ directory.
    Also update history_topics.txt with the script title (first line).
    """
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_path = OUTPUTS_DIR / f"senario_{timestamp}.txt"
    main_path = Path(output_file)

    # Save to main output file and archive copy
    main_path.write_text(script_text, encoding="utf-8")
    archive_path.write_text(script_text, encoding="utf-8")

    # Extract title (first line) and record in history
    first_line = script_text.strip().splitlines()[0].strip() if script_text else ""
    if first_line:
        append_history_topic(first_line)

    return main_path, archive_path
```

Update `open_claude_and_run_workflow` to use `build_phase_1_prompt()` instead of raw `PROMPT_PHASE_1`, and use `archive_script_output(script_text, output_file)` after script generation.

- [ ] **Step 2: Test helper functions via dry-run script test**

Run a python command to verify `load_history_topics()` seeds from `senario.txt` and `build_phase_1_prompt()` appends past topics properly.

Run:
```bash
python -c "from claude_prompt import load_history_topics, build_phase_1_prompt; print('Loaded topics:', load_history_topics()); print('\nPrompt preview:\n', build_phase_1_prompt()[-300:])"
```
Expected output: Shows the title loaded from `senario.txt` and included in the prompt preview.

- [ ] **Step 3: Test full execution with browser automation**

Run:
```bash
python claude_prompt.py --profile "Profile 1" --auto-followup
```
Expected output:
- `history_topics.txt` created/updated with topic title.
- Archived file `outputs/senario_YYYYMMDD_HHMMSS.txt` created.
- `senario.txt` updated.

- [ ] **Step 4: Verify outputs directory and history_topics.txt**

Check that `history_topics.txt` contains the video title and `outputs/` contains the archived timestamped script.
