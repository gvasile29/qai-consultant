"""The gate spec: every threshold and the one-line reason it exists.

The zero-tolerance gates encode an estimation asymmetry: these numbers get pasted into
plans/budgets/deliverables, so a glitch laundered into an authoritative-looking output
is far costlier than a near-miss. Consumed by ``estimate_integrity.py`` and ``rag.py``.
"""

from __future__ import annotations

# A kickoff form can't imply more than a few working-years of duration; beyond this
# is a parse artifact, not an estimate. Below a working week the field was mis-parsed.
DURATION_MAX_DAYS = 1825          # ~5 working-years
DURATION_MIN_DAYS = 5             # ~1 working week

# Restating headcount ("3 + 2, or 5 full-stack") must not change the count. Zero-tol.
TEAM_RESTATEMENT_DELTA_MAX = 0

# The display name must keep the user's spaces; only OS-reserved filename chars may drop.
NAME_MUST_PRESERVE_SPACES = True

# A physically-impossible magnitude must never read "High" confidence. Zero-tol.
CONFIDENCE_HIGH_FORBIDDEN_ABOVE_DAYS = DURATION_MAX_DAYS

# Version strings in a deliverable that the user never supplied (fabricated). Zero-tol.
FABRICATED_FACTS_MAX = 0

# ── rag (classical RAG metrics, local index + LLM judge via the app's LLMClient) ──
RAG_K = 5                 # retrieval depth (matches the app's RAG_K_GENERATION)
RECALL_AT_K_MIN = 0.8     # >=80% of golden queries must retrieve their expected source doc
MRR_MIN = 0.7             # mean reciprocal rank — labelled source must rank high, not just appear
FAITHFULNESS_MIN = 0.70   # answer grounded in the sources; margin for judge variance, still catches a bad run
ANSWER_RELEVANCE_MIN = 0.7  # the answer must substantively address the query, not generic filler
SOURCE_ATTRIBUTION_MIN = 0.9  # >=90% of [Source N] citations must point at a retrieved chunk (no invented provenance)
JUDGED_QUORUM_MIN = 0.5       # >=half of judged cases must grade successfully, else the judged metrics SKIP (not pass on thin data)
