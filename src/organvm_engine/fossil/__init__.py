"""fossil — Archaeological reconstruction of ORGANVM system history.

Crawls git history across all workspace repos, classifies commits by
Jungian archetype, and produces a hash-linked fossil record.

Public API::

    from organvm_engine.fossil import (
        Archetype, FossilRecord, Provenance,
        classify_commit, excavate_repo,
        DECLARED_EPOCHS, assign_epoch,
    )
"""

from organvm_engine.fossil.archivist import Intention, extract_intentions, load_intentions
from organvm_engine.fossil.classifier import classify_commit
from organvm_engine.fossil.drift import DriftRecord, analyze_all_drift, compute_drift
from organvm_engine.fossil.epochs import DECLARED_EPOCHS, Epoch, assign_epoch
from organvm_engine.fossil.excavator import excavate_repo
from organvm_engine.fossil.narrator import (
    EpochStats,
    compute_epoch_stats,
    generate_all_chronicles,
    generate_epoch_chronicle,
)
from organvm_engine.fossil.stratum import (
    Archetype,
    FossilRecord,
    Provenance,
    compute_record_hash,
    deserialize_record,
    serialize_record,
)

__all__ = [
    "Archetype",
    "DECLARED_EPOCHS",
    "DriftRecord",
    "Epoch",
    "EpochStats",
    "FossilRecord",
    "Intention",
    "Provenance",
    "analyze_all_drift",
    "assign_epoch",
    "classify_commit",
    "compute_drift",
    "compute_epoch_stats",
    "compute_record_hash",
    "deserialize_record",
    "excavate_repo",
    "extract_intentions",
    "generate_all_chronicles",
    "generate_epoch_chronicle",
    "load_intentions",
    "serialize_record",
]
