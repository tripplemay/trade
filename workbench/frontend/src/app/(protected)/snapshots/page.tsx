/**
 * F003 ships this as a stub so the SideNav link resolves; F011
 * (Snapshots) replaces the body with the DataTable + SSE refresh modal.
 */
export default function SnapshotsPage() {
  return (
    <section data-testid="page-snapshots" className="space-y-4">
      <h1 className="text-2xl font-semibold tracking-tight text-foreground">Snapshots</h1>
      <p className="text-sm text-muted-foreground">
        Snapshot inventory + refresh streaming land in B022 F011.
      </p>
    </section>
  );
}
