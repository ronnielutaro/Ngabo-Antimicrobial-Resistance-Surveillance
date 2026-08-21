"""Structured import-validation error (M2.1 / Issue #38).

One small immutable error value object, carried by
``ImportValidationReport``. Machine-readable shape required by Issue #38:
``code`` plus ``field``/``record_index``/``record_id``/``detail`` context,
so deterministic callers can route, count and display failures without
parsing prose.

- ``code`` — the stable ``ImportValidationErrorCode`` family; the primary
  machine-readable identity (never prose alone);
- ``field`` — optional dotted path into the candidate (``"ward"``,
  ``"ast_results.AMK.interpretation"``);
- ``record_index`` — optional zero-based position of the record inside an
  import batch (absent for batch-level and standalone-record failures);
- ``record_id`` — optional attempted isolate ID of the affected record,
  present only when the candidate carried a non-blank string
  ``isolate_id`` (diagnostic only; never invented);
- ``detail`` — optional safe supplemental human-readable detail.

``detail`` is supplemental: it never carries the error's identity and must
never contain model-generated chain-of-thought or invented medical values.
Optional strings are rejected when blank; ``record_index`` is rejected
when negative.
"""

from __future__ import annotations

from dataclasses import dataclass

from ngabo.domain.enums.import_validation_error_code import ImportValidationErrorCode


@dataclass(frozen=True)
class ImportValidationError:
    """Immutable structured validation failure for one import-boundary check."""

    code: ImportValidationErrorCode
    field: str | None = None
    record_index: int | None = None
    record_id: str | None = None
    detail: str | None = None

    def __post_init__(self) -> None:
        # StrEnum members compare equal to their string values, so the type
        # must be guarded with isinstance rather than a mapping lookup.
        if not isinstance(self.code, ImportValidationErrorCode):
            raise ValueError(
                f"Invalid import validation error code {self.code!r}; "
                "expected an ImportValidationErrorCode member"
            )
        if self.record_index is not None and (
            not isinstance(self.record_index, int)
            or isinstance(self.record_index, bool)
            or self.record_index < 0
        ):
            raise ValueError(
                f"Invalid record index {self.record_index!r}; "
                "expected a non-negative int or None"
            )
        for name, value in (
            ("field", self.field),
            ("record_id", self.record_id),
            ("detail", self.detail),
        ):
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise ValueError(f"Invalid {name} {value!r}; expected non-blank text or None")
