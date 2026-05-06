# Production deploy — Fly.io (backend) + Vercel (frontend)

This is the operational playbook for getting the suite live for
multiple users. It assumes the source is already on `main` at
`https://github.com/RiccardoLongobardi/poe1-suite`.

## Architecture

```
                    ┌──────────────────┐
   user (browser) ──┤  Vercel CDN      │ ←  apps/shell (Vite SPA, ~510 KB gzipped)
                    │  fob.vercel.app  │
                    └────────┬─────────┘
                             │ HTTPS (CORS)
                             ▼
                    ┌──────────────────┐
                    │  Fly.io          │ ←  apps/server (FastAPI + uv venv)
                    │  fob-api.fly.dev │     in a Docker container
                    └────────┬─────────┘
                             │ HTTPS
                ┌────────────┼────────────┐
                ▼            ▼            ▼
         poe.ninja    GGG Trade API  pobb.in/pastebin
```

Both services run on free tiers. Custom domains can be wired later
without changing the source.

## Backend (Fly.io)

### One-time setup

1. Install `flyctl`. On Windows:
   ```pwsh
   iwr https://fly.io/install.ps1 -useb | iex
   ```
2. Sign up:
   ```bash
   fly auth signup
   # follow the email confirmation; add a card for verification (no
   # charges in the free tier)
   ```
3. Launch the app from the repo root (this generates `fly.toml`):
   ```bash
   fly launch --no-deploy --copy-config --name fob-api --region fra
   ```
   - `--region fra` = Frankfurt (low latency from Italy).
   - `--copy-config` keeps any local edits you make to `fly.toml`.

4. Set production secrets:
   ```bash
   fly secrets set \
     ENVIRONMENT=production \
     LOG_FORMAT=json \
     POE_LEAGUE=Mirage \
     CORS_ALLOWED_ORIGINS=https://fob.vercel.app
   ```
   See `.env.production.example` for the full list.

5. (Optional) attach a persistent volume for the on-disk HTTP cache:
   ```bash
   fly volumes create cache --size 1 --region fra
   # then in fly.toml:
   #   [[mounts]]
   #     source = "cache"
   #     destination = "/data"
   ```
   Without a volume the cache lives ephemerally and is lost across
   deploys/restarts — perfectly acceptable for a fresh-data tool.

### Deploy

```bash
fly deploy
```

This builds the Dockerfile remotely on Fly.io's builders, pushes the
image, and rolls out a new machine. Takes ~3-5 minutes the first
time; subsequent deploys are faster thanks to layer caching.

Verify:
```bash
curl https://fob-api.fly.dev/health
```

## Frontend (Vercel)

### One-time setup

1. Sign up at https://vercel.com (free, login with GitHub).
2. Click **Add New → Project**, import the `poe1-suite` repo.
3. **Configure project**:
   - **Framework preset**: Vite
   - **Root directory**: `apps/shell`
   - **Build command**: `npm run build`
   - **Output directory**: `dist`
4. **Environment variables** (Project Settings → Environment Variables):
   - `VITE_API_BASE` = `https://fob-api.fly.dev`
5. **Deploy** — Vercel builds and pushes to `https://<project-name>.vercel.app`.

Each push to `main` triggers an automatic redeploy.

## Custom domain (optional, ~$10/year)

When/if you want `fob.tools` or similar:

1. Buy the domain at Namecheap / Cloudflare Registrar.
2. **Vercel**: Project → Settings → Domains → Add `fob.tools` and
   `www.fob.tools`. Vercel will tell you which CNAME to set.
3. **Fly.io**: ```fly certs add api.fob.tools``` then update DNS
   per the instructions printed.
4. Update `CORS_ALLOWED_ORIGINS` on Fly to include the new origin:
   ```bash
   fly secrets set CORS_ALLOWED_ORIGINS=https://fob.tools,https://www.fob.tools
   ```
5. Update `VITE_API_BASE` on Vercel to `https://api.fob.tools`,
   redeploy.

## Smoke test checklist

After both services are up:

- [ ] `https://<frontend>/` loads the welcome page
- [ ] `https://<frontend>/home` shows the 3 feature cards
- [ ] `https://<frontend>/finder` returns ladder builds (proves
      `/builds/list` reaches poe.ninja through the backend)
- [ ] Paste a real PoB code on `/analyze` and confirm parsing works
- [ ] Open `/planner`, paste a PoB, hit "Genera piano" — a 6-stage
      plan should stream back with progress bar + ETA
- [ ] Toggle "Modalità reverse-progression", regenerate — verify
      `[target]` ladder rationales appear under "Upgrade ladder" in
      the right stages
- [ ] Browser DevTools → Network: confirm requests go to
      `<api host>` (not the dev `127.0.0.1`)

## Rollback

Fly.io keeps previous releases:
```bash
fly releases
fly deploy --image registry.fly.io/fob-api:deployment-<id>
```

Vercel: Project → Deployments → click any past deployment →
"Promote to Production".
