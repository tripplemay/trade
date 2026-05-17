"use client";

import { ThemeProvider as NextThemesProvider, type ThemeProviderProps } from "next-themes";

/**
 * Workbench is dark-first; the `<html class="dark">` hardcode in
 * `app/layout.tsx` produces the SSR pass and this provider lets
 * client components toggle/observe the theme without flicker. Phase 1
 * does not ship a light theme — `enableSystem={false}` + `forcedTheme`
 * isn't used yet so a future light-mode rollout drops in with no
 * provider change.
 */
export function ThemeProvider({ children, ...props }: ThemeProviderProps) {
  return (
    <NextThemesProvider
      attribute="class"
      defaultTheme="dark"
      enableSystem={false}
      disableTransitionOnChange
      {...props}
    >
      {children}
    </NextThemesProvider>
  );
}
