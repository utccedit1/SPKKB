# Editorial decisions and complete-clip quality Implementation Plan

> **For agentic workers:** execute task-by-task with test-first changes and independent final review.

**Goal:** improve complete short-story selection, semantic Super Text, opt-in native camera choice, whole-clip quality reports, and real provider validation.
**Architecture:** retain caption-grounded story/owned result guards. Pure narrative/phrase/quality contracts feed existing planning and finishing; camera choice is explicit and preserves selected speech audio. No invented words/times, no timeout retry or fake provider fallback.
**Tech Stack:** existing Python3.9, Node, CapCut drafts, local FFmpeg/Vision and existing Gemini/UTCC routes.
**Spec:** user's authorized five priorities in current conversation; tasks P3.29–33.

## Global Constraints
Preserve original/manual and source media. Work in copies through existing import guard. Secrets remain account-owned outside source. Provider failure is a failure. Sampled visual evidence is not continuous tracking or human listening.

## Review Focus
- Bare coherent approvals lacking grounded beginning/development/payoff cannot pass enhanced mode.
- Compound splits, negation loss, dangling fragments and unreadable rows must fail conservatively.
- Camera material reused across cuts must be cloned before per-shot selection; original audio selection retained.
- Missing vision/media or unsupported nested timing leaves original camera and explicit uncertainty.
- Gap/readability findings need actual intervals; heuristic pacing must not be called objective failure.

### P3.29 narrative completeness
- [x] Test strict grounded narrative schema red→green in cli_highlight_coherence; opt in on finishing/highlight route and retain review evidence.
- [ ] Exercise actual long-source planning with a configured authorized provider; do not substitute previously reviewed ranges.
### P3.30 semantic phrase quality
- [x] Test shared editorial_quality.review(source,rows,form) reasons; integrate into local and AI exact-source choices without rewriting speech.
### P3.31 camera and motion decisions
- [x] Test opt-in multicam selection candidates at existing shot boundaries, preservation of chosen audio/material ownership, and safe fallback.
- [x] Integrate explicit option into saved CLI finishing/UI; local visual observation chooses supported camera when evidence improves framing, no random alternation.
### P3.32 complete clip checks
- [x] Test pure editorial_checks.report(draft,kinetic_report) gaps/readability/evidence classifications; persist and surface findings before import.
### P3.33 provider/end-to-end acceptance
- [x] Verify account-owned provider readiness and errors/cancellation/late-result guards; live calls only with authorized configured account.
- [ ] Full regression/Node checks/review, fresh long→short preview/native import/export, source hash and audio checks; update evidence and remaining limits.

## November 5 release status
Source/local contracts and failure paths shipped1.5.70. Fresh successful provider planning remains open (Gemini503; UTCC credits exhausted); native acceptance of an automatically changed camera remains open. Existing90.84s unchanged visual trial parameters match earlier native export. Full804Python/Node5/review/bundle/signature/private scan/public download/updater verified; see audits/release-1.5.70/report.md. Do not mark remaining live acceptance complete.
