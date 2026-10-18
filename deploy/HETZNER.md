# Hetzner deploy

1. Install Docker + Compose on the VPS.
2. Clone this repo, copy `.env.example` → `.env`, set strong secrets and domain.
3. Edit `deploy/Caddyfile` for your domain and enable HTTPS (remove `auto_https off`).
4. Set `NEXT_PUBLIC_API_URL=https://your.domain/api` (or same-origin `/api` via Caddy).
5. Open firewall: 22, 80, 443 only — **not** 5432.
6. Run:

```bash
docker compose up -d --build
```

## Update deployed code

```bash
cd /opt/dev_nev   # or your path
git pull
docker compose up -d --build
```

Or wire GitHub Actions SSH to run the same commands on `main` push.

## Backup Postgres

```bash
docker compose exec -T db pg_dump -U cable cable > backup-$(date +%F).sql
```
