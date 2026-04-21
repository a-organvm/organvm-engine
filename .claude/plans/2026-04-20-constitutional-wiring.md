# S-Constitutional-Wiring: Restore Corpus Access + Wire 33 Concepts

## Context

The Constitutional Intelligence Layer was delivered last session (S-Intelligence). The scanner expanded from 12 to 45 concepts, the knowledge graph grew to 151 nodes / 205 edges, and 4 MCP corpus tools were deployed. However, a superproject archival today (2026-04-20) moved `meta-organvm/post-flood/` into `.archive/superprojects-20260420-120747/meta-organvm/post-flood/`. This broke the corpus scanner and MCP tools which resolve `post-flood/` relative to the active workspace.

**Finding**: 33 SPEC-level concepts have zero `implements[]` declarations — theory outpaces embodiment. This session wires them.

---

## Phase 1: Restore Corpus Access (Symlink)

**Action**: Create symlink at `~/Workspace/organvm/post-flood` → archive location.

```bash
ln -s /Users/4jp/Workspace/.archive/superprojects-20260420-120747/meta-organvm/post-flood \
      /Users/4jp/Workspace/organvm/post-flood
```

**Why symlink, not move**: `post-flood/` is read-only constitutional source material (transcripts + specs). It's not a git repo. Placing it in the active workspace as a symlink preserves archive integrity while satisfying both path resolution chains:
- MCP server: `cfg.corpus_dir().parent / "post-flood"` → `~/Workspace/organvm/post-flood`
- CLI: `--corpus-dir post-flood` (relative, from organvm root)
- Meta-organvm symlink: `~/Workspace/meta-organvm/post-flood` (via `meta-organvm → organvm`)

**Verify**:
```bash
ls ~/Workspace/organvm/post-flood/archive_original/.zettel-index.yaml
ls ~/Workspace/organvm/post-flood/specs/SPEC-000/grounding.md
```

---

## Phase 2: Verify Intelligence Layer

1. Run engine corpus tests: `pytest tests/test_corpus*.py -v`
2. Run MCP server tests: `pytest tests/test_corpus*.py -v`
3. Live scan:
   ```bash
   organvm corpus scan --corpus-dir ~/Workspace/organvm/post-flood \
     --workspace ~/Workspace/organvm -o /tmp/corpus-verify.json
   ```
   Expected: 45 concepts, 151+ nodes, 205+ edges
4. MCP loader smoke test:
   ```python
   from organvm_mcp.data.loader import load_corpus_graph
   g = load_corpus_graph(live=True)
   ```

---

## Phase 3: Wire Concepts to Implementations

### Tier A — Auto-detectable (16 concepts, high confidence)

These have obvious code counterparts in organvm-engine:

| Concept | Implementing Module | Aspect |
|---------|-------------------|--------|
| `variable_resolution` | `metrics/variables.py` | Variable registry with resolution and caching |
| `temporal_metrics` | `metrics/timeseries.py` | Time-series storage, retrieval, and windowed queries |
| `workspace_topology` | `git/superproject.py` | Workspace reproduction and submodule topology |
| `agent_swarm_topology` | `coordination/` | Claims registry + tool checkout for concurrent agents |
| `governance_predicates` | `governance/audit.py` | Predicate-based governance rule evaluation |
| `generative_testament` | `fossil/` | Living stratigraphy + testament bridge |
| `zettelkasten_protocol` | `corpus/scanner.py` | Zettelkasten sidecar reading + concept extraction |
| `verification_plan` | Tests + CI pipeline | pytest suite + soak-test infrastructure |
| `pipeline_stages` | `atoms/` pipeline | 5-stage atomize→narrate→link→reconcile→fanout |
| `graph_indices` | `governance/dependency_graph.py` | Directed graph with produces/consumes edge indexing |
| `functional_taxonomy` | `distill/taxonomy.py` | 15 operational patterns with classification signals |
| `era_model` | Context: ERA-003 post-flood governance | Era transitions tracked in governance state |
| `system_dynamics` | `metrics/organism.py` | SystemOrganism + health pulse calculation |
| `ammoi_reconciliation` | `corpus/scanner.py` + `metrics/organism.py` | Cross-source concept reconciliation |
| `event_spine` | `dispatch/` | Event payload validation + cascade routing |
| `heartbeat_affect` | `metrics/organism.py` pulse functions | System liveness detection |

