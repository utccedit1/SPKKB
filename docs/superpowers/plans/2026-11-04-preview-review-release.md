# P3.24 preview review and P0.31 release implementation plan

Goal: make actual saved zoom intervals directly reviewable in full-clip preview and ship verified1.5.68.
Architecture: build review buttons from saved preview.scenes only; seek both source video and overlay clock together. Report current actual scene scale and end; clear review controls on invalidation. Preserve renderer/import semantics.
Tech stack: existing Python3.9, vanilla JavaScript, PyInstaller and verified release pipeline.
Spec: user requests continued editing development and new release when stable; P3.21–23 motion/native evidence.
Constraints: no new credential exposure, no original CapCut edits, no inferred timings, no installed app replacement during active work.
Review focus: empty scenes, saved revision replacing scene list, stale plan invalidation, seeking loaded proxy, same scale at cut boundary.

- [x] Add failing async UI test: saved scene produces two seek controls (onset/near end), actual scene readout; click synchronizes video clock; dirty clears controls.
- [x] Implement motion review panel and precise timing explanation without changing renderer.
- [x] Run Node regressions and Python full suite; independently review changes and package contract.
- [x] Build1.5.68; verify bundled self-test, signature, dependencies/module inclusion, ZIP/hash/size/credential exclusion.
- [x] Publish existingGitHub destination, verify public download and updater manifest, record evidence and limitations.
