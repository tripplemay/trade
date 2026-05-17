/**
 * F003 ships this as a stub so the SideNav link resolves; F010
 * (Recommendations) replaces the body with the target-portfolio pies,
 * gate panel, wash-sale flags and Export Markdown Ticket button.
 *
 * Hard reminder for F010: research-only; this page must never place
 * an order. Exported ticket is a manual review checklist.
 */
export default function RecommendationsPage() {
  return (
    <section data-testid="page-recommendations" className="space-y-4">
      <h1 className="text-2xl font-semibold tracking-tight text-foreground">Recommendations</h1>
      <p className="text-sm text-muted-foreground">
        Target portfolio + gate checks + ticket export land in B022 F010.
      </p>
    </section>
  );
}
