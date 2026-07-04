"""B080 F003 — the three re-validation landings (spec §2 F003.1).

A frozen re-validation run lands in exactly three places, and the safety invariant
(§3 ②) is absolute: **there is no code path here that sets an OOS card
``validated=True``.** Un-watching a red card is only ever a manual batch — this
pipeline can make a card more conservative or record it as-is, never validate it.
The card is always written with ``validated=False`` hardcoded (never read from a
computed result), which a grep/AST guard test + a runtime test both enforce.

Landings:
1. ``oos_verification_card`` — conservative update (fresh honest numbers, validated
   pinned False, source ``reverify_<date>``).
2. ``trial_registry`` — one trial per run, verdict by the double-gate mapping.
3. md report → ``docs/test-reports/auto/reverify-<strategy>-<date>.md``.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from workbench_api.db.repositories.oos_verification_card import (
    OosVerificationCardRepository,
)
from workbench_api.db.repositories.trial_registry import TrialRegistryRepository
from workbench_api.monitoring.cpcv import CPCV_LITE_LABEL
from workbench_api.strategy_modes.cn_attack_precompute import CN_ATTACK_RESEARCH_CAVEAT

# judge() verdict → trial_registry verdict (double gate: full-sample holds + OOS
# not worse → maintain/GO; collapses → flag/NO_GO; degenerate → INCONCLUSIVE).
_VERDICT_MAP = {
    "SURVIVES_DEBIASING": "GO",
    "COLLAPSES_DEBIASING": "NO_GO",
    "INCONCLUSIVE": "INCONCLUSIVE",
}

_REPORT_DIR = ("docs", "test-reports", "auto")


def _conservative_card(
    current: dict[str, Any] | None, payload: dict[str, Any], report_ref: str
) -> dict[str, Any]:
    """Build the updated card from the re-validation payload.

    Starts from the current card (or the in-code caveat fallback), refreshes the
    honest OOS numbers, and — critically — **hardcodes ``validated=False``** (never
    derived from ``payload``). ``oos_result`` reflects the fresh PIT OOS sign; the
    advisory-only ``detail`` disclaimer is preserved from the base card."""

    base = dict(current or CN_ATTACK_RESEARCH_CAVEAT)
    pit = payload["pit"]
    holds = pit["oos_cagr"] > 0 and pit["oos_sharpe"] > 0
    reverify_end = payload["window"].split("..")[-1]
    return {
        # ★ SAFETY INVARIANT: literal False — never read from a computed result.
        "validated": False,
        "oos_result": "positive_unvalidated" if holds else "negative",
        "oos_cagr_range": f"{pit['oos_cagr']:.1%} (reverify {reverify_end})",
        "headline_zh": (
            f"冻结再验证({reverify_end}）：去偏样本外 CAGR {pit['oos_cagr']:.1%} / "
            f"Sharpe {pit['oos_sharpe']}——仍未验证，advisory-only。"
        ),
        "headline_en": (
            f"Frozen re-validation ({reverify_end}): de-biased OOS CAGR "
            f"{pit['oos_cagr']:.1%} / Sharpe {pit['oos_sharpe']} — still unvalidated, "
            "advisory-only."
        ),
        "detail_zh": base["detail_zh"],
        "detail_en": base["detail_en"],
        "backtest_ref": report_ref,
    }


def _render_report(payload: dict[str, Any], strategy_id: str, as_of: date) -> str:
    pit, control, judgment = payload["pit"], payload["control"], payload["judgment"]
    cpcv = payload["cpcv_lite"]
    lines = [
        f"# Frozen re-validation — {strategy_id} — {as_of.isoformat()}",
        "",
        f"- Window: {payload['window']}  ·  factor={payload['factor_variant']} / "
        f"weighting={payload['weighting_scheme']} (**parameters frozen**)",
        f"- Verdict: **{judgment['verdict']}** — {judgment['reason']}",
        "",
        "## De-biased PIT vs survivor-biased control (walk-forward 70/30)",
        "",
        "| | full CAGR | full Sharpe | OOS CAGR | OOS Sharpe |",
        "|---|---|---|---|---|",
        f"| PIT (de-biased) | {pit['full_cagr']:.1%} | {pit['full_sharpe']} | "
        f"{pit['oos_cagr']:.1%} | {pit['oos_sharpe']} |",
        f"| control (biased) | {control['full_cagr']:.1%} | {control['full_sharpe']} | "
        f"{control['oos_cagr']:.1%} | {control['oos_sharpe']} |",
        f"| survivorship bias | {judgment['survivorship_bias_full_cagr']:.1%} | — | "
        f"{judgment['survivorship_bias_oos_cagr']:.1%} | "
        f"{judgment['survivorship_bias_oos_sharpe']} |",
        "",
        f"## {cpcv['label']}",
        "",
        f"- splits: {cpcv['n_splits']}  ·  mean OOS CAGR: {cpcv['oos_cagr_mean']}  ·  "
        f"mean OOS Sharpe: {cpcv['oos_sharpe_mean']}  ·  positive-OOS frac: "
        f"{cpcv['oos_positive_frac']}",
        "",
        "| split | OOS start | OOS end | OOS CAGR | OOS Sharpe |",
        "|---|---|---|---|---|",
        *[
            f"| {s['index']} | {s['oos_start']} | {s['oos_end']} | "
            f"{s['oos_cagr']:.1%} | {s['oos_sharpe']} |"
            for s in cpcv["splits"]
        ],
        "",
        "> Re-validation, not re-training: parameters were frozen; the card is only "
        "ever made more conservative / recorded as-is — never validated by this "
        "pipeline. advisory-only / research-only.",
        "",
    ]
    return "\n".join(lines)


def land_results(
    session: Session,
    *,
    strategy_id: str,
    payload: dict[str, Any],
    as_of: date,
    repo_root: Path,
) -> dict[str, Any]:
    """Perform the three landings; return ``{verdict, report_ref, validated}``."""

    verdict = _VERDICT_MAP.get(payload["judgment"]["verdict"], "INCONCLUSIVE")
    report_ref = f"docs/test-reports/auto/reverify-{strategy_id}-{as_of.isoformat()}.md"

    # 3. md report (write first so the card/trial can reference it).
    report_path = Path(repo_root).joinpath(*_REPORT_DIR) / (
        f"reverify-{strategy_id}-{as_of.isoformat()}.md"
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(_render_report(payload, strategy_id, as_of), encoding="utf-8")

    # 1. oos_verification_card — conservative update, validated pinned False.
    card_repo = OosVerificationCardRepository(session)
    new_card = _conservative_card(card_repo.get_card(strategy_id), payload, report_ref)
    card_repo.upsert_card(strategy_id, new_card, source=f"reverify_{as_of.isoformat()}")

    # 2. trial_registry — one trial per run (double-gate verdict).
    pit = payload["pit"]
    TrialRegistryRepository(session).register(
        id=f"reverify-{strategy_id}-{as_of.isoformat()}",
        batch="reverify",
        strategy_id=strategy_id,
        verdict=verdict,
        params={"description": "frozen re-validation (pure_momentum / equal)"},
        metrics={
            "summary": (
                f"PIT OOS_CAGR {pit['oos_cagr']:.1%} / OOS_Sharpe {pit['oos_sharpe']}; "
                f"full_CAGR {pit['full_cagr']:.1%}; {payload['judgment']['verdict']}"
            )
        },
        universe="B070 survivorship-free PIT (reverify snapshot)",
        oos_split=CPCV_LITE_LABEL,
        source_ref=report_ref,
        notes="frozen re-validation; card never validated by pipeline",
    )
    return {"verdict": verdict, "report_ref": report_ref, "validated": new_card["validated"]}
