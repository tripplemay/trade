/**
 * F003 ships this as a stub so the SideNav link resolves; F007
 * (Strategies page vertical slice) replaces the body with the real
 * DataTable + detail panel + provenance links.
 */
export default function StrategiesPage() {
  return (
    <section data-testid="page-strategies" className="space-y-4">
      <h1 className="text-2xl font-semibold tracking-tight text-foreground">Strategies</h1>
      <p className="text-sm text-muted-foreground">
        Strategy list and per-strategy detail land in B022 F007.
      </p>
    </section>
  );
}
