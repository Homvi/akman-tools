"use client";

import { useTranslations } from "next-intl";
export default function GuidePage() {
  const t = useTranslations("guide");
  return (
    <div className="prose prose-sm max-w-2xl text-[#111827]">
      <h1 className="text-2xl font-semibold">{t("title")}</h1>
      <p className="text-[#6B7280]">{t("intro")}</p>
      <ul className="mt-4 list-disc space-y-1 pl-5 text-sm text-[#6B7280]">
        <li>{t("deploy")}</li>
        <li>{t("design")}</li>
        <li>{t("auth")}</li>
      </ul>
    </div>
  );
}
