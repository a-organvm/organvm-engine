"""Discovery of parallel and kinship mirrors.

Technical mirrors are automated by scanner.py (dependency files).
This module handles the other two lenses:
- Parallel: projects solving similar problems (semi-automated)
- Kinship: communities with philosophical alignment (human-confirmed)

Discovery uses seed.yaml tags, ecosystem taxonomy, and registry
metadata to suggest mirrors for human review.
"""

from __future__ import annotations

from organvm_engine.network.schema import MirrorEntry

# Domain → relevant parallel projects mapping
# Expanded by research; this is the curated seed set
PARALLEL_PROJECTS: dict[str, list[dict]] = {
    "multi-repo-governance": [
        {"project": "lerna/lerna", "relevance": "JS monorepo orchestration"},
        {"project": "nrwl/nx", "relevance": "Smart monorepo build system"},
        {"project": "vercel/turborepo", "relevance": "High-performance monorepo builds"},
        {"project": "pantsbuild/pants", "relevance": "Polyglot monorepo build system"},
        {"project": "aspect-build/bazel-lib", "relevance": "Bazel build extensions"},
    ],
    "mcp-server": [
        {"project": "modelcontextprotocol/servers", "relevance": "Official MCP server implementations"},
        {"project": "modelcontextprotocol/python-sdk", "relevance": "MCP Python SDK"},
        {"project": "modelcontextprotocol/typescript-sdk", "relevance": "MCP TypeScript SDK"},
    ],
    "generative-art": [
        {"project": "processing/p5.js", "relevance": "Creative coding library"},
        {"project": "nannou-org/nannou", "relevance": "Creative coding in Rust"},
        {"project": "openframeworks/openFrameworks", "relevance": "Creative coding C++ toolkit"},
    ],
    "ai-orchestration": [
        {"project": "langchain-ai/langchain", "relevance": "LLM application framework"},
        {"project": "microsoft/autogen", "relevance": "Multi-agent AI framework"},
        {"project": "stanfordnlp/dspy", "relevance": "Programming with foundation models"},
    ],
    "registry-governance": [
        {"project": "open-policy-agent/opa", "relevance": "Policy-as-code engine"},
        {"project": "cerbos/cerbos", "relevance": "Authorization policy engine"},
    ],
    "schema-validation": [
        {"project": "json-schema-org/json-schema-spec", "relevance": "JSON Schema specification"},
    ],
    "session-analysis": [
        {"project": "brainlid/langchain", "relevance": "Conversation chain analysis"},
    ],
    "dashboard-monitoring": [
        {"project": "grafana/grafana", "relevance": "Observability dashboards"},
        {"project": "apache/superset", "relevance": "Data visualization platform"},
    ],
    "content-pipeline": [
        {"project": "getpelican/pelican", "relevance": "Static site generator for content"},
        {"project": "withastro/astro", "relevance": "Content-focused web framework"},
    ],
    "knowledge-graph": [
        {"project": "neo4j/neo4j", "relevance": "Graph database"},
        {"project": "oxigraph/oxigraph", "relevance": "RDF/SPARQL graph store in Rust"},
    ],
}

# Kinship communities — philosophical alignment, not technology
KINSHIP_COMMUNITIES: list[dict] = [
    {
        "project": "indieweb",
        "platform": "community",
        "relevance": "POSSE principles — own your content, syndicate everywhere",
        "url": "https://indieweb.org",
        "tags": ["posse", "content-ownership", "decentralization"],
    },
    {
        "project": "small-tech-foundation",
        "platform": "community",
        "relevance": "Solo-operator infrastructure, anti-platform philosophy",
        "url": "https://small-tech.org",
        "tags": ["solo-operator", "small-tech", "ethical-tech"],
    },
    {
        "project": "sfpc",
        "platform": "community",
        "relevance": "School for Poetic Computation — artist-technologist collective",
        "url": "https://sfpc.study",
        "tags": ["art-tech", "creative-coding", "education"],
    },
    {
        "project": "gray-area",
        "platform": "community",
        "relevance": "Art + technology incubator and cultural center",
        "url": "https://grayarea.org",
        "tags": ["art-tech", "incubator", "digital-art"],
    },
    {
        "project": "eyebeam",
        "platform": "community",
        "relevance": "Art + technology center fostering creative practice",
        "url": "https://eyebeam.org",
        "tags": ["art-tech", "residency", "new-media"],
    },
    {
        "project": "creative-coding-community",
        "platform": "discord",
        "relevance": "Creative coding practitioners — generative art, interactive media",
        "url": "https://discord.gg/creativecoding",
        "tags": ["creative-coding", "generative-art", "community"],
    },
    {
        "project": "lines-community",
        "platform": "forum",
        "relevance": "Monome/llllllll — modular synthesis, algorithmic music, sound art",
        "url": "https://llllllll.co",
        "tags": ["modular-synthesis", "sound-art", "algorithmic-music"],
    },
    {
        "project": "tools-for-thought",
        "platform": "community",
        "relevance": "Knowledge management, second brain, networked thought",
        "tags": ["knowledge-management", "pkm", "note-taking"],
    },
    {
        "project": "digital-humanities",
        "platform": "community",
        "relevance": "ADHO / Alliance of Digital Humanities Organizations",
        "url": "https://adho.org",
        "tags": ["digital-humanities", "academic", "text-analysis"],
    },
    {
        "project": "open-source-sustainability",
        "platform": "community",
        "relevance": "Open Collective, GitHub Sponsors ecosystem — sustaining OSS",
        "url": "https://opencollective.com",
        "tags": ["oss-sustainability", "funding", "commons"],
    },
    {
        "project": "cooperatives-tech",
        "platform": "community",
        "relevance": "Tech cooperatives and platform cooperativism",
        "url": "https://platform.coop",
        "tags": ["cooperatives", "governance", "institutional-design"],
    },
]


