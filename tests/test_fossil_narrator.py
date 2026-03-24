"""Tests for the Jungian chronicle narrator."""

from datetime import datetime, timezone

from organvm_engine.fossil.epochs import DECLARED_EPOCHS
from organvm_engine.fossil.narrator import (
    ARCHETYPE_VOICE,
    compute_epoch_stats,
    generate_all_chronicles,
    generate_epoch_chronicle,
)
from organvm_engine.fossil.stratum import Archetype, FossilRecord, Provenance


def _make_record(
    message="feat: test",
    organ="META",
    repo="engine",
    archetypes=None,
    epoch="EPOCH-001",
    **kwargs,
):
    """Helper to create FossilRecord with sensible defaults."""
    return FossilRecord(
        commit_sha=kwargs.get("sha", "abc"),
        timestamp=kwargs.get("ts", datetime(2026, 2, 1, tzinfo=timezone.utc)),
        author=kwargs.get("author", "test"),
        organ=organ,
        repo=repo,
        message=message,
        conventional_type=kwargs.get("conv", "feat"),
        files_changed=kwargs.get("files", 1),
        insertions=kwargs.get("ins", 10),
        deletions=kwargs.get("dels", 2),
        archetypes=archetypes or [Archetype.ANIMUS],
        provenance=Provenance.RECONSTRUCTED,
        session_id=None,
        epoch=epoch,
        tags=[],
        prev_hash="",
    )


# ── ARCHETYPE_VOICE completeness ──────────────────────────────────────


def test_archetype_voice_has_all_archetypes():
    for arch in Archetype:
        assert arch in ARCHETYPE_VOICE
        assert "verbs" in ARCHETYPE_VOICE[arch]
        assert "opening" in ARCHETYPE_VOICE[arch]


def test_archetype_voice_has_subjects_and_presence():
    for arch in Archetype:
        voice = ARCHETYPE_VOICE[arch]
        assert "subjects" in voice, f"{arch} missing 'subjects'"
        assert "presence" in voice, f"{arch} missing 'presence'"
        assert len(voice["verbs"]) >= 3, f"{arch} needs at least 3 verbs"


# ── compute_epoch_stats ───────────────────────────────────────────────


def test_compute_epoch_stats_basic():
    records = [
        _make_record(archetypes=[Archetype.ANIMUS], repo="engine", ins=100),
        _make_record(archetypes=[Archetype.SHADOW], repo="engine", ins=50),
        _make_record(archetypes=[Archetype.ANIMUS], repo="dashboard", ins=30),
    ]
    epoch = DECLARED_EPOCHS[0]  # Genesis
    stats = compute_epoch_stats(epoch, records)
    assert stats.commit_count == 3
    assert stats.dominant_archetype == Archetype.ANIMUS
    assert "engine" in stats.repos_touched
    assert "dashboard" in stats.repos_touched
    assert stats.total_insertions == 180
    assert stats.total_deletions == 6  # 3 records * 2 default


def test_compute_epoch_stats_empty():
    epoch = DECLARED_EPOCHS[0]
    stats = compute_epoch_stats(epoch, [])
    assert stats.commit_count == 0
    assert stats.repos_touched == []
    assert stats.organs_touched == []
    assert stats.total_insertions == 0
    assert stats.total_deletions == 0
    assert stats.trickster_ratio == 0.0


def test_compute_epoch_stats_filters_by_epoch():
    """Records from other epochs are excluded."""
    records = [
        _make_record(epoch="EPOCH-001", repo="engine"),
        _make_record(epoch="EPOCH-002", repo="corpus"),
        _make_record(epoch="EPOCH-001", repo="dashboard"),
    ]
    epoch = DECLARED_EPOCHS[0]  # EPOCH-001
    stats = compute_epoch_stats(epoch, records)
    assert stats.commit_count == 2
    assert "corpus" not in stats.repos_touched


