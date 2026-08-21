"""Domain entities — immutable framework-free canonical domain objects.

Must never import frameworks, cloud SDKs, AI SDKs, or outer Ngabo layers
(see ``docs/CLEAN_ARCHITECTURE.md``). Populated issue by issue; see Issue #38
for the canonical import-boundary entities (M2.1): the typed AST
observation, the canonical isolate record and the canonical import batch.
"""
