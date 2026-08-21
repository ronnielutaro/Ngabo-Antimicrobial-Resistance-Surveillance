"""Typed canonical import batch boundary (M2.1 / Issue #38).

An ordered, immutable sequence of ``CanonicalIsolate`` records as imported
into Ngabo. Shape notes:

- the batch is a plain ordered tuple, NOT a dict keyed by isolate ID:
  duplicate ``isolate_id`` values remain representable because dataset-level
  uniqueness, source hashing and deduplication semantics are owned by
  Issue #40 — this boundary must not silently deduplicate or reorder;
- the #30 dataset envelope (``schema_version``, ``dataset_id``,
  ``synthetic``, provenance) stays a schema-layer concern; the batch
  carries records only, so source/dataset identity remains available to
  #40 without this boundary guessing it.
"""

from __future__ import annotations

from dataclasses import dataclass

from ngabo.domain.entities.canonical_isolate import CanonicalIsolate


@dataclass(frozen=True)
class CanonicalImportBatch:
    """Immutable ordered canonical import batch (Issue #38)."""

    records: tuple[CanonicalIsolate, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.records, tuple):
            raise ValueError(f"Invalid records {self.records!r}; expected a tuple")
        for index, record in enumerate(self.records):
            if not isinstance(record, CanonicalIsolate):
                raise ValueError(
                    f"Invalid record at position {index}: {record!r}; "
                    "expected a CanonicalIsolate"
                )
        if not self.records:
            raise ValueError(
                "records cannot be empty; expected at least one canonical isolate"
            )
