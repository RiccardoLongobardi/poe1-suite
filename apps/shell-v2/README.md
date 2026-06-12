# poe1-shell-v2 — "Obsidian Pro" (UI PRO MAX initiative)

The **new** FOB frontend, built alongside the v1 shell per Riccardo's
instruction ("creane uno nuovo e non toccare quello già fatto"):
`apps/shell` stays untouched and deployed; this app evolves until it
reaches parity + approval, then the Vercel project root flips from
`apps/shell` to `apps/shell-v2`.

## What's different from v1

- **Chrome**: sticky top navbar with horizontal tool tabs (no side
  rail, no burger — the tab row scrolls on narrow screens), footer
  with the secondary links, no welcome/splash gate (`/` → Home).
- **Design system "Obsidian Pro"**: cool near-black slate base
  (replaces the warm parchment), ember-gold accent kept (brand),
  Space Grotesk headings + Inter body (Cinzel only in the wordmark),
  static ambient glow instead of the particle canvas.
- **Token compatibility**: the `--vs-*` CSS variable NAMES and all
  utility class names are identical to v1 — only the VALUES changed —
  so every feature page/component was ported without edits and any
  future v1 fix can be cherry-picked across.

## What's identical to v1 (ported verbatim)

All feature pages (Finder / Analyze / Planner / Theorycrafter /
Patch Notes / FAQ / Privacy), the API layer, the i18n system, the
Zustand page store, keyboard shortcuts, donation modal, warmup
overlay. Same backend (`:8765`), same endpoints.

## Dev

```bash
cd apps/shell-v2 && npm run dev   # http://127.0.0.1:5174 (v1 is 5173)
```

Both apps can run side by side against the same backend.

## Deploy switch (when ready)

Vercel dashboard → project settings → Root Directory:
`apps/shell` → `apps/shell-v2`. Nothing else changes
(same build command, same `VITE_API_BASE`).
