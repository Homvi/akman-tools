"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { AppShell } from "@/components/app-shell";

type Me = { email: string; roles: string[] };
type Dataset = { loaded: boolean; cable_count?: number; progress_as_of?: string | null };

export function AuthGate({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [me, setMe] = useState<Me | null>(null);
  const [dataset, setDataset] = useState<Dataset | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function refreshDataset() {
      try {
        const ds = await api.get<Dataset>("/dataset");
        if (!cancelled) setDataset(ds);
      } catch {
        if (!cancelled) setDataset({ loaded: false });
      }
    }
    (async () => {
      try {
        const user = await api.get<Me>("/auth/me");
        if (cancelled) return;
        setMe(user);
        await refreshDataset();
      } catch {
        if (!cancelled) router.replace("/login");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    const onChanged = () => {
      void refreshDataset();
    };
    window.addEventListener("dataset-changed", onChanged);
    return () => {
      cancelled = true;
      window.removeEventListener("dataset-changed", onChanged);
    };
  }, [router]);

  async function logout() {
    setBusy(true);
    try {
      await api.post("/auth/logout");
      router.replace("/login");
    } finally {
      setBusy(false);
    }
  }

  if (loading || !me) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#09090B] text-sm text-[#71717A]">Loading…</div>
    );
  }

  return (
    <AppShell
      loading={busy}
      onLogout={logout}
      status={{ loaded: !!dataset?.loaded, progressAsOf: dataset?.progress_as_of }}
    >
      {children}
    </AppShell>
  );
}
