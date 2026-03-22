# Fossil Phase 1: The Dig — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Crawl git history across all ~108 workspace repos, classify each commit by Jungian archetype, and produce a hash-linked `fossil-record.jsonl` with the complete stratigraphy of the system.

**Architecture:** New `fossil/` domain module with 4 source files (stratum, classifier, epochs, excavator) + 1 CLI module + package init. Follows the existing `irf/` module pattern: typed dataclasses, public API in `__init__.py`, CLI handler in `cli/fossil.py`. Git operations via `subprocess.run`. Zero new external dependencies.

**Tech Stack:** Python 3.11+, dataclasses, subprocess, json, hashlib, re, pathlib. Existing imports: `organ_config.py` (organ mapping), `paths.py` (workspace root).

**Spec:** `.claude/plans/2026-03-22-fossil-living-stratigraphy.md`

---

## File Structure

| File | Responsibility |
|------|---------------|
| **Create:** `src/organvm_engine/fossil/__init__.py` | Package init, public API exports |
| **Create:** `src/organvm_engine/fossil/stratum.py` | Data models: `FossilRecord`, `Archetype`, `Provenance`, serialization, hash-linking, query functions |
| **Create:** `src/organvm_engine/fossil/classifier.py` | Jungian archetype classifier: commit-level keyword/heuristic classification |
| **Create:** `src/organvm_engine/fossil/epochs.py` | Epoch definitions (declared + detected), session boundary detection |
| **Create:** `src/organvm_engine/fossil/excavator.py` | Git history crawler: walks repos, parses commits, yields `FossilRecord` objects |
| **Create:** `src/organvm_engine/cli/fossil.py` | CLI handlers: `cmd_fossil_excavate`, `cmd_fossil_stratum`, `cmd_fossil_epochs` |
| **Modify:** `src/organvm_engine/cli/__init__.py` | Wire `fossil` command group into argparse |
| **Modify:** `src/organvm_engine/paths.py` | Add `fossil_dir()` and `fossil_record_path()` helpers |
| **Create:** `tests/test_fossil_stratum.py` | Tests for data models, serialization, hash-linking |
| **Create:** `tests/test_fossil_classifier.py` | Tests for archetype classification |
| **Create:** `tests/test_fossil_epochs.py` | Tests for epoch detection and session boundaries |
| **Create:** `tests/test_fossil_excavator.py` | Tests for git history crawling (uses fixture repos) |
| **Create:** `tests/fixtures/fossil/` | Fixture data for fossil tests |

---

### Task 1: Stratum Data Models

**Files:**
- Create: `src/organvm_engine/fossil/stratum.py`
- Create: `src/organvm_engine/fossil/__init__.py`
- Create: `tests/test_fossil_stratum.py`

- [ ] **Step 1: Write failing tests for data models**

```python
# tests/test_fossil_stratum.py
"""Tests for fossil stratum data models."""

from datetime import datetime, timezone

from organvm_engine.fossil.stratum import (
    Archetype,
    FossilRecord,
    Provenance,
    compute_record_hash,
    serialize_record,
    deserialize_record,
)


def test_archetype_enum_has_eight_members():
    assert len(Archetype) == 8
    assert Archetype.SHADOW in Archetype
    assert Archetype.ANIMA in Archetype
    assert Archetype.ANIMUS in Archetype
    assert Archetype.SELF in Archetype
    assert Archetype.TRICKSTER in Archetype
    assert Archetype.MOTHER in Archetype
    assert Archetype.FATHER in Archetype
    assert Archetype.INDIVIDUATION in Archetype


def test_provenance_enum():
    assert Provenance.WITNESSED.value == "witnessed"
    assert Provenance.RECONSTRUCTED.value == "reconstructed"
    assert Provenance.ATTESTED.value == "attested"


def test_fossil_record_creation():
    record = FossilRecord(
        commit_sha="abc1234",
        timestamp=datetime(2026, 3, 20, 12, 0, tzinfo=timezone.utc),
        author="test",
        organ="META",
        repo="organvm-engine",
        message="feat: add omega criterion #19",
        conventional_type="feat",
        files_changed=3,
        insertions=120,
        deletions=5,
        archetypes=[Archetype.SELF, Archetype.ANIMUS],
        provenance=Provenance.RECONSTRUCTED,
        session_id=None,
        epoch=None,
        tags=["omega", "testament"],
        prev_hash="",
    )
    assert record.organ == "META"
    assert record.archetypes[0] == Archetype.SELF


def test_serialize_deserialize_roundtrip():
    record = FossilRecord(
        commit_sha="abc1234",
        timestamp=datetime(2026, 3, 20, 12, 0, tzinfo=timezone.utc),
        author="test",
        organ="I",
        repo="recursive-engine",
        message="fix: lint errors",
        conventional_type="fix",
        files_changed=1,
        insertions=2,
        deletions=2,
        archetypes=[Archetype.SHADOW],
        provenance=Provenance.RECONSTRUCTED,
        session_id="S28",
        epoch="EPOCH-011",
        tags=["lint"],
        prev_hash="0000",
    )
    json_str = serialize_record(record)
    restored = deserialize_record(json_str)
    assert restored.commit_sha == record.commit_sha
    assert restored.archetypes == record.archetypes
    assert restored.timestamp == record.timestamp


def test_hash_linking():
    r1 = FossilRecord(
        commit_sha="aaa",
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        author="test", organ="I", repo="test-repo",
        message="first", conventional_type="feat",
        files_changed=1, insertions=1, deletions=0,
        archetypes=[Archetype.ANIMA],
        provenance=Provenance.RECONSTRUCTED,
        session_id=None, epoch=None, tags=[], prev_hash="",
    )
    h1 = compute_record_hash(r1)
    assert len(h1) == 64  # SHA256 hex

    r2 = FossilRecord(
        commit_sha="bbb",
        timestamp=datetime(2026, 1, 2, tzinfo=timezone.utc),
        author="test", organ="I", repo="test-repo",
        message="second", conventional_type="fix",
        files_changed=1, insertions=1, deletions=1,
        archetypes=[Archetype.SHADOW],
        provenance=Provenance.RECONSTRUCTED,
        session_id=None, epoch=None, tags=[], prev_hash=h1,
    )
    h2 = compute_record_hash(r2)
    assert h2 != h1  # different content = different hash
    assert r2.prev_hash == h1  # chain link
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_fossil_stratum.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'organvm_engine.fossil'`

