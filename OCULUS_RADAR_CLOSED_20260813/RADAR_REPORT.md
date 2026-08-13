# ArtWeb / OCULUS Intelligence Radar — 2026-08-13 09:15 UTC

## Finding 1 — Conditional HTTP polling with ETag/Last-Modified
GitHub REST officially recommends authenticated conditional GETs with ETag / If-None-Match or Last-Modified / If-Modified-Since. A 304 Not Modified response does not consume primary rate limit when correctly authorized. n8n issue #36083 reproduces the failure mode when ETags are discarded and unchanged pull requests are fetched as full 200 responses until the credential hits 403 rate-limit exhaustion.

CANONICAL_CANDIDATE:
- ARTWEB.HTTP.CONDITIONAL_FETCH_STATE_IR
- ARTWEB.HTTP.ETAG_LAST_MODIFIED_REVALIDATION_GATE
- OCULUS.INGESTION.CONDITIONAL_POLLING_IR
- OCULUS.INGESTION.WEBHOOK_VS_POLL_ROUTER_IR
- OCULUS.ECONOMICS.UNCHANGED_FETCH_WASTE_LEDGER_IR

Invariant:
UNCHANGED HTTP SOURCES SHOULD BE REVALIDATED, NOT RE-DOWNLOADED; VALIDATORS MUST BE BOUND TO THE EXACT REQUEST IDENTITY.

## Finding 2 — Multiset-aware graph diff
n8n issue #36144 and PR #35652 show that using Map/set semantics for duplicate workflow connections can hide removal of one duplicate edge and can make a version appear additive, allowing history compaction to prune a restorable state.

CANONICAL_CANDIDATE:
- OCULUS.DIFF.MULTISET_GRAPH_EDGE_IR
- OCULUS.DIFF.MULTIPLICITY_PRESERVING_GRAPH_DIFF_GATE
- ARTWEB.POSTFLIGHT.INTERNAL_LINK_MULTIPLICITY_DIFF_IR
- OCULUS.HISTORY.IRREVERSIBLE_PRUNE_DIFF_SAFETY_GATE

Invariant:
IF DUPLICATE EDGES ARE LEGAL, GRAPH DIFFING MUST PRESERVE MULTIPLICITY; SET-STYLE DEDUPLICATION CAN TURN A REAL DELETION INTO AN INVISIBLE NO-OP.

## Finding 3 — Query-conditioned multi-skill compatibility
arXiv:2606.03565 argues that individually relevant skills may still be redundant, contradictory or unnatural when selected together for a specific query. R3-Skill preserves rejected skill combinations and uses a two-stage retrieve/rerank design with compatibility-aware reranking.

CANONICAL_CANDIDATE:
- OCULUS.SKILLS.QUERY_CONDITIONED_SKILL_COMPATIBILITY_IR
- OCULUS.SKILLS.REJECT_AS_RESOURCE_IR
- OCULUS.RETRIEVAL.TWO_STAGE_SKILL_ROUTER_IR
- OCULUS.SKILLS.SET_COMPATIBILITY_METRIC_IR

Invariant:
MULTI-SKILL ROUTING IS NOT THE SUM OF INDEPENDENT RELEVANCE SCORES; THE SELECTED SKILLS MUST ALSO FORM A QUERY-CONDITIONED COMPATIBLE SET.

## Maturity note
n8n 2.35.2 pre-release was published 2026-08-13 07:59 UTC. Its listed fix is the already-recorded publication-outbox activation-mode patch, so no duplicate module is created.

## Priority
P0:
1. ARTWEB.HTTP.ETAG_LAST_MODIFIED_REVALIDATION_GATE
2. OCULUS.DIFF.MULTIPLICITY_PRESERVING_GRAPH_DIFF_GATE
3. OCULUS.SKILLS.QUERY_CONDITIONED_SKILL_COMPATIBILITY_IR
