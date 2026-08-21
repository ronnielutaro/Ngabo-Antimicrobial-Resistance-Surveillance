"""Susceptibility interpretation vocabulary (M2.1 / Issue #38).

The four-value vocabulary fixed by the canonical hero schema
(``data/schemas/canonical_hero.schema.json``, M1B.6 / Issue #30), carried
as the enum's string values:

- ``"S"`` — susceptible;
- ``"I"`` — intermediate;
- ``"R"`` — resistant;
- ``"UNKNOWN"`` — no usable interpretation.

This enum fixes the vocabulary only: it deliberately encodes no clinical
meaning or ranking, and deterministic logic must never infer a "corrected"
interpretation for a record that carries ``UNKNOWN`` or an invalid value
(Issue #38 / ``docs/DATA_SAFETY_EVALUATION.md``). The committed golden hero
fixture contains no material ``UNKNOWN`` observation; the member exists so
the boundary can represent the full #30 contract without inventing values.
"""

from __future__ import annotations

from enum import StrEnum


class Interpretation(StrEnum):
    """Deterministic susceptibility interpretation vocabulary (Issue #30)."""

    SUSCEPTIBLE = "S"
    INTERMEDIATE = "I"
    RESISTANT = "R"
    UNKNOWN = "UNKNOWN"
