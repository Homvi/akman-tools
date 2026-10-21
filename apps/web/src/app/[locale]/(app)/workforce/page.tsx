"use client";

import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { TopProgress } from "@/components/progress-bar";

export default function WorkforcePage() {
  const t = useTranslations("workforce");
  const [series, setSeries] = useState<{
    headcount: Record<string, unknown>[];
    growth: Record<string, unknown>;
    m_per_hour: Record<string, unknown>[];
  } | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function refresh() {
    setLoading(true);
    setError("");
    try {
      setSeries(await api.get("/workforce/series"));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  async function onUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    const form = new FormData();
    form.append("file", file);
    setLoading(true);
    try {
      await api.post(`/workforce/upload?year=${new Date().getFullYear()}`, form);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("uploadFailed"));
      setLoading(false);
    }
  }

  return (
    <div>
      <TopProgress show={loading} />
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">{t("title")}</h1>
          <p className="text-sm text-[#6B7280]">{t("subtitle")}</p>
        </div>
        <label className="inline-flex h-9 cursor-pointer items-center rounded-md border border-[#27272A] bg-transparent px-3 text-sm text-[#FAFAFA] hover:bg-[#18181B]">
          {t("upload")}
          <input type="file" accept=".xlsx" className="hidden" onChange={onUpload} />
        </label>
      </div>
      {error && <p className="mb-3 text-sm text-[#B91C1C]">{error}</p>}
      {series?.growth && (
        <div className="mb-4 flex gap-2">
          {Object.entries(series.growth).map(([k, v]) => (
            <Badge key={k}>
              {k}: {String(v)}
            </Badge>
          ))}
        </div>
      )}
      <div className="mb-6 h-72 rounded-md border border-[#E5E7EB] bg-white p-3">
        <p className="mb-2 text-xs uppercase tracking-wide text-[#6B7280]">{t("dailyHeadcount")}</p>
        <ResponsiveContainer width="100%" height="90%">
          <BarChart data={series?.headcount || []}>
            <CartesianGrid stroke="#E5E7EB" vertical={false} />
            <XAxis dataKey="Date" tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} />
            <Tooltip />
            <Bar dataKey="Total" fill="#1B4F72" radius={[2, 2, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <div className="h-72 rounded-md border border-[#E5E7EB] bg-white p-3">
        <p className="mb-2 text-xs uppercase tracking-wide text-[#6B7280]">{t("mPerHour")}</p>
        <ResponsiveContainer width="100%" height="90%">
          <BarChart data={series?.m_per_hour || []}>
            <CartesianGrid stroke="#E5E7EB" vertical={false} />
            <XAxis dataKey="Date" tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} />
            <Tooltip />
            <Bar dataKey="M_per_hour" fill="#6B7280" radius={[2, 2, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <Button className="mt-4" variant="outline" onClick={refresh}>
        {t("refresh")}
      </Button>
    </div>
  );
}
