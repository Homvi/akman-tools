"use client";

import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { Check, FileSpreadsheet, Upload } from "lucide-react";
import { Link } from "@/i18n/routing";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { TopProgress } from "@/components/progress-bar";
import { cn } from "@/lib/utils";

function FilePick({
  label,
  hint,
  file,
  onPick,
  required,
  optionalLabel,
  chooseLabel,
  selectedLabel,
}: {
  label: string;
  hint?: string;
  file: File | null;
  onPick: (f: File | null) => void;
  required?: boolean;
  optionalLabel: string;
  chooseLabel: string;
  selectedLabel: (kb: string) => string;
}) {
  return (
    <label
      className={cn(
        "flex min-w-[240px] flex-1 cursor-pointer flex-col gap-1 rounded-md border border-dashed border-[#3F3F46] bg-transparent px-3 py-3 transition-colors hover:border-[#52525B]",
        file && "border-solid border-[#3F3F46] bg-[#18181B]"
      )}
    >
      <span className="flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-[#71717A]">
        <FileSpreadsheet size={14} className="text-[#71717A]" />
        {label}
        {!required && <span className="normal-case tracking-normal text-[#52525B]">{optionalLabel}</span>}
      </span>
      <span className={cn("truncate font-mono-data text-sm", file ? "text-[#FAFAFA]" : "text-[#52525B]")}>
        {file ? file.name : chooseLabel}
      </span>
      {hint && !file && <span className="text-xs text-[#52525B]">{hint}</span>}
      {file && (
        <span className="flex items-center gap-1 text-xs text-[#A1A1AA]">
          <Check size={12} /> {selectedLabel((file.size / 1024).toFixed(0))}
        </span>
      )}
      <input
        type="file"
        accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        className="hidden"
        onChange={(e) => onPick(e.target.files?.[0] ?? null)}
      />
    </label>
  );
}

