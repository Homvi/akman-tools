"use client";

import { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { TopProgress } from "@/components/progress-bar";

export default function ProgressPage() {
  const [daily, setDaily] = useState<Record<string, unknown>[]>([]);
  const [weekly, setWeekly] = useState<Record<string, unknown>[]>([]);
  const [stats, setStats] = useState<Record<string, unknown>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    setLoading(true);
    api
      .get<{ daily: Record<string, unknown>[]; weekly: Record<string, unknown>[]; stats: Record<string, unknown> }>(
        "/progress/daily"
      )
      .then((d) => {
        setDaily(d.daily);
        setWeekly(d.weekly);
        setStats(d.stats || {});
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <TopProgress show={loading} />
      <h1 className="mb-1 text-2xl font-semibold">Progress</h1>
      <p className="mb-4 text-sm text-[#6B7280]">Daily and weekly pulled meters.</p>
      {error && <p className="mb-3 text-sm text-[#B91C1C]">{error}</p>}
      <div className="mb-4 flex flex-wrap gap-2">
        {Object.entries(stats).slice(0, 6).map(([k, v]) => (
          <Badge key={k}>
            {k}: {String(v)}
          </Badge>
        ))}
      </div>
      <div className="mb-6 h-72 rounded-md border border-[#E5E7EB] bg-white p-3">
        <p className="mb-2 text-xs uppercase tracking-wide text-[#6B7280]">Daily</p>
        <ResponsiveContainer width="100%" height="90%">
          <BarChart data={daily}>
            <CartesianGrid stroke="#E5E7EB" vertical={false} />
            <XAxis dataKey="Date" tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} />
            <Tooltip />
            <Bar dataKey="Total" fill="#1B4F72" radius={[2, 2, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <div className="h-72 rounded-md border border-[#E5E7EB] bg-white p-3">
        <p className="mb-2 text-xs uppercase tracking-wide text-[#6B7280]">Weekly (KW)</p>
        <ResponsiveContainer width="100%" height="90%">
          <LineChart data={weekly}>
            <CartesianGrid stroke="#E5E7EB" vertical={false} />
            <XAxis dataKey="KW" tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} />
            <Tooltip />
            <Line type="monotone" dataKey="Total" stroke="#1B4F72" strokeWidth={2} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
