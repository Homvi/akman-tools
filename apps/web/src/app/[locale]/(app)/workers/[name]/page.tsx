"use client";

import { ChangeEvent, FormEvent, KeyboardEvent, useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import {
  AlertTriangle,
  ArrowLeft,
  Camera,
  MapPin,
  Pencil,
  Phone,
  Star,
  Trash2,
  X,
} from "lucide-react";
import { Link } from "@/i18n/routing";
import { api, qs } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { TopProgress } from "@/components/progress-bar";
import { isStaff, useMe } from "@/components/auth-gate";
import { cn } from "@/lib/utils";
import {
  daysBetween,
  formatShortRange,
  leaveInRange,
  leaveOverlapsNextWeek,
  parseIsoDate,
  personLeaveRanges,
  startOfDay,
  taskRange,
  LEAD_CATEGORIES,
  type Category,
  type Person,
} from "@/lib/staffing";
import { CategorySelect } from "@/components/category-select";

type CurrentTask = {
  id: string;
  title: string;
  role: "lead" | "worker";
  start_date: string | null;
  end_date: string | null;
  blocker: boolean;
  blocker_note: string;
  done: boolean;
};

type Entry = { id: number; author_email: string; created_at: string | null };
type Rating = Entry & { stars: number; comment: string };
type Note = Entry & { text: string };

type WorkerDetail = {
  name: string;
  key: string;
  in_workforce: boolean;
  person: Person | null;
  current_task: CurrentTask | null;
  tasks?: CurrentTask[];
  profile: {
    phone: string;
    address: string;
    languages: string[];
    has_photo: boolean;
    inactive: boolean;
    updated_at: string | null;
  };
  rating: { average: number | null; count: number };
  ratings: Rating[];
  notes: Note[];
};

const LANGUAGE_SUGGESTIONS = [
  "magyar",
  "angol",
  "német",
  "román",
  "szerb",
  "horvát",
  "szlovák",
  "lengyel",
  "ukrán",
  "bolgár",
  "orosz",
  "török",
];

function decodeParam(raw: string | string[] | undefined): string {
  const value = Array.isArray(raw) ? raw[0] : raw || "";
  try {
    return decodeURIComponent(value);
  } catch {
    return value;
  }
}

function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() || "")
    .join("");
}