- [ ] **Step 3: Implement stratum module**

Create `src/organvm_engine/fossil/__init__.py`:

```python
"""fossil — Archaeological reconstruction of ORGANVM system history.

Crawls git history across all workspace repos, classifies commits by
Jungian archetype, and produces a hash-linked fossil record.

Public API::

    from organvm_engine.fossil import (
        Archetype, FossilRecord, Provenance,
        classify_commit, excavate,
    )
"""
```

Create `src/organvm_engine/fossil/stratum.py`:

```python
"""Stratum — data models for the fossil record.

FossilRecord is the atomic unit: one commit, normalized, classified,
and hash-linked to the previous record for tamper evidence.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum


class Archetype(str, Enum):
    """Jungian archetypes for classifying system activity."""
    SHADOW = "shadow"
    ANIMA = "anima"
    ANIMUS = "animus"
    SELF = "self"
    TRICKSTER = "trickster"
    MOTHER = "mother"
    FATHER = "father"
    INDIVIDUATION = "individuation"


class Provenance(str, Enum):
    """How the record was obtained."""
    WITNESSED = "witnessed"
    RECONSTRUCTED = "reconstructed"
    ATTESTED = "attested"


@dataclass
class FossilRecord:
    """One commit, normalized and classified."""
    commit_sha: str
    timestamp: datetime
    author: str
    organ: str
    repo: str
    message: str
    conventional_type: str
    files_changed: int
    insertions: int
    deletions: int
    archetypes: list[Archetype]
    provenance: Provenance
    session_id: str | None
    epoch: str | None
    tags: list[str]
    prev_hash: str


def compute_record_hash(record: FossilRecord) -> str:
    """SHA256 of the record's content for chain linking."""
    content = (
        f"{record.commit_sha}|{record.timestamp.isoformat()}"
        f"|{record.organ}|{record.repo}|{record.message}"
        f"|{record.prev_hash}"
    )
    return hashlib.sha256(content.encode()).hexdigest()


def serialize_record(record: FossilRecord) -> str:
    """Serialize to a single JSON line."""
    d = asdict(record)
    d["timestamp"] = record.timestamp.isoformat()
    d["archetypes"] = [a.value for a in record.archetypes]
    d["provenance"] = record.provenance.value
    return json.dumps(d, separators=(",", ":"))


def deserialize_record(line: str) -> FossilRecord:
    """Deserialize from a JSON line."""
    d = json.loads(line)
    d["timestamp"] = datetime.fromisoformat(d["timestamp"])
    d["archetypes"] = [Archetype(a) for a in d["archetypes"]]
    d["provenance"] = Provenance(d["provenance"])
    return FossilRecord(**d)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_fossil_stratum.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/organvm_engine/fossil/__init__.py src/organvm_engine/fossil/stratum.py tests/test_fossil_stratum.py
git commit -m "feat(fossil): stratum data models — FossilRecord, Archetype, Provenance, hash-linking"
```

---

### Task 2: Archetype Classifier

**Files:**
- Create: `src/organvm_engine/fossil/classifier.py`
- Create: `tests/test_fossil_classifier.py`

- [ ] **Step 1: Write failing tests for classifier**

```python
# tests/test_fossil_classifier.py
"""Tests for Jungian archetype classifier."""

from organvm_engine.fossil.classifier import classify_commit
from organvm_engine.fossil.stratum import Archetype


def test_shadow_from_fix():
    result = classify_commit("fix: remediate 103 ESLint errors", "fix", "growth-auditor", "III")
    assert result[0] == Archetype.SHADOW


def test_shadow_from_security():
    result = classify_commit("chore: security remediation", "chore", "portfolio", "LIMINAL")
    assert result[0] == Archetype.SHADOW


def test_anima_creative_repo():
    result = classify_commit("feat: Bestiary v1 — 12 mythological beings", "feat", "vigiles-aeternae--theatrum-mundi", "II")
    assert result[0] == Archetype.ANIMA


def test_animus_governance():
    result = classify_commit("feat: temporal versioning for dependency graph", "feat", "organvm-engine", "META")
    assert result[0] == Archetype.ANIMUS


def test_self_testament():
    result = classify_commit("feat: testament self-referential event types", "feat", "organvm-engine", "META")
    assert result[0] == Archetype.SELF


def test_trickster_short_message():
    result = classify_commit("onnwards+upwards;", "", "some-repo", "I")
    assert result[0] == Archetype.TRICKSTER


def test_trickster_no_conventional_prefix():
    result = classify_commit("yolo", "", "some-repo", "II")
    assert result[0] == Archetype.TRICKSTER


def test_mother_ci():
    result = classify_commit("fix: resolve 6 pre-existing BATS CI failures", "fix", "domus", "LIMINAL")
    assert Archetype.MOTHER in result[:2]


def test_father_governance_gate():
    result = classify_commit("feat: individual primacy governance check", "feat", "organvm-engine", "META")
    assert Archetype.FATHER in result[:2]


def test_individuation_cross_organ():
    result = classify_commit(
        "feat: outbound contribution engine", "feat",
        "orchestration-start-here", "IV",
    )
    assert Archetype.INDIVIDUATION in result[:2]


def test_returns_ranked_list():
    result = classify_commit("feat: add omega criterion #19", "feat", "organvm-engine", "META")
    assert isinstance(result, list)
    assert len(result) >= 1
    assert all(isinstance(a, Archetype) for a in result)


def test_context_sync_is_self():
    result = classify_commit("chore: context sync — refresh auto-generated context files", "chore", "some-repo", "I")
    assert result[0] == Archetype.SELF
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_fossil_classifier.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement classifier**

Create `src/organvm_engine/fossil/classifier.py`:

```python
"""Jungian archetype classifier for commit messages.

Three-tier classification:
  1. Commit-level: keyword + heuristic → ranked archetype list
  2. Session-level: dominant archetype from commit distribution (not in this file)
  3. Epoch-level: narrative arc from archetype sequence (not in this file)
"""

