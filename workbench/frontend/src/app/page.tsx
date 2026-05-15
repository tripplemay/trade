import Footer from "@/components/shell/Footer";

export default function HomePage() {
  return (
    <>
      <main
        data-testid="workbench-home"
        className="flex flex-1 flex-col items-center justify-center px-6 py-16"
      >
        <section className="w-full max-w-xl rounded-lg border border-neutral-800 bg-neutral-900 p-8 shadow-lg">
          <h1 className="text-2xl font-semibold text-neutral-100">Workbench scaffold OK</h1>
          <p className="mt-3 text-sm text-neutral-400">
            B020 development infrastructure is online. Backend, frontend, lint, type-check and test
            tooling are wired. Strategy pages and broker integrations are intentionally absent —
            those land in later batches (B022 / B023).
          </p>
        </section>
      </main>
      <Footer />
    </>
  );
}
