# P3.29–P3.33 development evidence —2026-11-05

Source changes after public1.5.69, not committed/published as a new release.

Implemented strict grounded narrative approval, shared phrase-quality guard, opt-in bounded multicam space selection preserving original audio, complete nested-source coverage guards, and bounded structural clip QA with review notes. Independent review found a camera edge/internal coverage P1; fixed with full source-boundary walk and regressions. All801Python3.9 tests passed14.938s; CLIrecovery/kineticasync Node tests passed. Earlier agent sandbox suite failures were local socket/process restrictions and concurrent unfinished checks; final approved run passed.

Actual frozen BRAND source429.04s52speech cues assembled90.84s30caps4Super1scene using previously reviewed spans to test camera/QA integration, not new provider story selection. Localcamera changed0:3shots uncertain and1original equal/better. Latest nested structural QA0issues, no missing structural evidence; report still requires native review and lists unsupported listening/tracking/render checks. Render parameters match previous checked native export, ignoring regenerated cue IDs. No source project modified.

User explicitly authorized main-account live testing and confidentiality. Login used normal Firebase/license path without remembering credentials; secret input existed only in tool/process memory, no Key copying. Real Gemini returned HTTP503; UTCC returned JSONerror instead of valid plan. No successful new unattended narrative selection claimed. Fixed terminal provider-error recognition so it is not misreported as a malformed plan/used for repair requests; no raw provider error echo. Public reports contain no login credentials, headers or webhook URLs. Private/local raw job evidence must not be staged for Git.

Cleanup completed within the user’s explicit follow-up authorization after disclosure: 26 old build/dist directories (3.06 GiB) moved to recoverable Trash, 37 directories with found references protected, latest five versions 1.5.65–69 retained. All moved destinations/inodes and protected folders verified. Reference scan remains incomplete for 31 opaque project files; no claim that every old artifact is unused. Projects, media, outputs, audits and backups untouched; Trash not emptied. See cleanup-2026-11-05/moved-receipt.json. Disk space is not reclaimed until Trash is emptied by the user.

Final follow-up verification: 38 focused Python tests and three additional Node checks (Studio recovery, Gemini switching, kinetic preview) passed; no implementation changes after the recorded full 801-test run.

Remaining: successful live provider story and semantic design, actual automatically changed-camera native export, full human listening and continuous rendered crop checks. Public app remains1.5.69.

User confirmed UTCC credit exhaustion on November 5. Reproduced explicit Gemini selection being overridden by stale webhook_utcc flag in shared ce_ai caller. Regression failed with a forbidden Webhook dispatch before the fix and passed afterward. Explicit Gemini now wins; legacy and explicit Webhook behavior retained. Focused 21 Python tests and Gemini-switch UI check passed; no live provider calls or account configuration changes for this regression. Full suite: 802 Python tests passed in 21.628s (/tmp/p333-gemini-full.log).

Release follow-up: stale narrative evidence removed after manual cut changes (red→green, original plan unchanged); full804tests14.674s/Node5passed/reviewer32recheck no blockers. Fresh normal main-account Gemini planning still HTTP503; noUTCC call, sourcecopy unchanged. Packaging1.5.70 with experimental camera label/off by default; successful provider story/native changed-camera acceptance remain open.
