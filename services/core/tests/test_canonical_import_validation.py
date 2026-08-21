"""Focused unit tests for deterministic import-boundary validation (M2.1 / Issue #38).

Covers the structured error/report contracts and the multi-error,
deterministic, fail-closed validation semantics of
``ngabo.domain.services.import_validation``, including construction of typed
records from the committed canonical hero fixture (Issue #30) and repeated
validation stability. Framework-free by construction — no FastAPI/GCP/ADK/
Gemini dependency appears anywhere in the boundary.
"""

from __future__ import annotations

import json
from dataclasses import FrozenInstanceError
from datetime import date
from pathlib import Path
from typing import Any, cast

import pytest

from ngabo.domain.entities.ast_observation import AstObservation
from ngabo.domain.entities.canonical_import_batch import CanonicalImportBatch
from ngabo.domain.entities.canonical_isolate import CanonicalIsolate
from ngabo.domain.enums.import_validation_error_code import ImportValidationErrorCode
from ngabo.domain.enums.interpretation import Interpretation
from ngabo.domain.services.import_validation import (
    validate_import_candidate,
    validate_isolate_candidate,
)
from ngabo.domain.value_objects.import_validation_error import ImportValidationError
from ngabo.domain.value_objects.import_validation_report import ImportValidationReport

REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURE_PATH = REPO_ROOT / "data" / "synthetic" / "canonical_hero.json"


def make_candidate(**overrides: object) -> dict[str, object]:
    """Build a fully valid raw candidate mapping with optional overrides."""
    candidate: dict[str, object] = {
        "isolate_id": "ISO-001",
        "collection_date": "2026-08-16",
        "organism_code": "eco",
        "organism_name": "Escherichia coli",
        "facility_id": "SYNTH-FACILITY-001",
        "lab_id": "SYNTH-LAB-001",
        "ward": "SYNTH-WARD-A",
        "specimen_type": "urine",
        "patient_token": "SYNTH-CASE-001",
        "source_import_id": "SYNTH-IMPORT-001",
        "ast_results": {"AMK": {"interpretation": "S"}},
    }
    candidate.update(overrides)
    return candidate


def load_hero_records() -> list[dict[str, Any]]:
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    return cast(list[dict[str, Any]], payload["records"])


class TestImportValidationErrorCode:
    def test_codes_are_stable_strings(self) -> None:
        assert {member.value for member in ImportValidationErrorCode} == {
            "MISSING_REQUIRED_FIELD",
            "BLANK_REQUIRED_FIELD",
            "INVALID_FIELD_TYPE",
            "INVALID_ISOLATE_ID",
            "INVALID_COLLECTION_DATE",
            "INVALID_ANTIBIOTIC_CODE",
            "INVALID_INTERPRETATION",
            "EMPTY_AST_RESULTS",
            "MALFORMED_AST_OBSERVATION",
            "INVALID_RECORD_SHAPE",
            "INVALID_BATCH_SHAPE",
            "EMPTY_BATCH",
        }


class TestImportValidationError:
    def test_valid_construction(self) -> None:
        error = ImportValidationError(
            code=ImportValidationErrorCode.BLANK_REQUIRED_FIELD,
            field="ward",
            record_index=2,
            record_id="ISO-003",
            detail="blank ward",
        )
        assert error.code == ImportValidationErrorCode.BLANK_REQUIRED_FIELD
        assert error.field == "ward"
        assert error.record_index == 2
        assert error.record_id == "ISO-003"
        assert error.detail == "blank ward"

    def test_minimal_construction(self) -> None:
        error = ImportValidationError(code=ImportValidationErrorCode.EMPTY_BATCH)
        assert error.field is None
        assert error.record_index is None
        assert error.record_id is None
        assert error.detail is None

    def test_rejects_non_member_code(self) -> None:
        with pytest.raises(ValueError):
            ImportValidationError(code="BLANK_REQUIRED_FIELD")  # type: ignore[arg-type]

    @pytest.mark.parametrize("bad_index", [-1, 1.5, True])
    def test_rejects_invalid_record_index(self, bad_index: object) -> None:
        with pytest.raises(ValueError):
            ImportValidationError(
                code=ImportValidationErrorCode.EMPTY_BATCH,
                record_index=bad_index,  # type: ignore[arg-type]
            )

    @pytest.mark.parametrize("field_name", ["field", "record_id", "detail"])
    @pytest.mark.parametrize("bad_value", ["", "   "])
    def test_rejects_blank_optional_text(self, field_name: str, bad_value: str) -> None:
        overrides: dict[str, object] = {field_name: bad_value}
        with pytest.raises(ValueError):
            ImportValidationError(
                code=ImportValidationErrorCode.EMPTY_BATCH, **overrides  # type: ignore[arg-type]
            )

    def test_frozen(self) -> None:
        error = ImportValidationError(code=ImportValidationErrorCode.EMPTY_BATCH)
        with pytest.raises(FrozenInstanceError):
            error.detail = "changed"  # type: ignore[misc]


