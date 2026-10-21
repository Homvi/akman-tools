"use client";

import { FormEvent, useState } from "react";
import { useTranslations } from "next-intl";
import { useRouter } from "@/i18n/routing";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { TopProgress } from "@/components/progress-bar";
import { LanguageSwitcher } from "@/components/language-switcher";

export default function LoginPage() {
  const t = useTranslations("login");
  const router = useRouter();
  const [email, setEmail] = useState("admin@example.com");
  const [password, setPassword] = useState("changeme");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      await api.post("/auth/login", { email, password });
      router.replace("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : t("failed"));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-[#09090B] px-4">
      <TopProgress show={loading} />
      <div className="w-full max-w-md rounded-md border border-[#27272A] bg-[#0C0C0E] p-8">
        <div className="mb-4 flex justify-end">
          <LanguageSwitcher />
        </div>
        <h1 className="text-3xl font-semibold tracking-tight text-[#FAFAFA]">{t("title")}</h1>
        <p className="mt-2 text-sm text-[#71717A]">
          {t("subtitle")}
        </p>
        <form className="mt-8 space-y-4" onSubmit={onSubmit}>
          <label className="block text-xs text-[#71717A]">
            {t("email")}
            <Input className="mt-1" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          </label>
          <label className="block text-xs text-[#71717A]">
            {t("password")}
            <Input
              className="mt-1"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </label>
          {error && <p className="text-sm text-[#F87171]">{error}</p>}
          <Button className="w-full" type="submit" disabled={loading}>
            {t("submit")}
          </Button>
        </form>
      </div>
    </div>
  );
}
