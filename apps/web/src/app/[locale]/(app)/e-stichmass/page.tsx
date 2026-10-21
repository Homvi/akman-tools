"use client";

import { useTranslations } from "next-intl";
import { FormEvent, useState } from "react";
import { Download } from "lucide-react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { DataTable } from "@/components/data-table";
import { Input } from "@/components/ui/input";
import { TopProgress } from "@/components/progress-bar";

type StichmassRow = {
  kabelnr: string;
  ok: boolean;
  error: string;
  liste: string;
  node_a: string;
  aln_a: number;
  meters: number | null;
  route_m: number | null;
  allowance_a: number | null;
  route_html: string;
  route: string;
};

function fmtM(n: number | null | undefined) {
  if (n === null || n === undefined) return "—";
  return `${Number(n).toFixed(1).replace(".", ",")} m`;
}

const PREVIEW_COLS = ["Kabelnr", "Liste", "A", "Aln_A", "Stichmaß"];

export default function EStichmassPage() {
  const t = useTranslations("stichmass");
  const tc = useTranslations("common");
  const [stuetze, setStuetze] = useState("");
  const [idsText, setIdsText] = useState("");
  const [rows, setRows] = useState<StichmassRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState("");
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [lastStuetze, setLastStuetze] = useState("");

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    setExpandedId(null);
    try {
      const data = await api.post<{ stuetze: string; rows: StichmassRow[] }>("/stichmass/calc", {
        stuetze: stuetze.trim(),
        ids: idsText,
      });
      setRows(data.rows || []);
      setLastStuetze(data.stuetze || stuetze.trim());
    } catch (err) {
      setRows([]);
      setError(err instanceof Error ? err.message : t("failed"));
    } finally {
      setLoading(false);
    }
  }

  async function exportExcel() {
    setExporting(true);
    setError("");
    try {
      const slug = (lastStuetze || stuetze).replace(/[^a-zA-Z0-9-_]+/g, "_").slice(0, 80) || "stuetze";
      await api.downloadPost(
        "/stichmass/export",
        { stuetze: (lastStuetze || stuetze).trim(), ids: idsText },
        `e_stichmass_${slug}.xlsx`
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : tc("exportFailed"));
    } finally {
      setExporting(false);
    }
  }

  const tableRows = rows.map((r) => ({
    Kabelnr: r.kabelnr,
    Liste: r.liste || "—",
    A: r.node_a || "—",
    Aln_A: r.aln_a != null ? String(r.aln_a).replace(".", ",") : "—",
    "Stichmaß": r.ok ? fmtM(r.meters) : r.error || "—",
    _raw: r,
  }));

  return (
    <div>
      <TopProgress show={loading || exporting} />
      <div className="mb-4">
        <h1 className="text-2xl font-semibold tracking-tight text-[#FAFAFA]">{t("title")}</h1>
        <p className="mt-1 text-sm text-[#A1A1AA]">
          {t("subtitle")}
        </p>
      </div>

      <form onSubmit={onSubmit} className="mb-4 flex flex-wrap items-end gap-3">
        <label className="block text-xs text-[#71717A]">
          {t("stuetze")}
          <Input
            className="mt-1 w-48 font-mono-data"
            value={stuetze}
            onChange={(e) => setStuetze(e.target.value)}
            placeholder={t("placeholder")}
            required
          />
        </label>
        <label className="min-w-[280px] flex-1 text-xs text-[#71717A]">
          {t("ids")}
          <textarea
            className="mt-1 min-h-[72px] w-full rounded-md border border-[#27272A] bg-[#0C0C0E] px-3 py-2 font-mono-data text-sm text-[#FAFAFA] outline-none focus:border-[#2DD4BF]/50"
            value={idsText}
            onChange={(e) => setIdsText(e.target.value)}
            placeholder={"12345; 2114,1\n67890"}
            required
          />
        </label>
        <Button type="submit" disabled={loading || !stuetze.trim() || !idsText.trim()}>
          {t("calc")}
        </Button>
        <Button
          type="button"
          variant="outline"
          disabled={exporting || !rows.length}
          onClick={() => void exportExcel()}
        >
          <Download size={16} />
          {t("excel")}
        </Button>
      </form>

      {error && <p className="mb-3 text-sm text-[#F87171]">{error}</p>}

      {lastStuetze && rows.length > 0 && (
        <p className="mb-2 text-xs text-[#71717A]">
          {t("resultMeta", {
            stuetze: lastStuetze,
            ok: rows.filter((r) => r.ok).length,
            total: rows.length,
          })}
        </p>
      )}

      <DataTable
        rows={tableRows}
        columns={PREVIEW_COLS}
        rowKey={(row) => String(row.Kabelnr ?? "")}
        expandedKey={expandedId}
        onRowClick={(row) => {
          const id = String(row.Kabelnr ?? "").trim();
          setExpandedId((prev) => (prev === id ? null : id));
        }}
        renderExpanded={(row) => {
          const raw = (row as { _raw?: StichmassRow })._raw;
          if (!raw) return null;
          return (
            <div className="space-y-2">
              {raw.ok ? (
                <p className="text-sm text-[#FAFAFA]">
                  {t("routeDetail", {
                    route: fmtM(raw.route_m),
                    aln: fmtM(raw.allowance_a),
                    total: fmtM(raw.meters),
                  })}
                </p>
              ) : (
                <p className="text-sm text-[#F87171]">{raw.error || tc("error")}</p>
              )}
              <div
                className="overflow-x-auto rounded-md border border-[#27272A] bg-[#0C0C0E] p-3 font-mono-data text-sm leading-7 text-[#E4E4E7]"
                dangerouslySetInnerHTML={{ __html: raw.route_html || raw.route || "—" }}
              />
              <p className="text-xs text-[#52525B]">{t("routeHint")}</p>
            </div>
          );
        }}
      />
    </div>
  );
}
