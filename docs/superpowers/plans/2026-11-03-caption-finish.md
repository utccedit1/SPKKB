# P3.22 — measured one-line captions and English display

User authorized continued autonomous development.
Goal: two explicit opt-in whole-clip controls, retained in owned saved plans and reproduced identically in preview/Prepare. No source project mutation or new transcription.
Architecture: caption_phrase_anchors remains separate from word karaoke. Alignment gets opt-in caption phrase output, with trusted native words or local supplied-text raw alignment (bounded29s/400tokens); strict word mode unchanged. caption_finish validates complete source-text/time coverage, clones only speech captions, preserves source text and applies limited English display aliases. Render styles these captions even if prior choice keep (documented UI behavior), measures selected-font width and fails instead of silently emitting a long line. Super aliases applied before geometry; changed units skip karaoke spans explicitly.
Constraints: default behavior unchanged; AI snippet route rejects new whole-clip options; confidence gates not lowered; no external AI call/model download; missing alignment stops with actionable error. Preserve owner/project/source/media guards and cancellation.
Review focus: malformed/missing phrase coverage; UTF16 English lengths; shared speech/title materials; alias+karaoke interaction; revision/Prepare reuse without realignment; model budget/no cached model; portrait width.

- [x] Red tests for display aliases/unchanged ambiguous words, clone-only speech, time/text coverage rejection and width rejection.
- [x] Implement caption_finish pure validation/application plus renderer report; fit uses selected font, default7.5%canvas height.
- [x] Red alignment tests ensure weak internal words can form measured phrases but strict word mode remains rejected; explicit bounded raw mode.
- [x] Wire settings/whole-plan alignment persistence/Prepare, reject snippet scope; UI checkboxes/summary/dirty handling.
- [x] Full Python3.9/Node + independent review; real project local service pipeline and native testcopy/export when free.
- [x] Update architecture/tasks/evidence, source-only until native QA; no automatic new release.

Follow-up: concept/support rows, coveringphrase reveals, DBHeaventBlk default, knowncompound boundary protection and conservativepercentagedisplay verified on4Nov. Native and HTTP checks supersede initial lockblock; fullhumanlistening remainsunverified.
