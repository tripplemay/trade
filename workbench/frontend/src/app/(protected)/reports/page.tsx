/**
 * F003 ships this as a stub so the SideNav link resolves; F009
 * (Reports viewer) replaces the body with the markdown rendering +
 * tables-as-AG-Grid surface.
 */
export default function ReportsPage() {
  return (
    <section data-testid="page-reports" className="space-y-4">
      <h1 className="text-2xl font-semibold tracking-tight text-foreground">Reports</h1>
      <p className="text-sm text-muted-foreground">
        Test-report browser + markdown rendering land in B022 F009.
      </p>
    </section>
  );
}
