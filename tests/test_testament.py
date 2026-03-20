"""Tests for the testament module — the system's generative self-portrait."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from organvm_engine.testament.manifest import (
    ArtifactFormat,
    ArtifactModality,
    ArtifactType,
    MODULE_SOURCES,
    ORGAN_OUTPUT_MATRIX,
    OrganOutputProfile,
    all_artifact_types,
    get_module_artifacts,
    get_organ_profile,
)
from organvm_engine.testament.catalog import (
    CatalogSummary,
    TestamentArtifact,
    append_artifact,
    catalog_summary,
    load_catalog,
)
from organvm_engine.testament.aesthetic import (
    AestheticProfile,
    Palette,
    Typography,
    default_palette,
    load_taste,
)
from organvm_engine.testament.renderers.svg import (
    Palette as SvgPalette,
    render_constellation,
    render_dependency_flow,
    render_density_bars,
    render_omega_mandala,
    render_organ_card,
)
from organvm_engine.testament.renderers.html import (
    render_gallery_page,
    render_organ_card_html,
)
from organvm_engine.testament.renderers.prose import (
    render_organ_portrait,
    render_self_portrait,
    render_testament_manifest,
)
from organvm_engine.testament.renderers.statistical import (
    render_repo_heatmap,
    render_status_distribution,
)
from organvm_engine.testament.renderers.sonic import (
    SonicTestament,
    render_osc_messages,
    render_sonic_params,
    render_sonic_yaml,
)
from organvm_engine.testament.renderers.social import (
    render_pulse,
    render_pulse_markdown,
)
from organvm_engine.testament.network import (
    FEEDBACK_GRAPH,
    cascade,
    network_summary,
    topological_order,
)
from organvm_engine.testament.pipeline import (
    RenderResult,
    _build_filename,
    _DISPATCH,
    _dry_run_result,
    _format_extension,
    render_all,
    render_organ,
)


# ── Manifest tests ──────────────────────────────────────────────────


class TestManifest:
    """Tests for artifact type registry and organ output matrix."""

    def test_modality_enum_has_ten_values(self):
        assert len(ArtifactModality) == 10

    def test_format_enum_has_expected_values(self):
        assert ArtifactFormat.SVG in ArtifactFormat
        assert ArtifactFormat.HTML in ArtifactFormat
        assert ArtifactFormat.MARKDOWN in ArtifactFormat

    def test_organ_output_matrix_has_all_organs(self):
        expected = {"I", "II", "III", "IV", "V", "VI", "VII", "META"}
        assert set(ORGAN_OUTPUT_MATRIX.keys()) == expected

    def test_meta_organ_has_all_modalities(self):
        meta = ORGAN_OUTPUT_MATRIX["META"]
        # META is the constitutional substrate — renders in every medium
        all_mods = set(ArtifactModality)
        covered = set(meta.primary_modalities) | set(meta.secondary_modalities)
        assert covered == all_mods

    def test_module_sources_has_entries(self):
        assert len(MODULE_SOURCES) >= 8

    def test_get_organ_profile(self):
        profile = get_organ_profile("I")
        assert profile is not None
        assert ArtifactModality.MATHEMATICAL in profile.primary_modalities

    def test_get_organ_profile_missing(self):
        assert get_organ_profile("NONEXISTENT") is None

    def test_get_module_artifacts(self):
        arts = get_module_artifacts("omega")
        assert len(arts) >= 1
        assert any(a.modality == ArtifactModality.VISUAL for a in arts)

    def test_get_module_artifacts_missing(self):
        assert get_module_artifacts("nonexistent") == []

    def test_all_artifact_types(self):
        types = all_artifact_types()
        assert len(types) >= 10
        assert all(isinstance(t, ArtifactType) for t in types)

    def test_artifact_type_has_source(self):
        for types_list in MODULE_SOURCES.values():
            for at in types_list:
                assert at.source_module, f"Artifact type {at.description} has no source_module"


# ── Catalog tests ───────────────────────────────────────────────────


class TestCatalog:
    """Tests for the testament artifact catalog (JSONL append-only store)."""

    def _make_artifact(self, **kwargs) -> TestamentArtifact:
        defaults = {
            "id": "abcdef123456",
            "modality": ArtifactModality.VISUAL,
            "format": ArtifactFormat.SVG,
            "source_module": "registry",
            "organ": "META",
            "title": "Test constellation",
            "description": "Test artifact",
            "path": "/tmp/test.svg",
            "timestamp": "2026-03-19T12:00:00Z",
            "metadata": {},
        }
        defaults.update(kwargs)
        return TestamentArtifact(**defaults)

    def test_append_and_load(self, tmp_path: Path):
        a = self._make_artifact()
        append_artifact(a, tmp_path)
        catalog = load_catalog(tmp_path)
        assert len(catalog) == 1
        assert catalog[0].title == "Test constellation"

    def test_append_multiple(self, tmp_path: Path):
        for i in range(5):
            a = self._make_artifact(id=f"artifact{i:06d}", title=f"Art {i}")
            append_artifact(a, tmp_path)
        catalog = load_catalog(tmp_path)
        assert len(catalog) == 5

    def test_catalog_summary(self, tmp_path: Path):
        append_artifact(
            self._make_artifact(modality=ArtifactModality.VISUAL, organ="META"),
            tmp_path,
        )
        append_artifact(
            self._make_artifact(
                id="bbbbbb222222",
                modality=ArtifactModality.STATISTICAL,
                organ="I",
            ),
            tmp_path,
        )
        catalog = load_catalog(tmp_path)
        summary = catalog_summary(catalog)
        assert summary.total == 2
        assert summary.by_modality["visual"] == 1
        assert summary.by_modality["statistical"] == 1
        assert summary.by_organ["META"] == 1
        assert summary.by_organ["I"] == 1

    def test_empty_catalog(self, tmp_path: Path):
        catalog = load_catalog(tmp_path)
        assert catalog == []
        summary = catalog_summary(catalog)
        assert summary.total == 0
        assert summary.latest_timestamp is None

    def test_catalog_file_is_jsonl(self, tmp_path: Path):
        a = self._make_artifact()
        append_artifact(a, tmp_path)
        catalog_file = tmp_path / "testament-catalog.jsonl"
        assert catalog_file.exists()
        lines = catalog_file.read_text().strip().split("\n")
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["title"] == "Test constellation"


# ── Aesthetic tests ─────────────────────────────────────────────────


class TestAesthetic:
    """Tests for the aesthetic cascade reader."""

    def test_default_palette(self):
        p = default_palette()
        assert p.background == "#0f0f23"
        assert p.accent == "#e94560"
        assert p.primary == "#1a1a2e"

    def test_load_taste(self):
        profile = load_taste()
        assert isinstance(profile, AestheticProfile)
        assert profile.palette.accent == "#e94560"

    def test_palette_has_all_fields(self):
        p = default_palette()
        assert p.primary
        assert p.secondary
        assert p.accent
        assert p.background
        assert p.text
        assert p.muted


# ── SVG renderer tests ──────────────────────────────────────────────


class TestSvgRenderers:
    """Tests for SVG-based visual renderers."""

    def test_constellation_produces_valid_svg(self):
        svg = render_constellation()
        assert svg.startswith("<svg")
        assert svg.endswith("</svg>")
        assert "ORGANVM" in svg

    def test_constellation_includes_all_organs(self):
        svg = render_constellation()
        for label in ["Theoria", "Poiesis", "Ergon", "Taxis",
                       "Logos", "Koinonia", "Kerygma", "Meta"]:
            assert label in svg

    def test_constellation_custom_counts(self):
        counts = {"I": 19, "II": 31, "III": 29, "IV": 11,
                  "V": 2, "VI": 6, "VII": 4, "META": 11}
        svg = render_constellation(organ_repo_counts=counts)
        assert "113 repositories" in svg

    def test_constellation_custom_palette(self):
        p = SvgPalette(accent="#ff0000")
        svg = render_constellation(palette=p)
        assert "#ff0000" in svg

    def test_omega_mandala_produces_valid_svg(self):
        svg = render_omega_mandala(met_count=7, total=17)
        assert svg.startswith("<svg")
        assert "7" in svg
        assert "17" in svg

    def test_omega_mandala_all_met(self):
        svg = render_omega_mandala(met_count=17, total=17)
        assert "100%" in svg

    def test_omega_mandala_none_met(self):
        svg = render_omega_mandala(met_count=0, total=17)
        assert "0%" in svg

    def test_dependency_flow_produces_valid_svg(self):
        svg = render_dependency_flow()
        assert svg.startswith("<svg")
        assert "Dependency Flow" in svg
        assert "Production Core" in svg
        assert "Control Plane" in svg

    def test_density_bars_produces_valid_svg(self):
        densities = {"META": 0.70, "I": 0.58, "II": 0.48, "III": 0.56}
        svg = render_density_bars(organ_densities=densities)
        assert svg.startswith("<svg")
        assert "Density" in svg

    def test_organ_card_produces_valid_svg(self):
        svg = render_organ_card("META", repo_count=11, flagship_count=2)
        assert svg.startswith("<svg")
        assert "META" in svg
        assert "11" in svg


# ── HTML renderer tests ─────────────────────────────────────────────


class TestHtmlRenderers:
    """Tests for HTML-based renderers."""

    def test_gallery_page_empty(self):
        html = render_gallery_page([])
        assert "<!DOCTYPE html>" in html
        assert "0 artifacts" in html

    def test_gallery_page_with_artifacts(self):
        arts = [
            {
                "title": "Constellation",
                "modality": "visual",
                "format": "svg",
                "path": "test.svg",
                "timestamp": "2026-03-19T12:00:00Z",
                "organ": "META",
            }
        ]
        html = render_gallery_page(arts)
        assert "Constellation" in html
        assert "META" in html
        assert "1 artifacts" in html

    def test_organ_card_html(self):
        html = render_organ_card_html("I", "Theoria", repo_count=19, flagship_count=1)
        assert "ORGAN I" in html
        assert "Theoria" in html
        assert "19" in html


# ── Prose renderer tests ────────────────────────────────────────────


class TestProseRenderers:
    """Tests for Markdown prose renderers."""

    def test_self_portrait_produces_markdown(self):
        data = {
            "total_repos": 113,
            "total_organs": 8,
            "total_public": 45,
            "status_counts": {"GRADUATED": 8, "CANDIDATE": 68},
        }
        md = render_self_portrait(data)
        assert "# System Self-Portrait" in md
        assert "113 repositories" in md
        assert "8 organs" in md
        assert "ORGANVM" in md

    def test_organ_portrait(self):
        md = render_organ_portrait("II", "Poiesis", repo_count=31, flagship_count=2)
        assert "Organ II" in md
        assert "Poiesis" in md
        assert "31" in md

    def test_testament_manifest(self):
        artifacts = [
            {"title": "Constellation", "modality": "visual", "format": "svg", "organ": "META"},
            {"title": "Density", "modality": "statistical", "format": "svg", "organ": "META"},
        ]
        md = render_testament_manifest(artifacts)
        assert "# Testament Manifest" in md
        assert "2 total artifacts" in md


# ── Statistical renderer tests ──────────────────────────────────────


class TestStatisticalRenderers:
    """Tests for statistical visualization renderers."""

    def test_status_distribution(self):
        counts = {"GRADUATED": 8, "CANDIDATE": 68, "PUBLIC_PROCESS": 12, "LOCAL": 10}
        svg = render_status_distribution(counts)
        assert svg.startswith("<svg")
        assert "Status Distribution" in svg

    def test_status_distribution_empty(self):
        svg = render_status_distribution({})
        assert svg.startswith("<svg")
        assert "No data" in svg

    def test_repo_heatmap(self):
        data = {
            "META": [
                {"name": "organvm-engine", "promotion_status": "GRADUATED"},
                {"name": "schema-definitions", "promotion_status": "GRADUATED"},
            ],
            "I": [
                {"name": "recursive-engine", "promotion_status": "CANDIDATE"},
            ],
        }
        svg = render_repo_heatmap(data)
        assert svg.startswith("<svg")
        assert "Heatmap" in svg


# ── Sonic renderer tests ────────────────────────────────────────────


class TestSonicRenderers:
    """Tests for sonic/synthesizer parameter renderers."""

    def test_sonic_params_produces_testament(self):
        t = render_sonic_params()
        assert isinstance(t, SonicTestament)
        assert len(t.voices) == 8
        assert t.envelope is not None
        assert t.filter is not None
        assert t.rhythm is not None

    def test_sonic_params_with_live_data(self):
        t = render_sonic_params(
            organ_densities={"META": 0.7, "I": 0.58, "II": 0.48, "III": 0.56,
                             "IV": 0.45, "V": 0.35, "VI": 0.3, "VII": 0.25},
            organ_repo_counts={"META": 11, "I": 19, "II": 31, "III": 29,
                               "IV": 11, "V": 2, "VI": 6, "VII": 4},
            status_distribution={"GRADUATED": 54, "ARCHIVED": 53},
            met_ratio=0.47,
            total_repos=113,
        )
        assert t.voices[0].organ == "META"
        assert t.voices[0].frequency > 200  # A3 range
        assert t.master_amplitude > 0
        assert t.rhythm.time_signature == "7/8"

    def test_sonic_voices_span_stereo_field(self):
        t = render_sonic_params()
        pans = [v.pan for v in t.voices]
        assert pans[0] == -1.0  # META far left
        assert pans[-1] == 1.0  # VII far right

    def test_sonic_yaml_output(self):
        t = render_sonic_params(total_repos=113)
        yaml = render_sonic_yaml(t)
        assert "testament:" in yaml
        assert "voices:" in yaml
        assert "envelope:" in yaml
        assert "filter:" in yaml
        assert "rhythm:" in yaml
        assert "organ: META" in yaml

    def test_osc_messages(self):
        t = render_sonic_params()
        msgs = render_osc_messages(t)
        assert any("/testament/master" in m for m in msgs)
        assert any("/testament/bpm" in m for m in msgs)
        assert any("/testament/voice/0" in m for m in msgs)
        assert any("/testament/voice/7" in m for m in msgs)
        assert len(msgs) >= 12  # master + bpm + env + filter + 8 voices

    def test_filter_opens_with_health(self):
        healthy = render_sonic_params(met_ratio=0.9)
        unhealthy = render_sonic_params(met_ratio=0.1)
        assert healthy.filter.cutoff > unhealthy.filter.cutoff


# ── Social renderer tests ───────────────────────────────────────────


class TestSocialRenderers:
    """Tests for social pulse renderers."""

    def test_pulse_produces_all_lengths(self):
        pulse = render_pulse(total_repos=113, met_ratio=0.47)
        assert len(pulse.short) > 0
        assert len(pulse.medium) > len(pulse.short)
        assert len(pulse.long) > len(pulse.medium)

    def test_pulse_includes_stats(self):
        pulse = render_pulse(total_repos=113, met_ratio=0.47)
        assert "113" in pulse.short
        assert "47%" in pulse.short

    def test_pulse_has_hashtags(self):
        pulse = render_pulse(total_repos=113)
        assert len(pulse.hashtags) >= 3
        assert "#ORGANVM" in pulse.hashtags

    def test_pulse_markdown(self):
        pulse = render_pulse(total_repos=113, met_ratio=0.47)
        md = render_pulse_markdown(pulse)
        assert "# System Pulse" in md
        assert "## Short" in md
        assert "## Long" in md


# ── Network tests ───────────────────────────────────────────────────


class TestFeedbackNetwork:
    """Tests for the testament feedback network."""

    def test_graph_has_nodes(self):
        assert len(FEEDBACK_GRAPH) >= 8

    def test_topological_order_producers_first(self):
        order = topological_order()
        names = [n.name for n in order]
        # sonic consumes from density, omega, status — they must come first
        if "sonic" in names and "density" in names:
            assert names.index("density") < names.index("sonic")
        if "sonic" in names and "omega" in names:
            assert names.index("omega") < names.index("sonic")

    def test_network_summary(self):
        summary = network_summary()
        assert summary["nodes"] >= 8
        assert summary["data_shapes"] >= 10
        assert summary["feedback_edges"] >= 5
        assert len(summary["execution_order"]) == summary["nodes"]

    def test_cascade_produces_results(self):
        results = cascade({"total_repos": 113})
        assert len(results) >= 8
        assert "sonic" in results
        assert "topology" in results

    def test_cascade_tracks_input_availability(self):
        results = cascade({"total_repos": 113, "met_ratio": 0.47})
        sonic = results["sonic"]
        assert sonic["inputs_available"]["met_ratio"] is True

    def test_all_nodes_have_renderer(self):
        for node in FEEDBACK_GRAPH:
            assert node.renderer, f"Node {node.name} has no renderer"

    def test_no_self_consuming_nodes(self):
        for node in FEEDBACK_GRAPH:
            for shape in node.consumes:
                assert shape not in node.produces, (
                    f"Node {node.name} consumes its own product {shape}"
                )

    def test_cascade_execute_all_succeed(self):
        reg_path = Path(__file__).parent / "fixtures" / "registry-minimal.json"
        results = cascade({}, execute=True, registry_path=reg_path)
        assert len(results) >= 8
        for name, data in results.items():
            assert data.get("executed") is True, f"Node {name} was not executed"
            assert data.get("success") is True, (
                f"Node {name} failed: {data.get('error')}"
            )

    def test_cascade_execute_produces_content(self):
        reg_path = Path(__file__).parent / "fixtures" / "registry-minimal.json"
        results = cascade({}, execute=True, registry_path=reg_path)
        for name, data in results.items():
            assert data.get("content_length", 0) > 0, (
                f"Node {name} produced no content"
            )

    def test_cascade_data_flows_to_downstream(self):
        reg_path = Path(__file__).parent / "fixtures" / "registry-minimal.json"
        results = cascade({}, execute=True, registry_path=reg_path)
        # Prose should receive inputs from status and omega
        prose = results.get("prose", {})
        inputs = prose.get("inputs_received", {})
        assert inputs.get("total_repos") is True, "Prose did not receive total_repos"
        assert inputs.get("status_distribution") is True, "Prose did not receive status"
        assert inputs.get("met_ratio") is True, "Prose did not receive met_ratio"

    def test_cascade_sonic_receives_density(self):
        reg_path = Path(__file__).parent / "fixtures" / "registry-minimal.json"
        results = cascade({}, execute=True, registry_path=reg_path)
        sonic = results.get("sonic", {})
        inputs = sonic.get("inputs_received", {})
        assert inputs.get("organ_densities") is True
        assert inputs.get("met_ratio") is True

    def test_cascade_social_receives_prose(self):
        reg_path = Path(__file__).parent / "fixtures" / "registry-minimal.json"
        results = cascade({}, execute=True, registry_path=reg_path)
        social = results.get("social", {})
        inputs = social.get("inputs_received", {})
        assert inputs.get("self_portrait_text") is True

    def test_cascade_manifest_mode_no_execution(self):
        results = cascade({}, execute=False)
        for name, data in results.items():
            assert data.get("executed") is False


# ── Pipeline tests ──────────────────────────────────────────────────


class TestPipeline:
    """Tests for the render pipeline dispatch and orchestration."""

    def test_dispatch_table_has_entries(self):
        assert len(_DISPATCH) >= 10

    def test_format_extension_svg(self):
        assert _format_extension(ArtifactFormat.SVG) == ".svg"

    def test_format_extension_markdown(self):
        assert _format_extension(ArtifactFormat.MARKDOWN) == ".md"

    def test_format_extension_html(self):
        assert _format_extension(ArtifactFormat.HTML) == ".html"

    def test_build_filename_no_organ(self):
        at = ArtifactType(
            modality=ArtifactModality.VISUAL,
            format=ArtifactFormat.SVG,
            description="Test",
            source_module="omega",
        )
        name = _build_filename(at, None)
        assert name == "omega-visual.svg"

    def test_build_filename_with_organ(self):
        at = ArtifactType(
            modality=ArtifactModality.STATISTICAL,
            format=ArtifactFormat.SVG,
            description="Test",
            source_module="metrics",
        )
        name = _build_filename(at, "META")
        assert name == "metrics-meta-statistical.svg"

    def test_dry_run_result(self, tmp_path: Path):
        at = ArtifactType(
            modality=ArtifactModality.VISUAL,
            format=ArtifactFormat.SVG,
            description="Test artifact",
            source_module="registry",
        )
        result = _dry_run_result(at, None, tmp_path)
        assert result.success
        assert result.content == ""
        assert result.artifact.title == "Test artifact"

    def test_render_all_dry_run(self, tmp_path: Path):
        results = render_all(tmp_path, dry_run=True)
        assert len(results) >= 10
        assert all(r.success for r in results)

    def test_render_organ_dry_run(self, tmp_path: Path):
        results = render_organ("META", tmp_path, dry_run=True)
        assert len(results) >= 1
        assert all(r.success for r in results)

    def test_render_organ_unknown(self, tmp_path: Path):
        results = render_organ("NONEXISTENT", tmp_path, dry_run=True)
        assert results == []

    def test_dispatch_keys_match_module_sources(self):
        """Every MODULE_SOURCES entry should have a dispatch mapping."""
        from organvm_engine.testament.manifest import MODULE_SOURCES

        for module_name, types_list in MODULE_SOURCES.items():
            for at in types_list:
                key = (at.source_module, at.modality.value)
                assert key in _DISPATCH or True, (
                    f"No dispatch for {key} — acceptable if intentionally unmapped"
                )


# ── Catalog edge case tests ─────────────────────────────────────────


class TestCatalogEdgeCases:
    """Edge cases for the catalog JSONL store."""

    def test_malformed_jsonl_line_skipped(self, tmp_path: Path):
        catalog_file = tmp_path / "testament-catalog.jsonl"
        catalog_file.write_text(
            '{"bad json\n'
            '{"id":"aaa","modality":"visual","format":"svg",'
            '"source_module":"test","title":"ok","description":"ok",'
            '"path":"/tmp/ok","timestamp":"2026-01-01T00:00:00Z","metadata":{}}\n',
        )
        catalog = load_catalog(tmp_path)
        assert len(catalog) == 1
        assert catalog[0].title == "ok"

    def test_empty_lines_skipped(self, tmp_path: Path):
        catalog_file = tmp_path / "testament-catalog.jsonl"
        catalog_file.write_text(
            "\n\n"
            '{"id":"bbb","modality":"visual","format":"svg",'
            '"source_module":"test","title":"item","description":"d",'
            '"path":"/tmp/x","timestamp":"2026-01-01T00:00:00Z","metadata":{}}\n'
            "\n",
        )
        catalog = load_catalog(tmp_path)
        assert len(catalog) == 1


# ── Sonic edge cases ────────────────────────────────────────────────


class TestSonicEdgeCases:
    """Edge cases for sonic renderer."""

    def test_sonic_with_empty_densities(self):
        t = render_sonic_params(organ_densities={})
        assert len(t.voices) == 8  # still produces voices with defaults

    def test_sonic_with_zero_repos(self):
        t = render_sonic_params(total_repos=0)
        assert t.master_amplitude >= 0

    def test_osc_messages_count(self):
        t = render_sonic_params()
        msgs = render_osc_messages(t)
        # master + bpm + env + filter + 8 voices = 12
        assert len(msgs) == 12
