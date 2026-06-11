/**
 * B054 F-news — newsSourceLabel presentation-layer mapping.
 */
import { describe, expect, it } from "vitest";

import { newsSourceLabel } from "@/lib/sleeve-label";

describe("newsSourceLabel", () => {
  it("Sinicizes the known news source codes", () => {
    expect(newsSourceLabel("sec_edgar")).toBe("SEC 公告");
    expect(newsSourceLabel("yahoo_rss")).toBe("雅虎财经");
  });

  it("passes an unknown source through unchanged (raw id beats a crash)", () => {
    expect(newsSourceLabel("some_future_source")).toBe("some_future_source");
  });
});
