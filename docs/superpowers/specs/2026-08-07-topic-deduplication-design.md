# Topic Deduplication and Scenario Archiving Design

**Date:** 2026-08-07  
**Status:** Approved by User  
**Goal:** Prevent Claude from generating duplicate or repetitive video topics by persisting topic history and injecting excluded topics into Phase 1 prompt, while automatically archiving generated scripts.

---

## 1. Context & Problem
Currently, `claude_prompt.py` sends a static `PROMPT_PHASE_1` to Claude to generate 15 viral video topic ideas. Over multiple runs, Claude might suggest similar or identical topics because it has no memory of past runs. Furthermore, generated scripts overwrite `senario.txt`, leaving no historical archive of past video scripts.

---

## 2. Proposed Solution
Combine topic history tracking and output script archiving:
1. **Topic Persistence (`history_topics.txt`)**: Store all previously generated video titles in a central text file.
2. **Dynamic Exclude Injection**: In `claude_prompt.py`, dynamically read `history_topics.txt` before sending Phase 1 prompt and append a `DO NOT REPEAT` directive containing past topics.
3. **Automatic Script Archiving (`outputs/`)**: Whenever a script is generated, save it to `outputs/senario_YYYYMMDD_HHMMSS.txt` as well as updating `senario.txt`.
4. **Automatic Topic Extraction**: Extract the title (first line) of the generated script and append it to `history_topics.txt`. Also seed initial `history_topics.txt` from existing `senario.txt` if available.

---

## 3. Detailed Architecture & Workflows

### 3.1 Directory Structure
```
Text2Video/
├── claude_prompt.py
├── senario.txt                 # Latest generated script (backward compatibility)
├── history_topics.txt          # Persisted list of used titles (one per line)
└── outputs/                    # Archive directory
    ├── senario_20260807_181405.txt
    └── ...
```

### 3.2 Workflow Sequence
1. **Load History:** `claude_prompt.py` checks for `history_topics.txt`. If missing but `senario.txt` exists, it extracts the first line of `senario.txt` as the first history entry.
2. **Build Dynamic Phase 1 Prompt:**
   - Base `PROMPT_PHASE_1` text.
   - If history topics exist, append:
     ```
     ---
     PREVIOUSLY CREATED TOPICS (DO NOT REPEAT OR DUPLICATE):
     The following topics/scenarios have ALREADY been created. Do NOT generate topics that cover these same concepts, angles, or questions:
     1. [Title 1]
     2. [Title 2]
     ...
     ```
3. **Execute Automation:** Launch browser, send dynamic Phase 1 prompt, wait for response, send Phase 2 selection prompt, wait for script generation.
4. **Save Script & Update History:**
   - Extract final script text.
   - Extract title (first line).
   - Write script to `senario.txt` AND `outputs/senario_YYYYMMDD_HHMMSS.txt`.
   - Append title to `history_topics.txt` (avoiding duplicates).

---

## 4. Verification & Success Criteria
- Running `python claude_prompt.py --profile "Profile 1" --auto-followup` properly loads past titles from `history_topics.txt`.
- Claude's prompt in the browser context includes the `PREVIOUSLY CREATED TOPICS` block.
- The script generates a new topic, saves to `outputs/senario_YYYYMMDD_HHMMSS.txt` and `senario.txt`, and appends the new title to `history_topics.txt`.
