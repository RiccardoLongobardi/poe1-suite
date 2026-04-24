# poe1-suite — shell UI

React + Vite + Mantine SPA that composes every tool into a single user-facing application.

The frontend is intentionally **not** scaffolded yet: the Python pipeline must ship first (Steps 2–7 of the FOB roadmap) so the UI can be built against a stable HTTP contract.

## Planned stack

- **React 18** + **TypeScript**.
- **Vite 5** for dev server and bundling.
- **Mantine v7** as the component library (aligned with poeez.com as UX reference).
- **TanStack Query** for server state (API calls into `poe1-server`).
- **TanStack Router** for routing.

## Future packaging

When the web app is ready, we wrap it into other form factors without rewriting:

- Desktop: **Tauri** (Windows / macOS / Linux) — small bundle, native shell.
- Mobile: **Capacitor** — wraps the same SPA as a native iOS/Android app.

No code lives here yet.