from __future__ import annotations

import re

from organvm_engine.fossil.stratum import Archetype

# Creative repos where 'feat:' likely means Anima, not Animus
_CREATIVE_REPOS = frozenset({
    "metasystem-master", "a-mavs-olevm", "krypto-velamen",
    "chthon-oneiros", "alchemical-synthesizer", "styx-behavioral-art",
    "vigiles-aeternae--theatrum-mundi", "vigiles-aeternae--corpus-mythicum",
    "materia-collider", "object-lessons",
})

# Keyword → archetype mapping, checked in order
_PATTERNS: list[tuple[Archetype, re.Pattern[str]]] = [
    (Archetype.SHADOW, re.compile(
        r"fix:|security|remediat|(?<!\w)debt|lint\b|error|vulnerab|remove|delete|clean|deprecat",
        re.IGNORECASE,
    )),
    (Archetype.SELF, re.compile(
        r"testament|self-referent|context.sync|scorecard|registry.update|omega|system.density|auto-refresh|soak.test|network.map",
        re.IGNORECASE,
    )),
    (Archetype.TRICKSTER, re.compile(
        r"^.{0,5}$",  # messages <= 5 chars
    )),
    (Archetype.FATHER, re.compile(
        r"governance|promot|gate\b|enforce|constraint|rule\b|protect|permission|branch.protect|descent.protocol",
        re.IGNORECASE,
    )),
    (Archetype.MOTHER, re.compile(
        r"\bCI\b|test:|infra|docker|deploy|environment|dotfile|domus|LaunchAgent|setup|install|chezmoi|\bbats\b|workflow|dependabot",
        re.IGNORECASE,
    )),
    (Archetype.INDIVIDUATION, re.compile(
        r"cross-organ|contrib|atoms.pipeline|network.testament|outbound|syndication",
        re.IGNORECASE,
    )),
    (Archetype.ANIMUS, re.compile(
        r"feat:.*(?:governance|proof|formal|state.machine|schema|validat|type|dependency.graph|temporal|versioning|taxonomy|formation|signal)",
        re.IGNORECASE,
    )),
    (Archetype.ANIMA, re.compile(
        r"feat:.*(?:art|narrative|generat|visual|audio|essay|bestiary|worldbuild|character|mythology|corpus|research|paper|draft|synthesis)",
        re.IGNORECASE,
    )),
]


def classify_commit(
    message: str,
    conventional_type: str,
    repo: str,
    organ: str,
) -> list[Archetype]:
    """Classify a commit message into a ranked list of Jungian archetypes.

    Returns at least one archetype. Primary archetype is first.
    """
    scores: dict[Archetype, float] = {a: 0.0 for a in Archetype}

    # Trickster: short or non-conventional messages
    if len(message.strip()) <= 5 or (
        conventional_type == ""
        and not any(message.startswith(p) for p in ("Merge ", "Revert "))
    ):
        scores[Archetype.TRICKSTER] += 3.0

    # Pattern matching
    for archetype, pattern in _PATTERNS:
        if archetype == Archetype.TRICKSTER:
            continue  # already handled above
        if pattern.search(message):
            scores[archetype] += 2.0

    # Repo context boost
    if repo in _CREATIVE_REPOS or organ == "II":
        scores[Archetype.ANIMA] += 1.0

    # Organ context
    if organ == "IV":
        scores[Archetype.INDIVIDUATION] += 0.5
    if organ in ("META",):
        scores[Archetype.SELF] += 0.5

    # Conventional type fallback
    if conventional_type == "fix" and scores[Archetype.SHADOW] < 1.0:
        scores[Archetype.SHADOW] += 1.5
    if conventional_type == "test" or conventional_type == "chore":
        scores[Archetype.MOTHER] += 0.8
    if conventional_type == "feat" and max(scores.values()) < 1.0:
        # Unclassified feat: default to Animus (structural)
        scores[Archetype.ANIMUS] += 0.5

    # Rank by score, filter zeros
    ranked = sorted(
        ((a, s) for a, s in scores.items() if s > 0),
        key=lambda x: x[1],
        reverse=True,
    )

    if not ranked:
        return [Archetype.MOTHER]  # fallback: infrastructure work

    return [a for a, _ in ranked]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_fossil_classifier.py -v`
Expected: All 13 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/organvm_engine/fossil/classifier.py tests/test_fossil_classifier.py
git commit -m "feat(fossil): Jungian archetype classifier — 8 archetypes, keyword+heuristic scoring"
```

