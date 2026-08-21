"""Focused unit tests for the canonical import-boundary entities (M2.1 / Issue #38).

Covers the typed AST observation, canonical isolate record and canonical
import batch: construction, #30-shape preservation, deep immutability and
intrinsic-invariant failures. Framework-free by construction — no
FastAPI/GCP/ADK/Gemini dependency appears anywhere in the boundary.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import date, datetime

import pytest

from ngabo.domain.entities.ast_observation import AstObservation
from ngabo.domain.entities.canonical_import_batch import CanonicalImportBatch
from ngabo.domain.entities.canonical_isolate import (
    ANTIBIOTIC_CODE_PATTERN,
    ISOLATE_ID_PATTERN,
    CanonicalIsolate,
)
from ngabo.domain.enums.interpretation import Interpretation


def make_isolate(
    *,
    isolate_id: str = "ISO-001",
    collection_date: date = date(2026, 8, 16),
    organism_code: str = "eco",
    organism_name: str = "Escherichia coli",
    facility_id: str = "SYNTH-FACILITY-001",
    lab_id: str = "SYNTH-LAB-001",
    ward: str = "SYNTH-WARD-A",
    specimen_type: str = "urine",
    patient_token: str = "SYNTH-CASE-001",
    source_import_id: str = "SYNTH-IMPORT-001",
    ast_results: dict[str, AstObservation] | None = None,
) -> CanonicalIsolate:
    """Build a valid typed isolate with minimal ceremony for focused assertions."""
    if ast_results is None:
        ast_results = {"AMK": AstObservation(Interpretation.SUSCEPTIBLE)}
    return CanonicalIsolate(
        isolate_id=isolate_id,
        collection_date=collection_date,
        organism_code=organism_code,
        organism_name=organism_name,
        facility_id=facility_id,
        lab_id=lab_id,
        ward=ward,
        specimen_type=specimen_type,
        patient_token=patient_token,
        source_import_id=source_import_id,
        ast_results=ast_results,
    )


class TestInterpretation:
    @pytest.mark.parametrize(
        ("member", "value"),
        [
            (Interpretation.SUSCEPTIBLE, "S"),
            (Interpretation.INTERMEDIATE, "I"),
            (Interpretation.RESISTANT, "R"),
            (Interpretation.UNKNOWN, "UNKNOWN"),
        ],
    )
    def test_member_values(self, member: Interpretation, value: str) -> None:
        assert member.value == value

    def test_full_vocabulary(self) -> None:
        assert {member.value for member in Interpretation} == {"S", "I", "R", "UNKNOWN"}


class TestAstObservation:
    def test_valid_construction(self) -> None:
        observation = AstObservation(Interpretation.RESISTANT)
        assert observation.interpretation is Interpretation.RESISTANT

    def test_rejects_raw_string(self) -> None:
        # StrEnum members equal their string values, so only the isinstance
        # guard can reject the raw string.
        with pytest.raises(ValueError):
            AstObservation("R")  # type: ignore[arg-type]

    def test_rejects_unknown_value(self) -> None:
        with pytest.raises(ValueError):
            AstObservation("NOT-A-VALUE")  # type: ignore[arg-type]

    def test_carries_no_antibiotic_identity(self) -> None:
        """Antimicrobial identity lives only in the ast_results map key (Issue #30)."""
        observation = AstObservation(Interpretation.SUSCEPTIBLE)
        assert not hasattr(observation, "antibiotic_code")

    def test_frozen(self) -> None:
        observation = AstObservation(Interpretation.SUSCEPTIBLE)
        with pytest.raises(FrozenInstanceError):
            observation.interpretation = Interpretation.RESISTANT  # type: ignore[misc]

    def test_value_equality(self) -> None:
        assert AstObservation(Interpretation.SUSCEPTIBLE) == AstObservation(
            Interpretation.SUSCEPTIBLE
        )
        assert AstObservation(Interpretation.SUSCEPTIBLE) != AstObservation(
            Interpretation.RESISTANT
        )


class TestCanonicalIsolate:
    def test_valid_construction_preserves_fields(self) -> None:
        isolate = make_isolate(isolate_id="ISO-042", ward="SYNTH-WARD-B")
        assert isolate.isolate_id == "ISO-042"
        assert isolate.collection_date == date(2026, 8, 16)
        assert isolate.organism_code == "eco"
        assert isolate.organism_name == "Escherichia coli"
        assert isolate.facility_id == "SYNTH-FACILITY-001"
        assert isolate.lab_id == "SYNTH-LAB-001"
        assert isolate.ward == "SYNTH-WARD-B"
        assert isolate.specimen_type == "urine"
        assert isolate.patient_token == "SYNTH-CASE-001"
        assert isolate.source_import_id == "SYNTH-IMPORT-001"

    def test_preserves_canonical_isolate_id(self) -> None:
        """isolate_id must stay exactly as authored (suitable for CanonicalRecordReference)."""
        isolate = make_isolate(isolate_id="ISO-063")
        assert isolate.isolate_id == "ISO-063"

    @pytest.mark.parametrize(
        "bad_id",
        ["ISO-12", "ISO-1234", "iso-012", "ISO-ABC", "ISO-012 ", "", "   ", "ABC-012"],
    )
    def test_rejects_invalid_isolate_id_shape(self, bad_id: str) -> None:
        with pytest.raises(ValueError):
            make_isolate(isolate_id=bad_id)

    def test_rejects_non_string_isolate_id(self) -> None:
        with pytest.raises(ValueError):
            make_isolate(isolate_id=12)  # type: ignore[arg-type]

    def test_rejects_string_collection_date(self) -> None:
        """The typed boundary takes datetime.date; string conversion belongs to importers."""
        with pytest.raises(ValueError):
            make_isolate(collection_date="2026-08-16")  # type: ignore[arg-type]

    def test_rejects_datetime_collection_date(self) -> None:
        """Regression: datetime.datetime subclasses date, but this canonical
        field is date-only. A timestamp-bearing datetime must fail closed,
        never be normalized down to its date."""
        with pytest.raises(ValueError):
            make_isolate(collection_date=datetime(2026, 8, 16, 10, 30))

    @pytest.mark.parametrize(
        "field_name",
        [
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
    def test_rejects_blank_text_fields(self, field_name: str) -> None:
        for blank in ("", "   "):
            with pytest.raises(ValueError):
                make_isolate(**{field_name: blank})  # type: ignore[arg-type]

    def test_rejects_non_string_text_field(self) -> None:
        with pytest.raises(ValueError):
            make_isolate(organism_code=42)  # type: ignore[arg-type]

    def test_ast_identity_lives_in_map_key_only(self) -> None:
        isolate = make_isolate(
            ast_results={
                "AMK": AstObservation(Interpretation.SUSCEPTIBLE),
                "CAZ": AstObservation(Interpretation.RESISTANT),
            }
        )
        assert list(isolate.ast_results) == ["AMK", "CAZ"]
        assert isolate.ast_results["AMK"].interpretation is Interpretation.SUSCEPTIBLE
        assert isolate.ast_results["CAZ"].interpretation is Interpretation.RESISTANT

    def test_rejects_empty_ast_results(self) -> None:
        with pytest.raises(ValueError):
            make_isolate(ast_results={})

    def test_rejects_non_mapping_ast_results(self) -> None:
        bad_ast_results: object = [("AMK", AstObservation(Interpretation.SUSCEPTIBLE))]
        with pytest.raises(ValueError):
            make_isolate(ast_results=bad_ast_results)  # type: ignore[arg-type]

    @pytest.mark.parametrize("bad_key", ["amk", "AM1", "TOOLONGKEY", "AMK-X", ""])
    def test_rejects_invalid_antimicrobial_code(self, bad_key: str) -> None:
        with pytest.raises(ValueError):
            make_isolate(ast_results={bad_key: AstObservation(Interpretation.SUSCEPTIBLE)})

    def test_rejects_non_observation_ast_value(self) -> None:
        with pytest.raises(ValueError):
            make_isolate(ast_results={"AMK": "S"})  # type: ignore[dict-item]

    def test_ast_results_are_deeply_immutable(self) -> None:
        source = {"AMK": AstObservation(Interpretation.SUSCEPTIBLE)}
        isolate = make_isolate(ast_results=source)
        with pytest.raises(TypeError):
            isolate.ast_results["AMK"] = AstObservation(Interpretation.RESISTANT)  # type: ignore[index]
        # Mutating the caller's dict after construction must not reach the record.
        source["AMK"] = AstObservation(Interpretation.RESISTANT)
        assert isolate.ast_results["AMK"].interpretation is Interpretation.SUSCEPTIBLE

    def test_frozen(self) -> None:
        isolate = make_isolate()
        with pytest.raises(FrozenInstanceError):
            isolate.ward = "SYNTH-WARD-C"  # type: ignore[misc]

    def test_value_equality(self) -> None:
        assert make_isolate() == make_isolate()
        assert make_isolate() != make_isolate(ward="SYNTH-WARD-C")

    def test_patterns_match_fixture_shapes(self) -> None:
        assert ISOLATE_ID_PATTERN.fullmatch("ISO-012")
        assert ANTIBIOTIC_CODE_PATTERN.fullmatch("AMK")


class TestCanonicalImportBatch:
    def test_valid_construction_preserves_order(self) -> None:
        first = make_isolate(isolate_id="ISO-001")
        second = make_isolate(isolate_id="ISO-002")
        batch = CanonicalImportBatch(records=(first, second))
        assert batch.records == (first, second)

    def test_rejects_non_tuple_records(self) -> None:
        with pytest.raises(ValueError):
            CanonicalImportBatch(records=[make_isolate()])  # type: ignore[arg-type]

    def test_rejects_empty_batch(self) -> None:
        with pytest.raises(ValueError):
            CanonicalImportBatch(records=())

    def test_rejects_non_isolate_element(self) -> None:
        bad_records: tuple[object, ...] = (make_isolate(), "not-an-isolate")
        with pytest.raises(ValueError):
            CanonicalImportBatch(records=bad_records)  # type: ignore[arg-type]

    def test_duplicate_isolate_ids_remain_representable(self) -> None:
        """Duplicate-ID semantics are owned by Issue #40; the #38 boundary must
        not silently deduplicate, so duplicate IDs must stay constructible."""
        batch = CanonicalImportBatch(
            records=(make_isolate(isolate_id="ISO-001"), make_isolate(isolate_id="ISO-001"))
        )
        assert [record.isolate_id for record in batch.records] == ["ISO-001", "ISO-001"]

    def test_frozen(self) -> None:
        batch = CanonicalImportBatch(records=(make_isolate(),))
        with pytest.raises(FrozenInstanceError):
            batch.records = ()  # type: ignore[misc]
