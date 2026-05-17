/**
 * F003 ships this as a stub so the SideNav link resolves; F008
 * (Backtest viewer) replaces the body with the ResizablePanel split
 * (selector pane + metrics/equity/drawdown/trades pane).
 */
export default function BacktestPage() {
  return (
    <section data-testid="page-backtest" className="space-y-4">
      <h1 className="text-2xl font-semibold tracking-tight text-foreground">Backtest</h1>
      <p className="text-sm text-muted-foreground">
        Backtest runner + result panels land in B022 F008.
      </p>
    </section>
  );
}
