"""Network testament — external mirror mapping and engagement tracking.

Maps every ORGANVM repo to relevant open-source projects, communities,
and philosophical kinship networks through three equal lenses:
technical dependency, domain parallel, and philosophical kinship.

Tracks engagement over time as an accumulating testament via an
append-only ledger, living network maps, and periodic narrative synthesis.

Principle: context[current-work] > relevant[open-source] > expand[network]
"""

NETWORK_MAP_FILENAME = "network-map.yaml"

# Mirror lens categories — ontological, not empirical
MIRROR_LENSES = frozenset({"technical", "parallel", "kinship"})

# Engagement action types — simultaneous, not sequential
ENGAGEMENT_FORMS = frozenset({"presence", "contribution", "dialogue", "invitation"})

# Header fields in network-map.yaml that are not mirror lenses
HEADER_FIELDS = frozenset({"schema_version", "repo", "organ", "mirrors", "ledger", "last_scanned"})
