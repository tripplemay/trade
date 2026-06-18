"use client";

import { useLocale, useTranslations } from "next-intl";

import { Card, CardContent } from "@/components/ui/card";
import type { components } from "@/types/api";

type ResearchCaveat = components["schemas"]["ResearchCaveat"];

/**
 * B067 F003 — cn_attack out-of-sample (OOS) honesty disclosure.
 *
 * Spec §0 (non-negotiable): the A-share attack advisory modes are research-state
 * and were NOT validated out of sample — B066 found the OOS window a momentum
 * reversal (CAGR −9%~−11%, i.e. it lost money out of sample). This banner makes
 * that unmissable, going BEYOND the generic 研究态 badge, whenever such a mode's
 * recommendation is shown.
 *
 * It renders **only** when the API returns a `research_caveat`, which the backend
 * populates exclusively for the cn_attack momentum modes (from the snapshot's
 * `master_meta`). Presence of the caveat IS the cn_attack gate — no strategy_id
 * string-matching is needed, which avoids FE/BE id drift. Funded / other modes
 * return null and this renders nothing.
 *
 * The caveat carries bilingual headline/detail; the active locale picks which to
 * show. All disclosure copy is rendered verbatim from the API (honest disclosure,
 * not a computed value) with a red / destructive palette so the negative-OOS
 * warning is the most prominent element on the surface. Advisory-only: this
 * component has no order / execute affordance (no-execution gate).
 */
export function CnAttackOosDisclosure({
  researchCaveat,
}: {
  researchCaveat?: ResearchCaveat | null;
}) {
  const t = useTranslations("recommendations.oosDisclosure");
  const locale = useLocale();

  if (!researchCaveat) return null;

  const isZh = locale.startsWith("zh");
  const headline = isZh ? researchCaveat.headline_zh : researchCaveat.headline_en;
  const detail = isZh ? researchCaveat.detail_zh : researchCaveat.detail_en;
  // Nothing meaningful to disclose without at least a headline.
  if (!headline) return null;

  return (
    <Card
      data-testid="cn-attack-oos-disclosure"
      data-oos-result={researchCaveat.oos_result ?? undefined}
      className="border-destructive bg-destructive/20"
    >
      <CardContent className="space-y-1.5 py-3 text-sm text-destructive-foreground">
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
          <strong className="font-semibold">⚠ {t("title")}</strong>
          {researchCaveat.oos_cagr_range ? (
            <span data-testid="cn-attack-oos-cagr" className="text-xs">
              {t("oosCagrLabel")}: {researchCaveat.oos_cagr_range}
            </span>
          ) : null}
        </div>
        <p data-testid="cn-attack-oos-headline">{headline}</p>
        {detail ? (
          <p data-testid="cn-attack-oos-detail" className="text-xs">
            {detail}
          </p>
        ) : null}
        {researchCaveat.backtest_ref ? (
          <p className="text-xs">
            {t("backtestRefLabel")}: <code>{researchCaveat.backtest_ref}</code>
          </p>
        ) : null}
      </CardContent>
    </Card>
  );
}
