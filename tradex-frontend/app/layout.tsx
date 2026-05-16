import type { Metadata } from "next";
import { Inter } from "next/font/google";
import Link from "next/link";
import "./globals.css";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "TradeX OIE v17.19",
  description: "SMC Premium/Discount Confluence Engine — Opportunity Intelligence Dashboard",
};

function NavLink({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <Link
      href={href}
      className="px-3 py-2 rounded-md text-sm font-medium text-zinc-400 hover:text-white hover:bg-zinc-800 transition-colors"
    >
      {children}
    </Link>
  );
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className={`${inter.className} bg-zinc-950 text-zinc-100 min-h-screen`}>
        <header className="sticky top-0 z-40 w-full border-b border-zinc-800 bg-zinc-950/80 backdrop-blur-md">
          <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 md:px-6">
            <Link href="/" className="flex items-center gap-2">
              <div className="flex h-9 w-9 items-center justify-center rounded-md bg-emerald-600 text-white shadow-sm">
                <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={2}>
                  <polyline points="22 7 13.5 15.5 8.5 10.5 2 17" />
                  <polyline points="16 7 22 7 22 13" />
                </svg>
              </div>
              <span className="font-semibold text-lg">
                TradeX OIE <span className="text-emerald-400 font-mono text-sm ml-1">v17.19</span>
              </span>
            </Link>
            <nav className="hidden md:flex items-center gap-1">
              <NavLink href="/">Dashboard</NavLink>
              <NavLink href="/opportunities">Opportunities</NavLink>
              <NavLink href="/trades">Trade Log</NavLink>
              <NavLink href="/settings">Settings</NavLink>
            </nav>
            <div className="flex items-center gap-2">
              <span className="flex items-center gap-1.5 text-xs text-emerald-400 bg-emerald-950 px-2 py-1 rounded-full border border-emerald-800">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
                Online
              </span>
            </div>
          </div>
        </header>
        <main className="flex-1 mx-auto max-w-7xl px-4 md:px-6 py-6">
          {children}
        </main>
        <footer className="border-t border-zinc-800 mt-16">
          <div className="mx-auto max-w-7xl flex items-center justify-between px-4 py-6 text-sm text-zinc-500">
            <span>TradeX OIE <span className="font-mono text-zinc-300">v17.19</span></span>
            <div className="flex items-center gap-4">
              <Link href="/" className="hover:text-zinc-300 transition-colors">Dashboard</Link>
              <Link href="/opportunities" className="hover:text-zinc-300 transition-colors">Opportunities</Link>
              <Link href="/settings" className="hover:text-zinc-300 transition-colors">Settings</Link>
            </div>
          </div>
        </footer>
      </body>
    </html>
  );
}
