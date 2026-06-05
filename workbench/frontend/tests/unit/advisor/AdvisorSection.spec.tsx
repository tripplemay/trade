// @vitest-environment happy-dom
/**
 * B036 F003 — AdvisorSection renders per-sleeve advice + citations (ok),
 * the safety fallback (insufficient_grounding), and empty/error states.
 * Asserts citations render (boundary d) and external links are safe.
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, waitFor } from "@testing-library/react";

import { renderWithIntl } from "../../test-utils/intl";

import type { components } from "@/types/api";

import { AdvisorSection } from "@/components/advisor/AdvisorSection";

type AdvisorSleeveAdvice = components["schemas"]["AdvisorSleeveAdvice"];

const SLEEVES: AdvisorSleeveAdvice[] = [
  {
    sleeve: "satellite_us_quality",
    advice: "Stay diversified within the sleeve.",
    rationale: "Grounded in the quant signal + news.",
    references: [
      { quant_signal_sha: "sha256:abc", news_urls: ["https://a.example/1"] },
    ],
    status: "ok",
    generated_at: "2026-06-05T01:00:00+00:00",
  },
  {
    sleeve: "regime",
    advice: "",
    rationale: "",
    references: [],
    status: "insufficient_grounding",
    generated_at: "2026-06-05T01:00:00+00:00",
  },
];

function buildFetch(body: unknown, ok = true): typeof fetch {
  return vi.fn(async () =>
    ok
      ? new Response(JSON.stringify(body), {
          status: 200,
          headers: { "content-type": "application/json" },
        })
      : new Response("boom", { status: 500 }),
  ) as unknown as typeof fetch;
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("AdvisorSection (B036 F003)", () => {
  it("renders advice + citations for ok and fallback for insufficient", async () => {
    vi.stubGlobal("fetch", buildFetch({ sleeves: SLEEVES }));
    const { getByTestId, getAllByTestId } = renderWithIntl(<AdvisorSection />);

    await waitFor(() => expect(getByTestId("advisor-list")).toBeInTheDocument());
    expect(getAllByTestId("advisor-sleeve")).toHaveLength(2);

    // ok sleeve: advice text + a citation (quant sha + external news link).
    expect(getByTestId("advisor-advice")).toHaveTextContent("Stay diversified");
    const refs = getByTestId("advisor-references");
    expect(refs).toHaveTextContent("sha256:abc");
    const link = refs.querySelector("a");
    expect(link).toHaveAttribute("href", "https://a.example/1");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");

    // insufficient sleeve: the safety fallback, not the advice body.
    expect(getByTestId("advisor-fallback")).toBeInTheDocument();
  });

  it("renders the empty state when there is no advice", async () => {
    vi.stubGlobal("fetch", buildFetch({ sleeves: [] }));
    const { getByTestId } = renderWithIntl(<AdvisorSection />);
    await waitFor(() => expect(getByTestId("advisor-empty")).toBeInTheDocument());
  });

  it("renders the error state on fetch failure", async () => {
    vi.stubGlobal("fetch", buildFetch(null, false));
    const { getByTestId } = renderWithIntl(<AdvisorSection />);
    await waitFor(() => expect(getByTestId("advisor-error")).toBeInTheDocument());
  });

  it("has no execution / order buttons (research-only, boundary a)", async () => {
    vi.stubGlobal("fetch", buildFetch({ sleeves: SLEEVES }));
    const { getByTestId, container } = renderWithIntl(<AdvisorSection />);
    await waitFor(() => expect(getByTestId("advisor-list")).toBeInTheDocument());
    expect(container.querySelectorAll("button")).toHaveLength(0);
  });
});
