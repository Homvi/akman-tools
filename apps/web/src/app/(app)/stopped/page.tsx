"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { DataTable } from "@/components/data-table";
import { TopProgress } from "@/components/progress-bar";

export default function StoppedPage() {
  const [summary, setSummary] = useState<Record<string, unknown>[]>([]);
  const [detail, setDetail] = useState<Record<string, unknown>[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    setLoading(true);
    api
      .get<{ summary: Record<string, unknown>[]; detail: Record<string, unknown>[] }>("/stopped/summary")
      .then((d) => {
        setSummary(d.summary);
        setDetail(d.detail.slice(0, 200));
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <TopProgress show={loading} />
      <h1 className="mb-1 text-2xl font-semibold">Stopped cables</h1>
      <p className="mb-4 text-sm text-[#6B7280]">Current stop locations and remaining meters.</p>
      {error && <p className="mb-3 text-sm text-[#B91C1C]">{error}</p>}
      <h2 className="mb-2 text-sm font-medium uppercase tracking-wide text-[#6B7280]">By location</h2>
      <DataTable rows={summary} columns={["Stop_location", "Cable_count", "Remaining_unpulled_m", "Cables"]} />
      <h2 className="mb-2 mt-6 text-sm font-medium uppercase tracking-wide text-[#6B7280]">Detail</h2>
      <DataTable rows={detail} columns={["Kabelnr", "Stop_location", "Remaining_m", "Gestoppt", "Endsegment"]} />
    </div>
  );
}
