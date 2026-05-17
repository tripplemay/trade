import { Inter, JetBrains_Mono } from "next/font/google";

/**
 * UI typography for the workbench shell. Both fonts expose CSS variables
 * (`--font-inter`, `--font-jetbrains-mono`) that Tailwind's `font-sans`
 * and `font-mono` utilities resolve via tailwind.config.ts. The `.numeric`
 * utility (src/styles/globals.css) reads the same variables so numeric
 * cells stay column-aligned without re-importing the font per component.
 */
export const interSans = Inter({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-inter",
});

export const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-jetbrains-mono",
});
