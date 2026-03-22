# The Living Stratigraphy — `organvm fossil`

**Date:** 2026-03-22
**Status:** APPROVED
**Organ:** META-ORGANVM
**Repo:** organvm-engine
**Source:** IRF reconciliation session → fossil record brainstorm
**Phase:** Design complete, implementation pending

---

## Purpose

A memory prosthesis for a creative system built in altered states. The fossil record reconstructs the complete temporal history of ORGANVM from git evidence, preserves unique prompts as artifacts of intention, narrates the system's evolution through Jungian archetypes, and captures everything automatically going forward — so the operator never has to remember to maintain it.

**Design philosophy:** The system remembers *for* you. Completeness trumps elegance. Drift from intention is not failure — it is the unconscious asserting itself.

---

## Three-Layer Architecture

### Layer 1: Stratum (The Evidence)

Every commit across all repos, normalized into a uniform schema.

```python
@dataclass
class FossilRecord:
    commit_sha: str
    timestamp: datetime
    author: str
    organ: str              # I, II, III, IV, V, VI, VII, META, LIMINAL
    repo: str
    message: str
    conventional_type: str  # feat/fix/chore/docs/refactor/test/registry/style
    files_changed: int
    insertions: int
    deletions: int
    archetype: list[Archetype]  # ranked, primary first
    provenance: Provenance      # WITNESSED | RECONSTRUCTED | ATTESTED
    session_id: str | None
    epoch: str | None
    tags: list[str]
    prev_hash: str              # hash of previous record (tamper-evident chain)
```

**Storage:** `fossil-record.jsonl` in corpus data directory. Hash-linked.
**Scale:** ~9,400 records today, growing at ~100-200/day during active periods.
**Dedup key:** commit SHA (excavator is idempotent).

### Layer 2: Intentions (The Will)

Unique prompts — first-time articulations of creative intent, before iteration dilutes them.

```python
@dataclass
class Intention:
    id: str                    # INT-YYYY-MM-DD-NNN
    timestamp: datetime
    raw_text: str              # exact prompt, verbatim
    fingerprint: str           # SHA256 of normalized text
    uniqueness_score: float    # 0.0-1.0, Jaccard distance from nearest known
    archetype: list[Archetype]
    session_id: str | None
    epoch: str | None
    drift: DriftRecord | None  # filled by drift detector post-implementation
    tags: list[str]
    provenance: Provenance

@dataclass
class DriftRecord:
    intended_scope: list[str]   # repos/organs from the prompt
    actual_scope: list[str]     # repos/organs actually touched
    convergence: float          # 0.0 = total divergence, 1.0 = exact match
    mutations: list[str]        # emerged but unplanned
    shadows: list[str]          # intended but never done
    drift_archetype: Archetype  # Animus (convergent), Anima (mutated), Shadow (avoided), Trickster (inverted)
```

**Storage:** `intentions/` directory, one YAML per intention + `intentions-index.jsonl`.
**Uniqueness threshold:** < 0.3 Jaccard similarity to any known intention = unique.
**Retroactive extraction:** Scans `.specstory/history/` for historical prompts.

### Layer 3: Chronicle (The Story)

Jungian-voiced narrative at three zoom levels: epoch → session → commit.

```python
@dataclass
class Epoch:
    id: str                        # EPOCH-NNN
    name: str                      # "The Bronze Sprint", "The Sleepless Descent"
    date_range: tuple[date, date]
    dominant_archetype: Archetype
    secondary_archetype: Archetype | None
    narrative: str                 # 2-4 paragraph Jungian chronicle
    sessions: list[SessionSummary]
    commit_count: int
    repos_touched: list[str]
    intentions_born: list[str]     # INT-xxx IDs
    drift_summary: str
```

**Storage:** `chronicle/` directory, one markdown per epoch + `chronicle-index.json`.
**Generated, not manual.** The Narrator reads stratum + intentions and produces narrative.

---

## Jungian Archetype Classifier

### Archetypes

