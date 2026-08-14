# Review: Versions & Reality-Check Lens — ARCHITECTURE-SPINE.md

**Reviewer lens:** Was every named technology/library/model/dataset/version claim in the spine actually web-researched or reality-checked this run (traceable in `.memlog.md`), or asserted from training data? Independent web verification performed where the memlog's own trail looked thin or suspicious.

**Date of review:** 2026-08-11 (independent web searches run today)

---

## Method

1. Enumerated every named technology/library/model/dataset/version claim in the Stack table and every AD.
2. Cross-checked each against `.memlog.md`'s single `(version)` entry (the only line explicitly framed as "Verified current (web search, Aug 2026)") and the scattered `(decision)`/`(change)` entries that cite research.
3. Independently web-searched anything either (a) absent from the memlog's verification trail entirely, or (b) present but flagged with hedging language ("no fixed version pinned," "not independently confirmed") worth spot-checking against the live web.

---

## Findings

### 1. [HIGH] WhisperX version claim is stale — a fixed version *does* exist, contradicting the memlog's own verification

- **Spine (Stack table, line 175):** "WhisperX | latest — track latest, actively maintained, no fixed version pinned..."
- **Memlog (`(version)` entry, line 28):** "WhisperX actively maintained (releases through mid-Jul 2026, no fixed version number, wraps faster-whisper + pyannote)"
- **Independent web check (today):** WhisperX on PyPI has a normal, fixed-version release history — 44 versions listed, most recent being `3.8.7rc1`, `3.8.6` (stable, ~May 2026), `3.8.5` (~Apr 2026), etc. This is a conventional semver-tagged package, not an unversioned rolling dependency.
- **Verdict:** The memlog's own web-search-labeled claim ("no fixed version number") is incorrect, and the spine propagated that error verbatim into the Stack table. This is exactly the failure mode the review brief called out as worth spot-checking, and it reproduced. Every other Stack row got a real pinned version (or an explicit "latest stable" placeholder for genuinely fast-moving libs); WhisperX should too — pin to `3.8.6` (or whatever is current at implementation time) rather than asserting no version exists.
- **Fix:** Update Stack table row to a real pinned version and correct/remove the "no fixed version pinned" framing; the license-ambiguity caveat (BSD-2 vs BSD-4) is fine to keep as-is.

### 2. [MEDIUM-HIGH] Python 3.12 has no verification trail at all, and independent check suggests it's a stale pin for a greenfield 2026 project

