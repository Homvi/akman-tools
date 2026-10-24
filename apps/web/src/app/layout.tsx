import type { ReactNode } from "react";
import { IBM_Plex_Mono, IBM_Plex_Sans } from "next/font/google";
import "./globals.css";

const plexSans = IBM_Plex_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-plex-sans",
});

const plexMono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-plex-mono",
});

/** Root document shell — must own html/body (Next.js 15 hydration). */
export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="hu" suppressHydrationWarning>
      <body className={`${plexSans.variable} ${plexMono.variable} antialiased`} suppressHydrationWarning>
        {children}
      </body>
    </html>
  );
}