---

### Task 3: Epoch Definitions

**Files:**
- Create: `src/organvm_engine/fossil/epochs.py`
- Create: `tests/test_fossil_epochs.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_fossil_epochs.py
"""Tests for epoch definitions and session boundary detection."""

from datetime import datetime, timedelta, timezone

from organvm_engine.fossil.epochs import (
    DECLARED_EPOCHS,
    Epoch,
    assign_epoch,
    detect_session_boundaries,
)


def test_declared_epochs_exist():
    assert len(DECLARED_EPOCHS) >= 10
    names = [e.name for e in DECLARED_EPOCHS]
    assert "Genesis" in names
    assert "Launch" in names


def test_assign_epoch_by_date():
    # A commit on launch day should be in the Launch epoch
    dt = datetime(2026, 2, 11, 12, 0, tzinfo=timezone.utc)
    epoch = assign_epoch(dt)
    assert epoch is not None
    assert epoch.name == "Launch"


def test_assign_epoch_before_genesis():
    dt = datetime(2025, 1, 1, tzinfo=timezone.utc)
    epoch = assign_epoch(dt)
    assert epoch is None


def test_session_boundary_detection():
    base = datetime(2026, 3, 20, 10, 0, tzinfo=timezone.utc)
    timestamps = [
        base,
        base + timedelta(minutes=10),
        base + timedelta(minutes=30),
        # gap of 2 hours
        base + timedelta(hours=3),
        base + timedelta(hours=3, minutes=15),
    ]
    sessions = detect_session_boundaries(timestamps, gap_minutes=90)
    assert len(sessions) == 2
    assert len(sessions[0]) == 3  # first three commits
    assert len(sessions[1]) == 2  # last two commits


def test_session_single_commit():
    timestamps = [datetime(2026, 3, 20, 10, 0, tzinfo=timezone.utc)]
    sessions = detect_session_boundaries(timestamps, gap_minutes=90)
    assert len(sessions) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_fossil_epochs.py -v`
Expected: FAIL

- [ ] **Step 3: Implement epochs module**

Create `src/organvm_engine/fossil/epochs.py`:

```python
"""Epoch definitions and session boundary detection.

Epochs are the geological periods of the system's history.
Sessions are work bursts within epochs.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from organvm_engine.fossil.stratum import Archetype


@dataclass
class Epoch:
    """A geological period in the system's history."""
    id: str
    name: str
    start: date
    end: date
    dominant_archetype: Archetype
    secondary_archetype: Archetype | None = None
    description: str = ""


DECLARED_EPOCHS: list[Epoch] = [
    Epoch("EPOCH-001", "Genesis", date(2026, 1, 22), date(2026, 2, 7),
          Archetype.SELF, None,
          "The prima materia — repos exist but the system doesn't know it's a system yet"),
    Epoch("EPOCH-002", "The Naming", date(2026, 2, 8), date(2026, 2, 9),
          Archetype.FATHER, None,
          "8 organs named, env vars set, the ontology declared"),
    Epoch("EPOCH-003", "The Bronze Sprint", date(2026, 2, 10), date(2026, 2, 10),
          Archetype.MOTHER, None,
          "7 flagships documented, foundations laid"),
    Epoch("EPOCH-004", "The Silver Sprint", date(2026, 2, 10), date(2026, 2, 11),
          Archetype.ANIMUS, None,
          "58 READMEs, 202K words, cross-validation"),
    Epoch("EPOCH-005", "The Gold Sprint", date(2026, 2, 10), date(2026, 2, 11),
          Archetype.ANIMA, None,
          "Essays, health files, visual identity"),
    Epoch("EPOCH-006", "Launch", date(2026, 2, 11), date(2026, 2, 11),
          Archetype.INDIVIDUATION, None,
          "All 8 organs OPERATIONAL, the system becomes itself"),
    Epoch("EPOCH-007", "The Gap-Fill", date(2026, 2, 12), date(2026, 2, 17),
          Archetype.SHADOW, None,
          "11 missing repos created, 14 tier promotions, confronting what was incomplete"),
    Epoch("EPOCH-008", "The Quiet Growth", date(2026, 2, 18), date(2026, 3, 7),
          Archetype.MOTHER, Archetype.ANIMUS,
          "Steady infrastructure work, engine development, schema definitions"),
    Epoch("EPOCH-009", "The Research Tsunami", date(2026, 3, 8), date(2026, 3, 19),
          Archetype.ANIMA, Archetype.TRICKSTER,
          "170K+ words of research, 7 prompts, 13 papers, sleepless"),
    Epoch("EPOCH-010", "The Reckoning", date(2026, 3, 20), date(2026, 3, 20),
          Archetype.SELF, None,
          "22-session triage, the system observes what happened during the tsunami"),
    Epoch("EPOCH-011", "The Engine Expansion", date(2026, 3, 20), date(2026, 3, 21),
          Archetype.ANIMUS, Archetype.MOTHER,
          "42 modules, omega expansion, CI remediation, Hermeneus rewrite"),
    Epoch("EPOCH-012", "The Contribution Engine", date(2026, 3, 21), date(2026, 3, 22),
          Archetype.INDIVIDUATION, Archetype.ANIMUS,
          "The system reaches outward — contribution workspaces, Hive PR, open-source pattern"),
]


def assign_epoch(dt: datetime) -> Epoch | None:
    """Find which declared epoch a timestamp falls into."""
    d = dt.date() if isinstance(dt, datetime) else dt
    for epoch in DECLARED_EPOCHS:
        if epoch.start <= d <= epoch.end:
            return epoch
    return None


def detect_session_boundaries(
    timestamps: list[datetime],
    gap_minutes: int = 90,
) -> list[list[datetime]]:
    """Group timestamps into sessions by time proximity.

    Commits within gap_minutes of each other belong to the same session.
    Returns a list of sessions, each a list of timestamps.
    """
    if not timestamps:
        return []

    sorted_ts = sorted(timestamps)
    sessions: list[list[datetime]] = [[sorted_ts[0]]]
    gap = timedelta(minutes=gap_minutes)

    for ts in sorted_ts[1:]:
        if ts - sessions[-1][-1] > gap:
            sessions.append([ts])
        else:
            sessions[-1].append(ts)

    return sessions
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_fossil_epochs.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/organvm_engine/fossil/epochs.py tests/test_fossil_epochs.py
git commit -m "feat(fossil): epoch definitions — 12 declared geological periods + session boundary detection"
```

