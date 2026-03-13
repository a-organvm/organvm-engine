"""Tests for organvm_engine.pulse.nerve — subscription-based event routing."""

from __future__ import annotations

import yaml

import pytest

from organvm_engine.pulse.events import Event
from organvm_engine.pulse.nerve import (
    NerveBundle,
    Subscription,
    _source_matches,
    propagate,
    resolve_subscriptions,
)


# ---------------------------------------------------------------------------
# Subscription dataclass
# ---------------------------------------------------------------------------

class TestSubscription:
    def test_subscription_creation(self):
        """Subscription dataclass holds all declared fields."""
        sub = Subscription(
            subscriber="orgA/repo1",
            event_type="repo.promoted",
            source="orgB/*",
            action="notify",
        )
        assert sub.subscriber == "orgA/repo1"
        assert sub.event_type == "repo.promoted"
        assert sub.source == "orgB/*"
        assert sub.action == "notify"

    def test_subscription_to_dict(self):
        """to_dict includes all fields."""
        sub = Subscription(
            subscriber="orgA/repo1",
            event_type="repo.promoted",
            source="",
            action="default",
        )
        d = sub.to_dict()
        assert d["subscriber"] == "orgA/repo1"
        assert d["event_type"] == "repo.promoted"
        assert d["action"] == "default"


# ---------------------------------------------------------------------------
# NerveBundle
# ---------------------------------------------------------------------------

class TestNerveBundle:
    def test_nerve_bundle_add(self):
        """Adding a subscription populates by_event and by_subscriber."""
        bundle = NerveBundle()
        sub = Subscription(
            subscriber="orgA/r1",
            event_type="repo.promoted",
            source="",
            action="sync",
        )
        bundle.add(sub)
        assert len(bundle.subscriptions) == 1
        assert "repo.promoted" in bundle.by_event
        assert "orgA/r1" in bundle.by_subscriber

    def test_nerve_bundle_listeners_for(self):
        """listeners_for filters by event_type."""
        bundle = NerveBundle()
        bundle.add(Subscription("orgA/r1", "repo.promoted", "", "sync"))
        bundle.add(Subscription("orgA/r2", "gate.changed", "", "rebuild"))
        bundle.add(Subscription("orgB/r3", "repo.promoted", "", "notify"))

        listeners = bundle.listeners_for("repo.promoted")
        assert len(listeners) == 2
        subs = {s.subscriber for s in listeners}
        assert subs == {"orgA/r1", "orgB/r3"}

    def test_nerve_bundle_empty(self):
        """Empty bundle returns empty lists for any event type."""
        bundle = NerveBundle()
        assert bundle.listeners_for("anything") == []
        assert bundle.subscriptions_for("anyone") == []

    def test_nerve_bundle_to_dict(self):
        """to_dict serializes with expected structure."""
        bundle = NerveBundle()
        bundle.add(Subscription("orgA/r1", "repo.promoted", "", "sync"))
        bundle.add(Subscription("orgA/r2", "gate.changed", "", "rebuild"))
        d = bundle.to_dict()
        assert d["total"] == 2
        assert "by_event" in d
        assert "by_subscriber" in d
        assert "repo.promoted" in d["by_event"]


# ---------------------------------------------------------------------------
# Source matching
# ---------------------------------------------------------------------------

class TestSourceMatching:
    def test_empty_pattern_matches_all(self):
        """Empty source pattern matches any source."""
        assert _source_matches("", "anything/here") is True

    def test_exact_match(self):
        """Exact string match works."""
        assert _source_matches("orgA/r1", "orgA/r1") is True
        assert _source_matches("orgA/r1", "orgA/r2") is False

    def test_wildcard_match(self):
        """Prefix wildcard (org/*) matches repos in that org."""
        assert _source_matches("orgA/*", "orgA/r1") is True
        assert _source_matches("orgA/*", "orgA/r2") is True
        assert _source_matches("orgA/*", "orgB/r1") is False

    def test_wildcard_matches_org_itself(self):
        """orgA/* also matches the bare 'orgA' source."""
        assert _source_matches("orgA/*", "orgA") is True


