"use client";

import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { api, qs } from "@/lib/api";
import { DataTable } from "@/components/data-table";
import { TopProgress } from "@/components/progress-bar";

export default function RoutesPage() {
  const t = useTranslations("routes");
  const [groups, setGroups] = useState<Record<string, unknown>[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    setLoading(true);
    api
      .get<{ groups: Record<string, unknown>[] }>(`/routes/groups${qs({ similarity: 0.9, min_size: 2 })}`)
      .then((d) => setGroups(d.groups || []))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <TopProgress show={loading} />
      <h1 className="mb-1 text-2xl font-semibold">{t("title")}</h1>
      <p className="mb-4 text-sm text-[#6B7280]">{t("subtitle")}</p>
      {error && <p className="mb-3 text-sm text-[#B91C1C]">{error}</p>}
      <DataTable rows={groups} />
    </div>
  );
}