---

### Task 4: Excavator

**Files:**
- Create: `src/organvm_engine/fossil/excavator.py`
- Create: `tests/test_fossil_excavator.py`
- Create: `tests/fixtures/fossil/` (directory)
- Modify: `src/organvm_engine/paths.py`

- [ ] **Step 1: Add path helpers**

Add to `src/organvm_engine/paths.py`:

```python
def fossil_dir() -> Path:
    """Directory for fossil record artifacts."""
    return corpus_dir() / "data" / "fossil"


def fossil_record_path() -> Path:
    """Path to the fossil-record.jsonl file."""
    return fossil_dir() / "fossil-record.jsonl"
```

- [ ] **Step 2: Write failing tests for excavator**

```python
# tests/test_fossil_excavator.py
"""Tests for the git history excavator."""

import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest

from organvm_engine.fossil.excavator import (
    excavate_repo,
    parse_commit_type,
    parse_numstat,
    detect_organ_from_path,
)
from organvm_engine.fossil.stratum import Archetype, Provenance


def test_parse_commit_type():
    assert parse_commit_type("feat: add something") == "feat"
    assert parse_commit_type("fix: resolve bug") == "fix"
    assert parse_commit_type("chore(deps): bump version") == "chore"
    assert parse_commit_type("Merge pull request #1") == "merge"
    assert parse_commit_type("onnwards+upwards;") == ""


def test_parse_numstat():
    lines = "3\t1\tsrc/foo.py\n10\t0\tsrc/bar.py\n"
    files, ins, dels = parse_numstat(lines)
    assert files == 2
    assert ins == 13
    assert dels == 1


def test_parse_numstat_empty():
    files, ins, dels = parse_numstat("")
    assert files == 0
    assert ins == 0
    assert dels == 0


def test_detect_organ_from_path(tmp_path):
    # Simulate workspace structure
    organ_dir = tmp_path / "organvm-i-theoria" / "some-repo"
    organ_dir.mkdir(parents=True)
    result = detect_organ_from_path(organ_dir, tmp_path)
    assert result == "I"


def test_detect_organ_meta(tmp_path):
    organ_dir = tmp_path / "meta-organvm" / "organvm-engine"
    organ_dir.mkdir(parents=True)
    result = detect_organ_from_path(organ_dir, tmp_path)
    assert result == "META"


def test_detect_organ_liminal(tmp_path):
    organ_dir = tmp_path / "4444J99" / "portfolio"
    organ_dir.mkdir(parents=True)
    result = detect_organ_from_path(organ_dir, tmp_path)
    assert result == "LIMINAL"


@pytest.fixture
def fixture_repo(tmp_path):
    """Create a tiny git repo with 3 commits for testing."""
    repo = tmp_path / "organvm-i-theoria" / "test-repo"
    repo.mkdir(parents=True)
    subprocess.run(["git", "init"], cwd=repo, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, capture_output=True)

    # Commit 1: feat
    (repo / "foo.py").write_text("x = 1\n")
    subprocess.run(["git", "add", "."], cwd=repo, capture_output=True)
    subprocess.run(["git", "commit", "-m", "feat: initial"], cwd=repo, capture_output=True)

    # Commit 2: fix
    (repo / "foo.py").write_text("x = 2\n")
    subprocess.run(["git", "add", "."], cwd=repo, capture_output=True)
    subprocess.run(["git", "commit", "-m", "fix: correct value"], cwd=repo, capture_output=True)

    # Commit 3: trickster
    (repo / "bar.py").write_text("y = 1\n")
    subprocess.run(["git", "add", "."], cwd=repo, capture_output=True)
    subprocess.run(["git", "commit", "-m", "yolo"], cwd=repo, capture_output=True)

    return repo


def test_excavate_repo(fixture_repo, tmp_path):
    records = list(excavate_repo(fixture_repo, workspace_root=tmp_path))
    assert len(records) == 3

    # All should be RECONSTRUCTED
    assert all(r.provenance == Provenance.RECONSTRUCTED for r in records)

    # Should be sorted chronologically
    assert records[0].timestamp <= records[1].timestamp <= records[2].timestamp

    # Check organ detection
    assert all(r.organ == "I" for r in records)

    # Check archetype classification ran
    assert all(len(r.archetypes) >= 1 for r in records)

    # The "yolo" commit should be Trickster
    yolo = [r for r in records if "yolo" in r.message]
    assert len(yolo) == 1
    assert yolo[0].archetypes[0] == Archetype.TRICKSTER
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_fossil_excavator.py -v`
Expected: FAIL

- [ ] **Step 4: Implement excavator**

Create `src/organvm_engine/fossil/excavator.py`:

