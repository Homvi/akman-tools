"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { Menu, X } from "lucide-react";
import { Link, usePathname } from "@/i18n/routing";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { TopProgress } from "@/components/progress-bar";
import { LanguageSwitcher } from "@/components/language-switcher";

const NAV_KEYS = [
  { href: "/dashboard", key: "dashboard" as const },
  { href: "/devices", key: "devices" as const },
  { href: "/stopped", key: "stopped" as const },
  { href: "/near-complete", key: "nearComplete" as const },
  { href: "/stutzen", key: "stutzen" as const },
  { href: "/areas", key: "areas" as const },
  { href: "/workforce", key: "workforce" as const },
  { href: "/teams", key: "teams" as const },
  { href: "/routes", key: "routes" as const },
  { href: "/progress", key: "progress" as const },
  { href: "/errors", key: "errors" as const },
  { href: "/calculator", key: "calculator" as const },
  { href: "/e-stichmass", key: "stichmass" as const },
  { href: "/upload", key: "upload" as const },
  { href: "/guide", key: "guide" as const },
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
  const t = useTranslations("nav");
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  const NavLinks = (
    <nav className="flex flex-col gap-1">
      {NAV_KEYS.map((item) => (
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
          {t(item.key)}
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
            <div className="text-lg font-semibold tracking-tight text-[#FAFAFA]">{t("brand")}</div>
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
                  · <span className="text-[#F97316]">{t("conflicts", { count: status.conflicts })}</span>
                </>
              ) : null}
            </p>
            <LanguageSwitcher className="mt-3" />
          </div>
          {NavLinks}
          {onLogout && (
            <Button variant="outline" className="mt-6 w-full" onClick={onLogout}>
              {t("logout")}
            </Button>
          )}
        </aside>

        <div className="flex min-w-0 flex-1 flex-col">
          <header className="flex items-center justify-between border-b border-[#27272A] bg-[#0C0C0E] px-4 py-3 md:hidden">
            <div>
              <div className="font-semibold">{t("brand")}</div>
              <div className="text-xs text-[#71717A]">
                {status?.loaded && status.progressAsOf ? status.progressAsOf : "—"}
              </div>
            </div>
            <div className="flex items-center gap-3">
              <LanguageSwitcher />
              <button type="button" onClick={() => setOpen((v) => !v)} aria-label={t("menu")} className="text-[#FAFAFA]">
                {open ? <X size={20} /> : <Menu size={20} />}
              </button>
            </div>
          </header>
          {open && <div className="border-b border-[#27272A] bg-[#0C0C0E] p-4 md:hidden">{NavLinks}</div>}
          <main className="flex-1 p-4 md:p-6">{children}</main>
        </div>
      </div>
    </div>
  );
}
