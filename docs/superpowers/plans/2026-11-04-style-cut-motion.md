# P3.23 Style cut motion implementation plan

Goal: apply motion recipes to the final source-grounded phrase design, holding emphasis zoom to the next existing camera cut.
Architecture: compact measured phrases before applying recipes; use existing snap_to_cut renderer and native guards. Original/manual and clean retain their behavior. No new camera cuts, tracking or source changes.
Tech stack: Python 3.9, existing native/web scene renderer.
Spec: current user editing feedback and TASK_PHASES P3.21–22.

Review focus: matched phrase pairs, disabled beats, original/manual preservation, missing video guard, saved-plan/Prepare equality.

- [x] Add failing style-to-scene test: impact matched pair reaches 130% by .30s and holds beyond text until existing cut; clean/original stay unchanged.
- [x] Add service regression demonstrating final matched form receives recipe motion after compaction.
- [x] Apply recipes after compaction; update description to hold-to-cut; preserve source text, timing, font and all existing safety checks.
- [x] Run focused and full regression; record actual native QA limitations separately from source verification.

Native follow-up: new1104(1) exported and16samples inspected. Found and fixed microsecond edge duplication regression; final685tests passed.
