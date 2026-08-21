"""Deterministic canonical import-boundary validation (M2.1 / Issue #38).

Framework-free, model-free, fail-closed validation of raw candidate
isolate records and import batches against the canonical hero semantics
fixed by Issue #30 (``data/schemas/canonical_hero.schema.json``). This is
the deterministic ingestion boundary: it turns candidate mappings (as a
parser will later emit) into typed ``CanonicalIsolate`` /
``CanonicalImportBatch`` construction decisions by returning a structured
``ImportValidationReport``.

Semantics:

- candidates are raw JSON-derived values — ``collection_date`` is expected
  as a date STRING in the exact canonical shape (``YYYY-MM-DD`` full-match
  first, then calendar validity proven with ``datetime.date.fromisoformat``;
  converted nowhere); typed date-only ``date`` values belong to the
  constructed ``CanonicalIsolate``, not to the candidate;
- material invalid values are REPORTED, never repaired or "helpfully"
  corrected (Issue #38 / ``docs/DATA_SAFETY_EVALUATION.md``);
- every independent failure is collected — validation never stops at the
  first error unless no further check is structurally possible;
- ordering is deterministic: records in candidate order (ascending
  ``record_index``), fields in the fixed #30 declaration order, AST
  entries in the candidate mapping's insertion order; one pass, append in
  discovery order, no sets — so error order can never vary between runs;
- unknown extra keys in a candidate mapping are ignored: structural
  ``additionalProperties`` rejection belongs to the #30 JSON Schema layer
  (mirroring it here would duplicate the schema line-for-line), while the
  typed boundary owns the material invariants application code needs;
- antimicrobial identity lives only in the ``ast_results`` key; entries
  with an invalid key are reported and their value section is skipped
  (the entry is not addressable under an invalid code);
- duplicate ``isolate_id`` handling, source hashing and deduplication are
  OWNED BY ISSUE #40 — this boundary performs no uniqueness enforcement
  and keeps duplicates representable, so #40 can enforce its own
  semantics later without fighting an earlier dedup;
- synthetic-envelope checks (``synthetic``, provenance, SYNTH- prefixes)
  stay with the #30 schema layer; this boundary does not re-derive them.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import date

from ngabo.domain.entities.canonical_isolate import (
    ANTIBIOTIC_CODE_PATTERN,
    ISOLATE_ID_PATTERN,
)
from ngabo.domain.enums.import_validation_error_code import ImportValidationErrorCode
from ngabo.domain.enums.interpretation import Interpretation
from ngabo.domain.value_objects.import_validation_error import ImportValidationError
from ngabo.domain.value_objects.import_validation_report import ImportValidationReport

_REQUIRED_FIELDS = (
    "isolate_id",
    "collection_date",
    "organism_code",
    "organism_name",
    "facility_id",
    "lab_id",
    "ward",
    "specimen_type",
    "patient_token",
    "source_import_id",
    "ast_results",
)
"""Fixed canonical record field order (Issue #30) — also the deterministic error order."""

_TEXT_FIELDS = frozenset(
    {
        "organism_code",
        "organism_name",
        "facility_id",
        "lab_id",
        "ward",
        "specimen_type",
        "patient_token",
        "source_import_id",
    }
)
"""Required non-blank text fields. Membership tests only: ordering must never
be derived from this container (the field order above owns ordering)."""

_VALID_INTERPRETATIONS = frozenset(member.value for member in Interpretation)
"""#30 interpretation vocabulary, derived from the single Interpretation enum."""

_COLLECTION_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
"""Exact canonical collection-date string shape (Issue #30): YYYY-MM-DD.

The full-match shape check runs BEFORE ``date.fromisoformat`` because the
stdlib parser alone would also accept compact ISO (``20260816``) and ISO
week dates (``2026-W33-7``), which the canonical schema excludes."""


def validate_isolate_candidate(candidate: object) -> ImportValidationReport:
    """Validate one raw canonical record candidate.

    Returns a structured report: valid with no errors, or invalid with one
    or more deterministic errors (``record_index`` is always None here).
    Never raises for any input shape and never mutates the candidate.
    """
    errors = _isolate_candidate_errors(candidate, record_index=None)
    return ImportValidationReport(valid=not errors, errors=tuple(errors))


def validate_import_candidate(candidate: object) -> ImportValidationReport:
    """Validate one raw import batch candidate (JSON-array-shaped list of records).

    Returns a structured report covering batch shape plus every record
    failure in deterministic order. Never raises for any input shape and
    never mutates the candidate.
    """
    if not isinstance(candidate, list):
        return ImportValidationReport(
            valid=False,
            errors=(
                _error(
                    ImportValidationErrorCode.INVALID_BATCH_SHAPE,
                    field=None,
                    record_index=None,
                    record_id=None,
                    detail="expected a list of canonical isolate record candidates",
                ),
            ),
        )
    if not candidate:
        return ImportValidationReport(
            valid=False,
            errors=(
                _error(
                    ImportValidationErrorCode.EMPTY_BATCH,
                    field=None,
                    record_index=None,
                    record_id=None,
                    detail="expected at least one canonical isolate record candidate",
                ),
            ),
        )
    errors: list[ImportValidationError] = []
    for index, item in enumerate(candidate):
        errors.extend(_isolate_candidate_errors(item, record_index=index))
    return ImportValidationReport(valid=not errors, errors=tuple(errors))


def _isolate_candidate_errors(
    candidate: object, record_index: int | None
) -> list[ImportValidationError]:
    if not isinstance(candidate, Mapping):
        return [
            _error(
                ImportValidationErrorCode.INVALID_RECORD_SHAPE,
                field=None,
                record_index=record_index,
                record_id=None,
                detail="expected a mapping of canonical isolate fields",
            )
        ]
    isolate_id = candidate.get("isolate_id")
    record_id = isolate_id if isinstance(isolate_id, str) and isolate_id.strip() else None
    errors: list[ImportValidationError] = []
    for field in _REQUIRED_FIELDS:
        if field not in candidate:
            errors.append(
                _error(
                    ImportValidationErrorCode.MISSING_REQUIRED_FIELD,
                    field=field,
                    record_index=record_index,
                    record_id=record_id,
                )
            )
            continue
        value = candidate[field]
        if field == "isolate_id":
            errors.extend(_check_isolate_id(value, record_index, record_id))
        elif field == "collection_date":
            errors.extend(_check_collection_date(value, record_index, record_id))
        elif field == "ast_results":
            errors.extend(_check_ast_results(value, record_index, record_id))
        elif field in _TEXT_FIELDS:
            errors.extend(_check_text_field(field, value, record_index, record_id))
    return errors


def _check_isolate_id(
    value: object, record_index: int | None, record_id: str | None
) -> list[ImportValidationError]:
    if not isinstance(value, str):
        return [
            _error(
                ImportValidationErrorCode.INVALID_FIELD_TYPE,
                field="isolate_id",
                record_index=record_index,
                record_id=record_id,
                detail="expected a string",
            )
        ]
    if not value.strip():
        return [
            _error(
                ImportValidationErrorCode.BLANK_REQUIRED_FIELD,
                field="isolate_id",
                record_index=record_index,
                record_id=record_id,
            )
        ]
    if not ISOLATE_ID_PATTERN.fullmatch(value):
        return [
            _error(
                ImportValidationErrorCode.INVALID_ISOLATE_ID,
                field="isolate_id",
                record_index=record_index,
                record_id=record_id,
                detail=f"expected {ISOLATE_ID_PATTERN.pattern}",
            )
        ]
    return []


def _check_collection_date(
    value: object, record_index: int | None, record_id: str | None
) -> list[ImportValidationError]:
    if not isinstance(value, str):
        return [
            _error(
                ImportValidationErrorCode.INVALID_FIELD_TYPE,
                field="collection_date",
                record_index=record_index,
                record_id=record_id,
                detail="expected an ISO date string",
            )
        ]
    if not value.strip():
        return [
            _error(
                ImportValidationErrorCode.BLANK_REQUIRED_FIELD,
                field="collection_date",
                record_index=record_index,
                record_id=record_id,
            )
        ]
    if not _COLLECTION_DATE_PATTERN.fullmatch(value):
        # Exact #30 shape first: date.fromisoformat alone would also accept
        # compact ISO (20260816) and ISO week dates (2026-W33-7).
        return [
            _error(
                ImportValidationErrorCode.INVALID_COLLECTION_DATE,
                field="collection_date",
                record_index=record_index,
                record_id=record_id,
                detail="expected a valid ISO calendar date (YYYY-MM-DD)",
            )
        ]
    try:
        # Calendar validity: shape-correct strings must still name a real
        # date (e.g. 2026-02-30 fails). Parsed for proof only; the boundary
        # retains no converted value.
        date.fromisoformat(value)
    except ValueError:
        return [
            _error(
                ImportValidationErrorCode.INVALID_COLLECTION_DATE,
                field="collection_date",
                record_index=record_index,
                record_id=record_id,
                detail="expected a valid ISO calendar date (YYYY-MM-DD)",
            )
        ]
    return []


def _check_text_field(
    field: str, value: object, record_index: int | None, record_id: str | None
) -> list[ImportValidationError]:
    if not isinstance(value, str):
        return [
            _error(
                ImportValidationErrorCode.INVALID_FIELD_TYPE,
                field=field,
                record_index=record_index,
                record_id=record_id,
                detail="expected non-blank text",
            )
        ]
    if not value.strip():
        return [
            _error(
                ImportValidationErrorCode.BLANK_REQUIRED_FIELD,
                field=field,
                record_index=record_index,
                record_id=record_id,
            )
        ]
    return []


def _check_ast_results(
    value: object, record_index: int | None, record_id: str | None
) -> list[ImportValidationError]:
    if not isinstance(value, Mapping):
        return [
            _error(
                ImportValidationErrorCode.INVALID_FIELD_TYPE,
                field="ast_results",
                record_index=record_index,
                record_id=record_id,
                detail="expected a mapping keyed by antimicrobial code",
            )
        ]
    if not value:
        return [
            _error(
                ImportValidationErrorCode.EMPTY_AST_RESULTS,
                field="ast_results",
                record_index=record_index,
                record_id=record_id,
            )
        ]
    errors: list[ImportValidationError] = []
    for key, entry in value.items():
        if not isinstance(key, str) or not ANTIBIOTIC_CODE_PATTERN.fullmatch(key):
            errors.append(
                _error(
                    ImportValidationErrorCode.INVALID_ANTIBIOTIC_CODE,
                    field="ast_results",
                    record_index=record_index,
                    record_id=record_id,
                    detail=(
                        f"invalid antimicrobial code {key!r}; expected "
                        f"{ANTIBIOTIC_CODE_PATTERN.pattern}"
                    ),
                )
            )
            continue
        errors.extend(_check_ast_entry(key, entry, record_index, record_id))
    return errors


def _check_ast_entry(
    key: str, entry: object, record_index: int | None, record_id: str | None
) -> list[ImportValidationError]:
    entry_field = f"ast_results.{key}"
    if not isinstance(entry, Mapping):
        return [
            _error(
                ImportValidationErrorCode.MALFORMED_AST_OBSERVATION,
                field=entry_field,
                record_index=record_index,
                record_id=record_id,
                detail="expected a mapping carrying an interpretation",
            )
        ]
    interpretation_field = f"{entry_field}.interpretation"
    if "interpretation" not in entry:
        return [
            _error(
                ImportValidationErrorCode.MISSING_REQUIRED_FIELD,
                field=interpretation_field,
                record_index=record_index,
                record_id=record_id,
            )
        ]
    interpretation = entry["interpretation"]
    if not isinstance(interpretation, str):
        return [
            _error(
                ImportValidationErrorCode.INVALID_FIELD_TYPE,
                field=interpretation_field,
                record_index=record_index,
                record_id=record_id,
                detail="expected a string",
            )
        ]
    if interpretation not in _VALID_INTERPRETATIONS:
        return [
            _error(
                ImportValidationErrorCode.INVALID_INTERPRETATION,
                field=interpretation_field,
                record_index=record_index,
                record_id=record_id,
                detail="expected a canonical interpretation (S, I, R, UNKNOWN)",
            )
        ]
    return []


def _error(
    code: ImportValidationErrorCode,
    field: str | None,
    record_index: int | None,
    record_id: str | None,
    detail: str | None = None,
) -> ImportValidationError:
    """Build one structured error with the given context."""
    return ImportValidationError(
        code=code,
        field=field,
        record_index=record_index,
        record_id=record_id,
        detail=detail,
    )
