"use client";

import { useLocale, useTranslations } from "next-intl";
import { usePathname, useRouter, routing, type AppLocale } from "@/i18n/routing";
import { cn } from "@/lib/utils";

const LOCALES = routing.locales;

export function LanguageSwitcher({ className }: { className?: string }) {
  const t = useTranslations("common");
  const locale = useLocale() as AppLocale;
  const pathname = usePathname();
  const router = useRouter();

  return (
    <div className={cn("flex items-center gap-1", className)} role="group" aria-label={t("language")}>
      {LOCALES.map((code) => (
        <button
          key={code}
          type="button"
          className={cn(
            "rounded px-1.5 py-0.5 text-xs font-medium uppercase tracking-wide transition-colors",
            code === locale
              ? "bg-[#2DD4BF]/20 text-[#2DD4BF]"
              : "text-[#71717A] hover:bg-[#18181B] hover:text-[#FAFAFA]"
          )}
          onClick={() => {
            if (code === locale) return;
            router.replace(pathname, { locale: code });
          }}
        >
          {code}
        </button>
      ))}
    </div>
  );
}
