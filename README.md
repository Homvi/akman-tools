# Cable installation analysis

Site cable-pull planning: joins **Progressliste** + **CaTra / Gesamtliste**, filters, exports, areas scheduling, workforce, and progress charts.

## Preferred stack (Hetzner Docker)

- **API:** FastAPI (`apps/api`) wrapping existing Python domain (`src/`)
- **Web:** Next.js + shadcn-style UI (`apps/web`) — design: [`docs/design-system.md`](docs/design-system.md)
- **DB:** Postgres 16 (Compose; port not published)
- **Proxy:** Caddy (TLS on server)

```bash
cp .env.example .env
# edit secrets
docker compose up -d --build
```

Local ports (override): API [http://localhost:8000](http://localhost:8000), Web [http://localhost:3000](http://localhost:3000).  
Default login: `ADMIN_EMAIL` / `ADMIN_PASSWORD` from `.env` (defaults `admin@example.com` / `changeme`).

Deploy notes: [`deploy/HETZNER.md`](deploy/HETZNER.md).

### Update on server

```bash
git pull
docker compose up -d --build
```

## Legacy Streamlit

Still available during cutover:

```bash
pip install -r requirements.txt
streamlit run app.py
```

Open [http://localhost:8501](http://localhost:8501). Prefer the Docker stack for demos and production.

## Domain logic

Unchanged under `src/` (parsers, join, areas, export, progress, workforce, reconcile). API is a thin adapter; do not rewrite parse logic in TypeScript.

## Tests

```bash
pytest
```

## Project layout

```
apps/api/           # FastAPI
apps/web/           # Next.js UI
src/                # Python domain
views/ app.py       # Legacy Streamlit
docs/design-system.md
docker-compose.yml
deploy/             # Caddyfile + Hetzner runbook
tests/
```