```python
"""Excavator — crawls git history across workspace repos.

Walks every .git directory under the workspace root, extracts commit
metadata, classifies each by archetype, and yields FossilRecord objects.
"""

from __future__ import annotations

import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from organvm_engine.fossil.classifier import classify_commit
from organvm_engine.fossil.epochs import assign_epoch
from organvm_engine.fossil.stratum import (
    FossilRecord,
    Provenance,
    compute_record_hash,
)
from organvm_engine.organ_config import ORGANS

# Map directory prefixes to organ keys
_DIR_TO_ORGAN: dict[str, str] = {}
for key, meta in ORGANS.items():
    _DIR_TO_ORGAN[meta["dir"]] = key

_CONVENTIONAL_RE = re.compile(r"^(\w+)(?:\(.+?\))?[!]?:\s")


def parse_commit_type(message: str) -> str:
    """Extract conventional commit type from message."""
    m = _CONVENTIONAL_RE.match(message)
    if m:
        return m.group(1)
    if message.startswith("Merge "):
        return "merge"
    if message.startswith("Revert "):
        return "revert"
    return ""


def parse_numstat(numstat_output: str) -> tuple[int, int, int]:
    """Parse git numstat output into (files_changed, insertions, deletions)."""
    files = 0
    insertions = 0
    deletions = 0
    for line in numstat_output.strip().split("\n"):
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) >= 3:
            files += 1
            try:
                insertions += int(parts[0]) if parts[0] != "-" else 0
                deletions += int(parts[1]) if parts[1] != "-" else 0
            except ValueError:
                pass
    return files, insertions, deletions


def detect_organ_from_path(repo_path: Path, workspace_root: Path) -> str:
    """Determine which organ a repo belongs to from its directory path."""
    try:
        rel = repo_path.relative_to(workspace_root)
    except ValueError:
        return "UNKNOWN"

    top_dir = rel.parts[0] if rel.parts else ""

    for dir_name, organ_key in _DIR_TO_ORGAN.items():
        if top_dir == dir_name:
            return organ_key

    return "UNKNOWN"


def excavate_repo(
    repo_path: Path,
    *,
    workspace_root: Path,
    since: str | None = None,
    existing_shas: frozenset[str] | None = None,
) -> Iterator[FossilRecord]:
    """Excavate all commits from a single repo.

    Yields FossilRecord objects in chronological order.
    Skips commits whose SHA is in existing_shas (idempotent).
    """
    organ = detect_organ_from_path(repo_path, workspace_root)
    repo_name = repo_path.name

    cmd = [
        "git", "log", "--reverse",
        "--format=%H|%aI|%an|%s",
    ]
    if since:
        cmd.append(f"--since={since}")

    result = subprocess.run(
        cmd, cwd=repo_path, capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0:
        return

    skip = existing_shas or frozenset()

    for line in result.stdout.strip().split("\n"):
        if not line.strip():
            continue

        parts = line.split("|", 3)
        if len(parts) < 4:
            continue

        sha, iso_date, author, message = parts
        if sha in skip:
            continue

        # Parse timestamp
        try:
            timestamp = datetime.fromisoformat(iso_date)
        except ValueError:
            continue

        # Get numstat for this commit
        stat_result = subprocess.run(
            ["git", "diff", "--numstat", f"{sha}^..{sha}"],
            cwd=repo_path, capture_output=True, text=True, timeout=10,
        )
        numstat = stat_result.stdout if stat_result.returncode == 0 else ""
        files_changed, insertions, deletions = parse_numstat(numstat)

        # Classify
        conv_type = parse_commit_type(message)
        archetypes = classify_commit(message, conv_type, repo_name, organ)

        # Assign epoch
        epoch_obj = assign_epoch(timestamp)
        epoch_id = epoch_obj.id if epoch_obj else None

        yield FossilRecord(
            commit_sha=sha,
            timestamp=timestamp,
            author=author,
            organ=organ,
            repo=repo_name,
            message=message,
            conventional_type=conv_type,
            files_changed=files_changed,
            insertions=insertions,
            deletions=deletions,
            archetypes=archetypes,
            provenance=Provenance.RECONSTRUCTED,
            session_id=None,  # session assignment is a post-processing step
            epoch=epoch_id,
            tags=[],
            prev_hash="",  # filled during chain-linking
        )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_fossil_excavator.py -v`
Expected: All 8 tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/organvm_engine/fossil/excavator.py tests/test_fossil_excavator.py src/organvm_engine/paths.py
git commit -m "feat(fossil): excavator — git history crawler with organ detection and archetype classification"
```

---

### Task 5: Package Init — Public API

**Files:**
- Modify: `src/organvm_engine/fossil/__init__.py`

- [ ] **Step 1: Update __init__.py with public API exports**

```python
"""fossil — Archaeological reconstruction of ORGANVM system history.

Crawls git history across all workspace repos, classifies commits by
Jungian archetype, and produces a hash-linked fossil record.

Public API::

    from organvm_engine.fossil import (
        Archetype, FossilRecord, Provenance,
        classify_commit, excavate_repo,
        DECLARED_EPOCHS, assign_epoch,
    )
"""

from organvm_engine.fossil.classifier import classify_commit
from organvm_engine.fossil.epochs import DECLARED_EPOCHS, Epoch, assign_epoch
from organvm_engine.fossil.excavator import excavate_repo
from organvm_engine.fossil.stratum import (
    Archetype,
    FossilRecord,
    Provenance,
    compute_record_hash,
    deserialize_record,
    serialize_record,
)

