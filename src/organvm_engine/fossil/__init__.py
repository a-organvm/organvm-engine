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
from organvm_engine.fossil.bridge import (
    emit_drift_event,
    emit_epoch_event,
    emit_intention_event,
    fossil_uri,
)
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
from organvm_engine.fossil.witness import (
    generate_hook_script,
    install_hooks,
    record_witnessed_commit,
    witness_status,
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
    "emit_drift_event",
    "emit_epoch_event",
    "emit_intention_event",
    "excavate_repo",
    "extract_intentions",
    "fossil_uri",
    "generate_all_chronicles",
    "generate_epoch_chronicle",
    "generate_hook_script",
    "install_hooks",
    "load_intentions",
    "record_witnessed_commit",
    "serialize_record",
    "witness_status",
]
