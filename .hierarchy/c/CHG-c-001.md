# CHG-c-001
Brief rev: 1 → 2
Changed: §2 + §4 `read_zip`: now ignores OS junk first (entries under a top-level `__MACOSX/` folder and files named `.DS_Store` at any depth), before limit counting and wrapper stripping → previously a macOS-made zip kept its wrapper folder and failed with "missing index.html".
Action required: implement and test it (zip made the macOS Finder way: wrapper folder + `__MACOSX/` + `.DS_Store`; also a zip with only junk entries -> no files). Everything else in REPORT-c is accepted as is. Report only the delta (new delivery c-002.zip).
In-progress work: can continue
