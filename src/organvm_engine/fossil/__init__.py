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

from organvm_engine.fossil.classifier import classify_commit
from organvm_engine.fossil.epochs import DECLARED_EPOCHS, Epoch, assign_epoch
from organvm_engine.fossil.excavator import excavate_repo
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
    "Epoch",
    "FossilRecord",
    "Provenance",
    "assign_epoch",
    "classify_commit",
    "compute_record_hash",
    "deserialize_record",
    "excavate_repo",
    "serialize_record",
]
