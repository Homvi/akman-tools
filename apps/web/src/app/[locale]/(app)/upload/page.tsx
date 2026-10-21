"use client";

import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { Check, FileSpreadsheet, Upload } from "lucide-react";
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

export default function UploadPage() {
  const t = useTranslations("upload");
  const tc = useTranslations("common");
  const [hasDataset, setHasDataset] = useState(false);
  const [progressFile, setProgressFile] = useState<File | null>(null);
  const [gesamtFile, setGesamtFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState("");
  const [msgOk, setMsgOk] = useState(false);

  useEffect(() => {
    api
      .get<{ loaded: boolean }>("/dataset")
      .then((d) => setHasDataset(!!d.loaded))
      .catch(() => setHasDataset(false));
  }, []);

  const canUpload = !!progressFile && (!!gesamtFile || hasDataset);

  async function upload() {
    if (!progressFile) {
      setMsgOk(false);
      setMsg(t("needProgress"));
      return;
    }
    if (!gesamtFile && !hasDataset) {
      setMsgOk(false);
      setMsg(t("needGesamt"));
      return;
    }
    const form = new FormData();
    form.append("status_file", progressFile);
    if (gesamtFile) form.append("catra_file", gesamtFile);
    setLoading(true);
    setMsg("");
    try {
      const res = await api.post<{ cable_count: number; status_name: string; catra_name: string; progress_as_of?: string }>(
        "/dataset/upload",
        form
      );
      setMsgOk(true);
      setMsg(
        t("uploaded", { count: res.cable_count.toLocaleString(), status: res.status_name }) +
          (res.catra_name ? ` + ${res.catra_name}` : "") +
          (res.progress_as_of ? t("asOf", { date: res.progress_as_of }) : "")
      );
      setProgressFile(null);
      setGesamtFile(null);
      setHasDataset(true);
      window.dispatchEvent(new Event("dataset-changed"));
    } catch (err) {
      setMsgOk(false);
      setMsg(err instanceof Error ? err.message : t("failed"));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto max-w-2xl">
      <TopProgress show={loading} />
      <h1 className="text-2xl font-semibold tracking-tight text-[#FAFAFA]">{t("title")}</h1>
      <p className="mt-2 text-sm text-[#71717A]">{t("subtitle")}</p>

      <div className="mt-6 flex flex-wrap gap-3">
        <FilePick
          label="Progressliste"
          file={progressFile}
          required
          optionalLabel={tc("optional")}
          chooseLabel={tc("chooseFile")}
          selectedLabel={(kb) => tc("selectedKb", { kb })}
          onPick={(f) => {
            setProgressFile(f);
            setMsgOk(true);
            setMsg(f ? `Progressliste: ${f.name}` : "");
          }}
        />
        <FilePick
          label="Gesamtliste"
          file={gesamtFile}
          required={!hasDataset}
          optionalLabel={tc("optional")}
          chooseLabel={tc("chooseFile")}
          selectedLabel={(kb) => tc("selectedKb", { kb })}
          hint={hasDataset ? t("gesamtHint") : undefined}
          onPick={(f) => {
            setGesamtFile(f);
            setMsgOk(true);
            setMsg(f ? `Gesamtliste: ${f.name}` : "");
          }}
        />
      </div>

      <div className="mt-4">
        <Button variant="outline" onClick={upload} disabled={loading || !canUpload}>
          <Upload size={16} />
          {t("submit")}
        </Button>
      </div>

      {msg && (
        <p className={cn("mt-4 text-sm", msgOk ? "text-[#A1A1AA]" : "text-[#F87171]")}>{msg}</p>
      )}
    </div>
  );
}
