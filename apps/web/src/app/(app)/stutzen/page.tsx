"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { DataTable } from "@/components/data-table";
import { TopProgress } from "@/components/progress-bar";

export default function StutzenPage() {
  const [text, setText] = useState("");
  const [mode, setMode] = useState("AND");
  const [rows, setRows] = useState<Record<string, unknown>[]>([]);
  const [nodes, setNodes] = useState<string[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function run() {
    setLoading(true);
    setError("");
    try {
      const data = await api.post<{ rows: Record<string, unknown>[]; nodes: string[]; total: number }>(
        "/stutzen/filter",
        { nodes_text: text, unique_only: true, mode, page: 1, page_size: 100 }
      );
      setRows(data.rows);
      setNodes(data.nodes || []);
      setTotal(data.total ?? data.rows.length);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Szűrés sikertelen");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <TopProgress show={loading} />
      <h1 className="mb-1 text-2xl font-semibold tracking-tight text-[#FAFAFA]">Stützen / Bahn szűrő</h1>
      <div className="mb-4 space-y-2 text-sm leading-relaxed text-[#A1A1AA]">
        <p>A Stützenszámokat és Bahn számokat pontosvesszővel elválasztva kell megadni.</p>
        <p>
          A kapcsolót <span className="text-[#FAFAFA]">AND (mind)</span> értékre állítva azokat a kábeleket
          kapod, amelyek nyomvonalán <span className="text-[#FAFAFA]">mindegyik</span> megadott érték
          szerepel. <span className="text-[#FAFAFA]">OR (bármelyik)</span> esetén elég, ha a nyomvonalon{" "}
          <span className="text-[#FAFAFA]">bármelyik</span> megadott érték megjelenik.
        </p>
      </div>
      <textarea
        className="mb-3 h-28 w-full rounded-md border border-[#27272A] bg-[#09090B] p-3 font-mono-data text-sm text-[#FAFAFA] placeholder:text-[#52525B]"
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="1EDV606; 1E2104"
      />
      <div className="mb-4 flex flex-wrap gap-2">
        <select
          className="h-9 rounded-md border border-[#27272A] bg-[#09090B] px-2 text-sm text-[#FAFAFA]"
          value={mode}
          onChange={(e) => setMode(e.target.value)}
        >
          <option value="AND">AND — mind</option>
          <option value="OR">OR — bármelyik</option>
        </select>
        <Button onClick={run}>Szűrés</Button>
      </div>
      {error && <p className="mb-3 text-sm text-[#F87171]">{error}</p>}
      <p className="mb-2 text-xs text-[#71717A]">
        Keresett: {nodes.join("; ") || "—"}
        {nodes.length > 0 ? ` · ${total.toLocaleString()} találat` : ""}
      </p>
      <DataTable rows={rows} columns={["Kabelnr", "Category", "Thickness", "Length_m", "Pfad"]} />
    </div>
  );
}
