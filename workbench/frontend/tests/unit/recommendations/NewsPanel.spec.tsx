// @vitest-environment happy-dom
/**
 * B034 F003 — NewsPanel renders structured sleeve news (topic chips,
 * relevance score, matched tickers, external link) and re-queries the
 * backend when a filter changes. Asserts the panel carries no
 * AI-generated prose (B034 non-generative boundary §3).
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, waitFor } from "@testing-library/react";

import { renderWithIntl } from "../../test-utils/intl";

import type { components } from "@/types/api";

import { NewsPanel } from "@/components/recommendations/NewsPanel";

type SleeveNewsItem = components["schemas"]["SleeveNewsItem"];

const ITEMS: SleeveNewsItem[] = [
  {
    news_id: "n-1",
    title: "Apple 10-K filed",
    source: "sec_edgar",
    url: "https://www.sec.gov/aapl-10k",
    published_at: "2026-05-01T12:00:00+00:00",
    content_sha256: "a".repeat(64),
    topics: ["财报"],
    matched_tickers: ["AAPL"],
    score: 1.94,
  },
  {
    news_id: "n-2",
    title: "NVIDIA 8-K event",
    source: "sec_edgar",
    url: "https://www.sec.gov/nvda-8k",
    published_at: "2026-04-20T09:00:00+00:00",
    content_sha256: "b".repeat(64),
    topics: ["重大事件"],
    matched_tickers: ["NVDA"],
    score: 1.88,
  },
];

function buildFetch(handler: (url: string) => unknown): typeof fetch {
  return vi.fn(async (input: RequestInfo | URL) => {
    const url = typeof input === "string" ? input : (input as Request).url ?? input.toString();
    return new Response(JSON.stringify(handler(url)), {
      status: 200,
      headers: { "content-type": "application/json" },
    });
  }) as unknown as typeof fetch;
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("NewsPanel (B034 F003)", () => {
  it("renders structured items: link, score, tickers, topic chips", async () => {
    vi.stubGlobal("fetch", buildFetch(() => ({ items: ITEMS })));
    const { getByTestId, getAllByTestId } = renderWithIntl(<NewsPanel />);

    await waitFor(() => {
      expect(getByTestId("news-list")).toBeInTheDocument();
    });
    expect(getAllByTestId("news-item")).toHaveLength(2);

    const link = getByTestId("news-list").querySelector("a");
    expect(link).toHaveAttribute("href", "https://www.sec.gov/aapl-10k");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");

    const chips = getAllByTestId("news-topic-chip").map((c) => c.textContent);
    expect(chips).toContain("财报");
    expect(getAllByTestId("news-score")[0]).toHaveTextContent("1.94");
    expect(getAllByTestId("news-tickers")[0]).toHaveTextContent("AAPL");
  });

  it("renders empty state when no items", async () => {
    vi.stubGlobal("fetch", buildFetch(() => ({ items: [] })));
    const { getByTestId } = renderWithIntl(<NewsPanel />);
    await waitFor(() => {
      expect(getByTestId("news-empty")).toBeInTheDocument();
    });
  });

  it("re-queries the backend when the topic filter changes", async () => {
    const calls: string[] = [];
    vi.stubGlobal(
      "fetch",
      buildFetch((url) => {
        calls.push(url);
        return { items: url.includes("topic=") ? [ITEMS[0]] : ITEMS };
      }),
    );
    const { getByTestId, getAllByTestId } = renderWithIntl(<NewsPanel />);
    await waitFor(() => expect(getAllByTestId("news-item")).toHaveLength(2));

    fireEvent.change(getByTestId("news-filter-topic"), { target: { value: "财报" } });
    await waitFor(() => expect(getAllByTestId("news-item")).toHaveLength(1));

    expect(calls.some((url) => url.includes("topic=%E8%B4%A2%E6%8A%A5") || url.includes("topic=财报"))).toBe(true);
    expect(calls[0]).toContain("sleeve=satellite_us_quality");
  });

  it("surfaces an error message when the fetch fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response("boom", { status: 500 })) as unknown as typeof fetch,
    );
    const { getByTestId } = renderWithIntl(<NewsPanel />);
    await waitFor(() => {
      expect(getByTestId("news-error")).toBeInTheDocument();
    });
  });
});
