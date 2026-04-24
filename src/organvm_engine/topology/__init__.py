"""Topology: capability-to-location resolution.

The topology module makes the system location-independent. It discovers
repos by scanning for seed.yaml identity declarations, builds a capability
index, and resolves queries by identity — never by path.

The four laws of the ultima materia:
1. Identity is function (produces/consumes), not name.
2. Location is ephemeral — discovered, never stored as truth.
3. Composition is declaration — edges from seed.yaml, not config.
4. Everything enters stripped — reduced to identity + edges.
"""
