"""Domain services — deterministic framework-free domain policy.

Must never import frameworks, cloud SDKs, AI SDKs, or outer Ngabo layers
(see ``docs/CLEAN_ARCHITECTURE.md``). Populated issue by issue; see Issue #26
for the incident transition policy added in M1B.2, and Issue #38 for the
deterministic canonical import-boundary validation added in M2.1.
"""
