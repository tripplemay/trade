// @vitest-environment happy-dom
/**
 * B067 F003 — CnAttackOosDisclosure renders the cn_attack out-of-sample honesty
 * disclosure (spec §0): a prominent, red, locale-aware banner shown ONLY when the
 * recommendations API returns a `research_caveat` (present exclusively for the
 * research-state cn_attack momentum modes). Funded / other modes return null and
 * the banner must not render. Advisory-only: no order / execute affordance (the
 * no-execution scan in tests/safety/no-execution-buttons.spec.ts covers the source).
 */
import { afterEach, describe, expect, it } from "vitest";
import { cleanup } from "@testing-library/react";

import { renderWithIntl } from "../../test-utils/intl";

import type { components } from "@/types/api";

import { CnAttackOosDisclosure } from "@/components/recommendations/CnAttackOosDisclosure";

type ResearchCaveat = components["schemas"]["ResearchCaveat"];

const CAVEAT: ResearchCaveat = {
  validated: false,
  oos_result: "negative",
  oos_cagr_range: "-9% ~ -11%",
  headline_zh: "未经样本外验证：B066 样本外（2025H2 起）CAGR −9%~−11%（动量逆转期会亏）。",
  headline_en:
    "Unvalidated out-of-sample: B066 found the OOS window a momentum reversal — this strategy lost money out of sample.",
  detail_zh: "advisory-only：系统只给建议，不自动下单、不预测收益；按它交易风险自负。",
  detail_en:
    "Advisory-only: the system only suggests; it does not auto-trade or predict returns. Trading on it is at your own risk.",
  backtest_ref: "docs/specs/B066-ashare-attack-momentum-quality-spec.md",
};

afterEach(() => {
  cleanup();
});

describe("CnAttackOosDisclosure", () => {
  it("renders nothing when no research_caveat is present (funded / other modes)", () => {
    const { queryByTestId } = renderWithIntl(<CnAttackOosDisclosure researchCaveat={null} />);
    expect(queryByTestId("cn-attack-oos-disclosure")).toBeNull();
  });

  it("renders nothing when research_caveat is undefined (loading / error state)", () => {
    const { queryByTestId } = renderWithIntl(<CnAttackOosDisclosure researchCaveat={undefined} />);
    expect(queryByTestId("cn-attack-oos-disclosure")).toBeNull();
  });

  it("renders nothing when the caveat has no headline for the active locale", () => {
    const { queryByTestId } = renderWithIntl(
      <CnAttackOosDisclosure researchCaveat={{ ...CAVEAT, headline_en: null }} />,
      { locale: "en" },
    );
    expect(queryByTestId("cn-attack-oos-disclosure")).toBeNull();
  });

  it("renders the English headline + detail when locale=en", () => {
    const { getByTestId } = renderWithIntl(<CnAttackOosDisclosure researchCaveat={CAVEAT} />, {
      locale: "en",
    });
    expect(getByTestId("cn-attack-oos-disclosure")).toBeTruthy();
    expect(getByTestId("cn-attack-oos-headline").textContent).toBe(CAVEAT.headline_en);
    expect(getByTestId("cn-attack-oos-detail").textContent).toBe(CAVEAT.detail_en);
  });

  it("renders the Chinese headline + detail when locale=zh-CN", () => {
    const { getByTestId } = renderWithIntl(<CnAttackOosDisclosure researchCaveat={CAVEAT} />, {
      locale: "zh-CN",
    });
    expect(getByTestId("cn-attack-oos-headline").textContent).toBe(CAVEAT.headline_zh);
    expect(getByTestId("cn-attack-oos-detail").textContent).toBe(CAVEAT.detail_zh);
  });

  it("surfaces the OOS CAGR range, backtest reference, and oos_result marker", () => {
    const { getByTestId } = renderWithIntl(<CnAttackOosDisclosure researchCaveat={CAVEAT} />, {
      locale: "en",
    });
    expect(getByTestId("cn-attack-oos-cagr").textContent).toContain("-9% ~ -11%");
    expect(getByTestId("cn-attack-oos-disclosure").getAttribute("data-oos-result")).toBe(
      "negative",
    );
    // The B066 backtest record path must be reachable on the surface.
    expect(getByTestId("cn-attack-oos-disclosure").textContent).toContain(
      "docs/specs/B066-ashare-attack-momentum-quality-spec.md",
    );
  });
});