__all__ = [
    "Archetype",
    "DECLARED_EPOCHS",
    "Epoch",
    "FossilRecord",
    "Provenance",
    "assign_epoch",
    "classify_commit",
    "compute_record_hash",
    "deserialize_record",
    "excavate_repo",
    "serialize_record",
]
```

- [ ] **Step 2: Run full test suite**

Run: `pytest tests/test_fossil_*.py -v`
Expected: All tests PASS (stratum + classifier + epochs + excavator)

- [ ] **Step 3: Run ruff**

Run: `ruff check src/organvm_engine/fossil/`
Expected: Clean (0 errors)

- [ ] **Step 4: Commit**

```bash
git add src/organvm_engine/fossil/__init__.py
git commit -m "feat(fossil): public API exports in package init"
```

---

### Task 6: CLI Handler

**Files:**
- Create: `src/organvm_engine/cli/fossil.py`
- Modify: `src/organvm_engine/cli/__init__.py`

- [ ] **Step 1: Create CLI handler**

Create `src/organvm_engine/cli/fossil.py`:

```python
"""CLI handler for the fossil (Living Stratigraphy) command group."""

from __future__ import annotations

import json
import sys
from pathlib import Path


def cmd_fossil_excavate(args) -> int:
    """Crawl git history and produce fossil-record.jsonl."""
    from organvm_engine.fossil.excavator import excavate_repo
    from organvm_engine.fossil.stratum import (
        compute_record_hash,
        deserialize_record,
        serialize_record,
    )
    from organvm_engine.paths import fossil_record_path, workspace_root

    ws = Path(getattr(args, "workspace", None) or workspace_root())
    output = fossil_record_path()
    write = getattr(args, "write", False)
    since = getattr(args, "since", None)
    organ_filter = getattr(args, "organ", None)

    # Load existing SHAs for idempotent re-runs
    existing_shas: set[str] = set()
    if output.exists():
        with open(output) as f:
            for line in f:
                if line.strip():
                    try:
                        rec = deserialize_record(line.strip())
                        existing_shas.add(rec.commit_sha)
                    except (json.JSONDecodeError, TypeError):
                        pass

    # Find all git repos
    git_dirs: list[Path] = []
    for depth in range(1, 5):
        pattern = "/".join(["*"] * depth) + "/.git"
        git_dirs.extend(p.parent for p in ws.glob(pattern) if p.is_dir())

    # Deduplicate (nested repos)
    git_dirs = sorted(set(git_dirs))

    total_new = 0
    records_buffer: list[str] = []
    prev_hash = ""

    # If appending, get the last hash from existing file
    if output.exists() and existing_shas:
        with open(output) as f:
            lines = f.readlines()
            if lines:
                try:
                    last_rec = deserialize_record(lines[-1].strip())
                    prev_hash = compute_record_hash(last_rec)
                except (json.JSONDecodeError, TypeError):
                    pass

    for repo_path in git_dirs:
        organ = None
        if organ_filter:
            from organvm_engine.fossil.excavator import detect_organ_from_path
            organ = detect_organ_from_path(repo_path, ws)
            if organ != organ_filter:
                continue

        try:
            for record in excavate_repo(
                repo_path,
                workspace_root=ws,
                since=since,
                existing_shas=frozenset(existing_shas),
            ):
                record.prev_hash = prev_hash
                prev_hash = compute_record_hash(record)
                records_buffer.append(serialize_record(record))
                total_new += 1
        except Exception as exc:
            print(f"  SKIP {repo_path.name}: {exc}", file=sys.stderr)

    if write and records_buffer:
        output.parent.mkdir(parents=True, exist_ok=True)
        with open(output, "a") as f:
            for line in records_buffer:
                f.write(line + "\n")
        print(f"Wrote {total_new} new records to {output}")
    else:
        print(f"[dry-run] Would write {total_new} new records to {output}")

    return 0


def cmd_fossil_epochs(args) -> int:
    """List all declared epochs."""
    from organvm_engine.fossil.epochs import DECLARED_EPOCHS

    as_json = getattr(args, "json", False)

    if as_json:
        data = [
            {
                "id": e.id, "name": e.name,
                "start": e.start.isoformat(), "end": e.end.isoformat(),
                "dominant": e.dominant_archetype.value,
                "secondary": e.secondary_archetype.value if e.secondary_archetype else None,
                "description": e.description,
            }
            for e in DECLARED_EPOCHS
        ]
        print(json.dumps(data, indent=2))
    else:
        for e in DECLARED_EPOCHS:
            sec = f" + {e.secondary_archetype.value}" if e.secondary_archetype else ""
            print(f"  {e.id}  {e.start} → {e.end}  [{e.dominant_archetype.value}{sec}]")
            print(f"          {e.name}: {e.description}")
            print()

    return 0


def cmd_fossil_stratum(args) -> int:
    """Query the fossil record."""
    from organvm_engine.fossil.stratum import Archetype, deserialize_record
    from organvm_engine.paths import fossil_record_path

    path = fossil_record_path()
    if not path.exists():
        print("No fossil record found. Run: organvm fossil excavate --write")
        return 1

    organ_filter = getattr(args, "organ", None)
    archetype_filter = getattr(args, "archetype", None)
    as_json = getattr(args, "json", False)

    records = []
    with open(path) as f:
        for line in f:
            if not line.strip():
                continue
            rec = deserialize_record(line.strip())
            if organ_filter and rec.organ != organ_filter:
                continue
            if archetype_filter:
                target = Archetype(archetype_filter)
                if target not in rec.archetypes:
                    continue
            records.append(rec)

    if as_json:
        from organvm_engine.fossil.stratum import serialize_record
        print("[")
        for i, r in enumerate(records):
            comma = "," if i < len(records) - 1 else ""
            print(f"  {serialize_record(r)}{comma}")
        print("]")
    else:
        print(f"Fossil record: {len(records)} records")
        # Summary by archetype
        from collections import Counter
        arch_counts = Counter(r.archetypes[0].value for r in records if r.archetypes)
        for arch, count in arch_counts.most_common():
            print(f"  {arch:15s} {count:5d}")

    return 0
