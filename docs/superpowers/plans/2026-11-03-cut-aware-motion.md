# Cut-aware motion implementation plan

User authorized autonomous development; execute in this session.

Goal: expose fast hold-until-next-primary-cut and subtle cinematic motion through existing per-beat design and shared native/web scenes. Caption/English integration remains next independent task; no release bump here.
Architecture: scene builder receives original draft for measured primary segment boundaries. New move snap_to_cut clips at first actual primary cut after beat start; ramp max0.30s then130%hold. A later enabled motion starts a new interval, never overlapping. Cinematic uses centered100→105% over selected beat. Preserve old modes/guard semantics.
Files: kinetic_scene.py (scene resolution), kinetic_text.py (draft context), kinetic_ui.py (choices), test_kinetic_scene.py (behavior), test_kinetic_design.py (receipt roundtrip).

Constraints: no new camera selection/source edits; no fabricated cuts; absent/ambiguous/gapped primary track rejects hold mode. Source/media/owner/backup guards unchanged. Native keyframes and report/browser share all points. No headroom guarantee for130%.

Review focus: cut inside caption, final-shot boundary, adjacent motions/disabled beats, video gaps/overlays, modified saved plans and source hash.

- [x] Write failing scene tests: first cut even when caption crosses it; hold after caption end; no source mutation; final shot; no gap/ambiguous track; later motion truncation.
- [x] Implement scenes(blocks,draft=None), require original primary-video boundaries for snap_to_cut; validate nonoverlap and resolve clip duration.
- [x] Add cinematic centered105% behavior test and implementation, preserve existing keep/smooth semantics.
- [x] Pass draft from renderer; add design-save/prepare roundtrip regression and UI choices; verify shared report/native points.
- [ ] Run focused/full Python and Node tests; independent review; real draft offline render then native copy only when editor guard permits.
- [ ] Update architecture/tasks/evidence; no automatic publication before new QA.
