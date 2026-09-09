# Covenant & Credit Risk Monitor

An SEC-first, evidence-linked prototype for debt and covenant research. This is a separate product from Filing Radar, with a deliberately narrow first milestone: one issuer, one reporting-period comparison, and one debt-instrument family.

## Prototype decision

The first issuer is **Amazon.com, Inc. (AMZN)** and the initial instrument family is the **June 8, 2026 delayed-draw term loan facility (DDTL Facility)**.

Why this is a useful first case:

- the local Filing Radar corpus already contains Amazon's latest and prior-quarter 10-Qs;
- a June 10, 2026 8-K describes a publicly filed $17.5 billion senior unsecured facility and links Exhibit 10.1, the agreement;
- the 8-K explicitly says the facility has customary covenants and events of default but **does not contain financial covenants**;
- the latest 10-Q gives a clean quarter-over-quarter debt disclosure comparison and also states that the Notes have no financial covenants.

Tradeoff: Amazon is a strong test of “no maintenance covenant” handling and debt-change tracking, but it is not a distressed/private-credit style issuer. A later phase should add a smaller issuer with a maintenance leverage covenant after this evidence model is proven.

## Scope and trust boundary

The prototype uses only SEC filings and SEC exhibits. It does not use news, market prices, brokerage data, transcripts, autonomous alerts, default prediction, or trading recommendations.

Current source-method boundary: this first report reads SEC HTML filings and exhibits for narrative evidence and now includes a separate, machine-only SEC inline-XBRL corroboration artifact for selected standard debt facts. No covenant ratio is calculated.

The report labels every result as one of:

- directly reported fact;
- agreement-defined fact;
- calculated value;
- estimate;
- interpretation;
- missing information;
- human verification status.

Report construction itself rejects evidence URLs that are not HTTPS SEC URLs; the downstream evaluation repeats this check against the persisted report.

Quarter-over-quarter changes also carry a structured category (`facility_added`, `balance_reported`, `balance_changed`, or `amendment`) alongside the human-readable description and evidence.

No covenant ratio is calculated unless the exact definition, testing date, financial period, required inputs, relevant add-backs/exclusions, and agreement version are all available.

## Run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'

# Build the smallest viable local corpus from the existing Filing Radar data
ccrm ingest-amzn --filing-radar /path/to/filing-radar-export