class TestImportValidationReport:
    def test_valid_report_has_no_errors(self) -> None:
        report = ImportValidationReport(valid=True)
        assert report.valid is True
        assert report.errors == ()

    def test_invalid_report_carries_errors(self) -> None:
        report = ImportValidationReport(
            valid=False,
            errors=(ImportValidationError(code=ImportValidationErrorCode.EMPTY_BATCH),),
        )
        assert report.valid is False
        assert len(report.errors) == 1

    def test_rejects_non_bool_valid(self) -> None:
        # bool subclasses int, so raw 1/0 must never construct.
        with pytest.raises(ValueError):
            ImportValidationReport(valid=1)  # type: ignore[arg-type]

    def test_rejects_non_tuple_errors(self) -> None:
        with pytest.raises(ValueError):
            ImportValidationReport(
                valid=False,
                errors=[  # type: ignore[arg-type]
                    ImportValidationError(code=ImportValidationErrorCode.EMPTY_BATCH)
                ],
            )

    def test_rejects_wrong_error_element_type(self) -> None:
        with pytest.raises(ValueError):
            ImportValidationReport(valid=False, errors=("EMPTY_BATCH",))  # type: ignore[arg-type]

    def test_rejects_valid_with_errors(self) -> None:
        with pytest.raises(ValueError):
            ImportValidationReport(
                valid=True,
                errors=(ImportValidationError(code=ImportValidationErrorCode.EMPTY_BATCH),),
            )

    def test_rejects_invalid_without_errors(self) -> None:
        with pytest.raises(ValueError):
            ImportValidationReport(valid=False)


