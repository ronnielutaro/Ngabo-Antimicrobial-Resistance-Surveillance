"""Typed canonical isolate record boundary (M2.1 / Issue #38).

The immutable typed shape of one canonical hero record, following the
canonical hero schema field-for-field (``data/schemas/canonical_hero.schema.json``,
M1B.6 / Issue #30): ``isolate_id``, ``collection_date``, ``organism_code``,
``organism_name``, ``facility_id``, ``lab_id``, ``ward``, ``specimen_type``,
``patient_token``, ``source_import_id`` and the ``ast_results`` observation
map. This boundary preserves #30 semantics rather than redesigning them:

- antimicrobial identity lives ONLY in the ``ast_results`` map key (e.g.
  ``"AMK"``); entries are ``AstObservation`` values carrying only the
  interpretation — no nested antibiotic-code field is reintroduced;
- ``collection_date`` is typed as a date-only ``datetime.date`` on the
  constructed object — the exact type, so timestamp-bearing
  ``datetime.datetime`` values (which subclass ``date``) are rejected
  rather than normalized down to their date; converting the schema's ISO
  date string into that type belongs to the importing code, not to this
  boundary (which performs no parsing and no normalization);
- ``isolate_id`` keeps the ``^ISO-\\d{3}$`` shape so it stays suitable as
  the ``record_id`` of a later ``CanonicalRecordReference`` (M1B.4);
- the SYNTH- prefixed identifier patterns and the dataset envelope
  (``synthetic``, provenance) remain owned by the #30 schema layer, not
  this boundary.

The boundary encodes intrinsic typed invariants only. Whether duplicate
``isolate_id`` values may exist inside one import — dataset-level
uniqueness semantics, source hashing and deduplication — is owned by
Issue #40; ``CanonicalImportBatch`` deliberately keeps duplicates
representable as an ordered sequence.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from types import MappingProxyType

from ngabo.domain.entities.ast_observation import AstObservation

ISOLATE_ID_PATTERN = re.compile(r"^ISO-\d{3}$")
"""Canonical isolate ID shape (Issue #30): ``ISO-`` plus three digits."""

ANTIBIOTIC_CODE_PATTERN = re.compile(r"^[A-Z]{2,6}$")
"""Canonical antimicrobial code shape (Issue #30): 2–6 uppercase letters."""

_TEXT_FIELDS = (
    "organism_code",
    "organism_name",
    "facility_id",
    "lab_id",
    "ward",
    "specimen_type",
    "patient_token",
    "source_import_id",
)
"""Required non-blank text fields. Ordering here must never drive behavior."""


@dataclass(frozen=True)
class CanonicalIsolate:
    """Immutable typed canonical isolate/AST record (Issue #38)."""

    isolate_id: str
    collection_date: date
    organism_code: str
    organism_name: str
    facility_id: str
    lab_id: str
    ward: str
    specimen_type: str
    patient_token: str
    source_import_id: str
    ast_results: Mapping[str, AstObservation]

    def __post_init__(self) -> None:
        if not isinstance(self.isolate_id, str) or not ISOLATE_ID_PATTERN.fullmatch(
            self.isolate_id
        ):
            raise ValueError(
                f"Invalid isolate ID {self.isolate_id!r}; expected {ISOLATE_ID_PATTERN.pattern}"
            )
        # Exact type, not isinstance: datetime.datetime subclasses date, and
        # this canonical field is date-only. A datetime must fail closed,
        # never be normalized down to its date.
        if type(self.collection_date) is not date:
            raise ValueError(
                f"Invalid collection date {self.collection_date!r}; "
                "expected a date-only datetime.date (datetime is not accepted)"
            )
        for name in _TEXT_FIELDS:
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"Invalid {name} {value!r}; expected non-blank text")
        if not isinstance(self.ast_results, Mapping):
            raise ValueError(
                f"Invalid ast_results {self.ast_results!r}; expected a mapping "
                "keyed by antimicrobial code"
            )
        if not self.ast_results:
            raise ValueError(
                "ast_results cannot be empty; expected at least one observation"
            )
        checked: dict[str, AstObservation] = {}
        for key, value in self.ast_results.items():
            if not isinstance(key, str) or not ANTIBIOTIC_CODE_PATTERN.fullmatch(key):
                raise ValueError(
                    f"Invalid antimicrobial code {key!r}; "
                    f"expected {ANTIBIOTIC_CODE_PATTERN.pattern}"
                )
            if not isinstance(value, AstObservation):
                raise ValueError(
                    f"Invalid AST observation for {key!r}: {value!r}; "
                    "expected an AstObservation"
                )
            checked[key] = value
        # Deep immutability: copy the mapping behind a read-only proxy so no
        # mutable alias to the caller's dict survives construction.
        object.__setattr__(self, "ast_results", MappingProxyType(checked))