# Produce the human-reviewable report without cloud API calls
ccrm report --issuer AMZN
ccrm evaluate --issuer AMZN
ccrm llama-plan --issuer AMZN
```

In a clean public checkout, run `pytest -m "not integration"` for the corpus-independent suite. The full `pytest` suite becomes available after generating the private/local Amazon corpus; corpus-dependent tests are marked `integration`.

If `LLAMA_CLOUD_API_KEY` is available, parsing and schema extraction are opt-in:

```bash
export LLAMA_CLOUD_COST_AUTHORIZED=1  # only after approving the bounded API spend
ccrm parse --issuer AMZN
ccrm extract --issuer AMZN
```

The cloud commands require both the API key and the explicit cost-authorization variable; an API key alone cannot trigger a paid run.

These commands process only the bounded provider corpus: five quarterly/context filings plus the linked DDTL agreement and two linked revolving-credit amendments. The report corpus also retains Amazon's latest 10-K and two Senior Notes indentures as provider-excluded context; they are not sent to the cached provider run. These are not bulk jobs; runtime and API usage depend on document length and the selected LlamaCloud tier.

`ccrm llama-plan` makes no external calls. It records the exact eight-document Parse/Extract plan, per-document SHA-256 values, and validation gates so cloud usage can be authorized and reviewed separately.
The plan records its corpus root and validates that every planned absolute path resolves to the declared relative path inside that corpus. Filing-only annual context and provider-excluded Senior Notes indentures are deliberately excluded from this historical eight-document provider plan.

`ccrm review-checklist` creates a source-linked human-review handoff from the current report.
`ccrm review-state` creates a hash-bound `machine_assembled` review state. It can advance to `partially_reviewed` or `human_verified` only when explicit reviewer actions are recorded; a stale report, checklist, provider comparison, or Parse audit cannot be signed off. The checklist displays the current durable state.
Reviewers can record progress with `ccrm review-state --status partially_reviewed --reviewer NAME --date YYYY-MM-DD --complete-action ACTION --complete-evidence-id E-ID`; the command preserves prior completions and rejects unknown IDs or stale report, provider, Parse, or XBRL artifacts. The review summary displays completion counts.
`ccrm review-summary` creates a compact handoff of unresolved provider gaps, out-of-scope signals, parsed-text support, and required reviewer actions.
`ccrm agent-review` runs source-bound consistency and calculation-safety checks, writes `agent-review.json`, binds that artifact into `review-state.json`, and advances the evidence package to `agent_reviewed`. It never substitutes for human approval.
`ccrm decision-brief` creates a concise customer-facing summary of the liquidity conclusion, period changes, uncertainty boundaries, and prioritized review actions.
`ccrm approval-packet` turns the agent exceptions into a human approval handoff and preserves the evidence-level checklist as the release authority.
`ccrm workflow-metrics` records conservative workload-compression metrics without claiming measured analyst time savings.
`ccrm period-registry` inventories verified immutable periods and duplicate builds without treating duplicates as historical evidence. `ccrm agreement-map` creates a source-linked map of agreement sections requiring review.
`ccrm readiness` aggregates the persisted evaluation, review state, provider comparison, and Parse audit into `readiness.json`. It reports `internal_review` until human sign-off is complete and reports `customer_ready` only after the durable review state reaches `human_verified`.
The same artifact reports `expansion_ready` only after AMZN is human-verified and at least two immutable reporting-period runs exist; this prevents generalizing the workflow before its recurring behavior is demonstrated.
`ccrm snapshot` creates an immutable, self-contained run under `data/AMZN/runs/` with a deterministic run ID, copied corpus, regenerated bound artifacts, and a run manifest. `ccrm verify-snapshot --run-manifest PATH` rechecks every recorded artifact hash. `ccrm compare-runs --prior-run PATH --current-run PATH --output PATH` verifies both snapshots and writes corpus, instrument, covenant, and declared-report deltas without changing either run. Rebuilt snapshots of the same period are recognized as identical when their verified source corpus and report content match.

Reducto is the active alternative document-processing path when LlamaParse credits are unavailable:

```bash
export REDUCTO_COST_AUTHORIZED=1
ccrm reducto-parse --issuer AMZN
ccrm reducto-extract --issuer AMZN
ccrm reducto-audit --issuer AMZN
```

Set `REDUCTO_API_KEY` in the local environment; it is never written to the repository. The Reducto run remains bounded to the same eight SEC artifacts (Parse) and three agreement artifacts (Extract), and caches provider job IDs, usage, confidence, source hashes, and page/chunk excerpts for review.
`ccrm reducto-audit` makes no provider calls; it checks source-bound Parse caches for the agreement sections, default-cure language, and amendment text required by the report, and retains bounded context excerpts for human review.
The audit also records the manifest hash and fails if the cached Parse set drifts from the eight non-filing-only provider documents; the latest 10-K is explicitly excluded as filing-only context.
The audit removes local renderer paths, page counters, and timestamps from those excerpts and records an explicit evidence-cleanliness result.

After a cloud run, `ccrm compare-cloud --cloud-output PATH` creates a disagreement artifact without modifying the deterministic report. It checks the DDTL commitment, outstanding balance, covenant absence, revolving amendment, unsupported-headroom behavior, structured changes and financial definitions, and whether cloud evidence maps to the exact SEC documents in the bounded corpus.
The command exits non-zero when the comparison fails, while retaining the comparison artifact for review. For Reducto, the comparison explicitly marks filing-only signals such as quarter-end balances as out of scope when Extract received only agreement exhibits, and distinguishes structured Extract gaps from hooks present in the cached Parse text; missing agreement hooks or unresolved provenance still fail the comparison.

Parse and Extract outputs are cached by default. Use `--force` only when deliberately rerunning a cloud job; Parse metadata retains page numbers, character counts, page excerpts, and the source SHA-256. A Parse cache is reused only when its source hash still matches, and Extract validates parsed agreement freshness plus a valid three-document result envelope bound to each parsed-input SHA-256 before reusing an existing Extract output or uploading anything.

The corpus manifest records SHA-256 digests and HTTPS SEC provenance for every local SEC artifact. The full evaluation command verifies those digests and rejects non-SEC manifest URLs before treating the report as current.
Evaluation also rejects known local-renderer noise in persisted evidence excerpts.
Evaluation requires every persisted evidence item to have a stable ID; repeated citations of the same immutable item are allowed, while conflicting IDs or payloads fail closed.
Evaluation also checks that the report answers the ten first-report questions in the product brief, allowing explicit `not_calculable` or `missing` states where evidence is insufficient. The persisted evaluation includes a ten-row question-coverage matrix with scope notes and stable evidence IDs for reviewer triage.
Uncertainty and missing-information narratives are also required to retain supporting evidence.
When a corpus manifest is supplied, evaluation also verifies that each non-missing evidence excerpt occurs in the normalized text of its manifest-bound local SEC artifact.
Each generated report also records the aggregate corpus-manifest SHA-256, and manifest-backed evaluation requires that report fingerprint to match.
The customer-facing output bundle includes the matching corpus manifest so reviewers can independently verify the report’s source snapshot.
The report distinguishes the latest 10-Q's reported senior-notes principal from its fair value and links the Senior Notes to the 2012 Indenture and 2022 Supplemental Indenture identified in the latest 10-K. These annual and indenture sources are context only and are not used for quarter-over-quarter calculations. XBRL corroboration remains supplemental and separate from agreement interpretation.
Structured negative-covenant records may include bounded exception language, but the report does not normalize an exception schedule into available capacity or headroom.
Context debt instruments whose governing agreement is not in the bounded corpus now say so explicitly in the Markdown report.
The Markdown report surfaces the companion XBRL artifact and its machine-only boundary so reviewers do not mistake corroboration for human verification.

The bounded inline-XBRL corroboration command extracts selected June 30, 2026 debt facts without changing the deterministic report:

```bash
ccrm xbrl-corroborate --issuer AMZN
```

Its output preserves raw XBRL values and scale metadata, adds human-readable period/value labels, and checks alignment with the persisted report. It remains machine corroboration only: it does not establish agreement definitions, covenant headroom, remedies, or human verification.

## Layout

- `STATUS.md` — durable product state, blockers, readiness, and next iteration.
- `src/ccrm/schema.py` — structured debt, covenant, definition, risk, evidence, and report schema.
- `src/ccrm/ingest.py` — imports local SEC manifests and fetches the linked DDTL agreement exhibit.
- `src/ccrm/llama.py` — current unified `llama-cloud` SDK adapters for Parse and Extract.
- `src/ccrm/report.py` — deterministic evidence-linked report builder and conservative headroom status logic.
- `src/ccrm/evaluate.py` — persisted checks for evidence coverage, period accuracy, and safe headroom output.
- `data/AMZN/` — generated prototype corpus and report.

The project intentionally does not import Filing Radar internals. It reuses its immutable SEC artifacts by reading their manifests, keeping the customer workflow and schema separate.
