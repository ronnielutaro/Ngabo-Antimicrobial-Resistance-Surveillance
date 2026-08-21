"""Stable import-validation error codes (M2.1 / Issue #38).

Machine-readable identity for every structured import-validation failure,
carried by ``ImportValidationError``. Codes are stable identifiers for
routing, telemetry and evaluation — never prose. Reporting rules:

- a field present with the wrong runtime type -> ``INVALID_FIELD_TYPE``;
- a string field present but blank -> ``BLANK_REQUIRED_FIELD``;
- a field present, correctly typed, but shaped outside the #30 boundary ->
  the specific shape code.

Members:

- ``MISSING_REQUIRED_FIELD`` — required canonical field absent from the
  candidate mapping.
- ``BLANK_REQUIRED_FIELD`` — required text field present but blank.
- ``INVALID_FIELD_TYPE`` — required field present with the wrong runtime
  type (including ``ast_results`` not being a mapping).
- ``INVALID_ISOLATE_ID`` — isolate ID string outside ``^ISO-\\d{3}$``.
- ``INVALID_COLLECTION_DATE`` — collection date string not a valid ISO
  calendar date (checked with ``datetime.date.fromisoformat``; the
  boundary performs format validation only and converts nothing).
- ``INVALID_ANTIBIOTIC_CODE`` — ``ast_results`` key not a string matching
  ``^[A-Z]{2,6}$``; antimicrobial identity lives only in the map key.
- ``INVALID_INTERPRETATION`` — interpretation value not one of ``S``,
  ``I``, ``R``, ``UNKNOWN``.
- ``EMPTY_AST_RESULTS`` — ``ast_results`` mapping present but empty.
- ``MALFORMED_AST_OBSERVATION`` — ``ast_results`` entry not a mapping
  carrying an ``interpretation``.
- ``INVALID_RECORD_SHAPE`` — record-level candidate not a mapping (used
  both standalone and per batch item).
- ``INVALID_BATCH_SHAPE`` — import candidate not a JSON-array-shaped list.
- ``EMPTY_BATCH`` — import candidate a list with zero records.
"""

from __future__ import annotations

from enum import StrEnum


class ImportValidationErrorCode(StrEnum):
    """Stable machine-readable import-validation failure families (Issue #38)."""

    MISSING_REQUIRED_FIELD = "MISSING_REQUIRED_FIELD"
    BLANK_REQUIRED_FIELD = "BLANK_REQUIRED_FIELD"
    INVALID_FIELD_TYPE = "INVALID_FIELD_TYPE"
    INVALID_ISOLATE_ID = "INVALID_ISOLATE_ID"
    INVALID_COLLECTION_DATE = "INVALID_COLLECTION_DATE"
    INVALID_ANTIBIOTIC_CODE = "INVALID_ANTIBIOTIC_CODE"
    INVALID_INTERPRETATION = "INVALID_INTERPRETATION"
    EMPTY_AST_RESULTS = "EMPTY_AST_RESULTS"
    MALFORMED_AST_OBSERVATION = "MALFORMED_AST_OBSERVATION"
    INVALID_RECORD_SHAPE = "INVALID_RECORD_SHAPE"
    INVALID_BATCH_SHAPE = "INVALID_BATCH_SHAPE"
    EMPTY_BATCH = "EMPTY_BATCH"
