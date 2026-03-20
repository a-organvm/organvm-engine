"""Render pipeline — orchestrates artifact generation from system data.

Loads aesthetic profiles, iterates declared module sources, dispatches
to the correct renderer function, writes output files, and catalogs results.
Uses an explicit dispatch mapping rather than dynamic imports.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from organvm_engine.testament.aesthetic import (
    AestheticProfile,
    load_organ_aesthetic,
    load_taste,
)
from organvm_engine.testament.catalog import (
    TestamentArtifact,
    append_artifact,
)
from organvm_engine.testament.manifest import (
    MODULE_SOURCES,
    ORGAN_OUTPUT_MATRIX,
    ArtifactFormat,
    ArtifactType,
)

logger = logging.getLogger(__name__)


@dataclass
class RenderResult:
    """Outcome of rendering a single artifact."""

    artifact: TestamentArtifact
    content: str | bytes
    success: bool
    error: str | None = None


def _format_extension(fmt: ArtifactFormat) -> str:
    """Map an ArtifactFormat to a file extension."""
    extensions: dict[ArtifactFormat, str] = {
        ArtifactFormat.SVG: ".svg",
        ArtifactFormat.HTML: ".html",
        ArtifactFormat.MARKDOWN: ".md",
        ArtifactFormat.JSON: ".json",
        ArtifactFormat.LATEX: ".tex",
        ArtifactFormat.TXT: ".txt",
        ArtifactFormat.PNG: ".png",
    }
    return extensions.get(fmt, ".bin")


def _build_filename(artifact_type: ArtifactType, organ_key: str | None) -> str:
    """Build a descriptive filename for a rendered artifact."""
    parts = [artifact_type.source_module]
    if organ_key:
        parts.append(organ_key.lower())
    parts.append(artifact_type.modality.value)
    base = "-".join(parts)
    return base + _format_extension(artifact_type.format)


# ---------------------------------------------------------------------------
# Renderer dispatch mapping
# ---------------------------------------------------------------------------
# Maps (source_module, modality_value) → callable that returns content string.
# Each callable accepts (registry_path, aesthetic, organ_key) and returns str.
# ---------------------------------------------------------------------------


def _render_topology(
    registry_path: Path | None, aesthetic: AestheticProfile, organ_key: str | None,
) -> str:
    from organvm_engine.testament.renderers.svg import render_constellation
    from organvm_engine.testament.sources import topology_data

    data = topology_data(registry_path)
    palette = _to_svg_palette(aesthetic)
    return render_constellation(organ_repo_counts=data["organ_repo_counts"], palette=palette)


def _render_dependency(
    registry_path: Path | None, aesthetic: AestheticProfile, organ_key: str | None,
) -> str:
    from organvm_engine.testament.renderers.svg import render_dependency_flow

    palette = _to_svg_palette(aesthetic)
    return render_dependency_flow(palette=palette)


def _render_governance_proof(
    registry_path: Path | None, aesthetic: AestheticProfile, organ_key: str | None,
) -> str:
    from organvm_engine.testament.renderers.prose import render_self_portrait
    from organvm_engine.testament.sources import system_summary

    data = system_summary(registry_path)
    return render_self_portrait(data)


def _render_density(
    registry_path: Path | None, aesthetic: AestheticProfile, organ_key: str | None,
) -> str:
    from organvm_engine.testament.renderers.svg import render_density_bars
    from organvm_engine.testament.sources import density_data

    data = density_data(registry_path)
    palette = _to_svg_palette(aesthetic)
    return render_density_bars(organ_densities=data["organ_densities"], palette=palette)


def _render_timeline(
    registry_path: Path | None, aesthetic: AestheticProfile, organ_key: str | None,
) -> str:
    from organvm_engine.testament.renderers.statistical import render_status_distribution
    from organvm_engine.testament.sources import system_summary

    data = system_summary(registry_path)
    palette = _to_svg_palette(aesthetic)
    return render_status_distribution(data["status_counts"], palette=palette)


def _render_omega(
    registry_path: Path | None, aesthetic: AestheticProfile, organ_key: str | None,
) -> str:
    from organvm_engine.testament.renderers.svg import render_omega_mandala
    from organvm_engine.testament.sources import omega_data

    data = omega_data(registry_path)
    palette = _to_svg_palette(aesthetic)
    return render_omega_mandala(
        criteria=data["criteria"], met_count=data["met_count"],
        total=data["total"], palette=palette,
    )


def _render_seed_flow(
    registry_path: Path | None, aesthetic: AestheticProfile, organ_key: str | None,
) -> str:
    from organvm_engine.testament.renderers.svg import render_dependency_flow

    palette = _to_svg_palette(aesthetic)
    return render_dependency_flow(palette=palette)


def _render_entity_tree(
    registry_path: Path | None, aesthetic: AestheticProfile, organ_key: str | None,
) -> str:
    from organvm_engine.testament.renderers.svg import render_constellation
    from organvm_engine.testament.sources import topology_data

    data = topology_data(registry_path)
    palette = _to_svg_palette(aesthetic)
    return render_constellation(organ_repo_counts=data["organ_repo_counts"], palette=palette)


def _render_competitive_radar(
    registry_path: Path | None, aesthetic: AestheticProfile, organ_key: str | None,
) -> str:
    from organvm_engine.testament.renderers.svg import render_density_bars
    from organvm_engine.testament.sources import density_data

    data = density_data(registry_path)
    palette = _to_svg_palette(aesthetic)
    return render_density_bars(organ_densities=data["organ_densities"], palette=palette)


def _render_session_timeline(
    registry_path: Path | None, aesthetic: AestheticProfile, organ_key: str | None,
) -> str:
    from organvm_engine.testament.renderers.statistical import render_status_distribution
    from organvm_engine.testament.sources import system_summary

    data = system_summary(registry_path)
    palette = _to_svg_palette(aesthetic)
    return render_status_distribution(data["status_counts"], palette=palette)


def _render_pitch(
    registry_path: Path | None, aesthetic: AestheticProfile, organ_key: str | None,
) -> str:
    from organvm_engine.testament.renderers.html import render_gallery_page

    return render_gallery_page([], title="ORGANVM Pitch")


def _render_content_post(
    registry_path: Path | None, aesthetic: AestheticProfile, organ_key: str | None,
) -> str:
    from organvm_engine.testament.renderers.social import render_pulse, render_pulse_markdown
    from organvm_engine.testament.sources import density_data, omega_data, topology_data

    topo = topology_data(registry_path)
    omega = omega_data(registry_path)
    dens = density_data(registry_path)
    met_ratio = omega["met_count"] / omega["total"] if omega["total"] else 0
    pulse = render_pulse(
        total_repos=topo["total_repos"],
        met_ratio=met_ratio,
        organ_densities=dens["organ_densities"],
    )
    return render_pulse_markdown(pulse)


def _render_sonic(
    registry_path: Path | None, aesthetic: AestheticProfile, organ_key: str | None,
) -> str:
    from organvm_engine.testament.renderers.sonic import render_sonic_params, render_sonic_yaml
    from organvm_engine.testament.sources import (
        density_data,
        omega_data,
        system_summary,
        topology_data,
    )

    topo = topology_data(registry_path)
    omega = omega_data(registry_path)
    dens = density_data(registry_path)
    summary = system_summary(registry_path)
    met_ratio = omega["met_count"] / omega["total"] if omega["total"] else 0

    testament = render_sonic_params(
        organ_densities=dens["organ_densities"],
        organ_repo_counts=topo["organ_repo_counts"],
        status_distribution=summary["status_counts"],
        met_ratio=met_ratio,
        total_repos=topo["total_repos"],
    )
    return render_sonic_yaml(testament)


# The dispatch table: (source_module, modality_value) → renderer callable
_DISPATCH: dict[tuple[str, str], Callable[..., str]] = {
    ("registry", "schematic"): _render_topology,
    ("governance", "schematic"): _render_dependency,
    ("governance", "mathematical"): _render_governance_proof,
    ("metrics", "statistical"): _render_density,
    ("metrics", "statistical_timeline"): _render_timeline,
    ("omega", "visual"): _render_omega,
    ("seed", "schematic"): _render_seed_flow,
    ("ontologia", "schematic"): _render_entity_tree,
    ("ecosystem", "statistical"): _render_competitive_radar,
    ("session", "statistical"): _render_session_timeline,
    ("pitchdeck", "visual"): _render_pitch,
    ("content", "social"): _render_content_post,
}


def _to_svg_palette(aesthetic: AestheticProfile) -> Any:
    """Convert AestheticProfile to SVG Palette."""
    from organvm_engine.testament.renderers.svg import Palette as SvgPalette

    return SvgPalette(
        primary=aesthetic.palette.primary,
        secondary=aesthetic.palette.secondary,
        accent=aesthetic.palette.accent,
        background=aesthetic.palette.background,
        text=aesthetic.palette.text,
        muted=aesthetic.palette.muted,
    )


def _dispatch_renderer(
    artifact_type: ArtifactType,
    organ_key: str | None,
    output_dir: Path,
    aesthetic: AestheticProfile,
    registry_path: Path | None = None,
) -> RenderResult:
    """Dispatch to the correct renderer for an artifact type."""
    filename = _build_filename(artifact_type, organ_key)
    output_path = output_dir / filename

    artifact = TestamentArtifact(
        modality=artifact_type.modality,
        format=artifact_type.format,
        source_module=artifact_type.source_module,
        organ=organ_key,
        title=artifact_type.description,
        description=f"{artifact_type.description} from {artifact_type.source_module}",
        path=str(output_path),
        metadata={
            "palette_primary": aesthetic.palette.primary,
            "palette_accent": aesthetic.palette.accent,
        },
    )

    key = (artifact_type.source_module, artifact_type.modality.value)
    render_fn = _DISPATCH.get(key)

    if render_fn is None:
        return RenderResult(
            artifact=artifact, content="", success=False,
            error=f"No renderer mapped for ({key[0]}, {key[1]})",
        )

    try:
        content = render_fn(registry_path, aesthetic, organ_key)
        return RenderResult(artifact=artifact, content=content, success=True)
    except Exception as exc:
        return RenderResult(
            artifact=artifact, content="", success=False,
            error=f"Renderer error: {exc}",
        )


def _dry_run_result(
    artifact_type: ArtifactType,
    organ_key: str | None,
    output_dir: Path,
    label: str = "",
) -> RenderResult:
    """Build a dry-run RenderResult without actually rendering."""
    artifact = TestamentArtifact(
        modality=artifact_type.modality,
        format=artifact_type.format,
        source_module=artifact_type.source_module,
        organ=organ_key,
        title=artifact_type.description,
        description=f"[dry-run] {artifact_type.description} {label}".strip(),
        path=str(output_dir / _build_filename(artifact_type, organ_key)),
    )
    return RenderResult(artifact=artifact, content="", success=True)


def render_artifact(
    artifact_type: ArtifactType,
    organ_key: str | None,
    output_dir: Path,
    aesthetic: AestheticProfile,
    registry_path: Path | None = None,
) -> RenderResult:
    """Render a single artifact type and catalog it on success."""
    output_dir.mkdir(parents=True, exist_ok=True)
    result = _dispatch_renderer(
        artifact_type, organ_key, output_dir, aesthetic, registry_path,
    )
    if result.success and result.content:
        output_path = Path(result.artifact.path)
        if isinstance(result.content, bytes):
            output_path.write_bytes(result.content)
        else:
            output_path.write_text(result.content)
        append_artifact(result.artifact)
        logger.info("Rendered %s -> %s", result.artifact.title, result.artifact.path)
    elif not result.success:
        logger.debug("Skipped %s: %s", artifact_type.description, result.error)
    return result


def render_all(
    output_dir: Path,
    dry_run: bool = True,
    registry_path: Path | None = None,
) -> list[RenderResult]:
    """Render all declared artifact types across all modules."""
    aesthetic = load_taste()
    results: list[RenderResult] = []

    for _module_name, artifact_types in MODULE_SOURCES.items():
        for artifact_type in artifact_types:
            if dry_run:
                results.append(_dry_run_result(artifact_type, None, output_dir))
            else:
                results.append(
                    render_artifact(artifact_type, None, output_dir, aesthetic, registry_path),
                )

    return results


def render_organ(
    organ_key: str,
    output_dir: Path,
    dry_run: bool = True,
    registry_path: Path | None = None,
) -> list[RenderResult]:
    """Render artifacts matching a specific organ's modality profile."""
    profile = ORGAN_OUTPUT_MATRIX.get(organ_key)
    if profile is None:
        logger.warning("Unknown organ key: %s", organ_key)
        return []

    all_modalities = set(profile.primary_modalities + profile.secondary_modalities)
    aesthetic = load_organ_aesthetic(organ_key)
    results: list[RenderResult] = []

    for _module_name, artifact_types in MODULE_SOURCES.items():
        for artifact_type in artifact_types:
            if artifact_type.modality not in all_modalities:
                continue
            if dry_run:
                results.append(
                    _dry_run_result(
                        artifact_type, organ_key, output_dir,
                        f"for organ {organ_key}",
                    ),
                )
            else:
                results.append(
                    render_artifact(
                        artifact_type, organ_key, output_dir, aesthetic, registry_path,
                    ),
                )

    return results
