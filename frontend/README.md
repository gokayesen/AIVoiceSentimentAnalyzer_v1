# frontend

React 19 web console (Vite + TypeScript). DESIGN.md's token system lives in
`src/styles/tokens.css`; every component reads its colors, typography,
spacing, and radii from there — no ad hoc values.

Implemented as of Story 2.1 (Web Console Frontend Foundation & Session Call
List Shell): the `AppHeader` (wordmark/breadcrumb/analyst identity) and the
Session Call List shell (zero-Calls empty state). No backend integration yet
— `web-api` has no `GET /calls` list endpoint; upload/status wiring lands in
Story 2.2.

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
