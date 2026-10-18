"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { DataTable } from "@/components/data-table";
import { Badge } from "@/components/ui/badge";
import { TopProgress } from "@/components/progress-bar";

export default function ErrorsPage() {
  const [report, setReport] = useState<{
    only_status: string[];
    only_catra: string[];
    field_conflicts: Record<string, unknown>[];
  } | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    setLoading(true);
    api
      .get<typeof report>("/errors/report")
      .then((d) => setReport(d))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <TopProgress show={loading} />
      <div className="mb-4 flex items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Hibák</h1>
          <p className="text-sm text-[#6B7280]">Progressliste ↔ Gesamtliste mismatches</p>
        </div>
        <Button variant="outline" onClick={() => api.download("/errors/export", "hibak.xlsx")}>
          Export xlsx
        </Button>
      </div>
      {error && <p className="mb-3 text-sm text-[#B91C1C]">{error}</p>}
      {report && (
        <>
          <div className="mb-4 flex gap-2">
            <Badge>Only Progress: {report.only_status.length}</Badge>
            <Badge>Only Gesamt: {report.only_catra.length}</Badge>
            <Badge>Conflicts: {report.field_conflicts.length}</Badge>
          </div>
          <h2 className="mb-2 text-sm font-medium text-[#6B7280]">Field conflicts</h2>
          <DataTable rows={report.field_conflicts} />
        </>
      )}
    </div>
  );
}
