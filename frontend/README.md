# Dark Vessel Monitor: frontend

A full-window, flat MapLibre GL JS world map showing live ship positions from the backend WebSocket. Built with Vite, React and TypeScript. Milestone 1: no login yet (Auth0 is milestone 2).

## Run

Requires a current Node.js (22 or newer) and the backend running on `ws://localhost:8000/ws`.

```sh
npm install
cp .env.example .env
npm run dev
```

Then open http://localhost:5173.

Other scripts: `npm run build` (type-checks, then builds to `dist/`), `npm run preview`, `npm run lint`.

## Environment variables

Set in `.env` (Vite reads `.env`, not `.env.example`). All are optional at milestone 1.

| Variable | Default | Purpose |
|---|---|---|
| `VITE_WS_URL` | `ws://localhost:8000/ws` | Backend WebSocket URL. |
| `VITE_AUTH0_DOMAIN` | empty | Auth0 tenant domain. Milestone 2, not used yet. |
| `VITE_AUTH0_CLIENT_ID` | empty | Auth0 SPA client ID. Milestone 2, not used yet. |
| `VITE_AUTH0_AUDIENCE` | empty | Auth0 API audience. Milestone 2, not used yet. |

## What it does

- Connects to the WebSocket and keeps a map of vessels keyed by `mmsi`. A `snapshot` replaces the map, a `delta` upserts `vessels` and deletes `removed`. Other message types are ignored for now.
- If a `seq` number is skipped, it closes the socket and reconnects to get a fresh snapshot.
- On close, it reconnects with backoff: 1 s, doubling to a 15 s maximum.
- Ships are one GeoJSON source drawn as a `circle` layer. The source is updated once per snapshot or delta.
- The status line (top left) shows connection state, the number of ships shown, and messages per second.

Types follow the backend contract in `src/types.ts`.

![Live map, 7 Nov 2026: about 10,000 ships world-wide](docs/map.png)
