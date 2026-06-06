"use client";

/**
 * B036 F003 — Home AI Advisor section.
 *
 * Renders the latest precomputed AI advice per sleeve from the
 * same-origin, auth-gated ``GET /api/advisor``. The advice text is
 * generated upstream and gated by the red-team safety eval; this section
 * only displays it. Every ``ok`` item renders its citations
 * (quant_signal_sha + external news links, rel="noopener noreferrer") —
 * the v0.9.28 boundary (d) "must be citable". A ``insufficient_grounding``
 * item renders the ai-safety §6.2 fallback copy and never the advice body.
 *
 * There are NO execution / order buttons here — the workbench is
 * research-only and AI output never triggers a trade (boundary (a)).
 */

import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type { components } from "@/types/api";

type AdvisorResponse = components["schemas"]["AdvisorResponse"];
type AdvisorSleeveAdvice = components["schemas"]["AdvisorSleeveAdvice"];

const ADVISOR_URL = "/api/advisor";
const INSUFFICIENT = "insufficient_grounding";

export function AdvisorSection() {
  const t = useTranslations("home.advisor");
  const [sleeves, setSleeves] = useState<AdvisorSleeveAdvice[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetch(ADVISOR_URL)
      .then(async (response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return (await response.json()) as AdvisorResponse;
      })
      .then((payload) => {
        if (!cancelled) setSleeves(payload.sleeves ?? []);
      })
      .catch((reason: unknown) => {
        if (!cancelled) {
          setError(reason instanceof Error ? reason.message : String(reason));
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <Card data-testid="home-advisor-card">
      <CardHeader>
        <CardTitle>{t("title")}</CardTitle>
        <CardDescription>{t("description")}</CardDescription>
      </CardHeader>
      <CardContent>
        {error ? (
          <p data-testid="advisor-error" className="text-sm text-destructive">
            {t("error", { error })}
          </p>
        ) : sleeves === null ? (
          <p className="text-sm text-muted-foreground">{t("loading")}</p>
        ) : (
          // B039: the ⚠️ research disclaimer (mockup §2) is a card-level
          // general statement — it stays visible for both the ok and the
          // insufficient_grounding state (and the empty state), below the
          // advice/citations. It only hides while loading or on a fetch
          // error (no advice to qualify yet).
          <>
            {sleeves.length === 0 ? (
              <p data-testid="advisor-empty" className="text-sm text-muted-foreground">
                {t("empty")}
              </p>
            ) : (
              <ul data-testid="advisor-list" className="space-y-4">
                {sleeves.map((item) => (
                  <li
                    key={item.sleeve}
                    data-testid="advisor-sleeve"
                    className="rounded-md border border-border px-3 py-2"
                  >
                    <div className="text-xs font-semibold uppercase text-muted-foreground">
                      {item.sleeve}
                    </div>
                    {item.status === INSUFFICIENT ? (
                      <p data-testid="advisor-fallback" className="mt-1 text-sm text-amber-200">
                        {t("fallback")}
                      </p>
                    ) : (
                      <div className="mt-1 space-y-1">
                        <p data-testid="advisor-advice" className="text-sm text-foreground">
                          {item.advice}
                        </p>
                        <p className="text-xs text-muted-foreground">{item.rationale}</p>
                        <div data-testid="advisor-references" className="pt-1 text-xs">
                          {(item.references ?? []).map((ref, idx) => (
                            <div key={idx} className="flex flex-wrap items-center gap-2">
                              <span className="text-muted-foreground">
                                {t("quantLabel")}: <code>{ref.quant_signal_sha}</code>
                              </span>
                              {(ref.news_urls ?? []).map((url) => (
                                <a
                                  key={url}
                                  href={url}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="text-foreground underline-offset-2 hover:underline"
                                >
                                  {url}
                                </a>
                              ))}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </li>
                ))}
              </ul>
            )}
            <p
              data-testid="advisor-disclaimer"
              className="mt-3 border-t border-border/50 pt-2 text-xs text-muted-foreground"
            >
              {t("disclaimer")}
            </p>
          </>
        )}
      </CardContent>
    </Card>
  );
}
