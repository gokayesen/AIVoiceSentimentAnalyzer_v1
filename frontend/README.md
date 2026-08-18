# frontend

React 19 web console (Vite + TypeScript). DESIGN.md's token system lives in
`src/styles/tokens.css`; every component reads its colors, typography,
spacing, and radii from there — no ad hoc values.

Full MVP surface (Epics 1-3 complete): the `AppHeader` (wordmark/breadcrumb/
analyst identity), a session-scoped Call List (upload, async status polling,
delete — nothing persists past the browser session by design), and the
Analysis Dashboard (overall sentiment/emotion summary, emotional timeline,
transcript with per-turn text/tone signal breakdown and disagreement
flagging, acoustic insights, and speaker attribution where available).
Talks to `web-api` for every Call operation; no local mock data.

## Development

```bash
npm install
npm run dev      # local dev server
npm test         # vitest (jsdom + @testing-library/react)
npm run lint      # oxlint
npm run build     # tsc -b && vite build
```

## Docker

Built and served as part of the root `docker-compose.yml` stack (`frontend`
service, multi-stage build, served on port 3000 via `serve`).
