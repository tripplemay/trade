import { notFound } from "next/navigation";

import ChartsShowcase from "./ChartsShowcase";

/**
 * /dev/charts is gated by NEXT_PUBLIC_DEV_ROUTES so a production build
 * without the flag returns 404 (and is therefore invisible from the
 * SideNav by intent — the page deliberately is not registered in
 * `components/shell/nav-items.ts`). Dev / preview builds set
 * `NEXT_PUBLIC_DEV_ROUTES=true` to surface the chart showcase for design
 * review and snapshot work.
 *
 * The env check runs at request time on the server component; the
 * actual chart wrappers ship as a client-only subtree so they don't
 * pull lightweight-charts / echarts into the server bundle.
 */
export default function DevChartsPage() {
  if (process.env.NEXT_PUBLIC_DEV_ROUTES !== "true") {
    notFound();
  }
  return <ChartsShowcase />;
}
