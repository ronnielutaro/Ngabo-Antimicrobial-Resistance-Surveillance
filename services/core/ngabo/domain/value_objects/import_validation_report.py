"""Aggregate import-validation result contract (M2.1 / Issue #38).

``ImportValidationReport`` is the immutable result returned by the
deterministic framework-free import boundary when validating candidate
isolate records and import batches. Shape per Issue #38: ``valid`` plus
zero-or-more structured errors, with the hard invariants that a valid
report carries no errors and an invalid report carries at least one — so
callers can gate downstream work on ``valid`` alone without re-parsing.

Authority boundary: this report says only whether the candidate passed
deterministic import validation. It does NOT mean a record was persisted,
a signal exists, or any autonomous action may begin — and it deliberately
contains no repository, orchestration, model or action fields. It also
never contains corrected or "helpfully inferred" medical values: an
invalid material value is reported, never repaired by this layer
(Issue #38 / ``docs/DATA_SAFETY_EVALUATION.md``).

Deeply immutable: ``errors`` must be an actual tuple of
``ImportValidationError`` — non-tuple collections and wrong element types
are rejected at construction, so no mutable alias can reach the report.
"""

from __future__ import annotations

from dataclasses import dataclass

from ngabo.domain.value_objects.import_validation_error import ImportValidationError


@dataclass(frozen=True)
class ImportValidationReport:
    """Immutable pass/fail result of deterministic import-boundary validation."""

    valid: bool
    errors: tuple[ImportValidationError, ...] = ()

    def __post_init__(self) -> None:
        # bool subclasses int, so the type must be guarded with isinstance
        # rather than a truthiness check: raw 1/0 must never construct.
        if not isinstance(self.valid, bool):
            raise ValueError(f"Invalid validation result {self.valid!r}; expected a bool")
        if not isinstance(self.errors, tuple):
            raise ValueError(f"Invalid validation errors {self.errors!r}; expected a tuple")
        for index, error in enumerate(self.errors):
            if not isinstance(error, ImportValidationError):
                raise ValueError(
                    f"Invalid validation error at position {index}: {error!r}; "
                    "expected an ImportValidationError"
                )
        if self.valid and self.errors:
            raise ValueError("A valid validation report cannot carry validation errors")
        if not self.valid and not self.errors:
            raise ValueError(
                "An invalid validation report must carry at least one validation error"
            )
