import { DISCLAIMER_TEXT } from "@/lib/disclaimer";

export default function Footer() {
  return (
    <footer
      data-testid="workbench-footer"
      className="border-t border-neutral-800 bg-neutral-950 px-6 py-4 text-xs text-neutral-400"
    >
      <p data-testid="workbench-disclaimer">{DISCLAIMER_TEXT}</p>
    </footer>
  );
}
