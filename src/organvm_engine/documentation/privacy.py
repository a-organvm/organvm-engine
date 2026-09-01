"""Shared privacy matching for generated public documentation artifacts."""

from __future__ import annotations

import re
from typing import Any

REPOSITORY_CHARACTER = r"A-Za-z0-9._-"
PUBLIC_PROSE_REWRITES = (
    ("current personal profile/portfolio", "current individual profile/portfolio"),
    ("current personal profile", "current individual profile"),
    ("the personal profile", "the individual profile"),
    ("personal information management", "individual information management"),
)
PUBLIC_EXACT_REWRITES = {"contrib": "contribution"}


def bounded_identifier_pattern(identifiers: set[str]) -> str:
    """Build a longest-first, repository-token-bounded identifier pattern."""
    if not identifiers:
        return r"(?!)"
    alternatives = "|".join(
        re.escape(value) for value in sorted(identifiers, key=len, reverse=True)
    )
    return (
        rf"(?<![{REPOSITORY_CHARACTER}])(?:{alternatives})"
        rf"(?:(?=\.git(?:$|[^{REPOSITORY_CHARACTER}]))|"
        rf"(?![{REPOSITORY_CHARACTER}]))"
    )


def private_only_repository_slugs(
    private_full_identifiers: set[str],
    public_full_identifiers: set[str],
) -> set[str]:
    """Return private slugs that do not collide with a public repository slug."""
    private_slugs = {
        repository.split("/", 1)[-1] for repository in private_full_identifiers
    }
    public_slug_keys = {
        repository.split("/", 1)[-1].casefold()
        for repository in public_full_identifiers
    }
    return {
        slug for slug in private_slugs if slug.casefold() not in public_slug_keys
    }


def repository_reference_pattern(
    private_full_identifiers: set[str],
    private_only_slugs: set[str],
    public_full_identifiers: set[str],
) -> re.Pattern[str]:
    """Match every private-only reference while shielding complete public names."""
    if {value.casefold() for value in private_full_identifiers} & {
        value.casefold() for value in public_full_identifiers
    }:
        raise RuntimeError("A repository identifier is both public and private")
    return re.compile(
        rf"(?P<private_full>{bounded_identifier_pattern(private_full_identifiers)})"
        rf"|(?P<public_full>{bounded_identifier_pattern(public_full_identifiers)})"
        rf"|(?P<private_slug>{bounded_identifier_pattern(private_only_slugs)})",
        flags=re.IGNORECASE,
    )


def redact_private_references(
    value: Any,
    pattern: re.Pattern[str],
) -> Any:
    """Redact private references recursively while preserving public identities."""
    if isinstance(value, str):
        value = PUBLIC_EXACT_REWRITES.get(value, value)
        for original, replacement in PUBLIC_PROSE_REWRITES:
            value = value.replace(original, replacement)
        return pattern.sub(
            lambda match: (
                match.group(0)
                if match.lastgroup == "public_full"
                else "[private repository]"
            ),
            value,
        )
    if isinstance(value, list):
        return [redact_private_references(item, pattern) for item in value]
    if isinstance(value, dict):
        return {
            key: redact_private_references(item, pattern)
            for key, item in value.items()
        }
    return value