def suggest_parallel_mirrors(
    repo_tags: list[str],
    repo_description: str = "",
    existing_projects: set[str] | None = None,
) -> list[MirrorEntry]:
    """Suggest parallel mirror entries based on repo tags and description.

    Matches repo tags against PARALLEL_PROJECTS domain keys.
    Returns suggestions excluding already-mapped projects.
    """
    skip = existing_projects or set()
    suggestions: list[MirrorEntry] = []
    seen: set[str] = set()

    # Normalize tags for matching
    normalized_tags = {t.lower().replace("_", "-") for t in repo_tags}

    for domain, projects in PARALLEL_PROJECTS.items():
        # Check if any tag matches the domain key or its components
        domain_parts = set(domain.split("-"))
        if normalized_tags & domain_parts or domain in normalized_tags:
            for proj in projects:
                if proj["project"] not in skip and proj["project"] not in seen:
                    seen.add(proj["project"])
                    suggestions.append(MirrorEntry(
                        project=proj["project"],
                        platform="github",
                        relevance=proj["relevance"],
                        engagement=["watch", "discussions"],
                        tags=["suggested", "parallel", domain],
                    ))

    # Also check description for domain keywords
    if repo_description:
        desc_lower = repo_description.lower()
        for domain, projects in PARALLEL_PROJECTS.items():
            if domain.replace("-", " ") in desc_lower:
                for proj in projects:
                    if proj["project"] not in skip and proj["project"] not in seen:
                        seen.add(proj["project"])
                        suggestions.append(MirrorEntry(
                            project=proj["project"],
                            platform="github",
                            relevance=proj["relevance"],
                            engagement=["watch", "discussions"],
                            tags=["suggested", "parallel", domain],
                        ))

    return suggestions


def suggest_kinship_mirrors(
    repo_tags: list[str],
    organ: str = "",
    existing_projects: set[str] | None = None,
) -> list[MirrorEntry]:
    """Suggest kinship mirror entries based on repo and organ context.

    Matches against curated KINSHIP_COMMUNITIES list.
    These are SUGGESTIONS — human confirms before writing.
    """
    skip = existing_projects or set()
    suggestions: list[MirrorEntry] = []

    # Tag-based matching
    normalized_tags = {t.lower().replace("_", "-") for t in repo_tags}

    for community in KINSHIP_COMMUNITIES:
        if community["project"] in skip:
            continue
        comm_tags = set(community.get("tags", []))
        if comm_tags & normalized_tags:
            suggestions.append(MirrorEntry(
                project=community["project"],
                platform=community.get("platform", "community"),
                relevance=community["relevance"],
                engagement=["presence", "dialogue"],
                url=community.get("url"),
                tags=["suggested", "kinship"] + community.get("tags", []),
            ))

    # Organ-based suggestions (always relevant for certain organs)
    organ_upper = organ.upper()
    if organ_upper in ("ORGAN-I", "META") and "tools-for-thought" not in skip:
        suggestions.append(MirrorEntry(
            project="tools-for-thought",
            platform="community",
            relevance="Knowledge management alignment with ORGAN-I theory work",
            engagement=["presence", "dialogue"],
            tags=["suggested", "kinship", "knowledge-management"],
        ))
    if organ_upper == "ORGAN-II":
        for comm in KINSHIP_COMMUNITIES:
            if (
                any(t in comm.get("tags", []) for t in ("creative-coding", "art-tech"))
                and comm["project"] not in skip
            ):
                    suggestions.append(MirrorEntry(
                        project=comm["project"],
                        platform=comm.get("platform", "community"),
                        relevance=comm["relevance"],
                        engagement=["presence", "dialogue"],
                        url=comm.get("url"),
                        tags=["suggested", "kinship", "organ-ii"],
                    ))

    # Deduplicate by project
    seen: set[str] = set()
    unique: list[MirrorEntry] = []
    for s in suggestions:
        if s.project not in seen:
            seen.add(s.project)
            unique.append(s)

    return unique
