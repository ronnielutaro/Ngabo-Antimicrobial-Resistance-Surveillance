"""Domain value objects — small immutable framework-free domain types.

Must never import frameworks, cloud SDKs, AI SDKs, or outer Ngabo layers
(see ``docs/CLEAN_ARCHITECTURE.md``). Populated issue by issue; see Issue #25
for the identity/version primitives (M1B.1), Issue #27 for the autonomy
decision contract (M1B.3), Issue #28 for the proof-carrying claim and
proof-reference contracts (M1B.4), Issue #29 for the claim-verification
error and report contracts (M1B.5), and Issue #38 for the
import-validation error and report contracts (M2.1).
"""
