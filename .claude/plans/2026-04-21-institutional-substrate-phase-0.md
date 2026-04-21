# Institutional Substrate Phase 0 — Implementation Plan

**Date:** 2026-04-21
**Scope:** organvm-engine — 6 primitives, composition engine, AEGIS formation
**Copy to:** `organvm-engine/.claude/plans/2026-04-21-institutional-substrate-phase-0.md`

---

## Context

The routing law is live. `routing-law.yaml` + `resolve.py` in organvm-ontologia are the single source of truth for artifact placement. SPEC-025 (19 institutional primitives), INST-COMPOSITION (4 operators), and 4 formation specs (AEGIS, OIKONOMIA, PRAXIS, TESSERA) are complete as DRAFT specifications. Zero implementation exists. Phase 0 delivers the 6 foundational primitives that compose into AEGIS — the defensive perimeter — plus the composition engine that wires them.

**Why these 6:** assessor, guardian, ledger, counselor, mandator, archivist are the minimum set that composes into AEGIS (defense) and seeds every other formation. SPEC-025 §9: "Singularity emerges at compositional coverage, not capability depth."

**Why now:** The FRAME exists (routing law). Implementations derive from the law. The institutional substrate is the first derivative — it gives the system institutional agency (legal, financial, advisory, protective) that currently exists only as specification.

---

## Architecture Decisions

1. **Placement:** `organvm-engine/src/organvm_engine/primitives/` — new top-level package. Rule 6 of routing-law (`scope: system, function: govern → organvm-engine`) governs.

2. **No collision with existing modules:**
   - `fossil/archivist.py` = prompt-intention capturer (different concept). Institutional archivist is `primitives/archivist.py`.
   - `ledger/` = Testament Protocol hash chain. Institutional ledger is `primitives/inst_ledger.py`.

3. **ABC over Protocol** — the spec demands enforceable interface conformance. ABC catches violations at instantiation, Protocol only at call-site.

4. **Zero external dependencies** — follows engine convention. Stdlib only.

5. **Rule-based logic in Phase 0** — primitives use pattern matching and heuristics, not LLM calls. Getting all 6 working with correct composition is the priority. LLM integration is Phase 1.

6. **Stateful primitives store at `~/.organvm/institutional/`** — guardian (watchlist), ledger (entries), archivist (memory), mandator (directives). Assessor and counselor are stateless.

---

## File Plan

### New packages (3)

```
src/organvm_engine/primitives/       # 9 files
src/organvm_engine/composition/      # 5 files
src/organvm_engine/formations/       # 3 files
```

### New CLI modules (2)

```
src/organvm_engine/cli/primitives.py
src/organvm_engine/cli/formation.py
```

### Modified files (2)

```
src/organvm_engine/cli/__init__.py   # Wire new command groups
src/organvm_engine/events/spine.py   # Add 6 event types
```

### Tests (12)

```
tests/test_primitives_types.py
tests/test_primitives_base.py
tests/test_primitive_assessor.py
tests/test_primitive_guardian.py
tests/test_primitive_inst_ledger.py
tests/test_primitive_counselor.py
tests/test_primitive_archivist.py
tests/test_primitive_mandator.py
tests/test_composition_operators.py
tests/test_composition_engine.py
tests/test_composition_prohibitions.py
tests/test_formation_aegis.py
```

---

## Implementation Sequence

### Step 1: Foundation types and base class

**Files:**
- `primitives/__init__.py` — package, exports base types and registry
- `primitives/types.py` — core data structures
- `primitives/base.py` — `InstitutionalPrimitive` ABC
- `primitives/execution.py` — `mode_for_invocation()` standalone function
- `primitives/registry.py` — `PrimitiveRegistry` flat pool

**Core types in `types.py`:**
- `StakesLevel` enum: ROUTINE, SIGNIFICANT, CRITICAL
- `ExecutionMode` enum: AI_PERFORMED, AI_PREPARED_HUMAN_REVIEWED, HUMAN_ROUTED, PROTOCOL_STRUCTURED
- `FrameType` enum: LEGAL, FINANCIAL, RELATIONAL, REPUTATIONAL, STRATEGIC, OPERATIONAL
- `Frame` (frozen dataclass): frame_type, parameters, description
- `PrincipalPosition` (dataclass): interests, objectives, constraints, current_state
- `InstitutionalContext` (dataclass): context_id (uuid), timestamp, situation, data, source, tags, parent_context_id
- `AuditEntry` (dataclass): entry_id, timestamp, primitive_id/name, operation, rationale, inputs/output_summary, execution_mode, confidence, duration_ms
- `PrimitiveOutput` (dataclass): output, confidence, escalation_flag, audit_trail, execution_mode, stakes, context_id, primitive_id, metadata

