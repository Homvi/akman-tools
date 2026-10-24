"use client";

import { createContext, useContext, useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { useRouter } from "@/i18n/routing";
import { api } from "@/lib/api";
import { AppShell } from "@/components/app-shell";
import { ToastProvider } from "@/components/toast";

export type Me = { email: string; roles: string[] };

const MeContext = createContext<Me | null>(null);

export function useMe(): Me | null {
  return useContext(MeContext);
}

export function isStaff(me: Me | null): boolean {
  return Boolean(me?.roles.some((r) => r === "planner" || r === "admin"));
}
type Dataset = { loaded: boolean; cable_count?: number; progress_as_of?: string | null };

export function AuthGate({ children }: { children: React.ReactNode }) {
  const t = useTranslations("common");
  const router = useRouter();
  const [me, setMe] = useState<Me | null>(null);
  const [dataset, setDataset] = useState<Dataset | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function refreshDataset() {
      try {
        const ds = await api.get<Dataset>("/dataset/status");
        if (!cancelled) setDataset(ds);
      } catch {
        if (!cancelled) setDataset({ loaded: false });
      }
    }
    async function enrichProgressDate() {
      try {
        const full = await api.get<Dataset>("/dataset");
        if (cancelled) return;
        setDataset((prev) => ({
          loaded: full.loaded ?? prev?.loaded ?? false,
          cable_count: full.cable_count ?? prev?.cable_count,
          progress_as_of: full.progress_as_of ?? null,
        }));
      } catch {
        /* keep light status */
      }
    }
    (async () => {
      try {
        const [user, ds] = await Promise.all([
          api.get<Me>("/auth/me"),
          api.get<Dataset>("/dataset/status").catch(() => ({ loaded: false } as Dataset)),
        ]);
        if (cancelled) return;
        setMe(user);
        setDataset(ds);
        // Light status has no progress date — fill it without blocking the shell.
        if (ds.loaded && !ds.progress_as_of) void enrichProgressDate();
      } catch {
        if (!cancelled) router.replace("/login");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    const onChanged = () => {
      void refreshDataset().then(() => {
        void enrichProgressDate();
      });
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
      <div className="flex min-h-screen items-center justify-center bg-[#09090B] text-sm text-[#71717A]">
        {t("loading")}
      </div>
    );
  }

  return (
    <MeContext.Provider value={me}>
      <ToastProvider>
        <AppShell
          loading={busy}
          onLogout={logout}
          status={{ loaded: !!dataset?.loaded, progressAsOf: dataset?.progress_as_of }}
        >
          {children}
        </AppShell>
      </ToastProvider>
    </MeContext.Provider>
  );
}
