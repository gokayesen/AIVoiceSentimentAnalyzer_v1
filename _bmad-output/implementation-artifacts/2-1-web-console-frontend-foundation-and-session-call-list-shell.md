---
baseline_commit: b3a0fce
---

# Story 2.1: Web Console Frontend Foundation & Session Call List Shell

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an Analyst,
I want to open the application into a working console shell with my session's call list,
so that I have a starting point to begin uploading and reviewing calls.

## Acceptance Criteria

1. **Given** the frontend is built, **When** the Analyst opens the application, **Then** a React 19 app loads directly into the Session Call List (default landing surface) — no login/account screen, since MVP has no auth (PRD §2.3).
2. **Given** the app loads, **When** the App header renders, **Then** it shows the near-black chrome bar with the product wordmark (left, `chrome-text-strong`), a monospace breadcrumb (center, queue/case path), and analyst identity (right, name+role, no login UI).
3. **Given** the app renders any surface, **When** any color, typography, spacing, or shape is applied, **Then** it is sourced from DESIGN.md's token system — no ad hoc values.
4. **Given** the Session Call List has zero Calls, **When** the Analyst views it, **Then** it shows a plain prompt to upload the first Call — no illustration/mascot.
5. **Given** a viewport narrower than ~960px, **Then** this story does not implement the responsive fallback — that is Story 2.7's scope; this story only needs to render correctly at the primary desktop-width target.
6. **And** this story establishes the frontend build/serve pipeline within the existing docker-compose stack — no new deployment target beyond what AD-18 already defines.

**Traceability:** UX-DR1, UX-DR19, UX-DR20, UX-DR21 (token-sourced-only rendering, no ad hoc values); AD-18 (frontend build container, not a new decision).

**Dependency:** None from Epic 1 — this is Epic 2's first story and the frontend's first real commit (`frontend/` currently holds only a placeholder `README.md`, scaffolded by Story 1.1). This story makes **zero** calls to `web-api` — see Dev Notes "No backend calls in this story." Story 2.2 is the first to talk to the API.

## Tasks / Subtasks

