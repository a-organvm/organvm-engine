# Fossil Phase 2: The Chronicle — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate Jungian-voiced narrative chronicles from the fossil record — one per epoch, telling the system's story through archetypal patterns.

**Architecture:** Two new files in `fossil/`: `narrator.py` (template engine + statistics) and chronicle markdown output. CLI extension to `cli/fossil.py`. Templates use Python f-strings with slot-filling from computed epoch statistics.

**Tech Stack:** Python 3.11+, dataclasses, collections.Counter, pathlib. Reads `fossil-record.jsonl`. No new dependencies.

**Spec:** `.claude/plans/2026-03-22-fossil-living-stratigraphy.md` (Section 6: The Narrator)

---

## File Structure

| File | Responsibility |
|------|---------------|
| **Create:** `src/organvm_engine/fossil/narrator.py` | Epoch statistics, Jungian vocabulary, narrative template engine, chronicle generation |
| **Create:** `tests/test_fossil_narrator.py` | Tests for statistics, vocabulary, narrative generation |
| **Modify:** `src/organvm_engine/cli/fossil.py` | Add `cmd_fossil_chronicle` handler |
| **Modify:** `src/organvm_engine/cli/__init__.py` | Wire `chronicle` subcommand |
| **Modify:** `src/organvm_engine/fossil/__init__.py` | Export narrator public API |

---

### Task 1: Narrator — Statistics + Vocabulary + Generator

**Files:**
- Create: `src/organvm_engine/fossil/narrator.py`
- Create: `tests/test_fossil_narrator.py`

The narrator has three layers:

**Layer 1: Epoch Statistics** — compute from fossil records:
```python
@dataclass
class EpochStats:
    epoch_id: str
    epoch_name: str
    start: date
    end: date
    commit_count: int
    repos_touched: list[str]
    organs_touched: list[str]
    archetype_distribution: dict[Archetype, int]
    dominant_archetype: Archetype
    secondary_archetype: Archetype | None
    top_repos: list[tuple[str, int]]  # (repo_name, commit_count) top 5
    insertions: int
    deletions: int
    trickster_ratio: float  # fraction of commits with Trickster primary
    busiest_hour: int  # 0-23, most commits
    authors: list[str]
```

**Layer 2: Jungian Vocabulary** — per-archetype narrative fragments:
```python
ARCHETYPE_VOICE = {
    Archetype.SHADOW: {
        "verbs": ["stirs", "surfaces", "demands acknowledgment", "confronts"],
        "nouns": ["debt", "neglect", "the avoided", "what was hidden"],
        "tone": "The Shadow {verb} in {organ} — {detail}.",
    },
    Archetype.ANIMA: {
        "verbs": ["seizes", "flows", "emerges", "dreams"],
        ...
    },
    ...
}
```

**Layer 3: Narrative Generator** — produces markdown chronicle per epoch:
```python
def generate_epoch_chronicle(stats: EpochStats, records: list[FossilRecord]) -> str:
    """Generate a Jungian-voiced markdown chronicle for one epoch."""
```

The generator:
1. Opens with the dominant archetype speaking: "The {archetype} {verb} the organism."
2. Describes the epoch's character: duration, commit count, repos touched
3. Notes the secondary archetype's presence
4. Calls out Trickster moments if ratio > 0.1
5. Notes Shadow presence if significant
6. Closes with what the epoch left behind (mutations, unfinished business)

Tests should cover:
- `compute_epoch_stats()` with fixture records
- Vocabulary lookup for each archetype
- `generate_epoch_chronicle()` produces non-empty markdown with key elements
- Full `generate_all_chronicles()` produces one file per epoch

---

### Task 2: CLI + Wiring

**Files:**
- Modify: `src/organvm_engine/cli/fossil.py` — add `cmd_fossil_chronicle`
- Modify: `src/organvm_engine/cli/__init__.py` — add `chronicle` subcommand
- Modify: `src/organvm_engine/fossil/__init__.py` — export new functions

CLI: `organvm fossil chronicle [--epoch EPOCH_ID] [--regenerate] [--write]`
- Default: generate chronicles for all epochs
- `--epoch`: generate for one specific epoch
- `--regenerate`: overwrite existing chronicles
- `--write`: actually write files (dry-run default)
- Output: `data/fossil/chronicle/EPOCH-NNN-slug.md` per epoch

---

### Task 3: Integration Test

Test with real `fossil-record.jsonl` (or fixture subset) — generate chronicles, verify markdown structure, verify all 12 epochs get files.
