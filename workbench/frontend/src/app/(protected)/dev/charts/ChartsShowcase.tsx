"use client";

import { useRef, useState } from "react";

import {
  AllocationBar,
  AllocationPie,
  type ChartHandle,
  DrawdownChart,
  EquityCurveChart,
  type EquityCurveRange,
  SweepHeatmap,
} from "@/components/chart";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

/**
 * Sample data generators kept inline; this page exists only so designers
 * + Codex can eyeball the wrappers with realistic shapes. F008-F011
 * replace the generators with real backend data.
 */
function seedEquityCurve(seed: number, points = 60): Array<{ time: string; value: number }> {
  let value = 100;
  const out: Array<{ time: string; value: number }> = [];
  for (let i = 0; i < points; i++) {
    const date = new Date(2024, 0, i + 1).toISOString().slice(0, 10);
    value += Math.sin(i / 6 + seed) * 0.6 + seed * 0.05;
    out.push({ time: date, value: Number(value.toFixed(2)) });
  }
  return out;
}

function seedDrawdown(points = 60): Array<{ time: string; value: number }> {
  const out: Array<{ time: string; value: number }> = [];
  let dd = 0;
  for (let i = 0; i < points; i++) {
    const date = new Date(2024, 0, i + 1).toISOString().slice(0, 10);
    dd = Math.min(0, dd + (Math.random() - 0.55) * 0.005);
    out.push({ time: date, value: Number(dd.toFixed(4)) });
  }
  return out;
}

const HEATMAP_X = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug"];
const HEATMAP_Y = ["B013", "B014", "B015", "B016"];
const HEATMAP_DATA = HEATMAP_X.flatMap((_, xIndex) =>
  HEATMAP_Y.map((_y, yIndex) => ({
    xIndex,
    yIndex,
    value: Number((Math.sin(xIndex / 2 + yIndex) * 0.3).toFixed(3)),
  })),
);

const PIE_DATA = [
  { name: "Momentum", value: 0.4 },
  { name: "Value", value: 0.25 },
  { name: "Carry", value: 0.2 },
  { name: "Cash", value: 0.15 },
];

const BAR_DATA = [
  { name: "Buy AAA", value: 0.08 },
  { name: "Buy BBB", value: 0.05 },
  { name: "Sell CCC", value: -0.03 },
  { name: "Sell DDD", value: -0.06 },
];

function downloadBlob(blob: Blob | null | undefined, filename: string) {
  if (!blob) return;
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

export default function ChartsShowcase() {
  const [equitySeries] = useState(() => [
    { id: "master", name: "Master", color: "#00c853", data: seedEquityCurve(0) },
    { id: "spy", name: "SPY", color: "#888888", data: seedEquityCurve(1.4) },
  ]);
  const [drawdownData] = useState(seedDrawdown);
  const [syncedRange, setSyncedRange] = useState<EquityCurveRange | null>(null);

  const equityRef = useRef<ChartHandle>(null);
  const drawdownRef = useRef<ChartHandle>(null);
  const heatmapRef = useRef<ChartHandle>(null);
  const pieRef = useRef<ChartHandle>(null);
  const barRef = useRef<ChartHandle>(null);

  return (
    <section data-testid="dev-charts" className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">Chart wrappers</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Dev-only showcase for B022 F004 wrappers. Visible when
          <code className="mx-1 rounded bg-muted px-1 py-0.5 text-xs">NEXT_PUBLIC_DEV_ROUTES=true</code>
          at build; otherwise this route returns 404 and is intentionally absent from the SideNav.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>EquityCurveChart + DrawdownChart (shared time axis)</CardTitle>
          <CardDescription>
            Pan / zoom either chart — the other follows. Range pushed via the
            controlled <code>visibleRange</code> prop on the partner.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <EquityCurveChart
            ref={equityRef}
            series={equitySeries}
            visibleRange={syncedRange}
            onVisibleRangeChange={setSyncedRange}
          />
          <DrawdownChart
            ref={drawdownRef}
            data={drawdownData}
            visibleRange={syncedRange}
            onVisibleRangeChange={setSyncedRange}
          />
          <div className="flex gap-2">
            <Button
              variant="outline"
              onClick={async () => downloadBlob(await equityRef.current?.exportPng(), "equity.png")}
            >
              Export equity PNG
            </Button>
            <Button
              variant="outline"
              onClick={async () =>
                downloadBlob(await drawdownRef.current?.exportPng(), "drawdown.png")
              }
            >
              Export drawdown PNG
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>SweepHeatmap</CardTitle>
          <CardDescription>
            Strategy × month turnover heatmap shape (F007/F009 will feed real sweep data).
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <SweepHeatmap
            ref={heatmapRef}
            xCategories={HEATMAP_X}
            yCategories={HEATMAP_Y}
            data={HEATMAP_DATA}
          />
          <Button
            variant="outline"
            onClick={async () =>
              downloadBlob(await heatmapRef.current?.exportPng(), "heatmap.png")
            }
          >
            Export heatmap PNG
          </Button>
        </CardContent>
      </Card>

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>AllocationPie</CardTitle>
            <CardDescription>Target sleeve weights.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <AllocationPie ref={pieRef} data={PIE_DATA} />
            <Button
              variant="outline"
              onClick={async () =>
                downloadBlob(await pieRef.current?.exportPng(), "allocation-pie.png")
              }
            >
              Export pie PNG
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>AllocationBar</CardTitle>
            <CardDescription>Recommended buy / sell deltas (horizontal).</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <AllocationBar ref={barRef} data={BAR_DATA} />
            <Button
              variant="outline"
              onClick={async () =>
                downloadBlob(await barRef.current?.exportPng(), "allocation-bar.png")
              }
            >
              Export bar PNG
            </Button>
          </CardContent>
        </Card>
      </div>
    </section>
  );
}