def test_compute_epoch_stats_top_repos():
    """Top repos list is sorted descending by commit count, max 5."""
    records = [
        _make_record(repo="alpha"),
        _make_record(repo="alpha"),
        _make_record(repo="alpha"),
        _make_record(repo="beta"),
        _make_record(repo="beta"),
        _make_record(repo="gamma"),
    ]
    epoch = DECLARED_EPOCHS[0]
    stats = compute_epoch_stats(epoch, records)
    assert stats.top_repos[0] == ("alpha", 3)
    assert stats.top_repos[1] == ("beta", 2)
    assert len(stats.top_repos) <= 5


def test_compute_epoch_stats_trickster_ratio():
    """Trickster ratio measures primary archetype frequency."""
    records = [
        _make_record(archetypes=[Archetype.TRICKSTER]),
        _make_record(archetypes=[Archetype.ANIMUS]),
        _make_record(archetypes=[Archetype.TRICKSTER]),
        _make_record(archetypes=[Archetype.ANIMUS]),
    ]
    epoch = DECLARED_EPOCHS[0]
    stats = compute_epoch_stats(epoch, records)
    assert stats.trickster_ratio == 0.5


def test_compute_epoch_stats_secondary_archetype():
    """Secondary archetype is the second-most-common, or None if tie/single."""
    records = [
        _make_record(archetypes=[Archetype.ANIMUS]),
        _make_record(archetypes=[Archetype.ANIMUS]),
        _make_record(archetypes=[Archetype.SHADOW]),
        _make_record(archetypes=[Archetype.ANIMA]),
    ]
    epoch = DECLARED_EPOCHS[0]
    stats = compute_epoch_stats(epoch, records)
    assert stats.dominant_archetype == Archetype.ANIMUS
    assert stats.secondary_archetype in (Archetype.SHADOW, Archetype.ANIMA)


def test_compute_epoch_stats_authors():
    """Authors list is deduplicated."""
    records = [
        _make_record(author="alice"),
        _make_record(author="bob"),
        _make_record(author="alice"),
    ]
    epoch = DECLARED_EPOCHS[0]
    stats = compute_epoch_stats(epoch, records)
    assert sorted(stats.authors) == ["alice", "bob"]


def test_compute_epoch_stats_organs_touched():
    records = [
        _make_record(organ="I"),
        _make_record(organ="META"),
        _make_record(organ="I"),
    ]
    epoch = DECLARED_EPOCHS[0]
    stats = compute_epoch_stats(epoch, records)
    assert sorted(stats.organs_touched) == ["I", "META"]


# ── generate_epoch_chronicle ──────────────────────────────────────────


def test_generate_epoch_chronicle_not_empty():
    records = [
        _make_record(
            archetypes=[Archetype.ANIMA],
            repo="corpus-mythicum",
            organ="I",
            message="feat: B11 Foundation synthesis",
        ),
        _make_record(
            archetypes=[Archetype.TRICKSTER],
            repo="some-repo",
            organ="I",
            message="yolo",
        ),
    ]
    epoch = DECLARED_EPOCHS[0]
    stats = compute_epoch_stats(epoch, records)
    chronicle = generate_epoch_chronicle(stats, records)
    assert len(chronicle) > 100
    assert epoch.name in chronicle
    assert "Anima" in chronicle or "anima" in chronicle


def test_generate_epoch_chronicle_has_data_section():
    records = [
        _make_record(repo="engine", ins=200, dels=50),
        _make_record(repo="dashboard", ins=100, dels=10),
    ]
    epoch = DECLARED_EPOCHS[0]
    stats = compute_epoch_stats(epoch, records)
    chronicle = generate_epoch_chronicle(stats, records)
    assert "## Data" in chronicle
    assert "Commits" in chronicle
    assert "engine" in chronicle


