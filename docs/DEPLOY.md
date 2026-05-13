# Production deploy — Render (backend) + Vercel (frontend)

Operational playbook for getting the suite live for multiple users.
Assumes the source is on `main` at
`https://github.com/RiccardoLongobardi/poe1-suite`.

## Architecture

```
                    ┌──────────────────┐
   user (browser) ──┤  Vercel CDN      │ ←  apps/shell (Vite SPA, ~165 KB gzipped)
                    │ fob-ten.vercel…  │
                    └────────┬─────────┘
                             │ HTTPS (CORS)
                             ▼
                    ┌──────────────────┐
                    │  Render          │ ←  apps/server (FastAPI + uv venv)
                    │  fob-api.        │     in a Docker container
                    │  onrender.com    │
                    └────────┬─────────┘
                             │ HTTPS
                ┌────────────┼────────────┐
                ▼            ▼            ▼
         poe.ninja    GGG Trade API  pobb.in/pastebin
```

Both services run on free tiers. Custom domains can be wired later
without changing the source.

> **Migrated from Fly.io 2026-05-07.** Fly's trial ended and required
> a card on file even for the free tier; Render's free tier is
> permanent (with the spin-down trade-off described below) so the
> backend was moved without code changes — the same Dockerfile builds
> on either host.

## Backend (Render)

### Free tier characteristics

* **512 MB RAM, 0.1 CPU shared** — enough for FOB's async workload.
* **Spins down after 15 min idle.** First request after a spin-down
  takes ~30 s to wake the container. The frontend's request to
  `/health` will time out the first time; subsequent requests are
  instant.
* **750 hours/month** of running time across all free services on
  the account. Comfortably under FOB's expected traffic.
* **Auto-deploy from `main`** on every push (set in `render.yaml`).
* **Free SSL** on the `*.onrender.com` hostname.
* **No persistent disk** on free tier — the on-disk diskcache lives
  ephemerally in the container fs and is wiped on every redeploy /
  spin-down. Acceptable: poe.ninja responses are 15-min-cached
  anyway.

### One-time setup

1. Sign up at <https://render.com> (free, login with GitHub).
2. **New → Blueprint** in the dashboard.
3. **Connect the GitHub repo** `RiccardoLongobardi/poe1-suite`. Render
   reads the [`render.yaml`](../render.yaml) at the repo root and
   provisions one web service named `fob-api` from the Dockerfile.
4. **Set the secrets** (Render dashboard → service → Environment):
   * `POE_LEAGUE=Mirage` (or whatever the current league is)
   * `CORS_ALLOWED_ORIGINS=https://fob-ten.vercel.app`
5. Click **Apply** — the first build takes ~5 min (uv sync + Docker
   layer caching warming up).

### Deploy

Subsequent deploys happen automatically on every push to `main`.
Render builds the Dockerfile remotely, swaps the running container
with health-check-gated rollover, and serves the new version.

Verify:
```bash
curl https://fob-api.onrender.com/health
```

The first request after an idle period may take ~30 s while the
container boots. That's expected on the free tier.

### Render CLI (optional)

```bash
# Install
brew install render        # macOS
# or download from https://render.com/docs/cli

# Authenticate
render login

# Tail logs from your machine
render logs fob-api --tail
```

## Frontend (Vercel)

### One-time setup

1. Sign up at <https://vercel.com> (free, login with GitHub).
2. **Add New → Project**, import the `poe1-suite` repo.
3. **Configure project**:
   * **Framework preset**: Vite
   * **Root directory**: `apps/shell`
   * **Build command**: `npm run build`
   * **Output directory**: `dist`
4. **Environment variables** (Project Settings → Environment Variables):
   * `VITE_API_BASE` = `https://fob-api.onrender.com`
5. **Deploy** — Vercel builds and pushes to
   `https://<project-name>.vercel.app`.

Each push to `main` triggers an automatic redeploy.

### Updating VITE_API_BASE after the migration

If you previously pointed the frontend at `https://fob-api.fly.dev`,
update the env var:

1. Vercel dashboard → Project → Settings → Environment Variables.
2. Change `VITE_API_BASE` to `https://fob-api.onrender.com`.
3. **Redeploy** the latest production build (Deployments → … →
   Redeploy → uncheck "Use existing build cache" so the new env var
   is picked up).

## Custom domain (optional, ~$10/year)

When/if you want `fob.tools` or similar:

1. Buy the domain at Namecheap / Cloudflare Registrar.
2. **Vercel**: Project → Settings → Domains → Add `fob.tools` and
   `www.fob.tools`. Vercel prints the CNAME / A record to set.
3. **Render**: service → Settings → Custom Domains → Add
   `api.fob.tools`. Render gives you a CNAME target; add it to your
   DNS.
4. Update `CORS_ALLOWED_ORIGINS` on Render to include the new origin:
   ```
   CORS_ALLOWED_ORIGINS=https://fob.tools,https://www.fob.tools
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
- [ ] On any stage card, switch to Tree / Gear / Gems tabs (Step 14
      T5) and confirm the panels load progression data when the
      template ships one (RF Pohx is the reference)
- [ ] Click "Importa stage in PoB" — the code should be copied to
      the clipboard and rendered as a code preview
- [ ] Toggle "Modalità reverse-progression", regenerate — verify
      `[target]` ladder rationales appear under "Upgrade ladder" in
      the right stages
- [ ] Browser DevTools → Network: confirm requests go to
      `<api host>` (not the dev `127.0.0.1`)

## Rollback

**Render**: dashboard → service → Manual Deploy → "Deploy specific
commit" → pick a previous green commit hash.

**Vercel**: Project → Deployments → click any past deployment →
"Promote to Production".