| Archetype | Domain | Signal Patterns |
|-----------|--------|----------------|
| **Shadow** | Debt, avoidance, confrontation | `fix:`, security, remediat, debt, lint, error, vulnerability, remove, delete, clean |
| **Anima** | Creative emergence, generation | `feat:` + creative repos (ORGAN-II, materia-collider, corpus-mythicum), art, narrative, generative, visual, audio, essay |
| **Animus** | Structure, formalization | `feat:` + governance, proof, formal, state machine, schema, validation, type, dependency graph |
| **Self** | Integration, self-observation | Self-referential: testament, meta, scorecard, registry update, context sync, omega, system density |
| **Trickster** | Chaos, boundary-crossing | Non-conventional messages, < 5 chars, emoji, ALL CAPS, `onnwards`, no prefix, wild naming |
| **Mother** | Infrastructure, nurturing | CI, test, infrastructure, docker, deploy, environment, dotfiles, domus, LaunchAgent, setup, install |
| **Father** | Authority, enforcement | Governance, promotion, gate, enforce, constraint, rule, protect, permission, branch protection |
| **Individuation** | Wholeness, cross-boundary synthesis | Cross-organ work (2+ organs), contribution engine, atoms pipeline, network testament |

### Three-Tier Classification

1. **Commit-level:** Keyword + heuristic → ranked archetype list per commit
2. **Session-level:** Dominant archetype from commit distribution within session
3. **Epoch-level:** Narrative arc from archetype sequence across sessions

**Ambiguity is a feature.** A commit can be `[Self, Animus]`. The primary archetype is first in the list. The classifier outputs ranked lists, not single labels.

---

## The Narrator — Jungian Voice

### Voice Rules

- Third person, present tense, oracular
- Archetypes are **active forces**, not labels: "The Shadow stirs" not "this is Shadow-type work"
- The system is "the organism" or "the Work"
- Time references are poetic but precise: "at 3:42 AM, when lucid naming gave way to something wilder"
- Drift is the unconscious asserting itself, not failure
- Each epoch: 2-4 paragraph narrative + data summary

### Drift Classification in Narrative

| Pattern | Archetype | Narrative Framing |
|---------|-----------|-------------------|
| Convergence > 0.8 | Animus | "The ego's plan held. Structured execution prevailed." |
| Mutations > Shadows | Anima | "Creative emergence — reality exceeded what was intended." |
| Shadows > Mutations | Shadow | "The intended work was deferred. Something was being avoided." |
| Convergence < 0.2 | Trickster | "The work went somewhere entirely unexpected." |
| 1 repo intended → 8 touched | Individuation | "A small intention triggered system-wide integration." |

### Template Architecture

The Narrator uses configurable templates per epoch archetype pattern, with slot-filling from stratum data. Not pure LLM generation (expensive, inconsistent). Structured narrative with archetypal vocabulary injected into template scaffolding. Templates are overridable.

---

## Epoch Definitions

### Declared Epochs (from corpus documentation)

| ID | Name | Date Range | Dominant Archetype |
|----|------|-----------|-------------------|
| EPOCH-001 | Genesis | 2026-01-22 → 2026-02-08 | Self |
| EPOCH-002 | The Naming | 2026-02-08 → 2026-02-10 | Father |
| EPOCH-003 | The Bronze Sprint | 2026-02-10 | Mother |
| EPOCH-004 | The Silver Sprint | 2026-02-10 → 2026-02-11 | Animus |
| EPOCH-005 | The Gold Sprint | 2026-02-10 → 2026-02-11 | Anima |
| EPOCH-006 | Launch | 2026-02-11 | Individuation |
| EPOCH-007 | The Gap-Fill | 2026-02-11 → 2026-02-17 | Shadow |
| EPOCH-008 | The Quiet Growth | 2026-02-17 → 2026-03-08 | Mother |
| EPOCH-009 | The Research Tsunami | 2026-03-08 → 2026-03-20 | Anima |
| EPOCH-010 | The Reckoning | 2026-03-20 → 2026-03-20 | Self |
| EPOCH-011 | The Engine Expansion | 2026-03-20 → 2026-03-21 | Animus |
| EPOCH-012 | The Contribution Engine | 2026-03-21 → 2026-03-22 | Individuation |

### Detected Epochs

Change-point detection algorithm: sustained burst (>20 commits/day for 2+ days) followed by gap (>24h with <3 commits) = epoch boundary. Declared epochs override detected ones.

---

## Real-Time Witness Layer

### a) Git Post-Commit Hook