function uploadPhoto(name: string, file: File, onProgress: (pct: number) => void): Promise<WorkerDetail> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${api.url}/workers/photo${qs({ name })}`);
    xhr.withCredentials = true;
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) onProgress(Math.round((e.loaded / e.total) * 100));
    };
    xhr.onload = () => {
      let body: unknown = null;
      try {
        body = JSON.parse(xhr.responseText);
      } catch {
        /* non-JSON error */
      }
      if (xhr.status >= 200 && xhr.status < 300) resolve(body as WorkerDetail);
      else {
        const detail = (body as { detail?: unknown } | null)?.detail;
        reject(new Error(typeof detail === "string" ? detail : xhr.statusText || "Upload failed"));
      }
    };
    xhr.onerror = () => reject(new Error("Upload failed"));
    const form = new FormData();
    form.append("file", file);
    xhr.send(form);
  });
}

function Card({ title, children, className }: { title: string; children: React.ReactNode; className?: string }) {
  return (
    <section className={cn("rounded-md border border-[#27272A] bg-[#0C0C0E] p-4", className)}>
      <h2 className="mb-3 text-xs font-medium uppercase tracking-wide text-[#71717A]">{title}</h2>
      {children}
    </section>
  );
}

function Stars({ value, size = "h-4 w-4" }: { value: number; size?: string }) {
  return (
    <span className="inline-flex items-center gap-0.5" aria-label={`${value}/5`}>
      {[1, 2, 3, 4, 5].map((n) => (
        <Star
          key={n}
          className={cn(
            size,
            n <= Math.round(value) ? "fill-[#F59E0B] text-[#F59E0B]" : "text-[#3F3F46]"
          )}
        />
      ))}
    </span>
  );
}

function EditableField({
  icon,
  value,
  placeholder,
  href,
  linkLabel,
  onSave,
  editLabel,
}: {
  icon: React.ReactNode;
  value: string;
  placeholder: string;
  href?: string | null;
  linkLabel?: string;
  onSave: (value: string) => Promise<void>;
  editLabel: string;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value);

  useEffect(() => {
    if (!editing) setDraft(value);
  }, [value, editing]);

  async function commit() {
    setEditing(false);
    if (draft.trim() !== value) await onSave(draft.trim());
  }

  return (
    <div className="flex min-h-9 items-center gap-2 text-sm">
      <span className="shrink-0 text-[#71717A]">{icon}</span>
      {editing ? (
        <Input
          autoFocus
          value={draft}
          placeholder={placeholder}
          onChange={(e) => setDraft(e.target.value)}
          onBlur={() => void commit()}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              void commit();
            } else if (e.key === "Escape") {
              setDraft(value);
              setEditing(false);
            }
          }}
          className="h-8 flex-1"
        />
      ) : (
        <>
          <span className={cn("min-w-0 flex-1 break-words", value ? "text-[#FAFAFA]" : "text-[#52525B]")}>
            {value || placeholder}
          </span>
          {value && href ? (
            <a
              href={href}
              target={href.startsWith("http") ? "_blank" : undefined}
              rel="noreferrer"
              className="shrink-0 text-xs text-[#2DD4BF] hover:underline"
            >
              {linkLabel}
            </a>
          ) : null}
          <button
            type="button"
            onClick={() => setEditing(true)}
            className="shrink-0 text-[#71717A] hover:text-[#E4E4E7]"
            title={editLabel}
          >
            <Pencil className="h-3.5 w-3.5" />
          </button>
        </>
      )}
    </div>
  );
}

export default function WorkerPage() {
  const t = useTranslations("workers");
  const tc = useTranslations("common");
  const locale = useLocale();
  const params = useParams<{ name: string }>();
  const name = decodeParam(params?.name);
  const me = useMe();
  const staff = isStaff(me);
  const isAdmin = Boolean(me?.roles.includes("admin"));
  const fileRef = useRef<HTMLInputElement>(null);

  const [detail, setDetail] = useState<WorkerDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notFound, setNotFound] = useState(false);
  const [preview, setPreview] = useState<string | null>(null);
  const [uploadPct, setUploadPct] = useState<number | null>(null);
  const [photoBroken, setPhotoBroken] = useState(false);
  const [langDraft, setLangDraft] = useState("");
  const [stars, setStars] = useState(0);
  const [hoverStars, setHoverStars] = useState(0);
  const [ratingComment, setRatingComment] = useState("");
  const [noteText, setNoteText] = useState("");

  const dateFmt = new Intl.DateTimeFormat(locale, { year: "numeric", month: "short", day: "numeric" });
  const shortFmt = new Intl.DateTimeFormat(locale, { month: "short", day: "numeric" });

  useEffect(() => {
    if (!staff || !name) {
      setLoading(false);
      return;
    }
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError("");
      setNotFound(false);
      try {
        const data = await api.get<WorkerDetail>(`/workers/profile${qs({ name })}`);
        if (!cancelled) setDetail(data);
      } catch (err) {
        if (cancelled) return;
        const msg = err instanceof Error ? err.message : tc("loadFailed");
        if (/not found/i.test(msg)) setNotFound(true);
        else setError(msg);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [name, staff, tc]);

  useEffect(() => {
    return () => {
      if (preview) URL.revokeObjectURL(preview);
    };
  }, [preview]);

  async function run(action: () => Promise<WorkerDetail>) {
    setBusy(true);
    setError("");
    try {
      setDetail(await action());
    } catch (err) {
      setError(err instanceof Error ? err.message : tc("loadFailed"));
    } finally {
      setBusy(false);
    }
  }

  const q = qs({ name });

  function saveProfile(
    patch: Partial<{ phone: string; address: string; languages: string[]; inactive: boolean }>
  ) {
    return run(() => api.put<WorkerDetail>(`/workers/profile${q}`, patch));
  }

  async function saveCategory(category: Category | null) {
    setBusy(true);
    setError("");
    try {
      const res = await api.put<Pick<Person, "category" | "category_source">>("/workforce/people/category", {
        name,
        category,
      });
      setDetail((prev) =>
        prev?.person
          ? {
              ...prev,
              person: {
                ...prev.person,
                ...res,
                is_lead: res.category ? LEAD_CATEGORIES.has(res.category) : prev.person.is_lead,
              },
            }
          : prev
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : tc("loadFailed"));
    } finally {
      setBusy(false);
    }
  }

  async function onPhotoPicked(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    setPreview(URL.createObjectURL(file));
    setUploadPct(0);
    setError("");
    try {
      const data = await uploadPhoto(name, file, setUploadPct);
      setDetail(data);
      setPhotoBroken(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("photoFailed"));
    } finally {
      setUploadPct(null);
      setPreview(null);
    }
  }

  function addLanguage(raw: string) {
    const lang = raw.trim();
    setLangDraft("");
    if (!detail || !lang) return;
    if (detail.profile.languages.some((l) => l.toLowerCase() === lang.toLowerCase())) return;
    void saveProfile({ languages: [...detail.profile.languages, lang] });
  }

  function onLangKey(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault();
      addLanguage(langDraft);
    } else if (e.key === "Backspace" && !langDraft && detail?.profile.languages.length) {
      void saveProfile({ languages: detail.profile.languages.slice(0, -1) });
    }
  }

  function submitRating(e: FormEvent) {
    e.preventDefault();
    if (!stars) return;
    const payload = { stars, comment: ratingComment };
    setStars(0);
    setRatingComment("");
    void run(() => api.post<WorkerDetail>(`/workers/ratings${q}`, payload));
  }

  function submitNote(e: FormEvent) {
    e.preventDefault();
    const text = noteText.trim();
    if (!text) return;
    setNoteText("");
    void run(() => api.post<WorkerDetail>(`/workers/notes${q}`, { text }));
  }

  function canDelete(entry: Entry) {
    return isAdmin || entry.author_email === me?.email;
  }

  function formatWhen(iso: string | null) {
    if (!iso) return "";
    const d = new Date(iso);
    return Number.isNaN(d.getTime()) ? "" : dateFmt.format(d);
  }

  const backLink = (
    <Link href="/tasks" className="mb-4 inline-flex items-center gap-1 text-sm text-[#A1A1AA] hover:text-[#FAFAFA]">
      <ArrowLeft className="h-4 w-4" />
      {t("back")}
    </Link>
  );

  if (!staff) {
    return (
      <div>
        {backLink}
        <p className="rounded-md border border-[#27272A] bg-[#0C0C0E] p-4 text-sm text-[#A1A1AA]">{t("noAccess")}</p>
      </div>
    );
  }

  if (notFound) {
    return (
      <div>
        {backLink}
        <p className="rounded-md border border-[#27272A] bg-[#0C0C0E] p-4 text-sm text-[#A1A1AA]">
          {t("notFound", { name })}
        </p>
      </div>
    );
  }

  const person = detail?.person || null;
  const today = startOfDay(new Date());
  const onLeaveNow = Boolean(person?.on_leave);
  const nextWeek = person ? leaveOverlapsNextWeek(person) : false;
  const leaves = person ? personLeaveRanges(person) : [];
  const tasks = detail?.tasks?.length
    ? detail.tasks
    : detail?.current_task
      ? [detail.current_task]
      : [];
  const photoSrc =
    preview ||
    (detail?.profile.has_photo && !photoBroken
      ? `${api.url}/workers/photo${qs({ name, v: detail.profile.updated_at || "" })}`
      : null);
  const shownStars = hoverStars || stars;
  const phone = detail?.profile.phone || "";
  const address = detail?.profile.address || "";

  return (
    <div className="mx-auto max-w-5xl">
      <TopProgress show={loading || busy || uploadPct !== null} />
      {backLink}
      {error && <p className="mb-3 text-sm text-[#F87171]">{error}</p>}

      {detail && (
        <>
          <header className="mb-4 flex flex-wrap items-center gap-4 rounded-md border border-[#27272A] bg-[#0C0C0E] p-4">
            <div className="group relative h-24 w-24 shrink-0">
              <button
                type="button"
                onClick={() => fileRef.current?.click()}
                className="relative h-24 w-24 overflow-hidden rounded-full border border-[#3F3F46] bg-[#18181B]"
                title={detail.profile.has_photo ? t("changePhoto") : t("uploadPhoto")}
              >
                {photoSrc ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={photoSrc}
                    alt={detail.name}
                    className="h-full w-full object-cover"
                    onError={() => setPhotoBroken(true)}
                  />
                ) : (
                  <span className="flex h-full w-full items-center justify-center text-2xl font-semibold text-[#A1A1AA]">
                    {initials(detail.name)}
                  </span>
                )}
                <span className="absolute inset-0 flex flex-col items-center justify-center gap-0.5 bg-black/60 text-[10px] font-medium text-white opacity-0 transition-opacity group-hover:opacity-100">
                  <Camera className="h-4 w-4" />
                  {detail.profile.has_photo ? t("changePhoto") : t("uploadPhoto")}
                </span>
                {uploadPct !== null && (
                  <span className="absolute inset-x-0 bottom-0 h-1.5 bg-black/60">
                    <span className="block h-full bg-[#2DD4BF]" style={{ width: `${uploadPct}%` }} />
                  </span>
                )}
              </button>
              {detail.profile.has_photo && uploadPct === null && (
                <button
                  type="button"
                  onClick={() => void run(() => api.del<WorkerDetail>(`/workers/photo${q}`))}
                  className="absolute -right-1 -top-1 hidden h-6 w-6 items-center justify-center rounded-full border border-[#3F3F46] bg-[#0C0C0E] text-[#F87171] hover:bg-[#EF4444]/20 group-hover:flex"
                  title={t("removePhoto")}
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              )}
              <input
                ref={fileRef}
                type="file"
                accept="image/jpeg,image/png,image/webp"
                className="hidden"
                onChange={(e) => void onPhotoPicked(e)}
              />
            </div>
            <div className="min-w-0 flex-1">
              <h1 className="break-words text-2xl font-semibold tracking-tight text-[#FAFAFA]">{detail.name}</h1>
              <div className="mt-1 flex flex-wrap items-center gap-2 text-sm text-[#A1A1AA]">
                {person?.position ? <span>{person.position}</span> : null}
                {person ? (
                  <label className="inline-flex items-center gap-1.5">
                    <span className="text-xs text-[#71717A]">{t("category")}</span>
                    <CategorySelect person={person} disabled={busy} onChange={(c) => void saveCategory(c)} />
                  </label>
                ) : null}
                {person?.is_lead ? (
                  <span className="rounded bg-[#F59E0B]/20 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide text-[#FCD34D]">
                    {t("lead")}
                  </span>
                ) : null}
                {detail.profile.inactive ? (
                  <span className="rounded bg-[#EF4444]/20 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide text-[#FCA5A5]">
                    {t("statusInactive")}
                  </span>
                ) : !detail.in_workforce ? (
                  <span className="rounded bg-[#27272A] px-1.5 py-0.5 text-[10px] text-[#A1A1AA]">
                    {t("notInWorkforce")}
                  </span>
                ) : onLeaveNow ? (
                  <span className="rounded bg-[#52525B] px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide text-[#E4E4E7]">
                    {t("statusLeaveNow")}
                  </span>
                ) : (
                  <span className="rounded bg-[#2DD4BF]/15 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide text-[#5EEAD4]">
                    {t("statusAvailable")}
                  </span>
                )}
                {nextWeek && !detail.profile.inactive ? (
                  <span className="rounded bg-[#F97316] px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide text-black">
                    {t("statusLeaveNextWeek")}
                  </span>
                ) : null}
              </div>
              <label className="mt-3 inline-flex cursor-pointer items-center gap-2 text-sm text-[#E4E4E7]">
                <input
                  type="checkbox"
                  className="h-4 w-4 rounded border-[#3F3F46] bg-[#18181B] text-[#EF4444] focus:ring-[#EF4444]"
                  checked={Boolean(detail.profile.inactive)}
                  disabled={busy}
                  onChange={(e) => void saveProfile({ inactive: e.target.checked })}
                />
                <span>{t("markInactive")}</span>
              </label>
              {detail.profile.inactive ? (
                <p className="mt-1 text-xs text-[#A1A1AA]">{t("markInactiveHint")}</p>
              ) : null}
              <div className="mt-2 flex flex-wrap items-center gap-3 text-xs text-[#71717A]">
                {detail.rating.count ? (
                  <span className="inline-flex items-center gap-1.5">
                    <Stars value={detail.rating.average || 0} size="h-3.5 w-3.5" />
                    <span className="text-[#E4E4E7]">
                      {(detail.rating.average || 0).toLocaleString(locale, { maximumFractionDigits: 1 })}
                    </span>
                    ({detail.rating.count})
                  </span>
                ) : null}
                {person?.last_present ? (
                  <span>{t("lastPresent", { date: dateFmt.format(parseIsoDate(person.last_present) || today) })}</span>
                ) : null}
              </div>
            </div>
          </header>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <Card title={tasks.length > 1 ? t("currentTasks") : t("currentTask")}>
              {tasks.length ? (
                <div className="space-y-3">
                  {tasks.map((task) => {
                    const range = taskRange(task);
                    const conflict = person && range ? leaveInRange(person, range.start, range.end) : null;
                    return (
                      <div key={`${task.role}-${task.id}`} className="space-y-1.5 text-sm">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="font-medium text-[#FAFAFA]">{task.title}</span>
                          <span
                            className={cn(
                              "rounded px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide",
                              task.role === "lead" ? "bg-[#F59E0B]/20 text-[#FCD34D]" : "bg-[#27272A] text-[#A1A1AA]"
                            )}
                          >
                            {task.role === "lead" ? t("roleLead") : t("roleWorker")}
                          </span>
                          {task.done ? (
                            <span className="rounded bg-[#3F3F46] px-1.5 py-0.5 text-[10px] font-bold uppercase text-[#E4E4E7]">
                              {t("taskDone")}
                            </span>
                          ) : task.blocker ? (
                            <span className="rounded bg-[#EF4444]/20 px-1.5 py-0.5 text-[10px] font-bold uppercase text-[#FCA5A5]">
                              {t("taskBlocked")}
                            </span>
                          ) : null}
                        </div>
                        {range ? (
                          <p className="text-xs text-[#5EEAD4]">
                            {shortFmt.format(range.start)} – {shortFmt.format(range.end)}
                          </p>
                        ) : (
                          <p className="text-xs text-[#71717A]">{t("noTaskDates")}</p>
                        )}
                        {task.blocker && task.blocker_note ? (
                          <p className="text-xs text-[#FCA5A5]">{task.blocker_note}</p>
                        ) : null}
                        {conflict ? (
                          <p className="inline-flex items-center gap-1 rounded bg-[#EF4444] px-2 py-1 text-xs font-semibold text-white">
                            <AlertTriangle className="h-3.5 w-3.5" />
                            {t("leaveConflict", { range: formatShortRange(conflict) })}
                          </p>
                        ) : null}
                      </div>
                    );
                  })}
                  <div>
                    <Link href="/tasks" className="text-xs text-[#2DD4BF] hover:underline">
                      {t("openTeams")}
                    </Link>
                  </div>
                </div>
              ) : (
                <p className="text-sm text-[#71717A]">{t("noTask")}</p>
              )}
            </Card>

            <Card title={t("contact")}>
              <EditableField
                icon={<Phone className="h-4 w-4" />}
                value={phone}
                placeholder={t("addPhone")}
                href={phone ? `tel:${phone.replace(/[^\d+]/g, "")}` : null}
                linkLabel={t("call")}
                editLabel={t("edit")}
                onSave={(value) => saveProfile({ phone: value })}
              />
              <EditableField
                icon={<MapPin className="h-4 w-4" />}
                value={address}
                placeholder={t("addAddress")}
                href={
                  address
                    ? `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(address)}`
                    : null
                }
                linkLabel={t("openMap")}
                editLabel={t("edit")}
                onSave={(value) => saveProfile({ address: value })}
              />
            </Card>

            <Card title={t("languages")}>
              <div className="flex flex-wrap items-center gap-1.5 rounded-md border border-[#27272A] bg-[#18181B] p-1.5">
                {detail.profile.languages.map((lang) => (
                  <span
                    key={lang}
                    className="inline-flex items-center gap-1 rounded bg-[#2DD4BF]/15 px-2 py-0.5 text-sm text-[#5EEAD4]"
                  >
                    {lang}
                    <button
                      type="button"
                      onClick={() =>
                        void saveProfile({ languages: detail.profile.languages.filter((l) => l !== lang) })
                      }
                      className="text-[#5EEAD4]/70 hover:text-[#FAFAFA]"
                      aria-label={t("delete")}
                    >
                      <X className="h-3 w-3" />
                    </button>
                  </span>
                ))}
                <input
                  list="worker-language-suggestions"
                  value={langDraft}
                  onChange={(e) => {
                    const value = e.target.value;
                    if (LANGUAGE_SUGGESTIONS.includes(value)) addLanguage(value);
                    else setLangDraft(value);
                  }}
                  onKeyDown={onLangKey}
                  onBlur={() => langDraft.trim() && addLanguage(langDraft)}
                  placeholder={detail.profile.languages.length ? "" : t("addLanguage")}
                  className="min-w-[8rem] flex-1 bg-transparent px-1 py-0.5 text-sm text-[#FAFAFA] placeholder:text-[#52525B] focus:outline-none"
                />
                <datalist id="worker-language-suggestions">
                  {LANGUAGE_SUGGESTIONS.filter(
                    (s) => !detail.profile.languages.some((l) => l.toLowerCase() === s)
                  ).map((s) => (
                    <option key={s} value={s} />
                  ))}
                </datalist>
              </div>
              <p className="mt-1.5 text-[11px] text-[#52525B]">{t("languageHint")}</p>
            </Card>

            <Card title={t("leaves")}>
              {leaves.length ? (
                <ul className="space-y-1">
                  {leaves.map((leave) => {
                    const from = parseIsoDate(leave.start);
                    const to = parseIsoDate(leave.end) || from;
                    if (!from || !to) return null;
                    const current = from <= today && to >= today;
                    return (
                      <li
                        key={`${leave.start}-${leave.end}`}
                        className={cn(
                          "flex items-center justify-between rounded-md border px-2.5 py-1.5 text-sm",
                          current
                            ? "border-[#71717A] bg-[#3F3F46]/50 text-[#FAFAFA]"
                            : "border-[#27272A] text-[#E4E4E7]"
                        )}
                      >
                        <span>
                          {shortFmt.format(from)}
                          {leave.end !== leave.start ? ` – ${shortFmt.format(to)}` : ""}
                          {current ? (
                            <span className="ml-2 rounded bg-[#52525B] px-1.5 py-0.5 text-[10px] font-bold uppercase">
                              {t("statusLeaveNow")}
                            </span>
                          ) : null}
                        </span>
                        <span className="text-xs text-[#71717A]">
                          {t("days", { count: daysBetween(from, to) + 1 })}
                        </span>
                      </li>
                    );
                  })}
                </ul>
              ) : (
                <p className="text-sm text-[#71717A]">{t("noLeaves")}</p>
              )}
            </Card>

            <Card title={t("rating")}>
              <form onSubmit={submitRating} className="mb-3 space-y-2">
                <div className="flex items-center gap-1" onMouseLeave={() => setHoverStars(0)}>
                  {[1, 2, 3, 4, 5].map((n) => (
                    <button
                      key={n}
                      type="button"
                      onMouseEnter={() => setHoverStars(n)}
                      onClick={() => setStars(n === stars ? 0 : n)}
                      aria-label={`${n}/5`}
                      className="p-0.5"
                    >
                      <Star
                        className={cn(
                          "h-6 w-6 transition-colors",
                          n <= shownStars ? "fill-[#F59E0B] text-[#F59E0B]" : "text-[#3F3F46]"
                        )}
                      />
                    </button>
                  ))}
                </div>
                <textarea
                  value={ratingComment}
                  onChange={(e) => setRatingComment(e.target.value)}
                  placeholder={t("ratingCommentPlaceholder")}
                  rows={2}
                  maxLength={2000}
                  className="w-full resize-y rounded-md border border-[#3F3F46] bg-[#18181B] px-2 py-1.5 text-sm text-[#FAFAFA] placeholder:text-[#52525B] focus:outline-none focus:ring-1 focus:ring-[#2DD4BF]"
                />
                <Button type="submit" disabled={!stars || busy} className="h-8">
                  {t("submitRating")}
                </Button>
              </form>
              {detail.ratings.length ? (
                <ul className="space-y-2 border-t border-[#27272A] pt-3">
                  {detail.ratings.map((r) => (
                    <li key={r.id} className="text-sm">
                      <div className="flex items-center justify-between gap-2">
                        <Stars value={r.stars} size="h-3.5 w-3.5" />
                        <span className="flex items-center gap-2 text-[11px] text-[#71717A]">
                          {formatWhen(r.created_at)} · {r.author_email}
                          {canDelete(r) ? (
                            <button
                              type="button"
                              onClick={() =>
                                void run(() => api.del<WorkerDetail>(`/workers/ratings/${r.id}${q}`))
                              }
                              className="text-[#71717A] hover:text-[#F87171]"
                              title={t("delete")}
                            >
                              <Trash2 className="h-3.5 w-3.5" />
                            </button>
                          ) : null}
                        </span>
                      </div>
                      {r.comment ? <p className="mt-0.5 whitespace-pre-wrap text-[#E4E4E7]">{r.comment}</p> : null}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-[#71717A]">{t("noRatings")}</p>
              )}
            </Card>

            <Card title={t("notes")}>
              <form onSubmit={submitNote} className="mb-3 space-y-2">
                <textarea
                  value={noteText}
                  onChange={(e) => setNoteText(e.target.value)}
                  placeholder={t("notePlaceholder")}
                  rows={3}
                  maxLength={5000}
                  className="w-full resize-y rounded-md border border-[#3F3F46] bg-[#18181B] px-2 py-1.5 text-sm text-[#FAFAFA] placeholder:text-[#52525B] focus:outline-none focus:ring-1 focus:ring-[#2DD4BF]"
                />
                <Button type="submit" disabled={!noteText.trim() || busy} className="h-8">
                  {t("addNote")}
                </Button>
              </form>
              {detail.notes.length ? (
                <ul className="space-y-2 border-t border-[#27272A] pt-3">
                  {detail.notes.map((n) => (
                    <li key={n.id} className="text-sm">
                      <div className="flex items-center justify-between gap-2 text-[11px] text-[#71717A]">
                        <span>
                          {formatWhen(n.created_at)} · {n.author_email}
                        </span>
                        {canDelete(n) ? (
                          <button
                            type="button"
                            onClick={() => void run(() => api.del<WorkerDetail>(`/workers/notes/${n.id}${q}`))}
                            className="hover:text-[#F87171]"
                            title={t("delete")}
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </button>
                        ) : null}
                      </div>
                      <p className="mt-0.5 whitespace-pre-wrap text-[#E4E4E7]">{n.text}</p>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-[#71717A]">{t("noNotes")}</p>
              )}
            </Card>
          </div>
        </>
      )}
    </div>
  );
}