class TestValidateIsolateCandidate:
    def test_valid_candidate_produces_valid_report(self) -> None:
        report = validate_isolate_candidate(make_candidate())
        assert report.valid is True
        assert report.errors == ()

    def test_missing_required_field(self) -> None:
        candidate = make_candidate()
        del candidate["ward"]
        report = validate_isolate_candidate(candidate)
        assert report.valid is False
        assert len(report.errors) == 1
        error = report.errors[0]
        assert error.code == ImportValidationErrorCode.MISSING_REQUIRED_FIELD
        assert error.field == "ward"
        assert error.record_index is None
        assert error.record_id == "ISO-001"

    @pytest.mark.parametrize(
        "field_name",
        [
            "isolate_id",
            "organism_code",
            "organism_name",
            "facility_id",
            "lab_id",
            "ward",
            "specimen_type",
            "patient_token",
            "source_import_id",
        ],
    )
    @pytest.mark.parametrize("blank", ["", "   "])
    def test_blank_required_text_field(self, field_name: str, blank: str) -> None:
        report = validate_isolate_candidate(make_candidate(**{field_name: blank}))
        assert report.valid is False
        assert len(report.errors) == 1
        error = report.errors[0]
        assert error.code == ImportValidationErrorCode.BLANK_REQUIRED_FIELD
        assert error.field == field_name

    def test_blank_isolate_id_yields_no_record_id(self) -> None:
        """record_id is diagnostic only and must never be invented from a blank value."""
        report = validate_isolate_candidate(make_candidate(isolate_id="   "))
        assert report.valid is False
        assert report.errors[0].record_id is None

    def test_invalid_field_type(self) -> None:
        report = validate_isolate_candidate(make_candidate(organism_code=42))
        assert report.valid is False
        error = report.errors[0]
        assert error.code == ImportValidationErrorCode.INVALID_FIELD_TYPE
        assert error.field == "organism_code"

    @pytest.mark.parametrize("bad_id", ["ISO-12", "iso-012", "ISO-ABC"])
    def test_invalid_isolate_id(self, bad_id: str) -> None:
        report = validate_isolate_candidate(make_candidate(isolate_id=bad_id))
        assert report.valid is False
        error = report.errors[0]
        assert error.code == ImportValidationErrorCode.INVALID_ISOLATE_ID
        assert error.field == "isolate_id"
        assert error.record_id == bad_id

    @pytest.mark.parametrize(
        "bad_date",
        [
            "not-a-date",
            "2026-13-99",
            "2026-08-16T10:00:00",
            "08/16/2026",
            "2026-8-16",
            "2026-02-30",
            "2026-13-01",
        ],
    )
    def test_invalid_collection_date(self, bad_date: str) -> None:
        report = validate_isolate_candidate(make_candidate(collection_date=bad_date))
        assert report.valid is False
        error = report.errors[0]
        assert error.code == ImportValidationErrorCode.INVALID_COLLECTION_DATE
        assert error.field == "collection_date"

    def test_collection_date_rejects_compact_iso_form(self) -> None:
        """Regression: date.fromisoformat accepts 20260816; the canonical
        contract requires the exact YYYY-MM-DD shape."""
        report = validate_isolate_candidate(make_candidate(collection_date="20260816"))
        assert report.valid is False
        error = report.errors[0]
        assert error.code == ImportValidationErrorCode.INVALID_COLLECTION_DATE
        assert error.field == "collection_date"

    def test_collection_date_rejects_iso_week_date_form(self) -> None:
        """Regression: date.fromisoformat accepts ISO week dates such as
        2026-W33-7; the canonical contract requires the exact YYYY-MM-DD shape."""
        report = validate_isolate_candidate(make_candidate(collection_date="2026-W33-7"))
        assert report.valid is False
        error = report.errors[0]
        assert error.code == ImportValidationErrorCode.INVALID_COLLECTION_DATE
        assert error.field == "collection_date"

    @pytest.mark.parametrize("good_date", ["2026-08-16", "2024-02-29"])
    def test_collection_date_accepts_exact_calendar_dates(self, good_date: str) -> None:
        report = validate_isolate_candidate(make_candidate(collection_date=good_date))
        assert report.valid is True
        assert report.errors == ()

    def test_collection_date_must_be_string(self) -> None:
        """Candidates are raw JSON-derived values; typed date belongs to CanonicalIsolate."""
        report = validate_isolate_candidate(make_candidate(collection_date=date(2026, 8, 16)))
        assert report.valid is False
        assert report.errors[0].code == ImportValidationErrorCode.INVALID_FIELD_TYPE

    def test_empty_ast_results(self) -> None:
        report = validate_isolate_candidate(make_candidate(ast_results={}))
        assert report.valid is False
        error = report.errors[0]
        assert error.code == ImportValidationErrorCode.EMPTY_AST_RESULTS
        assert error.field == "ast_results"

    def test_ast_results_must_be_mapping(self) -> None:
        report = validate_isolate_candidate(make_candidate(ast_results=["AMK"]))
        assert report.valid is False
        error = report.errors[0]
        assert error.code == ImportValidationErrorCode.INVALID_FIELD_TYPE
        assert error.field == "ast_results"

    @pytest.mark.parametrize("bad_code", ["amk", "AM1", "TOOLONGKEY", ""])
    def test_invalid_antibiotic_code(self, bad_code: str) -> None:
        report = validate_isolate_candidate(
            make_candidate(ast_results={bad_code: {"interpretation": "S"}})
        )
        assert report.valid is False
        error = report.errors[0]
        assert error.code == ImportValidationErrorCode.INVALID_ANTIBIOTIC_CODE
        assert error.field == "ast_results"

    def test_non_string_antibiotic_code(self) -> None:
        report = validate_isolate_candidate(
            make_candidate(ast_results={42: {"interpretation": "S"}})
        )
        assert report.valid is False
        assert report.errors[0].code == ImportValidationErrorCode.INVALID_ANTIBIOTIC_CODE

    def test_malformed_ast_observation(self) -> None:
        report = validate_isolate_candidate(make_candidate(ast_results={"AMK": "S"}))
        assert report.valid is False
        error = report.errors[0]
        assert error.code == ImportValidationErrorCode.MALFORMED_AST_OBSERVATION
        assert error.field == "ast_results.AMK"

    def test_missing_interpretation(self) -> None:
        report = validate_isolate_candidate(make_candidate(ast_results={"AMK": {}}))
        assert report.valid is False
        error = report.errors[0]
        assert error.code == ImportValidationErrorCode.MISSING_REQUIRED_FIELD
        assert error.field == "ast_results.AMK.interpretation"

    def test_non_string_interpretation(self) -> None:
        report = validate_isolate_candidate(
            make_candidate(ast_results={"AMK": {"interpretation": 42}})
        )
        assert report.valid is False
        error = report.errors[0]
        assert error.code == ImportValidationErrorCode.INVALID_FIELD_TYPE
        assert error.field == "ast_results.AMK.interpretation"

    @pytest.mark.parametrize("bad_value", ["X", "", "s"])
    def test_invalid_interpretation(self, bad_value: str) -> None:
        report = validate_isolate_candidate(
            make_candidate(ast_results={"AMK": {"interpretation": bad_value}})
        )
        assert report.valid is False
        error = report.errors[0]
        assert error.code == ImportValidationErrorCode.INVALID_INTERPRETATION
        assert error.field == "ast_results.AMK.interpretation"

    @pytest.mark.parametrize("bad_candidate", [None, 42, "ISO-001", ["ISO-001"]])
    def test_non_mapping_candidate(self, bad_candidate: object) -> None:
        report = validate_isolate_candidate(bad_candidate)
        assert report.valid is False
        assert len(report.errors) == 1
        assert report.errors[0].code == ImportValidationErrorCode.INVALID_RECORD_SHAPE

    def test_never_raises_on_nasty_inputs(self) -> None:
        nasty_inputs: list[object] = [
            None,
            42,
            "text",
            [],
            {},
            {"isolate_id": None},
            {"ast_results": None},
        ]
        for nasty in nasty_inputs:
            report = validate_isolate_candidate(nasty)
            assert report.valid is False


