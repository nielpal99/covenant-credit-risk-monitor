# Product state and roadmap

## Product goal

Produce one trustworthy, human-reviewable, evidence-linked answer to: “What debt obligations govern this company, how much room remains under those obligations, and what changed since the previous reporting period?”

## Current milestone

**Single-issuer SEC prototype — AMZN, June 30, 2026.** The report covers the June 8 DDTL Facility and quarter-over-quarter debt disclosures. The facility has a $17.5B commitment, $0 outstanding at June 30, and no financial covenant disclosed in the filed 8-K. Headroom is therefore not calculable, not zero.

## Prioritized backlog

1. **Agreement evidence segmentation (completed in iteration 2):** extract section-level evidence from the full agreement for affirmative covenants, negative covenants, events of default, notices, and remedies. Definitions, cure/grace language, and amendment chaining remain open.
2. **Instrument-family reconciliation (completed in iteration 3):** represent the DDTL, revolving facilities, commercial paper, and Notes as separate instruments while keeping the first report focused on the DDTL family.
3. **Quarter comparison evaluation (completed in iterations 4–5):** add persisted checks for evidence coverage, period accuracy, agreement locators, safe headroom output, and direct evidence on every change statement, including a regression test that new-debt changes cite new-debt evidence.
4. **Detailed quarter-change fixtures (completed in iteration 6):** add fixture-backed classification for new debt and quarter-end outstanding balance, with report generation driven by the detected AMZN Q1/Q2 facts.
5. **Repayment, maturity, covenant, amendment, waiver fixtures (completed in iteration 7):** generic regression coverage now distinguishes balance changes, first-time balance reporting, maturity changes, repayment events, covenant-status changes, amendments, and waivers without weakening evidence requirements.
6. **Evidence-backed event extraction (completed in iteration 8):** connected real SEC excerpts for the June 8, 2026 revolving-agreement amendments and populated the dedicated risk-status amendment field.
7. **LlamaCloud evidence path (planning completed in iteration 9; adapter hardening completed in iteration 11; disagreement harness completed in iteration 12):** a no-upload plan records eight Parse jobs, three agreement Extract jobs, zero index/batch jobs, and validation gates. Outputs are cached by default, Parse metadata preserves page-level excerpts, and cloud output can be compared without changing the deterministic report. Actual cloud execution remains gated on cost authorization.
8. **Fail-closed source extraction (completed in iteration 10):** required SEC facts now raise an explicit error when their source excerpt is missing instead of receiving fallback prose that could be mislabeled as reported evidence.
9. **Human-review handoff (completed in iteration 13):** generated a source-linked checklist covering scope, debt instruments, covenant safety, amendments, agreement sections, open questions, and sign-off.
10. **Debt-inventory completeness (completed in iteration 14):** added other short-term credit facilities and Senior Notes fair value as clearly labeled latest-quarter context, without treating fair value as outstanding principal.
11. **Corpus integrity (completed in iteration 15):** recorded SHA-256 digests for all local filings, agreements, and amendments and added an evaluation gate that verifies the artifacts have not changed.
12. **Agreement-version traceability (completed in iteration 16):** added explicit governing-agreement version fields to debt instruments and covenants so any future calculation can bind to the correct agreement state.
13. **Integrity regression coverage (completed in iteration 17):** added a negative test proving a changed local artifact fails the corpus-integrity gate instead of being accepted as current.
14. **Agreement URL binding (completed in iteration 18):** bound DDTL agreement evidence to the explicit `ddtl-agreement` manifest record and added a regression test preventing amendment URLs from being used as the governing agreement source.
15. **Change-list precision (completed in iteration 19):** removed unchanged disclosures from the quarter-over-quarter change list and made amendment reporting depend on detected current-period amendment evidence.
16. **Evidence provenance gate (completed in iteration 20):** validate every report evidence object against the manifest’s authoritative document identifier and SEC URL, catching mislabeled source bindings before delivery.
17. **LlamaCloud plan validation (completed in iteration 21):** validate the persisted no-upload plan for bounded document count, local source existence, Parse coverage, agreement-only Extract scope, and no index/batch work.
18. **Parse fail-closed handling (completed in iteration 22):** normalize supported Parse response shapes and refuse to cache an empty artifact when the service returns no usable text.
19. **Cloud cost guard (completed in iteration 23):** require explicit `LLAMA_CLOUD_COST_AUTHORIZED=1` in addition to credentials before any paid Parse or Extract call can run.
20. **Cloud contradiction checks (completed in iteration 24):** reject structured cloud outputs that contradict the deterministic DDTL commitment or outstanding balance, even when expected phrases appear elsewhere in the response.
21. **Change-list evaluation invariant (completed in iteration 25):** persistently fail evaluation if unchanged-language markers reappear in the quarter-over-quarter change list.
22. **Review evidence detail (completed in iteration 26):** include governing agreement versions, evidence kinds, locators, and excerpts directly in the human-review checklist.
23. **Calculation completeness gate (completed in iteration 27):** reject estimated or verified covenant calculations unless threshold, testing period, reported input, agreement section, agreement version, and evidence are all present.
24. **Verification-status disclosure gate (completed in iteration 28):** fail evaluation if the report does not explicitly disclose that it is machine-assembled and not human verified.
25. **Agreement-section build gate (completed in iteration 29):** refuse to build a report when any required affirmative-covenant, negative-covenant, event-of-default, or remedy section is missing from the agreement segmentation.
26. **Default-cure evidence (completed in iteration 30):** surface the agreement’s exact non-payment treatment, including the five-Business-Day cure period for interest, fees, and other amounts, with source-backed review text.
27. **Portable integrity verification (completed in iteration 31):** resolve relative corpus artifact paths from the manifest root so integrity checks remain reliable outside the project’s working directory.
28. **Manifest-root precedence (completed in iteration 32):** prefer the manifest-derived artifact path over same-named caller-directory files, preventing integrity checks from validating a decoy artifact.
29. **Corpus completeness evaluation (completed in iteration 33):** enforce the exact bounded prototype corpus in the persisted evaluation artifact so missing filings or linked agreements cannot pass silently.
30. **Cloud evidence requirement (completed in iteration 34):** reject structured cloud debt or covenant outputs that lack evidence objects, even when their values match expected signals.
31. **Cloud comparison positive-path coverage (completed in iteration 35):** verify that evidence-bearing, non-contradictory structured cloud output passes alongside the existing failure-path tests.
32. **Parse-cache validity (completed in iteration 36):** refuse to reuse blank or unreadable cached Parse content so stale empty artifacts cannot bypass fail-closed handling.
33. **Per-document manifest consistency (completed in iteration 37):** write copied filing manifests after local paths and SHA-256 digests are recorded, keeping document-level provenance synchronized with the aggregate corpus manifest.
34. **Narrative risk evidence gate (completed in iteration 38):** require supporting evidence whenever the report populates defaults, waivers, amendments, breaches, reporting violations, or liquidity concerns.
35. **Runtime cloud scope enforcement (completed in iteration 39):** make Parse process exactly the eight planned corpus documents and Extract process only the three parsed agreement documents, preventing plan/runtime drift.
36. **Default-summary source linking (completed in iteration 40):** place a direct Section 8.01 source link beside the non-payment cure summary in the human-readable report.
37. **Extract-input fail-closed handling (completed in iteration 41):** reject missing or empty parsed inputs before constructing a cloud client or uploading any Extract input.
38. **Cloud-plan validation single source (completed in iteration 42):** centralize builder and persisted-plan validation checks and make malformed plans fail closed.
39. **Direct Extract scope enforcement (completed in iteration 43):** enforce the three-document agreement scope and non-empty input requirement at the library boundary, not only through the CLI.
40. **Persisted-report schema gate (completed in iteration 44):** validate every persisted report against the structured Pydantic schema before substantive evaluation checks can pass.
41. **Executive timing context (completed in iteration 45):** surface the DDTL commitment’s September 30, 2026 expiry beside the executive conclusion as a sourced, time-bounded availability observation.
42. **Evidence-object completeness gate (completed in iteration 46):** require every report evidence object to contain a document ID, SEC URL, locator, and non-empty excerpt.
43. **Amendment-source extraction (completed in iteration 47):** derive revolving-amendment evidence excerpts from each linked SEC amendment artifact and fail closed if the dated amendment title is absent.
44. **Evaluation exit status (completed in iteration 48):** make the CLI return a non-zero status when the persisted evaluation fails, preventing unsafe reports from appearing successful in automation.
45. **Cloud nested-result normalization (completed in iteration 49):** normalize JSON-encoded nested Extract results before evidence and contradiction checks, preventing stringified reports from bypassing validation.
46. **10-Q amendment-summary extraction (completed in iteration 50):** derive the quarter filing’s revolving-amendment evidence from its actual exhibit descriptions and fail closed if the dated descriptions are absent.
47. **Single-issuer CLI boundary (completed in iteration 51):** reject non-AMZN issuer arguments consistently across all issuer-specific commands before any data access.
48. **Short-term debt change coverage (completed in iteration 52):** detect and report the $152M-to-$325M increase in other short-term credit-facility borrowings with latest-quarter evidence.
49. **Real-filing balance regression (completed in iteration 53):** verify short-term debt extraction directly against the stored Q1 and Q2 SEC filing HTML, not only injected fixture values.
50. **Change-review handoff (completed in iteration 54):** give the human-review checklist a dedicated quarter-over-quarter change section with direct source links and excerpts for every detected change.
51. **Source-period metadata gate (completed in iteration 55):** verify that the manifest’s actual filing forms and report dates support the selected Q1/Q2 comparison pair.
52. **SEC-only evidence gate (completed in iteration 56):** require every report evidence URL to use the HTTPS SEC domain before evaluation can pass.
53. **Cloud evidence-field completeness (completed in iteration 57):** require structured cloud debt and covenant evidence to include document ID, SEC URL, locator, and excerpt before comparison can pass.
54. **Build-time filing-period gate (completed in iteration 58):** refuse report generation when either selected filing has the wrong form or report date, rather than relying only on downstream evaluation.
55. **Structured cloud-output gate (completed in iteration 59):** require recognized structured debt or covenant collections before a cloud comparison can pass, preventing free-text signal matches from being accepted as Extract output.
56. **Cloud agreement-hook coverage (completed in iteration 60):** require cloud comparison output to include events-of-default and remedies signals alongside debt, covenant, and amendment signals.
57. **Cloud risk-narrative evidence (completed in iteration 61):** require complete SEC evidence for any cloud-extracted default, waiver, amendment, breach, reporting-violation, or liquidity narrative.
58. **Two-sided period-change provenance (completed in iteration 62):** require the prior-quarter and latest-quarter SEC excerpts for the short-term-borrowings change, so a reported delta cannot be supported by only one side of the comparison.
59. **Evaluator period-change gate (completed in iteration 63):** fail evaluation when a from/to change does not have SEC excerpts covering both selected reporting periods.
60. **Fail-closed period metadata (completed in iteration 64):** prevent blank period metadata from vacuously satisfying the two-sided period-change evidence gate.
61. **Cloud corpus provenance gate (completed in iteration 65):** when a corpus manifest is supplied, require every cloud evidence object to map to an exact bounded-corpus document ID and SEC URL.
62. **Cloud comparison exit status (completed in iteration 66):** make failed cloud comparisons return non-zero from the CLI while retaining the diagnostic artifact.
63. **Cloud CLI failure-path coverage (completed in iteration 67):** exercise the real `compare-cloud` command to verify failed comparisons persist diagnostics and return status 1.
64. **Typed change categories (completed in iteration 68):** make each persisted quarter-over-quarter change machine-readable while retaining its evidence-linked narrative.
65. **Human-readable source register (completed in iteration 69):** enumerate all eight bounded SEC filings and exhibits in the Markdown report with identifiers, dates, and direct URLs.
66. **Source-register regression coverage (completed in iteration 70):** verify the generated report retains the selected quarter filings, governing agreement, and amendment exhibits in its source register.
67. **Visible evidence classification (completed in iteration 71):** expose reported, agreement-defined, calculated, estimate, interpretation, missing, and human-verification distinctions in the primary Markdown report.
68. **Revolving-agreement binding (completed in iteration 72):** bind the revolving-facilities context instrument to both amended governing agreements with direct 10-Q and exhibit evidence.
69. **Dedicated expiry provenance (completed in iteration 73):** attach a required, exact SEC excerpt to the DDTL commitment-expiry observation and link it in the executive report.
70. **Structured cloud-key normalization (completed in iteration 74):** normalize underscore-delimited structured risk fields so valid cloud output is not rejected by space-based signal checks.
71. **Parse-cache source binding (completed in iteration 75):** persist the source SHA-256 in Parse metadata and reject cached content when the source artifact has changed.
72. **Cloud-plan path binding (completed in iteration 76):** record the corpus root and reject persisted plans whose absolute paths escape or disagree with their declared relative corpus paths.
73. **Durable cloud-review status (completed in iteration 77):** record cloud comparison state and deterministic-report authority directly in the human-review checklist.
74. **Cloud structured-section provenance (completed in iteration 78):** require evidence for populated cloud financial definitions and structured quarter-over-quarter changes.
75. **Verification-flag consistency (completed in iteration 79):** reject evidence marked human verified when the report-level status still says unverified.
76. **Cloud-plan traversal containment (completed in iteration 80):** reject relative paths that resolve outside the declared corpus root, including `..` traversal.
77. **Source-register roles (completed in iteration 81):** label each bounded SEC artifact by its role as comparison period, facility disclosure, governing agreement, amendment, or context source.
78. **Report corpus fingerprint (completed in iteration 82):** bind persisted reports and reviewer handoffs to the aggregate corpus-manifest SHA-256 and reject mismatched manifests during evaluation.
79. **Visible corpus fingerprint (completed in iteration 83):** expose the report’s corpus-manifest SHA-256 in the primary Markdown evidence/status section.
80. **Extract-cache freshness gate (completed in iteration 84):** require parsed agreement metadata to match the current agreement artifact before any Extract upload.
81. **Extract-cache bypass prevention (completed in iteration 85):** validate parsed-input scope and freshness before reusing an existing Extract output.
82. **Extract-cache envelope validation (completed in iteration 86):** reuse an Extract cache only when it is valid JSON containing exactly three document/result entries.
83. **Extract-input hash binding (completed in iteration 87):** bind each cached Extract result to its parsed input path and SHA-256 before reuse.
84. **Cloud-plan source integrity (completed in iteration 88):** record and validate per-document SHA-256 values in the no-upload plan before any future cloud execution.
85. **Case-robust covenant-status parsing (completed in iteration 89):** make deterministic covenant-absence detection insensitive to SEC capitalization differences.
86. **Independent manifest delivery (completed in iteration 90):** include the exact corpus manifest in the customer-facing output bundle and verify its fingerprint matches the report.
87. **Build-time SEC URL gate (completed in iteration 91):** reject non-SEC evidence URLs while constructing the report, before unsafe provenance can be persisted.
88. **Transparent balance delta (completed in iteration 92):** calculate and display the sourced $173 million quarter-over-quarter short-term-borrowing increase with its explicit formula.
89. **Durable calculation handoff (completed in iteration 93):** carry the transparent balance-delta formula into the human-review checklist.
90. **XBRL-method disclosure (completed in iteration 94):** document that the first no-ratio report uses SEC HTML filings/exhibits and has not yet corroborated standard inputs with XBRL.
91. **Reducto provider path:** add a credential-gated, bounded Reducto Parse/Extract adapter with source-hash-bound caches and provider job/usage metadata; retain the LlamaCloud adapter for historical comparison.
92. **Reducto execution and review:** run the eight-document Parse and three-agreement Extract jobs, compare the structured output against the deterministic report, and route unresolved disagreements into the review checklist.
93. **Provider citation normalization:** map Reducto citation blocks to exact bounded-corpus SEC document IDs and URLs in the comparison view without rewriting raw provider output.
94. **Provider-scope evaluation:** distinguish filing-only signals from agreement-only Extract scope so comparison failures identify real extraction gaps instead of penalizing unavailable inputs.
95. **No-upload Parse audit:** verify the completed Reducto Parse caches retain the required covenant, default, remedy, and amendment hooks, with manifest-linked presence evidence and an explicit non-verification status.
96. **Contextual Parse evidence:** replace phrase-only Parse audit evidence with bounded source-text context and surface it in the durable human-review checklist.
97. **Fail-closed review state:** add a hash-bound review state machine that cannot claim human verification until all required review actions and provider disagreements are explicitly resolved.
98. **Reviewer decision aid:** generate a compact, evidence-linked summary separating parsed-text support, structured-provider gaps, out-of-scope signals, and sign-off actions.
99. **Supporting-artifact binding:** bind review state to provider comparison and Parse-audit hashes so changed evidence invalidates sign-off.
100. **Parse-versus-Extract distinction:** expose when an agreement hook is present in provider Parse text but missing from structured Extract, preserving the structured comparison failure while improving reviewer diagnosis.
101. **Evidence excerpt cleanliness:** reject persisted report evidence containing local renderer paths or transport noise.
102. **Evidence-ID evaluation gate:** fail evaluation when persisted evidence IDs are missing or map inconsistently to evidence payloads; allow intentional repeated citations of one stable item.
103. **Provider excerpt hygiene:** sanitize local renderer metadata from cached Parse excerpts and fail the Parse audit if reviewer-facing evidence contains transport noise.
104. **Gap-specific review links:** map each unresolved provider signal to only the relevant report evidence and SEC agreement section.
105. **Durable product status:** record current readiness, verified outcomes, blockers, required inputs, and next iteration outside chat history.
106. **Evidence source-content binding:** verify every non-missing report excerpt against the normalized text of its manifest-bound local SEC artifact.
107. **Senior Notes balance completeness:** capture the latest 10-Q's reported $132.1 billion senior-notes principal separately from its approximately $123.8 billion fair value.
108. **Bounded XBRL corroboration:** extract and persist selected inline-XBRL debt facts from the latest 10-Q while keeping agreement interpretation and headroom calculations outside the XBRL path.
109. **XBRL-report alignment:** compare each selected inline-XBRL debt fact with the corresponding persisted report value and fail corroboration when they diverge.
110. **XBRL review-state binding:** bind durable review transitions to the supplemental XBRL artifact hash so changed corroboration cannot be signed off silently.
111. **XBRL report visibility:** surface the supplemental corroboration status and its non-verification boundary in the human-readable report.
112. **Negative-covenant exception visibility:** surface bounded exception language for Sections 7.01 and 7.02 without converting incomplete schedules into capacity calculations.
113. **First-report question coverage:** add an explicit evaluation gate for the ten required questions in the original product brief.
114. **Uncertainty provenance:** require supporting evidence for populated uncertainty and missing-information narratives.
115. **Missing agreement-map disclosure:** explicitly label context instruments whose governing agreement is not identified in the bounded corpus.
116. **Latest annual context:** add Amazon's latest publicly available 10-K to the manifest-bound report corpus as filing-only annual context, while preserving the cached eight-document provider scope and evaluation integrity.
117. **Reproducible annual ingest:** make fresh corpus rebuilds select linked filings by accession rather than list position, and verify nine-document report generation and evaluation from a clean temporary corpus.
118. **Review-scope sign-off:** require explicit human confirmation of the selected issuer scope and reporting-period comparison before the durable review state can reach `human_verified`.
119. **Manifest URL provenance:** require every corpus manifest document to carry a valid HTTPS SEC URL and add a negative regression test for non-SEC source URLs.
120. **Provider-scope binding:** bind the cached Reducto Parse audit to the manifest hash and explicitly verify that filing-only annual context is excluded from the eight-document provider set.
121. **Question coverage matrix:** persist per-question status, caveats, and stable evidence IDs for all ten first-report requirements instead of exposing only an aggregate coverage boolean.
122. **Customer-facing coverage table:** surface the ten-question coverage matrix in the Markdown report with explicit bounded and not-calculable statuses.
123. **Reviewer scope visibility:** surface the verified Reducto Parse scope in the durable review summary so provider omissions are immediately distinguishable from extraction failures.
124. **Senior Notes agreement mapping:** add the 2012 Indenture and 2022 Supplemental Indenture identified by Amazon's latest 10-K as provider-excluded SEC context and link them to the Senior Notes record.
125. **Release readiness gate:** aggregate persisted evaluation, review, and optional provider gates into a durable `readiness.json` artifact and CLI command.
126. **Immutable reporting runs:** create deterministic, non-mutating run snapshots with copied corpus, regenerated bound artifacts, hash verification, and idempotent reruns.
127. **Snapshot-to-snapshot comparison:** verify two immutable runs and persist corpus, debt-instrument, covenant, and declared-report deltas without mutating either input.
128. **Expansion gate:** persist an explicit `expansion_ready` decision requiring AMZN human verification and two immutable reporting-period runs before adding another issuer.
129. **Approval handoff:** generate a focused human approval packet from agent-reviewed exceptions while retaining evidence-level sign-off as the release authority.
130. **Duplicate-run control:** distinguish same-period rebuilds from real period-over-period history in readiness and snapshot comparison.
131. **Workflow value measurement:** persist conservative review-focus metrics and distinguish measured analyst time savings from unvalidated workflow compression.
132. **Agreement review map:** normalize source-linked covenant, reporting, default, remedy, and amendment hooks while preserving human-review boundaries.
133. **Period registry:** inventory verified distinct periods and duplicate rebuilds so readiness cannot mistake rebuild noise for historical evidence.
134. **Public repository boundary:** prepare a safe GitHub publication boundary that excludes generated/provider artifacts, documents credential handling, and identifies sanitized-fixture and licensing gates.
135. **Controlled second-issuer scoping:** inventory genuine AAPL SEC sources and reporting dates without promoting source coverage into an unverified credit report.
136. **Commercialization evidence:** document the initial buyer, product wedge, critical gaps, pilot acceptance criteria, and trust boundaries in a durable commercialization artifact.
137. **Historical period snapshot:** add a bounded, source-linked historical AMZN snapshot and verified cross-period comparison without fabricating missing data or treating the snapshot as human-approved.

## Explicit non-goals

No news, market prices, brokerage integrations, autonomous alerts, default prediction, trading recommendations, or bulk processing.

## Evaluation scorecard

- Corpus completeness: 5 filings plus linked agreement exhibit present.
- Provenance coverage: every populated report fact has an evidence object; agreement-defined unknowns remain marked missing.
- Calculation safety: no covenant ratio/headroom is emitted without complete definition, date, period, inputs, exclusions, and agreement version.
- Period accuracy: latest 10-Q is June 30, 2026; prior 10-Q is March 31, 2026.
- Human review: report must remain explicitly machine-assembled and unverified until a reviewer confirms the agreement.
