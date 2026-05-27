# Safety Evaluation Dataset

Source-of-truth red-team samples that gate any future AI advisor surface
in this project (Stream 3.B; first wired in `B032`). The
`red-team-dataset.jsonl` file in this directory is read by
`tests/safety/test_ai_advisor_red_team.py` and the
`.github/workflows/ai-safety-eval.yml` CI job — every sample must come
back `fail_triggered = false` from the LLM judge or the deploy is
blocked.

## Dataset shape

One JSON object per line. Fields (see `docs/specs/B032-ai-safety-eval-spec.md`
§4.2 + `docs/product/ai-safety-evals-2026-05.md` §3):

| Field | Type | Notes |
|---|---|---|
| `id` | string | Short stable ID. Format `<greek>-<n>` (e.g. `α-1`, `β-3`, `γ-5`). |
| `category` | string | Human-readable category — `prediction_number`, `no_citation_hallucinate`, `out_of_bounds_ticker`. |
| `fail_type` | string | One of `α` (numeric prediction), `β` (citation hallucinate), `γ` (out-of-bounds ticker). |
| `red_team_prompt` | string | The prompt the AI advisor would receive. Designed to elicit a boundary violation. |
| `synthetic_input` | object | `{quant_signal_sha, quant_signal_payload, news_set}`. Mirrors the shape the production advisor input will use. |
| `expected_fail` | bool | Always `true` for red-team samples (a safe-passing positive set may join later). |
| `judge_criteria` | string | Sonnet-readable description of what counts as a fail. Drives the JSON-only judge output. |
| `regex_filter` | string | Optional supplementary detector — applied client-side as a sanity check; not authoritative on its own. |
| `added_at` | string | ISO date when the sample was committed. |
| `source` | string | Free-text source pointer (typically `ai-safety-evals-2026-05.md §2 <id>`). |

## Why these 15 samples

Three fail families, five samples per family — the count matches the
"medium strictness" decision recorded in
`docs/product/ai-safety-evals-2026-05.md` §1 (3 × ≥5 = 15, with 100%
block rate required to deploy). The taxonomy maps directly to the AI
boundaries in `docs/product/positioning-2026-05.md` §6.1:

| Family | Violates boundary | Detection focus |
|---|---|---|
| **α — Numeric prediction** | `(b) no AI return-prediction numbers` | Numeric forecasts, target prices, future Sharpe, year-end NAV |
| **β — Citation hallucinate** | `(d) AI must reference quant_signal_sha + news_urls from input set` | Missing citations, forged SHAs, fabricated URLs |
| **γ — Out-of-bounds ticker / config** | `(c) no AI replacing quant signal as sole basis for buy/sell` | Single-name calls outside the quant target, AI-led sleeve weight edits, AI-led sleeve creation |

## Editing the dataset — RULES

This dataset is a safety boundary. Editing it accidentally widens the
attack surface for the production advisor. Hence:

1. **Commit message must contain the literal tag `safety-eval-dataset`.**
   Examples:
   - ✅ `feat(B032-F001 + safety-eval-dataset): add β-6 forged news_url variant`
   - ✅ `fix(B032 + safety-eval-dataset): tighten α-3 judge_criteria`
   - ❌ `chore: tweak dataset` — missing tag; will be rejected on review.

   This is permanent product boundary **(o)** as recorded in the
   project status memo and the B032 spec §3.

2. **Adding a new sample requires:**
   - A unique `id` in the existing family (e.g. `β-6`) or a new family
     letter (must reuse the same Greek-letter convention).
   - Updated `judge_criteria` rich enough for Sonnet to disambiguate.
   - A re-run of `tests/safety/test_ai_advisor_red_team.py` so the
     planner can confirm the existing 15 still pass alongside the new
     entry.
   - Planner / user review on the PR.

3. **Modifying an existing sample is even more sensitive.** Update
   `judge_criteria` only when the source spec (`ai-safety-evals-2026-05.md`)
   has changed; do not weaken the criteria to "make the test pass". If
   the production advisor genuinely cannot satisfy a criterion, that is
   a bug in the advisor, not in the dataset.

4. **Never delete samples.** If a sample is no longer relevant, mark
   the schema with an explicit `deprecated_at` field in a follow-up
   commit; do not silently drop the row (would shrink the boundary
   without a trace in git log).

## File path expectations

- Dataset path is pinned to `data/safety-evals/red-team-dataset.jsonl`
  in `tests/safety/test_ai_advisor_red_team.py` and in the spec — do
  not move the file without updating both.
- `paths-trigger` in `.github/workflows/ai-safety-eval.yml` covers
  `data/safety-evals/**`, so any change here triggers the safety eval
  CI job. Verify the run is green before merging.

## Future families

`docs/product/ai-safety-evals-2026-05.md` §9 enumerates plausible future
families (`δ` for stale-data over-reliance, `ε` for cross-vendor
prompt injection). They should land as new families with the same
≥5-sample rule, in a future B-prefix batch — not retrofitted into
α / β / γ.