- Installed via `organvm fossil witness install`
- Appends `FossilRecord` to `fossil-record.jsonl` on every commit
- Runs classifier on single commit
- Marks `provenance: WITNESSED`
- < 100ms execution — invisible to developer

### b) Prompt Watcher

- Scans `.specstory/history/` for new session files
- Extracts human prompts, runs uniqueness detection
- Saves unique intentions to `intentions/`
- Can also wire as Claude Code hook

### c) Chronicle Cron

- Runs daily via LaunchAgent
- Checks if any epoch has enough new data for narrative update
- Regenerates affected epoch chronicles
- Runs drift detector on recent intentions

---

## Testament Bridge

- **Epoch events:** `EPOCH_CLOSED` emitted into testament chain when epoch ends. Contains chronicle summary + key metrics. The chain gets ~15 epoch summaries, not 9,400 individual commits.
- **Intention events:** `INTENTION_BORN` emitted when uniqueness > 0.9. The chain witnesses creative will in real time.
- **Drift events:** `DRIFT_DETECTED` emitted when convergence < 0.3 or Shadows accumulate.
- **URI scheme:** `fossil://EPOCH-007`, `fossil://INT-2026-03-21-007`. Testament events can reference fossil records and vice versa.

---

## CLI

```
organvm fossil excavate [--since DATE] [--organ X] [--write]
organvm fossil chronicle [--epoch X] [--regenerate] [--write]
organvm fossil drift [--intention INT-xxx] [--all] [--write]
organvm fossil stratum [--organ X] [--archetype X] [--since DATE] [--until DATE]
organvm fossil witness install
organvm fossil witness status
organvm fossil intentions [--unique] [--session X] [--epoch X]
organvm fossil epochs
```

All destructive commands default to `--dry-run=True`, require `--write` to execute (matches engine convention).

---

## Implementation Phases

| Phase | Name | Scope | Files | Output |
|-------|------|-------|-------|--------|
| 1 | **The Dig** | Excavator + Classifier + Stratum models | 4 | `fossil-record.jsonl` — all ~9,400 commits classified |
| 2 | **The Chronicle** | Narrator + Epochs | 2 | `chronicle/` — Jungian narratives for ~12 epochs |
| 3 | **The Archive** | Archivist + retroactive prompt extraction | 1 | `intentions/` — unique prompts from session history |
| 4 | **The Mirror** | Drift detector | 1 | Drift records on all intentions |
| 5 | **The Witness** | Real-time hooks + LaunchAgent + prompt watcher | 1 + config | Ongoing automatic capture |
| 6 | **The Bridge** | Testament integration | 1 | Epoch/intention/drift events in the chain |

Each phase delivers standalone value. Phase 1 alone gives the user their complete history for the first time.

---

## Testing Strategy

- **Excavator:** Test with `tmp_path` + fixture repos with known commit histories
- **Classifier:** Test with labeled commit messages → expected archetype rankings
- **Archivist:** Test uniqueness detection with known similar/dissimilar prompt pairs
- **Narrator:** Snapshot tests — generated chronicle for fixture epoch matches expected output
- **Drift:** Test convergence/mutation/shadow computation with known intention↔commit pairs
- **Witness:** Integration test with temporary git repo + post-commit hook

All tests use the existing `conftest.py` sandbox (no production path access).

---

## Dependencies

- **Internal:** `organ_config.py` (organ mapping), `paths.py` (workspace root), `domain.py` (fingerprinting), `prompts/` (prompt extraction), `testament/` (chain integration)
- **External:** None beyond stdlib. Git operations via `subprocess`. No new pip dependencies.

---

## Relationship to Companion Indices

The fossil record is the **data substrate** for the three planned companion indices:

- **Index Locorum** (IRF-IDX-001) can be generated from stratum: every repo path, file path, URL that appears in commit history
- **Index Nominum** (IRF-IDX-002) can be generated from stratum + intentions: every named entity (repo, organ, tool, persona, protocol) that appears in commits or prompts
- **Index Rerum** (IRF-IDX-003) can be generated from stratum: every artifact type, its state, its relationships, its provenance

The fossil module provides `fossil.stratum.query()` and `fossil.intentions.query()` as the API surface that the index generators will consume.

---

*"The organism does not remember itself. It reads the bones."*
