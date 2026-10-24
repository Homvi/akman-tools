"use client";

import { useEffect } from "react";

/** Keep <html lang> in sync when the locale segment changes. */
export function HtmlLang({ locale }: { locale: string }) {
  useEffect(() => {
    document.documentElement.lang = locale;
  }, [locale]);
  return null;
}