- [x] Task 1: Scaffold the React 19 + Vite frontend project (AC: 1, 6)
  - [x] `frontend/` already contains `README.md` (non-empty dir — most scaffolding CLIs refuse to run in place). Scaffold into a throwaway directory (`npm create vite@latest tmp-scaffold -- --template react-ts`), then move its contents into `frontend/`, delete `tmp-scaffold/`, and keep/update the existing `README.md` (it currently says "No implementation yet" — update it to reflect this story's outcome).
  - [x] Pin `react` and `react-dom` to `^19.2.8` in `package.json` — this is the exact version the Architecture Stack table pins (`ARCHITECTURE-SPINE.md#Stack`, line 194). Do not accept whatever newer/older version the scaffold tool defaults to without checking.
  - [x] Add test dependencies: `vitest`, `jsdom`, `@testing-library/react`, `@testing-library/jest-dom`, `@testing-library/user-event` (AD-21 — every module needs independently runnable tests). See Dev Notes "Frontend stack & tooling" for confirmed-current versions (Context7-verified 2026-08-15).
  - [x] Configure `vite.config.ts`: `@vitejs/plugin-react` plugin, plus a `test` block (`environment: 'jsdom'`, `setupFiles: './src/setupTests.ts'`) — Vitest reads its config from the same `vite.config.ts` (no separate config file needed) when using `vitest/config`'s `defineConfig`.
  - [x] Add `package.json` scripts: `dev` (`vite`), `build` (`tsc -b && vite build` if using the TS template, or `vite build`), `preview` (`vite preview`), `test` (`vitest run` — **not** `vitest` alone, so CI doesn't hang in watch mode), `lint` (see tooling note below).

- [x] Task 2: Transcribe DESIGN.md's token system into the codebase (AC: 3)
  - [x] Create `frontend/src/styles/tokens.css` — CSS custom properties transcribed **verbatim** from `DESIGN.md`'s YAML frontmatter (`colors`, `typography`, `rounded`, `spacing`). See Dev Notes "DESIGN.md token transcription" for the exact block to use — do not re-derive values by eye from the mockup HTML files, which contain some values that are **not** in DESIGN.md's token set (see "Known spec gaps" below).
  - [x] Create `frontend/src/index.css` (or `App.css`): global reset (`box-sizing: border-box`), body background = `var(--color-bg)`, body text color = `var(--color-text)`, body font = the `body` typography role. Import `tokens.css` first.
  - [x] Every component built in this story (and going forward) must reference `var(--color-*)`/`var(--font-*)`/`var(--space-*)`/`var(--radius-*)` — never a bare hex/px value. This is what AC3 tests for; there is no lint rule enforcing it (none is specified anywhere in this project's docs), so this is a manual discipline requirement, not an automated gate.

- [x] Task 3: Build the shared `AppHeader` component (AC: 1, 2, 3)
  - [x] New file `frontend/src/components/AppHeader.tsx` (+ `AppHeader.css`). Three-part layout matching `DESIGN.md`'s `app-header` component spec (background `chrome`, padding `{spacing.4} {spacing.8}`) **and** the actual markup pattern rendered in `mockups/analysis-dashboard.html` lines 202–205 (`.app-header > .brand`, `.crumb`, `.user`) — **not** `mockups/session-call-list.html`'s `.list-header`, which is a different, incomplete element missing the breadcrumb and identity. See Dev Notes "Known spec gaps: which mock to follow for the header" — this is the single most important judgment call in this story.
  - [x] Left: product wordmark, text `"VOICE SENTIMENT · CONSOLE"` (the literal copy from the one rendered reference, `analysis-dashboard.html` line 203), color `var(--color-chrome-text-strong)`.
  - [x] Center: a real `<button>` (not a link/div) with the breadcrumb text, monospace (`data-inline` typography role), color `var(--color-chrome-text)`. MVP has no real queue/case-path data — hardcode a representative root value such as `"queue/session"` (there is no "queue" concept anywhere in the PRD/Architecture beyond this UI copy string). Per EXPERIENCE.md Interaction Primitives, clicking this returns the Analyst to the Session Call List from anywhere in the Dashboard — since the Dashboard doesn't exist yet (Story 2.4), the click handler is a no-op in this story; the element must still be focusable and keyboard-activatable (it's explicitly listed under DESIGN.md `focus-ring.applies-to` and EXPERIENCE.md's Accessibility Floor).
  - [x] Right: analyst identity — a small avatar-style initials box + `"Elif Y. · CX Analyst"` text (literal copy from the mock, consistent with the PRD's named persona, Elif). No login/account UI (PRD §2.3 — MVP has no auth), so this is a static hardcoded placeholder, not fetched from any API or state.
  - [x] Apply the `focus-ring` **on-chrome** variant (`var(--color-focus-ring-on-chrome)`, 2px solid, 2px offset) to the breadcrumb button's `:focus-visible` state — the on-light variant is wrong here (this is a chrome surface).
  - [x] Avatar swatch background: use `var(--color-chrome-secondary)` (a real DESIGN.md token), **not** the mock's `#263140` (undocumented, not in DESIGN.md's token list — see "Known spec gaps").

- [x] Task 4: Build the Session Call List page (AC: 1, 3, 4)
  - [x] New file `frontend/src/pages/SessionCallList.tsx` (+ `.css`). Renders below `AppHeader`: a chrome-colored "session strip" (title `"This Session"` in `heading-sm` typography + a `"+ Add call"` control, subtitle line in `label`/`data-sm` typography e.g. `"0 calls analyzed this session · not saved after session ends"`) followed by the list content area on `var(--color-bg)`.
  - [x] The `"+ Add call"` control renders as a real, focusable, labeled control (matching the mock's affordance) but has **no working file-picker/drag-drop logic** in this story — that's Story 2.2's scope entirely (see epics.md Story 2.2 AC1/AC2). A no-op `onClick` (or none at all) is correct here; do not wire `<input type="file">` behavior yet.
  - [x] Empty state (AC4, zero Calls — the only state this story renders, since there is no data source yet): a single plain-text instruction (e.g. `"No calls yet. Add a call to begin."`) — **no illustration, no mascot, no icon graphic**. Follow EXPERIENCE.md Voice and Tone: no exclamation points, no hype framing.
  - [x] Do **not** build call-row rendering, `badge-dot`, sentiment display, or any per-Call UI in this story — there is no data source for it yet (see "No backend calls in this story" and "What NOT to build" in Dev Notes). It is fine to sketch a `Call` TypeScript type/interface now if it helps Story 2.2's continuity, but do not build components consuming it.
  - [x] `frontend/src/App.tsx` composes `<AppHeader />` + `<SessionCallList />`. Do **not** add `react-router-dom` or any routing library in this story — there is only one real page rendered (List); Dashboard navigation is Story 2.4's concern, and adding a router now with nothing to route to is unnecessary scope (YAGNI).

- [x] Task 5: Frontend Docker build/serve pipeline (AC: 6)
  - [x] New file `frontend/Dockerfile` — multi-stage build: a `node` build stage (`npm ci`, `npm run build` → static `dist/`), then a slim runtime stage serving `dist/` on port `3000` (matching `docker-compose.yml`'s existing `frontend.ports: ["3000:3000"]` mapping). See Dev Notes "Frontend stack & tooling" for a concrete pattern (`serve` package) — mirrors `web-api/Dockerfile`'s multi-stage-free simplicity where reasonable, but a build stage is unavoidable here since Vite's build step needs `devDependencies` that shouldn't ship in the runtime image.
  - [x] Edit `docker-compose.yml`: the `frontend` service currently has `profiles: ["full"]` (added when it was a placeholder with no real Dockerfile — see its comment "Placeholder — becomes functional in Story 2.1"). Remove the `profiles` key now that it's a real, buildable service, so `docker compose up` brings up the whole stack by default, consistent with AD-18's "single-machine docker-compose stack" description (which lists `frontend` as one of the standard services, not an opt-in extra). Update the comment to match the pattern already used for other services once they became functional (e.g. `ml-service`'s "Functional as of Story 1.2...").
  - [x] No new deployment target, no cloud config, no GPU assumption — AC6 explicitly forbids introducing anything AD-18 doesn't already define.

- [x] Task 6: Add a `frontend` job to CI (AD-21; supports AC: 6)
  - [x] `.github/workflows/ci.yml` currently has two jobs (`web-api`, `ml-service`), each: checkout → set up runtime → install deps → lint → test. Add a third `frontend` job following the same shape: `actions/setup-node@v4` (Node version — see Dev Notes, Architecture's Stack table does **not** pin one), `working-directory: frontend`, `npm ci`, lint step, `npm test` (runs `vitest run`, not watch mode), and a `npm run build` step (catches build breaks even though this project has no live deploy step, matching AD-21's "runs tests and lint on every push — no deployment step" framing; a build-breakage is a real regression this CI should still catch).

- [x] Task 7: Component tests (AC: 1, 2, 3, 4)
  - [x] `frontend/src/components/AppHeader.test.tsx` — render `<AppHeader />`; assert the wordmark text, breadcrumb text, and identity text are all present; assert there is no "log in"/"sign in"/"sign up" text anywhere (AC1's no-auth requirement, verified at the header level since that's where an app would normally put such UI); assert the breadcrumb is a real, focusable `<button>`.
  - [x] `frontend/src/pages/SessionCallList.test.tsx` — render `<SessionCallList />` (zero-Calls state, the only state that exists in this story); assert the plain-text upload prompt is present; assert no `<img>`/`<svg>` illustration-type element renders anywhere in the empty state (an icon-only control like "+ Add call" is fine — an illustration/mascot is not).
  - [x] `frontend/src/App.test.tsx` — render `<App />`; assert it renders directly into the Session Call List content (AC1 — "no login/account screen" at the whole-app level, not just the header).

- [x] Task 8: Full verification pass
  - [x] `cd frontend && npm run build` — must succeed with zero errors (this is also the file CI's build step runs).
  - [x] `cd frontend && npm test` — all tests pass.
  - [x] `cd frontend && npm run lint` — clean.
  - [x] `docker compose config --quiet` from the repo root — validates the edited `docker-compose.yml` still parses (no live Docker daemon build required to catch a YAML/reference error).
  - [x] If a Docker daemon is available, `docker compose build frontend` and `docker compose up frontend` (or the full stack) to confirm the container actually serves the app on port 3000 — if no daemon is available in the dev environment (as was the case for Story 1.1 — see its Dev Agent Record), note that explicitly rather than silently skipping it.

### Review Findings

- [x] [Review][Patch] AppHeader avatar swatch uses bare px literals, including a 9px font-size below DESIGN.md's stated 11px typography floor [frontend/src/components/AppHeader.css:48-55] — **Fixed:** `width`/`height` now `calc(var(--space-4) * 2)` (preserves the original 20px), `font-size` now `var(--font-data-inline-size)` (11px, meets the floor), `font-weight` now `var(--font-label-weight)` (700, same value, now tokenized).
- [x] [Review][Patch] AppHeader breadcrumb isn't guaranteed to sit at true visual center — `justify-content: space-between` across three unequal-width children only centers the middle item when the flanking items are equal width, and AC2 requires "center" [frontend/src/components/AppHeader.css:1-8] — **Fixed:** `.app-header` is now a 3-column grid (`1fr auto 1fr`) with `justify-self: start/center/end` on the three children — the breadcrumb is now at the true geometric center regardless of the flanking elements' widths.
- [x] [Review][Patch] Wordmark font-size (12px in the mock) has no matching DESIGN.md typography role; the implementation silently substitutes the `label` role without documenting it as a third "Known spec gap" alongside the two ad hoc colors [_bmad-output/implementation-artifacts/2-1-web-console-frontend-foundation-and-session-call-list-shell.md — Dev Notes "Known spec gaps"] — **Fixed:** added as item 3 in "Known spec gaps" (no code change needed — the existing `label`-role substitution was already AC3-compliant, just undocumented).
- [x] [Review][Patch] `.session-strip__subtitle` applies only `font-size` from the `label` role (omits weight/letter-spacing/uppercase) and doesn't match `data-sm` either — `session-strip` has no canonical DESIGN.md component spec to fully satisfy, undocumented as such [frontend/src/pages/SessionCallList.css:37-41] — **Fixed:** added a clarifying code comment explaining neither named role fully fits and why the current plain rendering (matching the mock's own subtitle) is the deliberate choice.
- [x] [Review][Patch] Story file's Task 1, "Frontend stack & tooling," and "Project Structure Notes" still reference the originally-planned `vitest.setup.ts` path; the actual code (and File List) correctly use `frontend/src/setupTests.ts` [_bmad-output/implementation-artifacts/2-1-web-console-frontend-foundation-and-session-call-list-shell.md:36,99,140] — **Fixed:** all 3 stale references updated to `frontend/src/setupTests.ts`.
- [x] [Review][Patch] `Dockerfile`'s runtime stage installs `serve` via a floating `serve@14` tag with no exact-version pin — a rebuild can silently pull a different patch version (confirmed current published version: 14.2.6) [frontend/Dockerfile:15] — **Fixed:** pinned to `serve@14.2.6`; image rebuilt and re-verified end-to-end (`docker compose build frontend` + `up` + `curl` → HTTP 200).
- [x] [Review][Patch] BEM-ish CSS class naming convention (`block__element`) introduced with no written documentation, despite the story declaring its structure decisions "baseline for Stories 2.2–2.7" [frontend/src/components/AppHeader.css, frontend/src/pages/SessionCallList.css] — **Fixed:** documented in "Project Structure Notes."
- [x] [Review][Patch] `AppHeader`'s `breadcrumbLabel=""` (empty string) bypasses the JS default-parameter fallback (only `undefined` triggers it), rendering an empty/inaccessible breadcrumb button — currently unreachable but a latent defect in a prop explicitly documented as Story 2.4's extension point [frontend/src/components/AppHeader.tsx:18-26] — **Fixed:** replaced the default-parameter with an explicit `breadcrumbLabel?.trim() ? breadcrumbLabel : 'queue/session'` guard; added a regression test (`AppHeader.test.tsx`: "falls back to the default breadcrumb when passed an empty/whitespace label").
- [x] [Review][Patch] No max-width/truncation guard on `.app-header__crumb` — a long future `breadcrumbLabel` (e.g. Story 2.4's real case path) could overflow the chrome bar and push the wordmark/identity out of view [frontend/src/components/AppHeader.css:18-28] — **Fixed:** added `max-width: 40ch; overflow: hidden; text-overflow: ellipsis; white-space: nowrap`.

## Dev Notes

### Known spec gaps — read this before touching the header or `mockups/session-call-list.html`

This is the highest-value finding in this story's research and the one most likely to produce a wrong implementation if missed:

1. **Which mock defines the App header.** `mockups/session-call-list.html` renders a `.list-header` block (lines 155–161: an `<h1>This Session</h1>` + a `"+ Add call"` link + a subtitle) on a chrome-colored bar. This does **not** match AC2's explicit three-part structure (wordmark / breadcrumb / analyst identity), and it does not match `DESIGN.md`'s `app-header` component spec or the `EXPERIENCE.md` Component Patterns description of it either. The *actual* 1:1 rendering of the `app-header` component — wordmark, clickable monospace breadcrumb, analyst identity with avatar — only exists in `mockups/analysis-dashboard.html` (lines 65–77 CSS, lines 202–205 markup). Per `EXPERIENCE.md` line 32 ("the spine ... always wins on conflict with a mock") and the epics AC being explicit and specific, build the header per AC2 using `analysis-dashboard.html`'s structure as the concrete reference, as a component shared by both the Session Call List and (later) the Dashboard — **not** a literal copy of `session-call-list.html`'s `.list-header`. Reconcile the two mocks by layering: global `AppHeader` (wordmark/breadcrumb/identity, per AC2) at the very top of every page, with the List's own `"This Session"` / call-count / `"+ Add call"` content (useful, real content from the mock) rendered as this page's own secondary strip *below* the AppHeader — the same pattern `analysis-dashboard.html` itself uses (`app-header` above its own page-specific `case-strip`).
2. **Two colors in the mocks are not DESIGN.md tokens.** `session-call-list.html`'s `.list-header .add-call` border uses `#3A4552`, and `analysis-dashboard.html`'s `.avatar` background uses `#263140`. Neither hex value appears anywhere in `DESIGN.md`'s token list. AC3 is explicit: "no ad hoc values." Do not copy these two literal hex values. Use the nearest real token instead — `var(--color-chrome-secondary)` (`#161C24`) is the correct substitute for the avatar background (see Task 3); for the `"+ Add call"` control, either omit the border (nothing in `DESIGN.md`'s component list defines a bordered-button treatment on chrome) or use `var(--color-chrome-text)` at reduced visual weight — a token-only design decision is required, and either resolution is acceptable as long as no untracked hex value is introduced.
3. **The wordmark's font-size in the mock is also not a DESIGN.md token.** `analysis-dashboard.html`'s `.app-header .brand` uses `font-size: 12px; letter-spacing: 0.04em` — 12px matches no typography role in DESIGN.md (`label`/`data-sm`/`data-inline` are 11px, `body` is 13px, `heading-sm` is 15px). The implementation uses the `label` role (11px/700/0.07em) instead, the nearest real token — code review (2026-08-15) confirmed this is the correct AC3-compliant substitution, called out explicitly here per that review's request.
4. **The mock's 380px `browser-frame` is a documentation-illustration artifact, not a layout target.** `session-call-list.html`'s outer `.browser-frame` is `width: 380px` (vs. `analysis-dashboard.html`'s `1120px`) purely for the mockup-gallery presentation — it is not a statement about the real target viewport. Per `EXPERIENCE.md` "Responsive & Platform," the real primary target is a desktop-width browser viewport (≥ ~960px, per AC5's own threshold), the same as the Dashboard. Do not build the List to look correct at 380px; build it for normal desktop widths and defer everything below ~960px to Story 2.7 (AC5).

### No backend calls in this story

`web-api` currently exposes exactly three endpoints (`web-api/app/routers/calls.py`): `POST /calls` (upload), `GET /calls/{call_id}/timeline`, `DELETE /calls/{call_id}`. **There is no `GET /calls` list endpoint** — confirmed by reading `web-api/app/db.py` (no `list_calls`/`get_calls` function exists) and `web-api/app/main.py` (only `calls_router` is registered). This is consistent with the product being a single-session tool with no persistent "my calls" concept across page loads (mock subtitle: "not saved after session ends") — the Session Call List's contents are expected to be built up client-side, one row at a time, as Story 2.2 wires real uploads. This story's zero-Calls empty state (AC4) is therefore not a loading/fetch state at all — it is simply the app's initial client-side state on every page load, with nothing to fetch. Do not add a `fetch`/`axios` call to any endpoint in this story.

Also note (for whoever picks up Story 2.2, not actionable here): `web-api/app/main.py` has no CORS middleware configured. A browser-based frontend calling `web-api` cross-origin (frontend on `:3000`, API on `:8000`) will need one of: FastAPI's `CORSMiddleware`, a Vite dev-server proxy, or serving both from one origin. Out of scope for this story since it makes zero API calls, but flagging it now so it isn't a surprise blocker for 2.2.

### Frontend stack & tooling (Context7-verified 2026-08-15)

- **Build tool: Vite + React + TypeScript.** Neither `ARCHITECTURE-SPINE.md` nor the PRD nor either UX doc names a build tool — this is this story's decision to make. `EXPERIENCE.md` Foundation line 17 states "No UI system inherited; this is a custom-built visual system" — do not add Tailwind, MUI, Chakra, or any component-kit dependency; DESIGN.md's token system is the entire visual system.
- Current `npm create vite@latest -- --template react-ts` output (verified via Context7 `/vitejs/vite`, 2026-08-15) pins: `react`/`react-dom` `^19.2.8` (matches the Architecture Stack pin exactly), `@vitejs/plugin-react` `^6.0.4`, `vite` `^8.x`, `@types/react` `^19.2.17`, `@types/react-dom` `^19.2.3`. The template's default lint tool is now `oxlint`, not ESLint — either is acceptable (nothing in this project's docs mandates one); pick whichever the scaffold produces rather than swapping it out for no reason.
- Testing (verified via Context7 `/vitest-dev/vitest`, 2026-08-15): `vitest`, `jsdom`, `@testing-library/react ^16.3.2`, `@testing-library/jest-dom ^6.9.1`, `@testing-library/user-event ^14.6.1`. Config lives inside `vite.config.ts` via `vitest/config`'s `defineConfig` (`test: { environment: 'jsdom', setupFiles: './src/setupTests.ts' }`) — no separate `vitest.config.ts` needed. Keep the setup file under `src/` (not the project root) so it falls inside `tsconfig.app.json`'s `include: ["src"]` boundary and gets type-checked by `tsc -b` like any other app file.
- **Node.js version is unpinned anywhere in this project.** The Architecture Stack table (`ARCHITECTURE-SPINE.md#Stack`) pins Python 3.13.15 exactly but has no frontend/Node.js row at all — use a current Active LTS release for both `frontend/Dockerfile`'s base image and `.github/workflows/ci.yml`'s `setup-node` step, and keep the two in sync with each other.
- **Docker serve pattern** — no precedent exists in this repo (every prior Dockerfile is Python/`pip install`). A reasonable minimal pattern: build stage `FROM node:<LTS>-alpine`, `npm ci && npm run build`; runtime stage also `node:<LTS>-alpine`, `npm install -g serve`, `COPY --from=build /app/dist ./dist`, `CMD ["serve", "-s", "dist", "-l", "3000"]`. This is a reasonable, low-ceremony choice consistent with AD-18's "no dedicated production infrastructure" framing — an nginx-based static-serve setup is a defensible alternative but adds config surface this single-machine, no-scale deployment doesn't need.

### DESIGN.md token transcription (Task 2)

Transcribed verbatim from `DESIGN.md`'s YAML frontmatter (`_bmad-output/planning-artifacts/ux-designs/ux-AIVoiceSentimentAnalyzer_v1-2026-08-10/DESIGN.md`, lines 10–82). Only the tokens this story's components actually consume are called out below as required; transcribing the **full** set now (including the sentiment/badge/timeline tokens this story doesn't use yet) is worth doing in the same pass since it's cheap and every later Epic 2 story needs the same file — do not re-derive it piecemeal story by story.

Required for this story's components (`AppHeader`, `SessionCallList` empty state):
- Colors: `--color-chrome: #0B0F14`, `--color-chrome-secondary: #161C24`, `--color-chrome-text: #B9C3CC`, `--color-chrome-text-strong: #E7ECF1`, `--color-bg: #F3F5F7`, `--color-panel: #FFFFFF`, `--color-border: #D8DEE4`, `--color-border-subtle: #EEF1F3`, `--color-text: #12181F`, `--color-text-dim: #5B6672`, `--color-text-faint: #6E7686`, `--color-text-label: #5F6B77`, `--color-focus-ring: #0B0F14`, `--color-focus-ring-on-chrome: #E7ECF1`.
- Typography roles needed: `label` (11px/700/uppercase/0.07em), `heading-sm` (15px/700), `data-inline` (monospace, 11px/400), `body` (13px/1.45 line-height, system font stack).
- Spacing scale: `--space-1: 4px` through `--space-8: 18px` (the full 8-step scale; `panel-padding` = `--space-8`, `row-padding` = `--space-5`).
- Shape: `--radius-sm: 2px`, `--radius-md: 3px`, `--radius-lg: 4px`, `--radius-full: 9999px`.

Also transcribe (not consumed until later Epic 2 stories, but part of the same one-time file): `negative`/`mixed`/`positive`/`neutral-signal`/`low-confidence`* sentiment colors, `panel-subtle`, `negative-bg`/`negative-border`, `data`/`data-sm` typography, `heading-md`. Full values are in `DESIGN.md` lines 10–82 — read the file directly rather than trusting a second-hand re-transcription here for the tokens this story doesn't exercise.

### Architecture compliance (non-negotiable)

- **AD-18** — this story's entire Docker/compose scope is "make the already-reserved `frontend` service in `docker-compose.yml` real," not a new service or deployment target. No cloud config, no GPU assumption.
- **AD-7** — the frontend must never call `ml-service` directly (it isn't reachable from the frontend at all per the container diagram); all backend calls go through `web-api`. Not exercised in this story (zero backend calls), but the constraint should shape how any future API-calling code in Story 2.2+ is structured (a single API-client module hitting `web-api`'s base URL only).
- **AD-21** — every module needs independently runnable tests (Task 7) and CI lint+test (Task 6); this story is what extends that baseline to a third language/toolchain (Node/Vite) alongside the existing two Python services.
- **PRD §2.3 / §10** — no auth, no accounts, no persistent storage guarantee; the analyst identity in the header is a hardcoded placeholder, not a real identity system, and nothing here should imply otherwise (matches EXPERIENCE.md Voice and Tone's "no hype/no false claims" discipline extended to the UI shell itself).

### What NOT to build in this story

- No real file upload, drag-and-drop, or `web-api` integration of any kind — Story 2.2.
- No call-row rendering, `badge-dot`, sentiment/confidence display — there's no data source until Story 2.2, and no design for it needed until then.
- No Analysis Dashboard, no routing/navigation library — Story 2.4 (Dashboard) and its own navigation needs come later; adding `react-router-dom` now with nothing to route to is premature.
- No delete UI/`confirm-dialog` — Story 2.3.
- No responsive/narrow-viewport handling — Story 2.7 (AC5 explicitly excludes it here).
- No CORS middleware change to `web-api` — flagged for Story 2.2, not actionable here (zero API calls in this story).

### Testing Standards

- Vitest + `@testing-library/react`, `jsdom` environment (AD-21 — independently runnable: `cd frontend && npm test` with no other service running).
- Test what a screen reader / keyboard user would perceive (text content, focusable elements, absence of illustration nodes) — not pixel-level style assertions; `jsdom` has no real layout engine, so anything requiring actual rendered geometry (e.g. verifying the 960px breakpoint) is out of reach for this story's test tooling and isn't needed yet (AC5 defers responsive behavior to 2.7 anyway).
- CI (`.github/workflows/ci.yml`) must run `npm test` (non-watch) and `npm run build` on every push, mirroring the existing `web-api`/`ml-service` job shape.

### Project Structure Notes

- This is the first real code under `frontend/` — `frontend/README.md` is the only existing file (placeholder, per Story 1.1). All structure decisions here become the baseline for Stories 2.2–2.7.
- New: `frontend/package.json`, `frontend/vite.config.ts`, `frontend/tsconfig.json` (+ node variant if the TS template splits it), `frontend/index.html`, `frontend/src/setupTests.ts`, `frontend/src/main.tsx`, `frontend/src/App.tsx` (+ `App.test.tsx`), `frontend/src/index.css`, `frontend/src/styles/tokens.css`, `frontend/src/components/AppHeader.tsx` (+ `.css`, `.test.tsx`), `frontend/src/pages/SessionCallList.tsx` (+ `.css`, `.test.tsx`), `frontend/Dockerfile`, `frontend/.dockerignore` (exclude `node_modules`).
- Modified: `frontend/README.md` (update from "No implementation yet" to reflect this story), `docker-compose.yml` (remove `frontend.profiles`), `.github/workflows/ci.yml` (new `frontend` job).
- No changes anywhere under `web-api/` or `ml-service/` — this story is entirely `frontend/`-internal plus the two shared infra files (`docker-compose.yml`, `ci.yml`) every prior story that touched deployment/CI has also edited.
- **CSS naming convention (code review, 2026-08-15):** every component uses BEM-lite class names — `block__element` (e.g. `app-header__crumb`, `session-strip__add-call`), no modifier classes needed yet. No build-time enforcement (no stylelint or equivalent configured); follow this convention by hand in Stories 2.2–2.7.

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 2.1: Web Console Frontend Foundation & Session Call List Shell] (lines 315–330, AC text + Traceability)
- [Source: _bmad-output/planning-artifacts/epics.md#Story 2.2: Call Upload & Processing-Status Feedback] (lines 332–350, confirms upload/list-population logic is 2.2's scope, not 2.1's)
- [Source: _bmad-output/planning-artifacts/architecture/architecture-AIVoiceSentimentAnalyzer_v1-2026-08-10/ARCHITECTURE-SPINE.md#AD-18 Deployment envelope] (lines 156–160)
- [Source: ARCHITECTURE-SPINE.md#AD-7 Model serving boundary] (lines 75–89, container diagram — frontend only ever talks to `web-api`)
- [Source: ARCHITECTURE-SPINE.md#AD-21 CI, testing, and logging baseline] (lines 174–178)
- [Source: ARCHITECTURE-SPINE.md#Stack] (lines 188–204 — React 19.2.8 pin; confirms no Node.js version is pinned anywhere)
- [Source: ARCHITECTURE-SPINE.md#Structural Seed] (lines 231–246 — `frontend/` source-tree placement)
- [Source: _bmad-output/planning-artifacts/prds/prd-AIVoiceSentimentAnalyzer_v1-2026-08-10/prd.md#2.3 Key User Journeys] (no-auth confirmation)
- [Source: _bmad-output/planning-artifacts/ux-designs/ux-AIVoiceSentimentAnalyzer_v1-2026-08-10/DESIGN.md] (full file read — frontmatter token system lines 10–82; Components lines 221–237; Do's and Don'ts lines 239–250)
- [Source: _bmad-output/planning-artifacts/ux-designs/ux-AIVoiceSentimentAnalyzer_v1-2026-08-10/EXPERIENCE.md] (full file read — Foundation line 17 "no UI system inherited"; Information Architecture lines 21–34; Responsive & Platform lines 36–44; Component Patterns lines 58–69; Interaction Primitives lines 84–90; Accessibility Floor lines 92–99)
- [Source: _bmad-output/planning-artifacts/ux-designs/ux-AIVoiceSentimentAnalyzer_v1-2026-08-10/mockups/session-call-list.html] (full file read — `.list-header` structure, `#3A4552` ad hoc value, `380px` `.browser-frame` illustration width)
- [Source: _bmad-output/planning-artifacts/ux-designs/ux-AIVoiceSentimentAnalyzer_v1-2026-08-10/mockups/analysis-dashboard.html] (lines 65–77, 202–205 — the actual `.app-header` markup/CSS this story's `AppHeader` is built from; `#263140` ad hoc avatar value)
- [Source: web-api/app/main.py] (full file read — confirms no CORS middleware exists)
- [Source: web-api/app/routers/calls.py, web-api/app/db.py] (full file read — confirms no `GET /calls` list endpoint and no `list_calls`/`get_calls` function exist)
- [Source: frontend/README.md] (current placeholder content, to be updated)
- [Source: docker-compose.yml] (current `frontend` service block — `profiles: ["full"]` to be removed)
- [Source: .github/workflows/ci.yml] (current two-job shape, mirrored for the new `frontend` job)
- [Source: web-api/Dockerfile] (existing single-service Dockerfile pattern this story's `frontend/Dockerfile` is styled after, adapted for a two-stage Node build)
- [Source: Vite official docs, retrieved via Context7 (`/vitejs/vite`), 2026-08-15 — `create-vite` react-ts template's current package.json/vite.config.ts output, exact current dependency versions]
- [Source: React official docs/source, retrieved via Context7 (`/react/react`), 2026-08-15 — React 19 `createRoot`/`StrictMode` canonical entry pattern]
- [Source: Vitest official docs, retrieved via Context7 (`/vitest-dev/vitest`), 2026-08-15 — jsdom environment config, `@testing-library/react` dependency versions]

## Dev Agent Record

### Agent Model Used

Claude Sonnet 5 (claude-sonnet-5)

### Debug Log References

- `npm create vite@latest tmp-scaffold-vsa -- --template react-ts` — scaffolded outside `frontend/` (non-empty dir), then relevant files moved in and demo boilerplate (counter `App.tsx`/`App.css`, `assets/react.svg`/`vite.svg`/`hero.png`, `public/icons.svg`) discarded rather than kept.
- `cd frontend && npm install` — 118 packages, 0 vulnerabilities.
- `npx vitest run src/components/AppHeader.test.tsx` (RED, pre-implementation) — `Failed to resolve import "./AppHeader"`, confirming the test was written before the component existed.
- `npx vitest run src/components/AppHeader.test.tsx` (GREEN, first implementation pass) — 2 of 4 tests failed with `TestingLibraryElementError: Found multiple elements...`, root-caused to `@testing-library/react`'s automatic per-test `cleanup()` never firing because Vitest globals are off (this project intentionally uses explicit `import { describe, it, expect } from 'vitest'`, not `test.globals: true`) — fixed by adding an explicit `afterEach(cleanup)` to `src/setupTests.ts`. Re-run: 4/4 passed.
- `npx vitest run src/pages/SessionCallList.test.tsx` (RED, pre-implementation) — import-resolution failure as expected.
- `npx vitest run src/pages/SessionCallList.test.tsx` (GREEN, first implementation pass) — 1 of 4 tests failed: `getByText(/This Session/i)` matched two elements because the case-insensitive regex also matched the substring "this session" inside the subtitle copy ("...analyzed **this session**..."). Fixed by switching the assertion to `getByRole('heading', { name: /this session/i })`, which only matches the `<h1>`.
- `npx vitest run src/App.test.tsx` (RED then GREEN) — RED confirmed pre-`App.tsx`; GREEN passed on first try after fixing `main.tsx`'s import (see next line).
- `npm run build` — first run failed: `error TS2613: Module '"...App"' has no default export` — `main.tsx` (from the scaffold) used `import App from './App.tsx'` (default import) but this story's `App.tsx`/`AppHeader.tsx`/`SessionCallList.tsx` all use named exports for consistency. Fixed `main.tsx` to `import { App } from './App.tsx'`. Re-run: builds clean (`tsc -b && vite build`, 20 modules, `dist/index.html` + JS/CSS bundles).
- `npm test` (full suite) — 3 files, 10 tests, all passing.
- `npm run lint` (`oxlint`) — clean, exit code 0.
- `docker compose config --quiet` — valid.
- `docker compose build frontend` — built successfully (`node:22-alpine` build stage → `node:22-alpine` + `serve@14` runtime stage).
- `docker compose up -d frontend` + `curl http://localhost:3000/` — `HTTP_STATUS:200`, correct `index.html` (title "Voice Sentiment · Console", hashed asset references) returned. Both the JS bundle and CSS bundle assets were separately curled and also returned `200`. Container stopped and removed afterward (`docker compose stop frontend && docker compose rm -f frontend`) — this story's own verification, not something left running.

### Completion Notes List

- **All 6 ACs implemented and verified**: AC1 (no-login landing into Session Call List) — `App.test.tsx`; AC2 (three-part App header) — `AppHeader.tsx` + `AppHeader.test.tsx`; AC3 (token-sourced only) — every color/typography/spacing/radius value in `AppHeader.css`/`SessionCallList.css`/`index.css` is a `var(--...)` reference into `src/styles/tokens.css`, transcribed verbatim from `DESIGN.md`'s frontmatter; AC4 (zero-Calls plain prompt, no illustration) — `SessionCallList.test.tsx` asserts both the prompt text and the absence of any `<img>`/`<svg>` node; AC5 (no responsive fallback built) — intentionally not implemented, deferred to Story 2.7 as directed; AC6 (docker-compose frontend pipeline, no new deployment target) — `frontend/Dockerfile` + `docker-compose.yml`'s `profiles` removal, verified end-to-end against a real running Docker daemon (build + up + curl), not just `docker compose config` static validation.
- **Known spec gap resolved as directed**: built the `AppHeader` (wordmark/breadcrumb/identity) from `mockups/analysis-dashboard.html`'s actual `.app-header` markup, not `mockups/session-call-list.html`'s incomplete `.list-header` — and layered the List's own "This Session"/"+ Add call" content as a page-specific `session-strip` below the shared `AppHeader`, per the story's Dev Notes reconciliation. Also avoided both of the mocks' undocumented ad hoc hex colors (`#3A4552` add-call border, `#263140` avatar background), using `var(--color-chrome-secondary)` for the avatar and no border on `+ Add call` instead.
- **No backend calls made**: confirmed no `fetch`/`axios` call exists anywhere in `frontend/src/` — the Session Call List's zero-Calls state is purely client-side initial state, per the story's "No backend calls in this story" Dev Note. `web-api` was not touched.
- **No router library added**: `App.tsx` renders `<AppHeader />` + `<SessionCallList />` directly, no `react-router-dom` dependency — per the story's explicit YAGNI guidance (Dashboard navigation is Story 2.4).
- **Two real bugs found and fixed during implementation, beyond what the story anticipated** (both documented above in Debug Log References): (1) Vitest without `globals: true` needs an explicit `afterEach(cleanup)` in the setup file, or `@testing-library/react`'s auto-cleanup never fires and state leaks across tests within a file; (2) a case-insensitive substring text-matcher can accidentally match a heading's own copy inside a *different* element's prose (`getByText(/This Session/i)` matched the subtitle "...analyzed this session...") — fixed by asserting on `getByRole('heading', ...)` instead. Neither was anticipated by the story's Dev Notes; both are now reflected in the actual test suite.
- **`vitest` pinned to `^4.1.6`** (the newest version Context7 listed for `/vitest-dev/vitest` at story-creation time) rather than `latest`, consistent with this story's stated preference for confirmed-current-at-implementation versions over floating tags.
- **Docker daemon was available in this environment** (unlike Story 1.1's sandbox) — Task 8's conditional Docker verification step was fully exercised, not skipped/noted-as-unavailable.
- **Code review (2026-08-15):** 3-layer review (Blind Hunter, Edge Case Hunter, Acceptance Auditor) against the uncommitted diff. 14 unique findings after dedup; 5 dismissed after empirical verification (a full `docker compose up` — all 4 default services, no `--profile` flag — was actually run and confirmed working end-to-end, not just asserted; `@types/node` confirmed as standard `create-vite` scaffold output, not cruft; the `node:22-alpine` vs. `nginx:alpine` runtime-image choice was already a documented, deliberate tradeoff, not a defect); 9 `patch` findings applied, re-verified (`npm test` — 11/11 passing, `npm run build`, `npm run lint`, Docker image rebuilt and re-curled — all clean). No `decision-needed` or `defer` findings. See "Review Findings" above for the itemized list and fixes.

### File List

**Created:**
- `frontend/package.json`
- `frontend/package-lock.json`
- `frontend/vite.config.ts`
- `frontend/tsconfig.json`
- `frontend/tsconfig.app.json`
- `frontend/tsconfig.node.json`
- `frontend/index.html`
- `frontend/.gitignore`
- `frontend/.oxlintrc.json`
- `frontend/.dockerignore`
- `frontend/Dockerfile`
- `frontend/public/favicon.svg`
- `frontend/src/main.tsx`
- `frontend/src/App.tsx`
- `frontend/src/App.test.tsx`
- `frontend/src/index.css`
- `frontend/src/setupTests.ts`
- `frontend/src/styles/tokens.css`
- `frontend/src/components/AppHeader.tsx`
- `frontend/src/components/AppHeader.css`
- `frontend/src/components/AppHeader.test.tsx`
- `frontend/src/pages/SessionCallList.tsx`
- `frontend/src/pages/SessionCallList.css`
- `frontend/src/pages/SessionCallList.test.tsx`

**Modified:**
- `frontend/README.md` — replaced the "No implementation yet" placeholder with real setup/dev/test/build/Docker instructions.
- `docker-compose.yml` — removed the `frontend` service's `profiles: ["full"]` gate; updated its comment to "Functional as of Story 2.1...".
- `.github/workflows/ci.yml` — added a third `frontend` job (checkout, Node 22 setup with npm cache, `npm ci`, lint, test, build), mirroring the existing `web-api`/`ml-service` job shape.

## Change Log

- 2026-08-15: Story created via create-story workflow. Epic 2 moved to `in-progress` (first story of the epic).
- 2026-08-15: Story 2.1 implemented — `frontend/` scaffolded (Vite + React 19.2.8 + TypeScript); DESIGN.md's full token system transcribed into `src/styles/tokens.css`; shared `AppHeader` (wordmark/breadcrumb/analyst identity) built from `analysis-dashboard.html`'s actual markup per the story's mock-vs-spec reconciliation; `SessionCallList` zero-Calls shell; frontend Docker build/serve pipeline wired into `docker-compose.yml` (profile gate removed, verified end-to-end against a live Docker daemon); CI gained a third `frontend` job. 3 test files, 10 passing tests (Vitest + Testing Library); build and lint clean. All 8 tasks and 6 ACs complete. Status moved to `review`.
- 2026-08-15: Code review (3-layer adversarial + edge-case + acceptance-audit) run against the implementation. 9 `patch` findings, all fixed: AppHeader avatar swatch fully tokenized (including a 9px-below-the-11px-floor font-size fix), breadcrumb now true-centered via CSS grid (was `justify-content: space-between`), a max-width/ellipsis guard and an empty-string fallback guard added to the breadcrumb (both latent issues in the prop API Story 2.4 will extend), `serve` pinned to an exact version in the Dockerfile, and three story-documentation gaps closed (stale `vitest.setup.ts` references, an undocumented third mock-vs-token gap, an undocumented BEM naming convention). 5 findings dismissed after empirical re-verification (full default `docker compose up` re-tested and confirmed working; `@types/node` confirmed as standard scaffold output). Full suite re-verified after fixes: 11/11 tests passing, build clean, lint clean, Docker image rebuilt and re-curled successfully. Status moved to `done`.
