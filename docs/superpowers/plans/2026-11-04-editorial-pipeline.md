# P3.25–P3.28 editorial pipeline implementation plan

Goal: make emphasis selective, select grounded semantic phrase pairs, check placement over saved motion, and exercise an undecorated long-source-to-short pipeline.
Architecture: independent pure editorial scoring and phrase selection feed existing owned kinetic plans; denser local vision evidence checks image-space placements under shared scene transforms without reframing source. Reuse existing CLI narrative selection/rendering and guard/receipts; no invented words/times or new transcription.
Spec: user authorized all four priorities: rhythm/rest, face/hand/space throughout zoom, semantic Super designs, complete short from undecorated source.
Constraints: original/manual stays unchanged; all speech captions retained; no forced camera shift/PiP; unsupported vision/motion reports uncertainty; no credential publication; no automatic POST retry. Native visual/audio checks distinguish decoded output from human listening.
Review focus: ordinary/repeated beats, disconnected short phrases, negative/comparative speech, camera cuts within sample spans, motion carrying past text, source hashes and owned saved revisions.

- [x] P3.25: add source-grounded editorial score/reason and style-specific selection spacing; preserve caption text/timing and enabled manual mode; tests ordinary/repeated/high-value beats and source invariants.
- [x] P3.26: replace 3-frame static-only assist with bounded denser sampling over actual rendered text/motion intervals and selected-camera changes; detect face and hands when supported, retain frame, flag uncertain intervals; tests transformed rectangles/obstruction/missing observations and persistence.
- [x] P3.27: replace project-specific phrase table with general grounded semantic pair selection and role-based forms; tests unfamiliar questions/definitions/contrast/numbers/negation and measured timing conservation.
- [x] P3.28: connect short assembly to current decoration stages through reviewable owned results using existing source captions, story validation and source/media guards; test undeccorated long source to90s staging, full preview/Prepare, then native export and inspect all subtitle/zoom boundaries.
- [x] Run full regression, independent review, update task/architecture/audit evidence; report actual remaining uncertainty without claiming human-quality guarantee.

Source/local/native acceptance complete in checked scope: full764 tests/Node5/review45; automatic90.84s native export decoded and36samples inspected, peak−4.0. Original source unchanged. See audit report for exact evidence. Optional paid-provider response/full human listening/continuous tracking remain unverified; narrative spans previously agent-reviewed.
