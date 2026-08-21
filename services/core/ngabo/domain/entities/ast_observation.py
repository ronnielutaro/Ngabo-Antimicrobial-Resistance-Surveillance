"""Typed canonical AST observation (M2.1 / Issue #38).

One susceptibility observation for one isolate/antimicrobial pair, shaped
exactly like the ``ast_results`` entry of the canonical hero schema
(``data/schemas/canonical_hero.schema.json``, M1B.6 / Issue #30): the entry
carries only ``interpretation``. Antimicrobial identity deliberately lives
ONLY in the ``ast_results`` map key of ``CanonicalIsolate`` — no nested
antibiotic-code field exists here, so key/value disagreement about the
antimicrobial is structurally impossible (Issue #30 semantic invariant).
"""

from __future__ import annotations

from dataclasses import dataclass

from ngabo.domain.enums.interpretation import Interpretation


@dataclass(frozen=True)
class AstObservation:
    """Immutable susceptibility observation for one antimicrobial code."""

    interpretation: Interpretation

    def __post_init__(self) -> None:
        # StrEnum members compare equal to their string values, so the type
        # must be guarded with isinstance rather than a membership lookup.
        if not isinstance(self.interpretation, Interpretation):
            raise ValueError(
                f"Invalid interpretation {self.interpretation!r}; "
                "expected an Interpretation member"
            )