class TestValidateImportCandidate:
    def test_valid_batch(self) -> None:
        report = validate_import_candidate(
            [make_candidate(), make_candidate(isolate_id="ISO-002")]
        )
        assert report.valid is True
        assert report.errors == ()

    def test_batch_must_be_list(self) -> None:
        report = validate_import_candidate((make_candidate(),))
        assert report.valid is False
        assert len(report.errors) == 1
        assert report.errors[0].code == ImportValidationErrorCode.INVALID_BATCH_SHAPE

    def test_empty_batch(self) -> None:
        report = validate_import_candidate([])
        assert report.valid is False
        assert len(report.errors) == 1
        assert report.errors[0].code == ImportValidationErrorCode.EMPTY_BATCH

    def test_non_mapping_batch_item(self) -> None:
        report = validate_import_candidate([make_candidate(), "not-a-record"])
        assert report.valid is False
        assert len(report.errors) == 1
        error = report.errors[0]
        assert error.code == ImportValidationErrorCode.INVALID_RECORD_SHAPE
        assert error.record_index == 1
        assert error.record_id is None

    def test_never_raises_on_nasty_inputs(self) -> None:
        nasty_inputs: list[object] = [None, 42, "text", {}, (), [None], [42], ["x"]]
        for nasty in nasty_inputs:
            report = validate_import_candidate(nasty)
            assert report.valid is False


