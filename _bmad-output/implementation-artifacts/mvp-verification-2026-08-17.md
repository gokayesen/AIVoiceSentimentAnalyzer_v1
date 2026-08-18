# Final MVP Verification — 2026-08-17

**Status: MVP READY — 3 Epics complete, no blockers.** Confirmed by Project Lead (2026-08-17).

Inspection-only pass performed after Epic 3's retrospective and `next-epic-prep-2026-08-17.md` approval, per Project Lead's explicit request: *"Before any further development, I want a final MVP verification only."* No code or planning artifacts were modified during the inspection itself; all runtime verification (Docker build/up, live pipeline test uploads, an offline-resilience stress test) was reversed/cleaned up before this report was written. This document, and the corresponding `deferred-work.md`/`sprint-status.yaml` updates, are the only artifacts produced as a result.

**This is not an Epic 4 authorization.** No new epic, story, sprint, or implementation work follows from this verification. `next-epic-prep-2026-08-17.md` remains the sole future-planning input; it is revisited only when a new product/development need is identified.

---

## Scope

Requested by Project Lead: git tracking status; test status across web-api/ml-service/frontend; docker-compose startup viability; end-to-end pipeline runnability and environment blockers; browser-only-unverifiable UX/AC items (esp. Epic 2); mismatches vs. PRD/UX/Architecture Spine/Epics/story ACs; any remaining actual blocker to MVP completeness.

## BLOCKER

None found.

## WARNING (new findings from this verification pass, logged in `deferred-work.md` under "Final MVP Verification (2026-08-17)")

- **W1** — `torch==2.13.0` has no macOS x86_64 (Intel) wheel; native (non-Docker) ml-service development/testing is unavailable on this class of host. Docker is the supported path and was fully verified. See `deferred-work.md`.
- **W2** — The acoustic classifier performs live Hugging Face Hub metadata calls per-Call at runtime, which is imprecise against AD-14's literal "never needs network access" claim. Verified functionally resilient (pipeline completes correctly with the Hub unreachable, via local cache) but adds latency when the network round-trip occurs. Logged as future architecture-hardening work, not an MVP blocker. See `deferred-work.md`.
- **W3** — `frontend/README.md` is stale, still describing Story 2.1's state, 6 stories out of date. Documentation debt; not to be rewritten unless explicitly requested. See `deferred-work.md`.

## KNOWN LIMITATION / DEFERRED (re-confirmed during this pass, not new — all already tracked)

- No real-browser validation exists anywhere in the project (Story 2.7's own disclosed gap: focus-ring rendering, 200% zoom reflow, `<960px` breakpoint firing — no automated-test equivalent under jsdom, never manually verified in a real browser).
- No `HF_TOKEN` configured in this environment — mono-path diarization degrades to unattributed for every mono Call (confirmed live), correct AD-1 graceful-degradation behavior; diarization itself was not exercised end-to-end by this pass.
- AD-11 duplicate-transcript-text on overlapping context-margin slices (observed directly in this session's own live test output) — matches the already-triaged, high-priority Next Epic Candidate item.
- `ACOUSTIC_SANITY_FLOOR` (0.15) still mathematically unreachable for the 4-class model — confirmed unchanged; correctly parked against AD-17/calibration work.
- Schema migration path and DB reliability bundle — both confirmed still absent/unaddressed; both already scoped in `next-epic-prep-2026-08-17.md` as "Must resolve before next epic," neither newly broken by this pass.
- No automated accessibility-regression tooling (axe-core/jest-axe) — already-known, Story 2.7's own deferred finding.

## VERIFIED

- **Git:** `frontend/`, `ml-service/`, `web-api/` fully tracked; no `node_modules`/`dist` tracked; working tree clean.
- **web-api tests:** 113/113 passed.
- **frontend tests:** 184/184 passed; `tsc -b && vite build` clean.
- **ml-service tests:** 136/136 passed (run inside the built Docker image; native install blocked per W1).
- **docker-compose build:** all 3 custom images (frontend, web-api, ml-service) build successfully from the current Dockerfiles, including all 3 model pre-fetch steps.
- **docker-compose up:** all 4 services (redis, web-api, ml-service worker, frontend) start and stay healthy; `web-api` `/docs` → 200, `frontend` `/` → 200.
- **End-to-end pipeline:** exercised live, twice. A synthetic silent-tone Call correctly completed with 0 segments. A real synthesized-speech Call ran the full chain (ingest → acoustic → transcript → text-sentiment → fusion) and produced a coherent, correct result including correct graceful degradation (`speaker_attribution_unavailable: true` with no `HF_TOKEN`).
- **AD-14 offline-inference claim:** functionally verified true (pipeline completes correctly with `huggingface.co` access blocked) — see W2 for the caveat on the claim's literal precision.
- **Cross-document consistency:** independent full-document cross-check (PRD's 16 FRs, all 21 ADs, DESIGN.md/EXPERIENCE.md, epics.md, all story ACs) against current source found no new mismatches beyond what the 3 epic retrospectives and deferred-work triage already document.
- **UX-DR18 breadcrumb click-to-return:** confirmed implemented (`App.tsx` → `handleReturnToList`).
- **NFR-5 (no unqualified accuracy claims):** grep-clean across `frontend/src`.

## Verdict

**3 Epics complete — MVP READY — no blockers.**
