/**
 * F003 ships this as a stub so the SideNav link resolves; F012
 * (Backlog CRUD) replaces the body with the DataTable + Add/Edit/Delete
 * modals + git-auto-commit pipeline.
 */
export default function BacklogPage() {
  return (
    <section data-testid="page-backlog" className="space-y-4">
      <h1 className="text-2xl font-semibold tracking-tight text-foreground">Backlog</h1>
      <p className="text-sm text-muted-foreground">
        Backlog CRUD + git auto-commit land in B022 F012.
      </p>
    </section>
  );
}