**ABC in `base.py`:**
- Class attrs: `PRIMITIVE_ID`, `PRIMITIVE_NAME`, `CLUSTER`, `DEFAULT_STAKES`
- Abstract: `invoke(context, frame, principal_position) -> PrimitiveOutput`
- Concrete: `determine_execution_mode(confidence, stakes) -> ExecutionMode`
- Concrete: `_make_audit_entry(...)` convenience builder

**Registry in `registry.py`:**
- `PrimitiveRegistry`: register/lookup by ID or name, list all. Flat pool (no hierarchy per spec).

### Step 2: Archivist (first — used by all others for precedent)

**File:** `primitives/archivist.py`

**Specific types:**
- `MemoryRecord`: record_id, timestamp, category (decision/precedent/outcome/pattern/lesson), summary, context_snapshot, outcome, tags, formation_id, related_records, search_text

**Storage:** `~/.organvm/institutional/archivist/memory.jsonl` (append) + `index.json` (tag/category → record_id)

**Two modes:**
- Capture: takes a PrimitiveOutput, creates MemoryRecord, appends to JSONL, updates index. Mode = PROTOCOL_STRUCTURED.
- Retrieve: takes search params (tags, category, text), returns matching records via index + substring. Mode = AI_PERFORMED.

### Step 3: Assessor and Guardian

**File:** `primitives/assessor.py`

**Specific types:**
- `RiskFactor`: category, description, severity (0-1), likelihood (0-1), exposure (severity*likelihood), mitigations, deadline
- `OpportunityFactor`: category, description, potential_value, effort_required, time_sensitivity
- `AssessmentProfile`: risk_factors, opportunity_factors, net_exposure, action_vectors, frame_applied, novel_situation

**Logic:** Frame-specific criteria dictionaries (legal: liability/statute-of-limitations/jurisdiction; financial: exposure/liquidity/solvency; etc.). Scans context.data against criteria, builds risk/opportunity factors, computes net_exposure as max of individual exposures. Escalates if confidence < 0.6 or any severity > 0.8.

**File:** `primitives/guardian.py`

**Specific types:**
- `WatchItem`: item_id, category (deadline/threshold/registration/benefit), description, watched_value, threshold, direction (above/below/approaching/expired), current_value, last_checked, alert_window_days, status
- `Alert`: alert_id, watch_item_id, alert_type, severity, message, timestamp, context_payload
- `GuardianState` class: manages watchlist JSONL at `~/.organvm/institutional/guardian/watchlist.jsonl`

**Logic:** Loads watchlist, evaluates each item against context.data. Deadlines: compare now vs deadline-alert_window. Thresholds: compare current vs threshold in direction. Exposes `add_watch()` and `remove_watch()` mutations.

### Step 4: Institutional Ledger

**File:** `primitives/inst_ledger.py`

**Specific types:**
- `LedgerEntry`: entry_id, timestamp, category (income/expense/obligation/receivable/equity/asset), subcategory, amount, currency, counterparty, description, direction (inflow/outflow/neutral), recurring, frequency, status, tags
- `EconomicSnapshot`: timestamp, total_assets, total_liabilities, net_position, monthly_inflow, monthly_outflow, runway_months, entries_by_category, alerts

**Storage:** `~/.organvm/institutional/ledger/economic-entries.jsonl` (append) + `snapshot.json` (computed state)

**Logic:** Record mode = PROTOCOL_STRUCTURED (deterministic append). Snapshot computation reads all entries, groups by category, calculates position. Alerts on negative runway, overdue receivables, etc.

### Step 5: Counselor

**File:** `primitives/counselor.py`

**Specific types:**
- `TradeOff`: option, pros, cons, second_order_effects, estimated_confidence
- `Recommendation`: recommended_action, rationale, trade_offs, alternatives, urgency, reversibility, precedent_used, second_order_effects

**Logic:** Expects upstream AssessmentProfile(s) + optional archivist precedent in context.data. Synthesizes across profiles: identifies highest-risk factors, cross-references, finds frame conflicts. Ranks actions by risk mitigation weighted against opportunity cost. Escalates on irreversible actions or conflicting frame assessments. Confidence = min(upstream) - 0.05 synthesis penalty.

### Step 6: Mandator

**File:** `primitives/mandator.py`

**Specific types:**
- `Directive`: directive_id, timestamp, action, authority, scope, completion_criteria, expiry, priority (urgent/normal/deferred), status (pending/approved/active/completed/expired/revoked), source_recommendation, assigned_to, constraints

**Storage:** `~/.organvm/institutional/mandator/directives.jsonl` (append)

**Logic:** Transforms counselor Recommendation into structured Directive. ALWAYS escalates (per AEGIS spec: principal approves all defense directives). Confidence inherited from upstream.

### Step 7: Composition engine

**Files:**
- `composition/__init__.py`
- `composition/graph.py` — `PrimitiveNode`, `CompositionEdge`, `CompositionGraph` (with `validate()` and `execution_order()` topological sort)
- `composition/operators.py` — `chain_execute()`, `parallel_execute()`, `envelope_execute()`, `feedback_execute()`
- `composition/prohibitions.py` — 5 rules from COMP-013 + `validate_composition(graph)` 
- `composition/engine.py` — `CompositionEngine` with `execute_graph()` and `execute_formation()`