# ---------------------------------------------------------------------------
# Propagation
# ---------------------------------------------------------------------------

class TestPropagate:
    def test_propagate_matching(self):
        """Event matching a subscription produces a dispatch record."""
        bundle = NerveBundle()
        bundle.add(Subscription("orgA/r1", "repo.promoted", "", "sync"))
        event = Event(
            event_type="repo.promoted",
            source="orgB/r2",
            payload={"new_status": "CANDIDATE"},
        )
        records = propagate(event, bundle)
        assert len(records) == 1
        assert records[0]["subscriber"] == "orgA/r1"
        assert records[0]["action"] == "sync"

    def test_propagate_source_filter(self):
        """Subscription with source constraint filters correctly."""
        bundle = NerveBundle()
        bundle.add(Subscription("orgA/r1", "repo.promoted", "orgB/*", "sync"))
        bundle.add(Subscription("orgA/r2", "repo.promoted", "orgC/*", "notify"))

        event = Event(event_type="repo.promoted", source="orgB/r5")
        records = propagate(event, bundle)
        assert len(records) == 1
        assert records[0]["subscriber"] == "orgA/r1"

    def test_propagate_no_match(self):
        """No matching subscriptions produces empty list."""
        bundle = NerveBundle()
        bundle.add(Subscription("orgA/r1", "gate.changed", "", "rebuild"))
        event = Event(event_type="repo.promoted", source="orgB/r2")
        records = propagate(event, bundle)
        assert records == []


# ---------------------------------------------------------------------------
# resolve_subscriptions (from seed files)
# ---------------------------------------------------------------------------

class TestResolveSubscriptions:
    def test_resolve_from_seeds(self, tmp_path, monkeypatch):
        """resolve_subscriptions builds a NerveBundle from seed.yaml files."""
        # Create two seed files with subscriptions
        seed_a = tmp_path / "orgA" / "r1" / "seed.yaml"
        seed_a.parent.mkdir(parents=True)
        seed_a.write_text(yaml.dump({
            "org": "orgA",
            "repo": "r1",
            "subscriptions": [
                {"event": "repo.promoted", "source": "orgB/*", "action": "sync"},
            ],
        }))

        seed_b = tmp_path / "orgB" / "r2" / "seed.yaml"
        seed_b.parent.mkdir(parents=True)
        seed_b.write_text(yaml.dump({
            "org": "orgB",
            "repo": "r2",
            "subscriptions": [
                {"event": "gate.changed", "action": "rebuild"},
            ],
        }))

        # Monkeypatch discover_seeds to return our test seed paths
        monkeypatch.setattr(
            "organvm_engine.pulse.nerve.discover_seeds",
            lambda workspace, orgs=None: [seed_a, seed_b],
        )

        bundle = resolve_subscriptions(workspace=tmp_path)
        assert len(bundle.subscriptions) == 2
        assert len(bundle.listeners_for("repo.promoted")) == 1
        assert len(bundle.listeners_for("gate.changed")) == 1

    def test_resolve_bare_string_subscription(self, tmp_path, monkeypatch):
        """Bare string subscriptions (not dicts) are handled."""
        seed_file = tmp_path / "org" / "repo" / "seed.yaml"
        seed_file.parent.mkdir(parents=True)
        seed_file.write_text(yaml.dump({
            "org": "org",
            "repo": "repo",
            "subscriptions": ["product.release"],
        }))

        monkeypatch.setattr(
            "organvm_engine.pulse.nerve.discover_seeds",
            lambda workspace, orgs=None: [seed_file],
        )

        bundle = resolve_subscriptions(workspace=tmp_path)
        assert len(bundle.subscriptions) == 1
        assert bundle.subscriptions[0].event_type == "product.release"
        assert bundle.subscriptions[0].source == ""
        assert bundle.subscriptions[0].action == "default"
