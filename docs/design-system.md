# Design system — Cable installation

Minimalist industrial planning tool. Serious, dense, mobile-ready.

## Brand

- Product name is the primary visual signal on login and home.
- One accent only. No purple gradients, no glow, no emoji loaders.

## Color (dark shadcn)

| Token | Value | Use |
|-------|--------|-----|
| `--background` | `#09090B` | Page (near-black) |
| `--surface` | `#0C0C0E` | Panels |
| `--border` | `#27272A` | 1px rules |
| `--foreground` | `#FAFAFA` | Text |
| `--muted` | `#A1A1AA` | Secondary text |
| `--accent` | `#2DD4BF` | Primary / Progressliste |
| `--orange` | `#F97316` | Secondary / Gesamtliste / Kurzliste |
| `--danger` | `#F87171` | Errors / Hibák |
| `--success` | `#34D399` | OK states |

Charts: zinc grid + turquoise primary + orange secondary.

## Typography

- UI: **IBM Plex Sans**
- IDs / nodes / meters: **IBM Plex Mono**
- Scale: 12 / 14 / 16 / 20 / 28 — prefer dense tables over large marketing type.

## Components (shadcn)

Button, Input, Textarea, Select, Checkbox, Dialog, Sheet, Table, Tabs, Badge, Separator, DropdownMenu, Sonner, Skeleton.

Surfaces: white + 1px border. No multi-layer shadows. Cards only for interactive containers.

## Motion & loading

- Thin indeterminate **top progress bar** on navigation / uploads.
- Skeleton rows for tables.
- Never cycling emoji / icon carousels.

## Layout

- Desktop: left nav + main.
- Mobile: drawer nav; filter **Sheet**; sticky primary actions; tables scroll horizontally or stack as cards below `md`.

## Future worker forms

Same tokens. Mobile-first Sheet/fullscreen forms under `/forms`. Role `worker`.
