"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { Menu, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { TopProgress } from "@/components/progress-bar";

const NAV = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/devices", label: "Device list" },
  { href: "/stopped", label: "Stopped" },
  { href: "/stutzen", label: "Stützen / Bahn" },
  { href: "/areas", label: "Areas" },
  { href: "/workforce", label: "Workforce" },
  { href: "/routes", label: "Routes" },
  { href: "/progress", label: "Progress" },
  { href: "/errors", label: "Hibák" },
  { href: "/calculator", label: "Calculator" },
  { href: "/upload", label: "Upload" },
  { href: "/guide", label: "Guide" },
];

export function AppShell({
  children,
  status,
  loading,
  onLogout,
}: {
  children: React.ReactNode;
  status?: { progressAsOf?: string | null; loaded?: boolean; conflicts?: number };
  loading?: boolean;
  onLogout?: () => void;
}) {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  const NavLinks = (
    <nav className="flex flex-col gap-1">
      {NAV.map((item) => (
        <Link
          key={item.href}
          href={item.href}
          onClick={() => setOpen(false)}
          className={cn(
            "rounded-md px-3 py-2 text-sm transition-colors",
            pathname === item.href
              ? "bg-[#2DD4BF] font-medium text-[#042F2E]"
              : item.href === "/upload"
                ? "text-[#52525B] hover:bg-[#18181B] hover:text-[#A1A1AA]"
                : "text-[#A1A1AA] hover:bg-[#18181B] hover:text-[#FAFAFA]"
          )}
        >
          {item.label}
        </Link>
      ))}
    </nav>
  );

  return (
    <div className="min-h-screen bg-[#09090B] text-[#FAFAFA]">
      <TopProgress show={!!loading} />
      <div className="mx-auto flex min-h-screen max-w-[1400px]">
        <aside className="hidden w-56 shrink-0 border-r border-[#27272A] bg-[#0C0C0E] p-4 md:block">
          <div className="mb-6">
            <div className="text-lg font-semibold tracking-tight text-[#FAFAFA]">Cable installation</div>
            <p className="mt-1 text-xs text-[#71717A]">
              {status?.loaded && status.progressAsOf ? (
                <span className="text-[#2DD4BF]">{status.progressAsOf}</span>
              ) : status?.loaded ? (
                <span className="text-[#A1A1AA]">—</span>
              ) : (
                "—"
              )}
              {status?.conflicts ? (
                <>
                  {" "}
                  · <span className="text-[#F97316]">{status.conflicts} conflicts</span>
                </>
              ) : null}
            </p>
          </div>
          {NavLinks}
          {onLogout && (
            <Button variant="outline" className="mt-6 w-full" onClick={onLogout}>
              Log out
            </Button>
          )}
        </aside>

        <div className="flex min-w-0 flex-1 flex-col">
          <header className="flex items-center justify-between border-b border-[#27272A] bg-[#0C0C0E] px-4 py-3 md:hidden">
            <div>
              <div className="font-semibold">Cable installation</div>
              <div className="text-xs text-[#71717A]">
                {status?.loaded && status.progressAsOf ? status.progressAsOf : "—"}
              </div>
            </div>
            <button type="button" onClick={() => setOpen((v) => !v)} aria-label="Menu" className="text-[#FAFAFA]">
              {open ? <X size={20} /> : <Menu size={20} />}
            </button>
          </header>
          {open && <div className="border-b border-[#27272A] bg-[#0C0C0E] p-4 md:hidden">{NavLinks}</div>}
          <main className="flex-1 p-4 md:p-6">{children}</main>
        </div>
      </div>
    </div>
  );
}