- **Spine (Stack table, line 171):** "Python | 3.12 (pyannote.audio 4.0 requires 3.10+)"
- **Memlog:** No entry anywhere verifies the Python version choice. It is absent from the single `(version)` web-search line (which covers FastAPI, React, faster-whisper, WhisperX, transformers, PyTorch, RQ, Redis, SQLite/SQLAlchemy — but not Python itself). The Stack table's own parenthetical only checks a *minimum* bound (pyannote.audio 4.0 needs 3.10+) — it never checks whether 3.12 is still the sensible *current* pin, which is a different question.
- **Independent web check (today):** As of Aug 2026, Python 3.13.15 and 3.14.7 are both current, actively-supported stable releases (3.14 released Oct 2025), and 3.15.0rc1 already shipped Aug 4, 2026. Python 3.12 (released Oct 2023) is past its bugfix-support window and is now in security-fix-only maintenance under the standard 5-year EOL cycle.
- **Verdict:** This reads as asserted from training data (3.12 was the "current-ish" version in the assistant's training window) rather than reality-checked. A greenfield project starting today choosing a version that's already in its security-only tail — when 3.13/3.14 exist, are stable, and are what pyannote.audio 4.0/PyTorch 2.13/transformers 5.x actually get tested against upstream — is worth an explicit go/no-go rather than a silent default.
- **Fix:** Either re-verify 3.12 is intentional (e.g., a specific dependency wheel/CI constraint) and say so, or bump the pin to 3.13/3.14 and update the pyannote.audio compatibility note accordingly.

### 3. [MEDIUM] librosa/torchaudio "latest stable" has zero verification trail — same unpinned pattern that just failed on WhisperX

- **Spine (Stack table, line 179):** "librosa / torchaudio | latest stable — handcrafted acoustic-feature extraction..."
- **Memlog:** No `(version)` or web-search citation covers librosa or torchaudio specifically anywhere in `.memlog.md`. The entry exists only to justify the *license* choice (vs. openSMILE/Praat), not to confirm current version/API compatibility.
- **Verdict:** Not necessarily wrong — these are mature, stable libraries — but it's structurally the identical "unpin and assert liveness" pattern that Finding 1 just showed was inaccurate for WhisperX. Nothing here confirms librosa/torchaudio's current stable versions were actually checked rather than assumed. Lower risk than Finding 1 because these libraries are far more API-stable than WhisperX, but still an untraceable claim.
- **Fix:** A one-line web-verified version pin (or an explicit "checked, no pin needed because X" rationale) would close the gap cheaply.

### 4. [LOW / INFORMATIONAL] RQ 2.10.0 patch version not independently reproducible today, but memlog does carry a verification citation

- **Spine (Stack table, line 180) / Memlog (`(version)` line 28):** "RQ 2.10.0 (BSD, now officially supports Valkey too)"
- **Independent web check:** Confirmed RQ does officially support Valkey (>=7.2) per current docs — that part checks out. Could not independently reproduce the exact `2.10.0` patch number today; GitHub release-tag search surfaced only through `v2.8` in the visible results, which doesn't contradict 2.10.0 (release cadence is roughly monthly, so 2.9/2.10 landing between April and August 2026 is plausible) but doesn't confirm it either.
- **Verdict:** This one *does* have a traceable memlog verification step (unlike Findings 1–3), so it passes the core review bar ("was it checked this run"). Flagging only as a minor "couldn't fully reproduce" note, not a real defect.

### 5. [LOW / INFORMATIONAL] Model families and datasets are inherited citations, not re-verified this run — acceptable but worth naming

- Wav2Vec2/HuBERT/WavLM (AD-3), RoBERTa/DistilBERT (AD-19), CREMA-D and IEMOCAP (AD-4, AD-17) are all sourced by citation to "Technical Research §1.2/§3.4/§8.4" rather than a fresh web-search line in this run's memlog. No specific model checkpoint is pinned for any of them (e.g. no exact HuggingFace repo ID) — likely intentional deferral to implementation time, but it's not explicitly listed under the spine's "Deferred" section the way other unresolved specifics are.
- These are all long-established, stable names (Meta/Microsoft model families, decade-old benchmark datasets) — low risk of having changed or stopped existing, so this is not a "could be out of date" concern in practice, just a traceability note: the spine's own text (AD-14) is careful to distinguish `[VERIFIED]` vs `[RESEARCH FINDING]` vs plain assertion for the cloud-SER claim, but doesn't apply that same rigor to naming these model families.

---

## What checked out cleanly (independently reconfirmed today, not just trusted from the memlog)

- **FastAPI 0.141.1** — confirmed real, released July 29, 2026.
- **React 19.2.8** — confirmed real, released July 21, 2026.
- **faster-whisper v1.2.1** — confirmed current on PyPI, actively maintained.
- **transformers v5.14.1** — confirmed real, released July 16, 2026 (the major 4→5 version jump is real, not hallucinated — the memlog's caveat to re-verify Wav2Vec2/HuBERT/WavLM class import paths at implementation time is well-placed given the major-version risk).
- **pyannote.audio 4.0.7, Community-1, CC-BY-4.0** — confirmed real; 4.0.7 uploaded June 30, 2026; the memlog's mid-run `(change)` correction from the Technical Research's now-outdated "3.1 pipeline" to 4.0/Community-1 is a genuine, well-documented catch — good example of the process working as intended.
- **PyTorch 2.13** — roughly corroborated (release cadence consistent with 2.11 in March 2026 → ~2.13 by Aug 2026); memlog's own "2.14 imminent, recheck at implementation time" hedge is appropriate and doesn't need strengthening.
- **Redis 8.10, dual BSL/AGPLv3 licensing since May 2025** — confirmed accurate.
- **AD-3's license rejections** (openSMILE/eGeMAPS = research-only/commercial license required; Praat/parselmouth = GPLv3 copyleft) — independently confirmed accurate today, even though this specific claim is only traceable to inherited Technical Research citations rather than this run's memlog.

---

## Bottom line

The run's process was mostly sound — one real `(version)` web-search pass plus a genuine mid-run correction (pyannote 3.1→4.0/Community-1) shows real verification happened, and most Stack-table numbers independently reproduce. But the process had a blind spot: **the one entry the memlog flagged as unpinned-because-unversioned (WhisperX) turned out to actually have a normal versioned release the memlog missed**, and **Python's own version pin was never run through the same web-search pass at all**. Both should be re-checked before this spine is treated as implementation-ready.