def test_generate_epoch_chronicle_trickster_note():
    """When trickster_ratio > 0.10, the Trickster is mentioned."""
    records = [
        _make_record(archetypes=[Archetype.TRICKSTER]),
        _make_record(archetypes=[Archetype.TRICKSTER]),
        _make_record(archetypes=[Archetype.ANIMUS]),
    ]
    epoch = DECLARED_EPOCHS[0]
    stats = compute_epoch_stats(epoch, records)
    chronicle = generate_epoch_chronicle(stats, records)
    assert "Trickster" in chronicle


def test_generate_epoch_chronicle_shadow_note():
    """When Shadow is in top 3 archetypes, it is acknowledged."""
    records = [
        _make_record(archetypes=[Archetype.SHADOW]),
        _make_record(archetypes=[Archetype.SHADOW]),
        _make_record(archetypes=[Archetype.ANIMUS]),
        _make_record(archetypes=[Archetype.ANIMUS]),
        _make_record(archetypes=[Archetype.ANIMUS]),
    ]
    epoch = DECLARED_EPOCHS[0]
    stats = compute_epoch_stats(epoch, records)
    chronicle = generate_epoch_chronicle(stats, records)
    assert "Shadow" in chronicle


def test_generate_epoch_chronicle_empty_epoch():
    """An epoch with zero records still produces a chronicle stub."""
    epoch = DECLARED_EPOCHS[0]
    stats = compute_epoch_stats(epoch, [])
    chronicle = generate_epoch_chronicle(stats, [])
    assert epoch.name in chronicle
    assert "0 commits" in chronicle or "0" in chronicle


# ── generate_all_chronicles ───────────────────────────────────────────


def test_generate_all_chronicles(tmp_path):
    """Creates markdown files for each epoch that has records."""
    records = [
        _make_record(epoch="EPOCH-001", ts=datetime(2026, 1, 25, tzinfo=timezone.utc)),
        _make_record(epoch="EPOCH-006", ts=datetime(2026, 2, 11, tzinfo=timezone.utc)),
    ]
    paths = generate_all_chronicles(records, tmp_path)
    assert len(paths) >= 1
    for p in paths:
        assert p.exists()
        content = p.read_text()
        assert len(content) > 50


def test_generate_all_chronicles_file_naming(tmp_path):
    """Output files follow the EPOCH-NNN-slug pattern."""
    records = [
        _make_record(epoch="EPOCH-001"),
    ]
    paths = generate_all_chronicles(records, tmp_path)
    assert len(paths) == 1
    assert "EPOCH-001" in paths[0].name
    assert paths[0].suffix == ".md"


def test_generate_all_chronicles_skip_existing(tmp_path):
    """Existing files are not overwritten unless regenerate=True."""
    records = [_make_record(epoch="EPOCH-001")]

    # First generation
    paths1 = generate_all_chronicles(records, tmp_path)
    assert len(paths1) == 1
    first_content = paths1[0].read_text()

    # Second generation (should skip)
    paths2 = generate_all_chronicles(records, tmp_path)
    assert len(paths2) == 0  # skipped

    # Content unchanged
    assert paths1[0].read_text() == first_content


def test_generate_all_chronicles_regenerate(tmp_path):
    """With regenerate=True, existing files are overwritten."""
    records = [_make_record(epoch="EPOCH-001")]

    paths1 = generate_all_chronicles(records, tmp_path)
    assert len(paths1) == 1

    paths2 = generate_all_chronicles(records, tmp_path, regenerate=True)
    assert len(paths2) == 1


def test_generate_all_chronicles_multiple_epochs(tmp_path):
    """Records spanning multiple epochs produce multiple files."""
    records = [
        _make_record(epoch="EPOCH-001"),
        _make_record(epoch="EPOCH-001"),
        _make_record(epoch="EPOCH-007"),
        _make_record(epoch="EPOCH-007"),
        _make_record(epoch="EPOCH-012"),
    ]
    paths = generate_all_chronicles(records, tmp_path)
    assert len(paths) == 3
    names = {p.name for p in paths}
    assert any("EPOCH-001" in n for n in names)
    assert any("EPOCH-007" in n for n in names)
    assert any("EPOCH-012" in n for n in names)
