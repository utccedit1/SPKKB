# P3.23 — final phrase recipes and actual cut motion

Recipes now run after measured phrase compaction, so matched main/support text receives impact motion. Impact punch/numeric/matched/contrast and story punch/numeric use existing snap_to_cut; clean stays still, original/manual is preserved. No new cuts, tracking or forced text-space reframing.

Real BRAND STORM comparison: clean 2 Super/0zoom; story14Super/0zoom for these matched forms; impact14Super/7zoom; all30short captions. Seven zoom intervals in comparison.json reach130% in≤.30s and hold to existing shot boundary. Original project and previous1104 preserved.

First guarded import rejected a zero-duration native piece at46.88 due equivalent float edge values. Reproduced in test, fixed by microsecond endpoint dedup; no guard bypass. New empty1104(1), activeD19331BF-2FC1-487A-953E-6408E1B2F8ED, imported via preview/commit with backup20261104_114304_before_cli_replace_f4b1e698.

CapCut export BRAND-STORM-impact-cut-native.mp4:90.84s1920×1080/50fps,226288469bytes. Full decode succeeded;16 sampled export frames inspected in native-contact.jpg, including zoom onset/hold/next-shot reset. No exposed canvas or clipped head in inspected samples; text remains unboxed and captions single-line in these samples. DBHeaventBlk uses same selected font as P3.22. This is not full human listening or every-frame tracking certification.

Verification: Python3.9 full685passed17.635s (/tmp/p323-final-tests.log); Nodekinetic_ui_test.js + kinetic_ui_async_test.js passed; independent reviewer47focused plus16scene tests no important blockers. Initial sandbox full run had4environment errors (process/socket permissions), approved rerun passed; attempted nonexistent kinetic_preview_test.js corrected to actual async suite.

Source-only; public binary1.5.67 does not include this change. No version bump or installed app replacement.
