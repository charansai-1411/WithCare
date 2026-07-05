# WithCare — Frontend

The web client for **WithCare**, a multi-agent AI healthcare-navigation assistant for India.
It's a single-page app that streams the agent's work live and renders every result — hospitals,
schemes, plans, price comparisons, reminders — as consistent cards.

Built with **React + Vite + Tailwind**, styled on **Google Material 3** (light + dark).

## Run locally

```bash
npm install
echo "VITE_API_URL=http://localhost:8001" > .env    # where the backend runs
npm run dev                                          # http://localhost:5173
```

`npm run build` produces a static bundle in `dist/` (deployed to Firebase Hosting).

## Layout

| Path | What's there |
|------|--------------|
| `src/App.jsx` | App shell, routing between views, auth + connector state |
| `src/hooks/useChat.js` | Chat state + the SSE client wiring |
| `src/services/` | `api.js` (SSE stream), `readerApi.js`, `connectorsService.js` (per-user OAuth tokens) |
| `src/components/` | Chat, cards (`PlanCards`, `ProductCards`…), Sidebar, views |
| `src/constants/agents.js` | Agent → icon-badge mapping |

## Notes
- Talks to the backend over **SSE** (`POST /chat/stream`); set `VITE_API_URL` for prod.
- "Connect" buttons request real Google consent and send each user's own token, so calendar/
  email actions run on **their** account.

See the [root README](../README.md) for the full architecture and design system.