**Key behaviors:**
- CHAIN: output feeds forward. Halts on escalation, stores continuation at `~/.organvm/institutional/continuations.jsonl`.
- PARALLEL: same context to all, outputs merged. Confidence = min() across branches. Any escalation propagates.
- ENVELOPE: outer constrains inner's execution.
- FEEDBACK: iterative until convergence or max 5 iterations.
- Prohibited compositions enforced before execution: mandator-without-counselor, assessor-self-assessment, enforcer-without-guardian, allocator-without-ledger, representative-without-insulator (adversarial).

### Step 8: AEGIS formation

**Files:**
- `formations/__init__.py`
- `formations/registry.py` — load/save formation definitions
- `formations/aegis.py` — FORM-INST-001

**AEGIS graph:**
```
guardian(threats) → [assessor(legal) || assessor(financial)] → counselor → mandator
                                                                  ^
                                                              archivist(precedent)
```

**Escalation policy per spec:**
- Guardian: never escalates (sensing layer)
- Assessor: escalates if confidence < 0.6
- Counselor: escalates for irreversible actions
- Mandator: ALWAYS escalates (principal approves all defense directives)

**Trigger conditions:** Threats to housing, income, legal standing, benefits.

### Step 9: CLI integration

**File:** `cli/primitives.py` — exports `cmd_primitive_list`, `cmd_primitive_inspect`, `cmd_primitive_invoke`, `cmd_primitive_guardian_*`, `cmd_primitive_ledger_*`

**Commands:**
```
organvm primitive list
organvm primitive inspect <name>
organvm primitive invoke <name> --context <json> --frame <type> [--stakes <level>] [--json]
organvm primitive guardian add-watch --category <cat> --description <desc> --threshold <val> --direction <dir>
organvm primitive guardian watchlist
organvm primitive guardian check
organvm primitive ledger record --category <cat> --amount <n> --description <desc>
organvm primitive ledger snapshot
organvm primitive ledger entries [--category <cat>]
```

**File:** `cli/formation.py` — exports `cmd_formation_list`, `cmd_formation_show`, `cmd_formation_invoke`

**Commands:**
```
organvm formation list
organvm formation show <name>
organvm formation invoke <name> --context <json> [--json]
```

**File (modify):** `cli/__init__.py`
- Add imports for new CLI modules
- Add `primitive` and `formation` parser definitions (following irf/fossil pattern: `sub.add_parser()` + subcommand parsers)
- Add dispatch blocks (inline-if pattern with local dispatch dicts)

### Step 10: Event integration

**File (modify):** `events/spine.py` — add to `EventType` enum:
```python
# -- Institutional primitives ------------------------------------------------
PRIMITIVE_INVOKED = "institutional.primitive_invoked"
PRIMITIVE_ESCALATED = "institutional.primitive_escalated"
FORMATION_INVOKED = "institutional.formation_invoked"
FORMATION_COMPLETED = "institutional.formation_completed"
GUARDIAN_ALERT = "institutional.guardian_alert"
DIRECTIVE_ISSUED = "institutional.directive_issued"
```

---

## Verification

1. **Unit tests pass:** `pytest tests/test_primitive_*.py tests/test_composition_*.py tests/test_formation_*.py -v`
2. **Full suite green:** `pytest tests/ -v` (ensure no regressions)
3. **Lint clean:** `ruff check src/organvm_engine/primitives/ src/organvm_engine/composition/ src/organvm_engine/formations/`
4. **CLI smoke test:**
   - `organvm primitive list` → shows 6 primitives
   - `organvm primitive inspect assessor` → shows metadata
   - `organvm primitive guardian add-watch --category deadline --description "test" --threshold "2026-05-01" --direction approaching --alert-window 7`
   - `organvm primitive guardian watchlist` → shows the item
   - `organvm primitive guardian check` → runs check cycle
   - `organvm formation list` → shows AEGIS
   - `organvm formation show aegis` → shows graph
5. **AEGIS end-to-end:** `organvm formation invoke aegis --context '{"situation": "lease renewal deadline approaching", "data": {"deadline": "2026-05-15", "category": "housing"}}'` → produces guardian alert → assessor profiles → counselor recommendation → mandator directive (escalated for human review)
6. **Prohibited composition rejected:** Test that building a graph with mandator but no counselor raises validation error

---

## What This Does NOT Include

- LLM-powered primitive logic (Phase 1)
- The other 13 institutional primitives beyond Phase 0
- OIKONOMIA, PRAXIS, TESSERA formations (Phase 1 — they need primitives 005, 007-013, 017-019)
- Guardian daemon integration with fabrica heartbeat
- Vector-similarity search in archivist
- Routing law updates (the routing gap for `function: guard` — separate PR)