```

- [ ] **Step 2: Wire into CLI __init__.py**

Add imports near the top of `src/organvm_engine/cli/__init__.py` (with the other CLI imports):

```python
from organvm_engine.cli.fossil import (
    cmd_fossil_excavate,
    cmd_fossil_epochs,
    cmd_fossil_stratum,
)
```

Add the `fossil` subparser in `build_parser()` (follow the pattern of existing command groups like `irf`). Add dispatch entries in the main dispatch section.

- [ ] **Step 3: Run ruff**

Run: `ruff check src/organvm_engine/cli/fossil.py`
Expected: Clean

- [ ] **Step 4: Commit**

```bash
git add src/organvm_engine/cli/fossil.py src/organvm_engine/cli/__init__.py
git commit -m "feat(fossil): CLI — excavate, epochs, stratum commands"
```

---

### Task 7: Integration Test — Full Excavation

**Files:**
- Create: `tests/test_fossil_integration.py`

- [ ] **Step 1: Write integration test**

```python
# tests/test_fossil_integration.py
"""Integration test: excavate a fixture workspace and verify the full pipeline."""

import subprocess
from pathlib import Path

import pytest

from organvm_engine.fossil.excavator import excavate_repo
from organvm_engine.fossil.stratum import (
    Archetype,
    compute_record_hash,
    deserialize_record,
    serialize_record,
)


@pytest.fixture
def mini_workspace(tmp_path):
    """Create a workspace with 2 repos in different organs."""
    # ORGAN-I repo
    repo1 = tmp_path / "organvm-i-theoria" / "test-theory"
    repo1.mkdir(parents=True)
    subprocess.run(["git", "init"], cwd=repo1, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=repo1, capture_output=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=repo1, capture_output=True)
    (repo1 / "a.py").write_text("x=1\n")
    subprocess.run(["git", "add", "."], cwd=repo1, capture_output=True)
    subprocess.run(["git", "commit", "-m", "feat: initial theory"], cwd=repo1, capture_output=True)

    # META repo
    repo2 = tmp_path / "meta-organvm" / "test-engine"
    repo2.mkdir(parents=True)
    subprocess.run(["git", "init"], cwd=repo2, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=repo2, capture_output=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=repo2, capture_output=True)
    (repo2 / "b.py").write_text("y=1\n")
    subprocess.run(["git", "add", "."], cwd=repo2, capture_output=True)
    subprocess.run(["git", "commit", "-m", "feat: governance state machine"], cwd=repo2, capture_output=True)
    (repo2 / "b.py").write_text("y=2\n")
    subprocess.run(["git", "add", "."], cwd=repo2, capture_output=True)
    subprocess.run(["git", "commit", "-m", "fix: lint errors"], cwd=repo2, capture_output=True)

    return tmp_path


def test_full_excavation_pipeline(mini_workspace):
    """Excavate 2 repos, verify records, hash-link, serialize/deserialize."""
    all_records = []

    for git_dir in sorted(mini_workspace.rglob(".git")):
        if not git_dir.is_dir():
            continue
        repo_path = git_dir.parent
        records = list(excavate_repo(repo_path, workspace_root=mini_workspace))
        all_records.extend(records)

    # Should have 3 commits total (1 + 2)
    assert len(all_records) == 3

    # Sort chronologically and hash-link
    all_records.sort(key=lambda r: r.timestamp)
    prev_hash = ""
    for rec in all_records:
        rec.prev_hash = prev_hash
        prev_hash = compute_record_hash(rec)

    # Verify chain integrity
    prev = ""
    for rec in all_records:
        assert rec.prev_hash == prev
        prev = compute_record_hash(rec)

    # Verify organs detected
    organs = {r.organ for r in all_records}
    assert "I" in organs
    assert "META" in organs

    # Verify serialize/deserialize roundtrip
    for rec in all_records:
        json_str = serialize_record(rec)
        restored = deserialize_record(json_str)
        assert restored.commit_sha == rec.commit_sha
        assert restored.archetypes == rec.archetypes

    # The "fix: lint errors" commit should be Shadow
    lint_rec = [r for r in all_records if "lint" in r.message]
    assert len(lint_rec) == 1
    assert lint_rec[0].archetypes[0] == Archetype.SHADOW
```

- [ ] **Step 2: Run all fossil tests**

Run: `pytest tests/test_fossil_*.py -v`
Expected: All tests PASS

- [ ] **Step 3: Run ruff on entire module**

Run: `ruff check src/organvm_engine/fossil/`
Expected: Clean

- [ ] **Step 4: Commit**

```bash
git add tests/test_fossil_integration.py
git commit -m "test(fossil): integration test — full excavation pipeline with hash-linked chain"
```

---

## Summary

| Task | Tests | Source Files | Description |
|------|-------|-------------|-------------|
| 1 | 5 | 2 | Stratum data models |
| 2 | 13 | 1 | Archetype classifier |
| 3 | 5 | 1 | Epoch definitions |
| 4 | 8 | 2 | Excavator |
| 5 | 0 | 1 | Package init |
| 6 | 0 | 2 | CLI handler + wiring |
| 7 | 1 | 1 | Integration test |
| **Total** | **32** | **10** | Phase 1 complete |

After Phase 1, run: `organvm fossil excavate --write` to produce the first `fossil-record.jsonl` with all ~9,400 commits classified by Jungian archetype.