function Section({
  title,
  description,
  children,
}: {
  title: string;
  description: string;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-md border border-[#27272A] bg-[#0C0C0E] p-4">
      <h2 className="text-sm font-medium text-[#FAFAFA]">{title}</h2>
      <p className="mt-1 text-xs text-[#71717A]">{description}</p>
      <div className="mt-3">{children}</div>
    </section>
  );
}

type Feedback = { ok: boolean; text: string } | null;

export default function UploadPage() {
  const t = useTranslations("upload");
  const tc = useTranslations("common");
  const [hasDataset, setHasDataset] = useState(false);
  const [progressFile, setProgressFile] = useState<File | null>(null);
  const [gesamtFile, setGesamtFile] = useState<File | null>(null);
  const [workforceFile, setWorkforceFile] = useState<File | null>(null);
  const [workforce600File, setWorkforce600File] = useState<File | null>(null);
  const [areasFile, setAreasFile] = useState<File | null>(null);
  const [liveFile, setLiveFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [datasetMsg, setDatasetMsg] = useState<Feedback>(null);
  const [workforceMsg, setWorkforceMsg] = useState<Feedback>(null);
  const [workforce600Msg, setWorkforce600Msg] = useState<Feedback>(null);
  const [areasMsg, setAreasMsg] = useState<Feedback>(null);
  const [liveMsg, setLiveMsg] = useState<Feedback>(null);

  useEffect(() => {
    api
      .get<{ loaded: boolean }>("/dataset")
      .then((d) => setHasDataset(!!d.loaded))
      .catch(() => setHasDataset(false));
  }, []);

  const canUploadDataset = !!progressFile && (!!gesamtFile || hasDataset);

  async function uploadDataset() {
    if (!progressFile) {
      setDatasetMsg({ ok: false, text: t("needProgress") });
      return;
    }
    if (!gesamtFile && !hasDataset) {
      setDatasetMsg({ ok: false, text: t("needGesamt") });
      return;
    }
    const form = new FormData();
    form.append("status_file", progressFile);
    if (gesamtFile) form.append("catra_file", gesamtFile);
    setLoading(true);
    setDatasetMsg(null);
    try {
      const res = await api.post<{
        cable_count: number;
        status_name: string;
        catra_name: string;
        progress_as_of?: string;
      }>("/dataset/upload", form);
      setDatasetMsg({
        ok: true,
        text:
          t("uploaded", { count: res.cable_count.toLocaleString(), status: res.status_name }) +
          (res.catra_name ? ` + ${res.catra_name}` : "") +
          (res.progress_as_of ? t("asOf", { date: res.progress_as_of }) : ""),
      });
      setProgressFile(null);
      setGesamtFile(null);
      setHasDataset(true);
      window.dispatchEvent(new Event("dataset-changed"));
    } catch (err) {
      setDatasetMsg({ ok: false, text: err instanceof Error ? err.message : t("failed") });
    } finally {
      setLoading(false);
    }
  }

  async function uploadWorkforce() {
    if (!workforceFile) {
      setWorkforceMsg({ ok: false, text: t("needWorkforce") });
      return;
    }
    const form = new FormData();
    form.append("file", workforceFile);
    setLoading(true);
    setWorkforceMsg(null);
    try {
      const res = await api.post<{ rows: number; people: number }>(
        `/workforce/upload?year=${new Date().getFullYear()}`,
        form
      );
      setWorkforceMsg({
        ok: true,
        text: t("workforceUploaded", {
          people: res.people.toLocaleString(),
          rows: res.rows.toLocaleString(),
        }),
      });
      setWorkforceFile(null);
      window.dispatchEvent(new Event("dataset-changed"));
    } catch (err) {
      setWorkforceMsg({ ok: false, text: err instanceof Error ? err.message : t("failed") });
    } finally {
      setLoading(false);
    }
  }

  async function uploadWorkforce600() {
    if (!workforce600File) {
      setWorkforce600Msg({ ok: false, text: t("needWorkforce600") });
      return;
    }
    const form = new FormData();
    form.append("file", workforce600File);
    setLoading(true);
    setWorkforce600Msg(null);
    try {
      const res = await api.post<{
        rows: number;
        people: number;
        project_updated?: number;
        project_598_updated?: number;
      }>(`/workforce/upload?year=${new Date().getFullYear()}&project=600`, form);
      setWorkforce600Msg({
        ok: true,
        text: t("workforce600Uploaded", {
          people: res.people.toLocaleString(),
          rows: res.rows.toLocaleString(),
          tagged598: (res.project_598_updated ?? 0).toLocaleString(),
        }),
      });
      setWorkforce600File(null);
      window.dispatchEvent(new Event("dataset-changed"));
    } catch (err) {
      setWorkforce600Msg({ ok: false, text: err instanceof Error ? err.message : t("failed") });
    } finally {
      setLoading(false);
    }
  }

  async function uploadAreas() {
    if (!areasFile) {
      setAreasMsg({ ok: false, text: t("needAreas") });
      return;
    }
    const form = new FormData();
    form.append("file", areasFile);
    setLoading(true);
    setAreasMsg(null);
    try {
      const res = await api.post<{ count: number }>("/areas/upload", form);
      setAreasMsg({ ok: true, text: t("areasUploaded", { count: res.count.toLocaleString() }) });
      setAreasFile(null);
    } catch (err) {
      setAreasMsg({ ok: false, text: err instanceof Error ? err.message : t("failed") });
    } finally {
      setLoading(false);
    }
  }

  async function uploadLive() {
    if (!liveFile) {
      setLiveMsg({ ok: false, text: t("needLive") });
      return;
    }
    const form = new FormData();
    form.append("file", liveFile);
    setLoading(true);
    setLiveMsg(null);
    try {
      const res = await api.post<{ cable_count: number; file_name?: string }>(
        "/near-complete/live-progressliste",
        form
      );
      setLiveMsg({
        ok: true,
        text: t("liveUploaded", {
          name: res.file_name || liveFile.name,
          count: res.cable_count.toLocaleString(),
        }),
      });
      setLiveFile(null);
    } catch (err) {
      setLiveMsg({ ok: false, text: err instanceof Error ? err.message : t("failed") });
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto max-w-3xl">
      <TopProgress show={loading} />
      <h1 className="text-2xl font-semibold tracking-tight text-[#FAFAFA]">{t("title")}</h1>
      <p className="mt-2 text-sm text-[#71717A]">{t("subtitle")}</p>

      <div className="mt-6 flex flex-col gap-4">
        <Section title={t("datasetTitle")} description={t("datasetHint")}>
          <div className="flex flex-wrap gap-3">
            <FilePick
              label="Progressliste"
              file={progressFile}
              required
              optionalLabel={tc("optional")}
              chooseLabel={tc("chooseFile")}
              selectedLabel={(kb) => tc("selectedKb", { kb })}
              onPick={setProgressFile}
            />
            <FilePick
              label="Gesamtliste"
              file={gesamtFile}
              required={!hasDataset}
              optionalLabel={tc("optional")}
              chooseLabel={tc("chooseFile")}
              selectedLabel={(kb) => tc("selectedKb", { kb })}
              hint={hasDataset ? t("gesamtHint") : undefined}
              onPick={setGesamtFile}
            />
          </div>
          <div className="mt-3">
            <Button variant="outline" onClick={() => void uploadDataset()} disabled={loading || !canUploadDataset}>
              <Upload size={16} />
              {t("submitDataset")}
            </Button>
          </div>
          {datasetMsg && (
            <p className={cn("mt-3 text-sm", datasetMsg.ok ? "text-[#A1A1AA]" : "text-[#F87171]")}>
              {datasetMsg.text}
            </p>
          )}
        </Section>

        <Section title={t("workforceTitle")} description={t("workforceHint")}>
          <div className="flex flex-wrap items-end gap-3">
            <FilePick
              label={t("workforceLabel")}
              file={workforceFile}
              required
              optionalLabel={tc("optional")}
              chooseLabel={tc("chooseFile")}
              selectedLabel={(kb) => tc("selectedKb", { kb })}
              onPick={setWorkforceFile}
            />
            <Button
              variant="outline"
              onClick={() => void uploadWorkforce()}
              disabled={loading || !workforceFile}
            >
              <Upload size={16} />
              {t("submitWorkforce")}
            </Button>
          </div>
          <p className="mt-2 text-xs text-[#52525B]">
            <Link href="/organisation" className="text-[#2DD4BF] underline-offset-2 hover:underline">
              {t("goOrganisation")}
            </Link>
            {" · "}
            <Link href="/workforce" className="text-[#2DD4BF] underline-offset-2 hover:underline">
              {t("goWorkforce")}
            </Link>
          </p>
          {workforceMsg && (
            <p className={cn("mt-3 text-sm", workforceMsg.ok ? "text-[#A1A1AA]" : "text-[#F87171]")}>
              {workforceMsg.text}
            </p>
          )}
        </Section>

        <Section title={t("workforce600Title")} description={t("workforce600Hint")}>
          <div className="flex flex-wrap items-end gap-3">
            <FilePick
              label={t("workforce600Label")}
              file={workforce600File}
              required
              optionalLabel={tc("optional")}
              chooseLabel={tc("chooseFile")}
              selectedLabel={(kb) => tc("selectedKb", { kb })}
              onPick={setWorkforce600File}
            />
            <Button
              variant="outline"
              onClick={() => void uploadWorkforce600()}
              disabled={loading || !workforce600File}
            >
              <Upload size={16} />
              {t("submitWorkforce600")}
            </Button>
          </div>
          <p className="mt-2 text-xs text-[#52525B]">
            <Link href="/organisation" className="text-[#2DD4BF] underline-offset-2 hover:underline">
              {t("goOrganisation")}
            </Link>
          </p>
          {workforce600Msg && (
            <p className={cn("mt-3 text-sm", workforce600Msg.ok ? "text-[#A1A1AA]" : "text-[#F87171]")}>
              {workforce600Msg.text}
            </p>
          )}
        </Section>

        <Section title={t("areasTitle")} description={t("areasHint")}>
          <div className="flex flex-wrap items-end gap-3">
            <FilePick
              label={t("areasLabel")}
              file={areasFile}
              required
              optionalLabel={tc("optional")}
              chooseLabel={tc("chooseFile")}
              selectedLabel={(kb) => tc("selectedKb", { kb })}
              onPick={setAreasFile}
            />
            <Button variant="outline" onClick={() => void uploadAreas()} disabled={loading || !areasFile}>
              <Upload size={16} />
              {t("submitAreas")}
            </Button>
          </div>
          <p className="mt-2 text-xs text-[#52525B]">
            <Link href="/areas" className="text-[#2DD4BF] underline-offset-2 hover:underline">
              {t("goAreas")}
            </Link>
          </p>
          {areasMsg && (
            <p className={cn("mt-3 text-sm", areasMsg.ok ? "text-[#A1A1AA]" : "text-[#F87171]")}>
              {areasMsg.text}
            </p>
          )}
        </Section>

        <Section title={t("liveTitle")} description={t("liveHint")}>
          <div className="flex flex-wrap items-end gap-3">
            <FilePick
              label={t("liveLabel")}
              file={liveFile}
              required
              optionalLabel={tc("optional")}
              chooseLabel={tc("chooseFile")}
              selectedLabel={(kb) => tc("selectedKb", { kb })}
              onPick={setLiveFile}
            />
            <Button variant="outline" onClick={() => void uploadLive()} disabled={loading || !liveFile}>
              <Upload size={16} />
              {t("submitLive")}
            </Button>
          </div>
          <p className="mt-2 text-xs text-[#52525B]">
            <Link href="/near-complete" className="text-[#2DD4BF] underline-offset-2 hover:underline">
              {t("goNearComplete")}
            </Link>
          </p>
          {liveMsg && (
            <p className={cn("mt-3 text-sm", liveMsg.ok ? "text-[#A1A1AA]" : "text-[#F87171]")}>
              {liveMsg.text}
            </p>
          )}
        </Section>
      </div>
    </div>
  );
}
