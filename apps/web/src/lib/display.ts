/** Treat pandas/Excel NaN leftovers as empty for UI display. */
export function isBlankDisplay(value: unknown): boolean {
  if (value == null) return true;
  const text = String(value).trim();
  if (!text) return true;
  return ["nan", "<na>", "none", "nat", "null", "undefined"].includes(text.toLowerCase());
}

export function displayText(value: unknown, fallback = "—"): string {
  return isBlankDisplay(value) ? fallback : String(value).trim();
}

/** True when pathway should show the missing-Pfad warning instead of nan HTML. */
export function isRouteMissing(detail: {
  status?: string;
  route_missing?: boolean;
  route_html?: string | null;
  route?: string | null;
}): boolean {
  if (detail.route_missing) return true;
  if (detail.status === "none") return false;
  const html = (detail.route_html || "").trim();
  if (html && !isBlankDisplay(html.replace(/<[^>]+>/g, ""))) return false;
  return isBlankDisplay(detail.route);
}
