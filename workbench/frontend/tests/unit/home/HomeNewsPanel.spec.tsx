// @vitest-environment happy-dom
/**
 * B038 F002 — HomeNewsPanel renders the global "Today's market news" feed
 * (title link / source / date / deterministic topic chips) with loading,
 * empty and error states, in both locales. Headlines only — no AI prose
 * (B034 non-generative boundary) and no execution affordance.
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, waitFor } from "@testing-library/react";

import { renderWithIntl } from "../../test-utils/intl";

import type { components } from "@/types/api";

import { HomeNewsPanel } from "@/components/home/HomeNewsPanel";

type LatestNewsItem = components["schemas"]["LatestNewsItem"];

const ITEMS: LatestNewsItem[] = [
  {
    news_id: "n1",
    title: "Fed minutes released",
    source: "sec_edgar",
    url: "https://www.sec.gov/fed-minutes",
    published_at: "2026-06-05T13:00:00+00:00",
    topics: ["重大事件"],
  },
  {
    news_id: "n2",
    title: "TSMC reports Q1 earnings beat",
    source: "yahoo_rss",
    url: "https://finance.yahoo.com/tsmc",
    published_at: "2026-06-05T09:30:00+00:00",
    topics: ["财报"],
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

describe("HomeNewsPanel (B038 F002)", () => {
  it("renders one item per headline with title link, source, date", async () => {
    vi.stubGlobal("fetch", buildFetch({ items: ITEMS }));
    const { getByTestId, getAllByTestId } = renderWithIntl(<HomeNewsPanel />);

    await waitFor(() => expect(getByTestId("home-news-list")).toBeInTheDocument());
    expect(getAllByTestId("home-news-item")).toHaveLength(2);

    const link = getAllByTestId("home-news-item")[0]!.querySelector("a");
    expect(link?.textContent).toBe("Fed minutes released");
    expect(link).toHaveAttribute("href", "https://www.sec.gov/fed-minutes");
    // External links must open safely in a new tab.
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
    // B054 F-news — the source code is Sinicized, never a raw English code.
    const items = getAllByTestId("home-news-item");
    expect(items[0]!.textContent).toContain("SEC 公告");
    expect(items[0]!.textContent).not.toContain("sec_edgar");
    expect(items[1]!.textContent).toContain("雅虎财经");
    expect(items[1]!.textContent).not.toContain("yahoo_rss");
  });

  it("renders deterministic topic chips", async () => {
    vi.stubGlobal("fetch", buildFetch({ items: ITEMS }));
    const { getAllByTestId } = renderWithIntl(<HomeNewsPanel />);
    await waitFor(() => expect(getAllByTestId("home-news-topic-chip").length).toBeGreaterThan(0));
    const chips = getAllByTestId("home-news-topic-chip").map((n) => n.textContent);
    expect(chips).toContain("重大事件");
    expect(chips).toContain("财报");
  });

  it("shows an empty state when there is no news", async () => {
    vi.stubGlobal("fetch", buildFetch({ items: [] }));
    const { getByTestId } = renderWithIntl(<HomeNewsPanel />);
    await waitFor(() => expect(getByTestId("home-news-empty")).toBeInTheDocument());
  });

  it("shows an error state when the fetch fails", async () => {
    vi.stubGlobal("fetch", buildFetch(null, false));
    const { getByTestId } = renderWithIntl(<HomeNewsPanel />);
    await waitFor(() => expect(getByTestId("home-news-error")).toBeInTheDocument());
  });

  it("has no execution / order button (research-only surface)", async () => {
    vi.stubGlobal("fetch", buildFetch({ items: ITEMS }));
    const { container, getByTestId } = renderWithIntl(<HomeNewsPanel />);
    await waitFor(() => expect(getByTestId("home-news-list")).toBeInTheDocument());
    expect(container.querySelector("button")).toBeNull();
  });

  it("renders the English section title", async () => {
    vi.stubGlobal("fetch", buildFetch({ items: ITEMS }));
    const { getByText } = renderWithIntl(<HomeNewsPanel />, { locale: "en" });
    await waitFor(() => expect(getByText("Today's market news")).toBeInTheDocument());
  });

  it("renders the zh-CN section title", async () => {
    vi.stubGlobal("fetch", buildFetch({ items: ITEMS }));
    const { getByText } = renderWithIntl(<HomeNewsPanel />, { locale: "zh-CN" });
    await waitFor(() => expect(getByText("今日市场新闻")).toBeInTheDocument());
  });
});
