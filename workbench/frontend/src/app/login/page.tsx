import Footer from "@/components/shell/Footer";
import { signIn } from "@/lib/auth";

const RESTRICTED_NOTICE = "This workbench is restricted to a single authorized user.";

type SearchParams = {
  error?: string;
  callbackUrl?: string;
};

async function signInWithGoogle(formData: FormData): Promise<void> {
  "use server";
  const callbackUrl = formData.get("callbackUrl");
  await signIn("google", {
    redirectTo: typeof callbackUrl === "string" && callbackUrl ? callbackUrl : "/",
  });
}

// Next.js 15 made route-level `searchParams` a Promise on server components.
// We must `await` it before destructuring; reading the prop synchronously
// trips the dev-time warning and breaks in a future Next major.
export default async function LoginPage({
  searchParams,
}: {
  searchParams?: Promise<SearchParams>;
}) {
  const resolved = (await searchParams) ?? {};
  const error = resolved.error;
  const callbackUrl = resolved.callbackUrl ?? "/";
  return (
    <>
      <main
        data-testid="login-page"
        className="flex flex-1 flex-col items-center justify-center px-6 py-16"
      >
        <section className="w-full max-w-md rounded-lg border border-neutral-800 bg-neutral-900 p-8 shadow-lg">
          <h1 className="text-2xl font-semibold text-neutral-100">Workbench sign-in</h1>
          <p className="mt-3 text-sm text-neutral-400">
            Google sign-in is the only entry point. Account creation is intentionally absent — the
            workbench is single-user by design.
          </p>
          {error ? (
            <p
              data-testid="login-restricted-notice"
              role="alert"
              className="mt-4 rounded border border-amber-700 bg-amber-950 px-3 py-2 text-sm text-amber-200"
            >
              {RESTRICTED_NOTICE}
            </p>
          ) : null}
          <form action={signInWithGoogle} className="mt-6">
            <input type="hidden" name="callbackUrl" value={callbackUrl} />
            <button
              type="submit"
              data-testid="login-google-button"
              className="w-full rounded-md border border-neutral-700 bg-neutral-100 px-4 py-2 text-sm font-medium text-neutral-900 transition hover:bg-white"
            >
              Sign in with Google
            </button>
          </form>
        </section>
      </main>
      <Footer />
    </>
  );
}
