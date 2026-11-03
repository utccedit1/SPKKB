# P3.13 — Local face-assisted framing and fine adjustment

Goal: use actual selected-camera samples to propose speaker/text placement, retaining review and precise manual controls. No automatic editorial quality or face identity claim.

- [x] Closed bounded per-beat composition geometry (video x/y, scale; text x/y) shared by native/render/web, persisted and validated through existing revision receipts. Scene merge only for identical geometry/motion. Keep default output unchanged.
- [x] Local macOS Vision face rectangle adapter, no external service/model install. Sample selected-camera start/middle/end within original cue times using existing source mapping; require single confident face and consistency across samples. Uncertain/multiple/no-face leaves original framing. Save only geometry/coverage in owned plan; no face crops or biometric identity.
- [x] New cancellable/idempotent kinetic_assist operation consumes owned full-plan receipt, source/media/profile checks, proposes geometry for enabled beats, server-renders before a new receipt. Existing cuts/cameras/audio remain. No camera selection inference in this slice.
- [x] UI assist button, bounded geometry fields/reset, dirty/busy guards; use same clock and preserve proxy. Tests source-only/time/owner/cancel, uncertain fallback, geometry/motion/native-report parity; full regression, independent review and actual BRAND sample. No Git/build/release.

- [ ] Latest native CapCut import/playback and human listening/export QA: representative native import/playback completed on1103 (1); full export pending existing CapCut queue, human listening not signed off. Source tests and approximate preview do not satisfy this check.

- [ ] Real-account UI8884 assistance/revision/Prepare QA, then conditional reviewed source Git upload authorized by user. No release requested.