class TestMultipleErrorsAndDeterminism:
    def test_multiple_independent_errors_in_one_record(self) -> None:
        candidate = make_candidate(
            isolate_id="ISO-12",
            collection_date="2026-13-99",
            organism_name="   ",
            ast_results={"AMK": {"interpretation": "X"}},
        )
        del candidate["facility_id"]
        report = validate_isolate_candidate(candidate)
        assert report.valid is False
        assert [error.code for error in report.errors] == [
            ImportValidationErrorCode.INVALID_ISOLATE_ID,
            ImportValidationErrorCode.INVALID_COLLECTION_DATE,
            ImportValidationErrorCode.BLANK_REQUIRED_FIELD,
            ImportValidationErrorCode.MISSING_REQUIRED_FIELD,
            ImportValidationErrorCode.INVALID_INTERPRETATION,
        ]
        assert [error.field for error in report.errors] == [
            "isolate_id",
            "collection_date",
            "organism_name",
            "facility_id",
            "ast_results.AMK.interpretation",
        ]
        assert all(error.record_id == "ISO-12" for error in report.errors)

    def test_multiple_errors_across_batch_records(self) -> None:
        report = validate_import_candidate(
            [
                make_candidate(isolate_id="ISO-001", ward=""),
                make_candidate(isolate_id="ISO-002", organism_code=42),
            ]
        )
        assert report.valid is False
        assert [error.record_index for error in report.errors] == [0, 1]
        assert [error.record_id for error in report.errors] == ["ISO-001", "ISO-002"]
        assert [error.code for error in report.errors] == [
            ImportValidationErrorCode.BLANK_REQUIRED_FIELD,
            ImportValidationErrorCode.INVALID_FIELD_TYPE,
        ]

    def test_repeated_validation_is_stable(self) -> None:
        candidate = make_candidate(ward="", ast_results={"AMK": {"interpretation": "X"}})
        first = validate_isolate_candidate(candidate)
        second = validate_isolate_candidate(candidate)
        assert first == second
        assert first.errors == second.errors
        assert [error.code for error in first.errors] == [
            error.code for error in second.errors
        ]

    def test_repeated_batch_validation_is_stable(self) -> None:
        batch = [make_candidate(ward=""), "not-a-record", make_candidate()]
        first = validate_import_candidate(batch)
        second = validate_import_candidate(batch)
        assert first == second
        assert first.errors == second.errors

    def test_error_order_follows_field_declaration_order(self) -> None:
        """All-independent failures must appear in the fixed #30 field order."""
        candidate = make_candidate(
            isolate_id="",
            organism_code=42,
            source_import_id="   ",
        )
        report = validate_isolate_candidate(candidate)
        assert [error.field for error in report.errors] == [
            "isolate_id",
            "organism_code",
            "source_import_id",
        ]
        assert [error.code for error in report.errors] == [
            ImportValidationErrorCode.BLANK_REQUIRED_FIELD,
            ImportValidationErrorCode.INVALID_FIELD_TYPE,
            ImportValidationErrorCode.BLANK_REQUIRED_FIELD,
        ]


class TestCanonicalHeroFixtureCompatibility:
    """The committed #30 golden fixture must flow through the #38 boundary unchanged."""

    def test_fixture_candidates_validate(self) -> None:
        records = load_hero_records()
        assert len(records) == 8
        for record in records:
            report = validate_isolate_candidate(record)
            assert report.valid is True, report.errors

    def test_fixture_batch_validates(self) -> None:
        report = validate_import_candidate(load_hero_records())
        assert report.valid is True
        assert report.errors == ()

    def test_fixture_constructs_typed_batch_preserving_ids(self) -> None:
        expected_ids = [
            "ISO-012",
            "ISO-027",
            "ISO-031",
            "ISO-034",
            "ISO-039",
            "ISO-052",
            "ISO-063",
            "ISO-071",
        ]
        isolates = tuple(
            CanonicalIsolate(
                isolate_id=record["isolate_id"],
                collection_date=date.fromisoformat(record["collection_date"]),
                organism_code=record["organism_code"],
                organism_name=record["organism_name"],
                facility_id=record["facility_id"],
                lab_id=record["lab_id"],
                ward=record["ward"],
                specimen_type=record["specimen_type"],
                patient_token=record["patient_token"],
                source_import_id=record["source_import_id"],
                ast_results={
                    code: AstObservation(Interpretation(entry["interpretation"]))
                    for code, entry in record["ast_results"].items()
                },
            )
            for record in load_hero_records()
        )
        batch = CanonicalImportBatch(records=isolates)
        assert [record.isolate_id for record in batch.records] == expected_ids