### Tier B — Requires judgment (12 concepts)

| Concept | Likely Location | Notes |
|---------|----------------|-------|
| `system_manifesto` | organvm-corpvs-testamentvm | The corpus IS the manifesto |
| `ontology_charter` | organvm-ontologia | Entity identity + ULID registry |
| `entity_primitives` | organvm-ontologia + organ_config.py | Formation types as primitives |
| `invariant_register` | governance/audit.py | Enforces invariants (partial) |
| `logical_specification` | governance/dependency_graph.py + state_machine.py | Logical rules encoded |
| `architectural_specification` | organ_config.py | 8-organ architecture definition |
| `traceability_matrix` | corpus/ + MCP corpus_trace tool | This tool IS the trace matrix |
| `evolution_law` | governance/state_machine.py | Promotion state machine |
| `dispersio_formalis` | ORGAN-VII repos (kerygma) | Content syndication |
| `process_sequence_governance` | governance/ + coordination/ | Process sequencing |
| `gravitas_culturalis` | ecosystem/ or pulse | Cultural weight (partial) |
| `system_manifestation` | contextmd/ | System rendering to context files |

### Tier C — Genuinely unimplemented (5 concepts)

| Concept | Status |
|---------|--------|
| `resource_compute_constraints` | No resource budget tracking yet |
| `escalation_attention_policy` | No attention-based escalation logic |
| `epistemic_routing` | No epistemic routing beyond formation signals |
| `agent_authority_matrix` | Only claims registry, no authority matrix |
| `architectural_patterns` | SPEC-009 content needs verification |

**These remain as documented gaps** — note in IRF, don't force-wire.

### Edit format for seed.yaml

Append to existing `implements:` list:
```yaml
  - concept: <concept_id>
    zettel_source: "post-flood/specs/<SPEC-dir>/grounding.md"
    aspect: "<module_path> -- <description>"
```

### Files to edit
- `/Users/4jp/Workspace/organvm/organvm-engine/seed.yaml` — +16 Tier A, +8 Tier B entries
- `/Users/4jp/Workspace/organvm/organvm-corpvs-testamentvm/seed.yaml` — +1 (`system_manifesto`)
- `/Users/4jp/Workspace/organvm/organvm-ontologia/seed.yaml` — +2 (`ontology_charter`, `entity_primitives`)
- `/Users/4jp/Workspace/organvm/organvm-mcp-server/seed.yaml` — +1 (`traceability_matrix`)

---

## Phase 4: Branch Reconciliation

- Merge `feat/contrib-backflow-pipeline` → main (self-contained, no conflicts)
- Create `feat/constitutional-wiring` from main for concept additions
- Or: work directly on the existing branch since it's conceptually related

---

## Phase 5: Verification Gate

```bash
# Re-scan
organvm corpus scan --corpus-dir ~/Workspace/organvm/post-flood \
  --workspace ~/Workspace/organvm -o ~/Workspace/organvm/post-flood/data/corpus-graph.json

# Tests
cd ~/Workspace/organvm/organvm-engine && pytest tests/ -v
cd ~/Workspace/organvm/organvm-mcp-server && pytest tests/ -v

# Gap report
organvm corpus gaps --corpus-dir ~/Workspace/organvm/post-flood \
  --workspace ~/Workspace/organvm -v
```

**Success criteria**:
- Unimplemented count: 33 → ~5 (Tier C only)
- All existing tests pass
- `corpus_trace` returns implementations for all Tier A/B concepts
- Updated `corpus-graph.json` artifact saved

---

## Critical Files

| File | Role |
|------|------|
| `organvm-engine/seed.yaml` | Primary target for implements[] additions |
| `organvm-engine/src/organvm_engine/corpus/scanner.py` | Reads seed.yaml implements → builds IMPLEMENTS edges |
| `organvm-mcp-server/src/organvm_mcp/data/loader.py:160` | Broken path: `corpus_dir().parent / "post-flood"` |
| `organvm-engine/src/organvm_engine/paths.py` | Path resolution foundation |
| `post-flood/specs/` | SPEC grounding docs (read-only reference) |
| `post-flood/archive_original/.zettel-index.yaml` | Zettelkasten concept index |
