import { redirect } from "next/navigation";

import { SessionProvider } from "@/components/shell/SessionProvider";
import { ThemeProvider } from "@/components/shell/ThemeProvider";
import Footer from "@/components/shell/Footer";
import SideNav from "@/components/shell/SideNav";
import TopBar from "@/components/shell/TopBar";
import { auth } from "@/lib/auth";

/**
 * Auth gate for every authenticated workbench route.
 *
 * Middleware already redirects anonymous traffic to `/login`; this layout
 * is the second fence so a misconfigured matcher cannot accidentally
 * expose anything inside the `(protected)` route group.
 *
 * Once auth passes, the layout owns the workbench shell: ThemeProvider
 * (next-themes, dark-first per F003), SessionProvider (so client
 * components like TopBar can read the user via useSession without
 * prop-drilling), then the TopBar / SideNav / main / Footer grid. Footer
 * used to live in `(protected)/page.tsx`; F003 hoists it here so every
 * page under the group renders it automatically.
 */
export default async function ProtectedLayout({ children }: { children: React.ReactNode }) {
  const session = await auth();
  if (!session?.user) {
    redirect("/login");
  }
  return (
    <SessionProvider session={session}>
      <ThemeProvider>
        <div className="flex min-h-screen flex-col">
          <TopBar />
          <div className="flex flex-1">
            <SideNav />
            <main
              data-testid="workbench-main"
              className="flex-1 overflow-x-hidden px-4 py-6 md:px-6"
            >
              {children}
            </main>
          </div>
          <Footer />
        </div>
      </ThemeProvider>
    </SessionProvider>
  );
}
