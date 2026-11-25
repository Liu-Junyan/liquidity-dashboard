# Real-data integration development plan

Updated: November 18, 2026. Status: Slices 1–6 implemented locally within reviewed/authorized scope. Slice 6 activates 24 series (19 displayed); Treasury bid–ask is deferred, and iFind/price-impact definitions remain pending. Slice 5 configures scheduled production publication and rollback; first hosted deployment and live rollback acceptance remain pending after merge. Mobile UI polish is deferred at the maintainer's request.

## 1. Goal and first release

Replace synthetic observations with validated automatic and manual inputs while retaining the existing Chinese-language static dashboard and GitHub Pages hosting. Keep the four research layers, CSV-controlled membership, source-only inputs, chart interactions, and statistics disclosures.

This document defines the implementation sequence. The [mixed-source implementation guide](implementation-brief.md#mixed-source-data-implementation-guide-future-real-data-milestone) remains the requirements reference; the [registry guide](../data/README.md) defines the editable CSV. All commands and new paths described below are proposed unless explicitly identified as existing.

The first production milestone is deliberately small:

- Fed total assets (`fed-assets`, FRED `WALCL`), exercising weekly collection and amount conversion.
- SOFR and EFFR source inputs, producing `sofr-effr-spread`, exercising daily collection and derivation.
- Fed overnight repo totals across Treasury, agency debt, and agency MBS collateral (`fed-repo`, FRED `RPONTTLD`), exercising daily collection with identity conversion in billions. This replaces the earlier manual all-collateral pilot.
- Manual import and correction validation remain in Slice 2, using isolated offline test fixtures. A real manual series and its publication check move to Slice 6 after a source is ready; they are not prerequisites for this first release.
- Other categorized entries remain visible with `待接入` and empty charts until their implementations pass activation checks. Existing `unavailable` entries remain excluded; source-only inputs remain hidden.

Completion means these pilot series work through collection, normalization, derivation, snapshot assembly, frontend rendering, and repeatable publication, with manual import validation covered offline. Full coverage of all 23 displayed indicators is a later milestone. Trading signals, a database, accounts, and maintenance controls in the browser are outside this release.

## 2. Current state and implementation constraints

| Existing component | Current behavior | Required change |
| --- | --- | --- |
| `data/registry.csv` and `scripts/registry.py` | Membership, specifications, dependency checks, optional JSON export | Add production completeness checks for activated series without requiring all draft sources to be finished |
| `scripts/catalog.py` | Separate demo and reviewed production metadata | Extend reviewed sources in Slice 6 |
| `scripts/build.py` | Demo and validated production snapshot modes | Slice 5 publisher builds an exact artifact revision |
| `site/assets/data.js` | Native-frequency comparisons, labels and valid sample counts | Retain these checks as new sources activate |
| `site/assets/app.js` and `charts.js` | Mode-specific labels, source notices, safe empty/short-history rendering | Mobile polish deferred by maintainer |
| `.github/workflows/pages.yml` | Offline PR checks; saved-input pushes; daily/manual refresh, production publication and rollback | Verify first hosted release after merge |

Use Python 3.10+; prefer standard-library modules where they keep the implementation simple. Excel extraction uses `openpyxl`, pinned in `requirements.txt`, to avoid maintaining an XLSX parser. GitHub Actions installs these dependencies before tests. Use the environment specified in AGENTS.md for local dependencies. Keep routine tests offline. Do not add extra maintainer-filled registry columns for scheduling, matching, or aggregation policies.

## 3. Calculation and source decisions

### Normalize before evaluating formulas

`source_unit` describes the collector/importer's input scale; `normalized_unit` describes the values supplied to downstream formulas and the website. Raw/source-scale observations and normalized observations must remain distinguishable. Unit labels alone do not execute conversions.

| Series | Planned rule | Example / acceptance result |
| --- | --- | --- |
| `reserve-balances` | Millions → billions: divide by 1,000 | 3,000,000 → 3,000 |
| `bank-total-assets` | Billions → billions: unchanged | 25,000 → 25,000 |
| `reserve-assets-ratio` | `100 * reserve-balances / bank-total-assets`, using normalized inputs | 3,000 / 25,000 → 12 (%) |
| `sofr-effr-spread`, `sofr-tail-spread` | Subtract normalized percent-level inputs and multiply the difference by 100 for bp | (4.10 − 4.00) × 100 = 10 bp |
| `treasury-yield-chg` | Request `DGS10` with `units=chg`; current registry specifies `%` → `bp`, so multiply the returned difference by 100 once | Yield 4.00% → 4.10% gives API change 0.10, then normalized change 10 bp |
| `fed-repo` | FRED `RPONTTLD`; Treasury, agency debt, and agency MBS collateral; daily billions → billions with `units=lin` | No division by 1,000; replaces manual all-collateral aggregation |
| `reverse-repo` | Use the updated `RRPONTSYD` mapping; daily billions → billions | No weekly resampling or amount conversion by default |

Slice 1 corrected the reserve/assets CSV formula to include `100` and corrected the `Biliions` spelling. The source review records the reserve/bank-asset coverage and seasonal-adjustment mismatch; resolve and disclose it before activation. Common units alone do not establish identical coverage.

FRED supports `units=chg` (difference) and `units=pch` (relative percent change). Use `chg` for the agreed Treasury yield measure. The current `notes=units=chg` records intent; implement an explicit request policy keyed by series ID rather than executing or parsing arbitrary notes. Retain `automatic` ownership for this provider-transformed series. Record both the original provider units and applied transformation in provenance. [FRED API: transformations](https://fred.stlouisfed.org/docs/api/fred/series_observations.html#units).

The latest registry's Treasury output is bp. If percent-scale output is preferred later, explicitly change `normalized_unit` to `%`, remove the scaling step, and review dependent price-impact units. Do not silently change that choice during implementation.

### Native dates and derived inputs

- Preserve each source's dates and native frequency within the collection window (FRED: `2010-01-01` onward). Observation dates, publication dates, and collection times have separate meanings.
- Join derived inputs on equal observation dates by default, after normalization. Missing inputs and zero denominators yield null. Recompute the complete derived history after every refresh.
- Do not forward-fill inputs or interpolate. A different alignment needs a named per-indicator rule and an age limit in code.
- Preserve explicit missing values and true zeroes. Do not add weekend or holiday observations to native data. Identify unexpected missing periods using source-specific calendars where needed.
- Use named calculation functions keyed by derived series ID, validated against their declared inputs and formula. Hyphenated IDs are identifiers, not Python subtraction expressions; do not use unrestricted `eval` on registry text. Reject unknown or mismatched calculation definitions before activation.

## 4. Storage, policy, and production contract

Keep `data/registry.csv` authoritative; `data/registry.json` remains an optional generated export and never controls production independently.

| Planned path | Responsibility |
| --- | --- |
| `scripts/policies.py` | Activated-series set; provider request transforms; conversions; date, comparison, and freshness policies |
| `scripts/import_manual.py` | Parse and validate manually maintained inputs and corrections |
| `scripts/export_wind_issuance.py` (implemented) | Read saved Wind workbook values and prepare the five manual CSVs |
| `scripts/collect.py` and `scripts/providers/fred.py` | Fetch, validate, and stage automatic inputs with bounded retries/timeouts |
| `scripts/normalize.py` and `scripts/derive.py` | Convert source-scale values and calculate dependency-ordered outputs |
| `scripts/assemble.py` | Validate the complete candidate dataset and create one snapshot |
| `data/manual/<series-id>.csv` | Maintainer-owned source observations |
| `data/sources/wind/Wind-data.xlsx` | Refreshable Wind workbook; versioned with CSV updates for use across machines, outside published assets |
| `data/automatic/<series-id>.json` | Last validated automatic response values and sanitized provenance |
| `data/snapshot/` | Current validated catalog, observations, and manifest; previous versions retained through Git |

Policies must reference existing registry IDs and methods. Avoid duplicating names, categories, provider IDs, or unit declarations in policy code. An activated series must have a reviewed source, supported units, implementation, and valid input ownership; `ready` by itself does not activate collection. Unfinished unactivated definitions may remain in the registry. Invalid registry structure or activated policies block assembly.

Introduce production schema version 2, leaving schema version 1 fixtures intact:

- `catalog.json`: `schemaVersion`, `snapshotId`, dataset mode and generation time, categories, and indicator definitions. Indicators retain stable IDs, units, native frequency, comparison policy, reviewed explanation, source references, and an availability field. Availability describes numeric/empty/nonnumeric rendering, not operational status badges.
- `observations.json`: an envelope with `schemaVersion`, `snapshotId`, and `series` keyed by displayed indicator ID. Each series is a sorted array of `{date, value}`. Empty arrays, single observations, different history lengths, and null values are valid. Source-only inputs remain in the snapshot's internal inputs/provenance, outside the chart series map.
- `manifest.json`: snapshot ID, source-input commit, generation time, input hashes, sanitized request parameters, transformation/calculation policy version, per-series outcomes, revision summary, and provenance. Derived provenance identifies the exact input hashes used.
- Catalog and observations must share the same snapshot ID and schema version. Reject mismatches in both build validation and browser loading. Compute dataset bounds from actual observations; allow null bounds if all series are empty. Bounds are summaries, not constraints forcing equal series lengths.
- Track latest observation date, last attempt, last successful check, and last data-change time separately per automatic series. Use timezone-aware UTC operational timestamps. No-change successes advance check time; failures do not.

The source-input commit identifies the checked-out registry, policies, and manual inputs; fetched inputs are identified by hashes. The later commit containing automatic inputs and the snapshot is the artifact revision used for deployment. This avoids requiring a commit to contain its own Git hash.

Use temporary staging directories and atomic replacement after validation. The production build will copy a selected snapshot into the output directory without overwriting checked-in demo observations in `site/data/`. The Slice 2 command already fails clearly for a missing snapshot and never falls back to fixtures; Slice 4 now validates and builds production output locally.

## 5. Development sequence

Implement the slices in order, with each slice independently reviewable. Do not enable production publication before slice 5 passes its release checks.

### Slice 1 — Source review and policy foundation

- [x] Populate and verify explicit provider series IDs for pilot automatic sources; URLs remain readable references.
- [x] Review definitions, units, frequency, coverage/seasonality, publication lag, history, revisions, and public redistribution conditions for pilot sources (activation remains gated).
- [x] Fix the reserve/assets formula and document normalization semantics in the registry guide. Preserve the updated bank-assets and ON RRP definitions.
- [x] Implement policy validation and the version 2 contract; keep the current registry validator usable for incomplete future entries.
- [x] Resolve the repo pilot's exact measure, source reference, source unit, and observation-date convention; updated to automatic FRED `RPONTTLD` on November 16, 2026.

Implemented November 16, 2026: [source review](source-review.md),
[contract reference](production-contract.md), `scripts/policies.py`,
`scripts/contracts.py`, and offline regression tests. The original manual
all-collateral repo specification was superseded at the maintainer's request by
automatic FRED `RPONTTLD`, covering Treasury, agency debt, and agency MBS collateral. The registry, source
review, and policy now reflect that choice.
`python3 scripts/policies.py` checks all five pilot specifications. The activation
set is empty; `--check-activation` fails until executable paths arrive in later
slices. No credentials are read, no production observations generated, and no
publication workflow enabled by this slice.

Verification: 34 Python tests and 10 JavaScript regression checks passed; the
demo build and registry/policy validation passed. The JavaScript suite ran through
the available Node runtime because the local shell has no `node` executable.
Demo observations stayed unchanged; generated catalog metadata reflects the CSV.

Exit check: pilot specifications are complete; unknown conversions, ambiguous transforms, missing implementations, or conflicting ownership cannot be activated. No live credentials are needed for this slice.

### Slice 2 — Manual import and fixture isolation

No manual data preparation is required to begin this slice. Implement build-mode
isolation and the importer using temporary test registries/CSV fixtures for a
manual series; do not activate a placeholder or use `fed-repo` as manual input.
The maintainer has selected the three SIFMA issuance series as manual test inputs:
`bond-issuance`, `treasury-bond-issuance`, and `corporate-bond-issuance`. Prepared
samples can exercise the importer after their registry source, units, and monthly
date conventions are specified. Their production activation remains in Slice 6.

- [x] Prepare the SIFMA issuance CSVs from the saved Wind workbook with `scripts/export_wind_issuance.py` (November 17, 2026). This `openpyxl` adapter checks headers, billions units, manual ownership, month-end dates, and cached numeric values. The raw workbook is versioned in `data/sources/wind/`; outputs use `date,value` in `data/manual/`. This does not implement the CSV importer, Git-baseline correction checks, source activation, or publication. See the [export workflow](../data/README.md#exporting-the-wind-workbook).
- [x] Implement UTF-8 CSV import with exactly `date,value` at `data/manual/<series-id>.csv`; blank values become null. Enforce the two-column schema, sorted unique ISO dates, finite numbers, and supported registry units. Resolve the shared source reference and table/measurement details from `data/registry.csv`, not individual observations. Require a reviewed source reference before activation; no publication-date or correction-note columns are maintained.
- [x] Compare manual edits against the previous committed input. Changed values, nulling a prior value, and removed rows require a reason in the input commit message identifying the series and affected dates or range. New rows need no correction reason. CI fetches enough history for this comparison and reports a missing baseline rather than bypassing validation.
- [x] Enforce input ownership: manual files cannot override automatic or derived inputs. The importer is read-only; a shared ownership gate rejects automatic access to manual series. Slice 3 collectors must use this gate and write only automatic paths.
- [x] Add explicit demo and production build modes. Preserve existing demo commands/tests; production cannot invoke `generate_fixtures.py` or write to its output paths.

Implemented November 17, 2026. The workbook, exported inputs, exporter, and related
changes were already committed together in `7ea1a09` before importer work.
`scripts/import_manual.py` audits every first-parent input revision, accepts
`Manual-Reason: <series-id> YYYY-MM-DD[..YYYY-MM-DD]: <reason>` lines in each
correcting commit, and supports read-only working-tree preflight. CI fetches full
history. Tests use isolated Git repositories and registries for additions,
corrections, nulling, removals, ownership, units, and missing baselines.
The three SIFMA files validate as candidate inputs (570 observations); source
review and production activation remain deferred. See the
[import commands and audit semantics](../data/README.md#manual-observation-files-slice-2-format).

`python3 scripts/build.py --mode production` requires a version 2 snapshot and
validates its contract. Missing/invalid snapshots fail before any output changes;
valid snapshots are also blocked until Slice 4 supplies production assembly and
rendering. `--mode demo` and the existing no-argument build preserve demo behavior.

Exit check: a manual addition and a documented correction validate as candidate inputs offline using isolated test fixtures (full snapshot assembly arrives in Slice 4); duplicate dates, undocumented corrections/removals, and cross-method writes fail. Production with no snapshot fails without modifying demo files.

### Slice 3 — FRED collection, normalization, and derivation

Decision, November 17: fetch the **entire current FRED history from 2010-01-01 onward on every run** and
replace the prior series only after the complete response validates. Recompute
all derived history from the resulting inputs. No ALFRED/vintage queries,
point-in-time dataset, revision ledger, incremental merge, or affected-date
recomputation is needed. Revision reporting is only three counts (added, changed,
removed) against the prior file; Git supplies ordinary file history and rollback.
Use one observations request per series with `limit=100000` and `offset=0`;
pagination is unnecessary for this scope and is not implemented. A response that
exceeds the limit or returns fewer observations than its reported count fails
collection. Series introduced after 2010 retain their actual inception dates.

- [x] Implement metadata review checks and JSON observations collection for `WALCL`, `SOFR`, `EFFR`, and `RPONTTLD`. Read only `FRED_API_KEY` from the environment or ignored local `.env`; never record credential-bearing URLs.
- [x] Fetch the complete 2010-onward window every time in a single response, with response-count and cutoff-aware metadata-bound checks. Unexpected empty/truncated or over-limit responses fail collection; provider missing markers become null. Keep source-scale values before project normalization.
- [x] Add bounded retries/timeouts for transient failures and source-specific freshness diagnostics. Do not change providers after a failure.
- [x] Normalize units and implement the pilot spread. Cover reserve/assets and FRED `chg` with illustrative offline inputs, without activating those future series.
- [x] Retain a series's previous valid input on collection failure. A first-time failed series has no history. Report revision/removal counts, unchanged responses, and failures distinctly.

Implemented in `scripts/collect.py`, `scripts/providers/fred.py`,
`scripts/normalize.py`, and `scripts/derive.py`; policy version 4. Run
`python3 scripts/collect.py` to refresh candidate files under `data/automatic/`.
Normalization and derivation are recomputed in memory; production snapshot assembly
and publication remain in Slices 4–5. `--check-activation` now verifies executable
pilot paths successfully, but `ACTIVE_SERIES` remains empty.

The initial live November 17 download, before the 2010 cutoff, validated 1,248 WALCL, 2,249 SOFR, 6,880 EFFR, and
7,011 RPONTTLD observations. Bounds and first values match the published FRED
tables; see the [reconciliation record](source-review.md#slice-3-live-reconciliation).
Offline tests cover single-response completeness, the 2010 cutoff, later inception,
over-limit rejection, metadata drift, malformed/truncated responses,
retries, source compatibility, full replacement and revision propagation,
unchanged checks, partial failure, source ownership, and normalization/formulas.
Verification: all 81 Python tests and 18 JavaScript regression checks passed;
registry/policy checks and demo/manual-preview builds passed. A second live
refresh returned unchanged observations for all four sources, advancing check
times while preserving change times. Demo files remained unchanged.

After simplifying to one observations response and applying the 2010 cutoff,
all 83 Python tests passed. A live refresh saved 880 WALCL, 2,249 SOFR, 4,401 EFFR,
and 4,402 RPONTTLD observations, with no revised values in the overlapping history.
Pre-2010 removals are the intended collection-window change, not provider revisions.

Freshness is a conservative calendar-day warning: 14 days for WALCL and 7 for
each daily pilot, measured from the latest numeric observation. It tolerates
ordinary release lags and holidays, does not fabricate missing dates, and does
not reject an otherwise valid response. More precise release calendars can be
added if operational experience warrants them.

Retained inputs are reusable only when the reviewed specification, source identity,
units, and provider transformation match the current policy. After a reviewed
source change, a successful full refetch replaces the old definition; a failed
refetch blocks promotion rather than relabeling or retaining incompatible history.

Exit check: one real download matches its source; a provider revision changes derived history; an unchanged response preserves values but advances check metadata; one failed fetch retains its history while another source updates. Never manufacture values to complete the pilot.

### Slice 4 — Snapshot assembly and frontend migration

A local SIFMA preview preceded production assembly on November 17, 2026.
It was retired after the three issuance series entered production.

- [x] Assemble activated automatic/manual inputs and derived outputs into one validated version 2 snapshot. Unconnected categorized numeric entries emit empty arrays; unavailable entries are omitted; unquantified entries stay nonnumeric.
- [x] Validate IDs, ownership, policy consistency, dates, finite/null values, units, provenance, and shared snapshot identity before replacing the publishable candidate.
- [x] Update `catalog.py`, production build validation, and the frontend loader together. Remove unconditional synthetic explanations and notices only in production mode, including chart tooltips, accessibility text, statistics, and expanded details.
- [x] Guard empty selected ranges and single-point histories in overview cards, charts, dataset dates, and expanded-dialog first/last-date access. Distinguish `待接入`, no observations in a selected range, and unquantified explanations.
- [x] Preserve observation dates beside latest values. Keep collection diagnostics in manifest/Actions reports. Do not add `最近检查`, `人工录入时间`, `自动更新`, `人工维护`, or update-status badges to charts or overview cards.

Comparison policy for the initial implementation:

| Frequency | Comparisons | Matching rule |
| --- | --- | --- |
| Daily | 4 and 13 calendar weeks | Latest valid observation on/before the target date, at most 7 calendar days old; explicit missing target observations return `—` |
| Weekly | 4 and 13 calendar weeks | Exact observation date; missing comparator returns `—` |
| Monthly | 1 and 12 months | Same source observation-date convention in the target month; missing month returns `—` |
| Quarterly | 1 and 4 quarters | Same source observation-date convention in the target quarter; missing quarter returns `—` |
| Annual / irregular | No default comparison | Require a reviewed series-specific policy before displaying a change |

Comparison matching is only for summary metrics; it never fills source history or relaxes derived-input joins. Anchor chart ranges to the snapshot's latest observation date, not a download timestamp. Keep 3M/1Y arithmetic means over actual native observations ending on each series's latest valid date, and the selected-range empirical percentile. State the sample basis and count; do not increase counts by filling dates. Comparison-unit scaling must be explicit so bp-normalized data is not converted twice.

Exit check: weekly and daily pilot data and monthly/quarterly/irregular test inputs render with correct labels, values, gaps, counts, and empty states. Deep links, repository-subpath hosting, keyboard controls, and mobile layouts continue to work. Demo mode remains clearly synthetic.

Implemented November 17, 2026: `scripts/assemble.py` validates saved source inputs,
normalizes and derives histories offline, and promotes the complete content-hashed
snapshot atomically. Production builds validate/copy that snapshot; the frontend
uses reviewed metadata and frequency-specific comparisons. Source-only inputs stay
outside the chart map; pending indicators remain empty. Publisher: Junyan Liu.
The manifest records base source commit, exact source-file hashes and local changes;
commit source changes and reassemble before a release.

Verification: 96 Python tests and 26 JavaScript checks passed. The suites cover
assembly, manual ownership,
retained/failed sources, corruption, atomic replacement, production markup, source
notices, daily/weekly/monthly/quarterly comparisons, native sample counts, deep links,
empty dialogs and keyboard cancellation. HTTP preview responds successfully.
Follow-up desktop Chrome verification reproduced a cached pre-migration script
reading schema-v2 observations and crashing in `latestObservation`. Build output now
versions the complete JavaScript import graph and styles; JSON requests revalidate
cached responses. An ordinary reload, visible charts, statistics, expanded details,
and Escape-to-close were verified in Chrome. Cache regression tests brought the
passing suite to 99 Python tests and 26 JavaScript checks. Mobile visual acceptance remains
**pending** at completion of Slice 4. On November 17 the maintainer deferred mobile
UI work and requested Slice 5 implementation. Slice 4 itself changed no deployment.

### Slice 5 — Automated publication and rollback

- [x] Extend CI so pull requests run offline validation and both contracts' tests without secrets or deployment. Manual input changes assemble from last validated automatic inputs without requiring a successful network request.
- [x] Add daily and on-demand collection on the default branch. The daily schedule is `17 7 * * *` UTC (15:17 Asia/Shanghai), after the previous US business day's releases; this is a daily research refresh, not a release-time guarantee. Scheduled jobs can be delayed. [GitHub Actions scheduling](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule).
- [x] Serialize all production writers and publication runs in one shared concurrency group; do not cancel a writer midway through promotion. Refresh the default-branch checkout after obtaining the lock. If inputs advance before the snapshot commit, reassemble from the newer inputs rather than force-pushing stale output.
- [x] Commit validated automatic inputs and snapshot together, then build and deploy from that exact artifact commit. Permit repository writes only in the trusted publication job, subject to branch rules; keep pull requests read-only. If direct writes are disallowed, use a data-update PR and publish after merge.
- [x] Configure only the built-in `GITHUB_TOKEN` for generated pushes; publish in the same workflow. GitHub documents that these pushes do not trigger another push workflow. Hosted verification of this token/trigger strategy remains part of release acceptance.
- [x] Upload the complete Pages artifact as one unit. Fatal validation/build errors block upload. Recoverable source failures may publish retained history, with warnings reported in the workflow summary. Hosted deployment acceptance remains pending.
- [x] Document and exercise restoring an earlier committed snapshot without fresh collection using temporary Git remotes. Exclude credentials, manual exports, and unreviewed observations from Pages artifacts. Live redeployment acceptance remains pending.
- [ ] Observe first production deployment, on-demand/scheduled execution, and a live rollback/recovery; verify generated commits do not start recursive runs.

Implementation: `scripts/check.py` runs offline checks for all three build modes;
`scripts/release.py` prepares, validates and stamps exact artifacts;
`scripts/publish.py` uses disposable worktrees, bounded reassembly on concurrent
input changes, normal fast-forward pushes and a data-PR fallback. One Actions job
holds the production lock through deployment. Rollback restores saved automatic
inputs and exact snapshot bytes in a new commit on current `main`.
The [publication runbook](publication.md) covers setup, modes, PR delivery, error
handling, artifact identities and rollback. Local integration tests exercise real
Git races, protected-branch fallback, merge/squash adoption, exact rollback,
fatal preservation, retained histories and public artifact exclusions.

The maintainer reports the FRED secret and Pages Actions source are configured.
The GitHub repository exists and is public. Existing source workbooks remain
versioned by the earlier maintainer decision; excluding them from Pages does not
remove them from repository history. NY Fed terms/notices were rechecked for the
pilot on November 17, 2026; no additional series are activated.

Verification on November 17: 117 Python tests and 26 JavaScript checks passed;
actionlint 1.7.12 reported no workflow errors. An end-to-end publication rehearsal
used a disposable clone with the saved real inputs and a local bare remote, ran
the complete offline suite, committed the candidate, and built/stamped the exact
remote artifact revision without an API key. The source checkout stayed clean in
that rehearsal. No implementation commit was pushed to GitHub and no live
deployment was performed during local implementation.

Exit check: the first production milestone is published successfully; scheduled, on-demand, and manual-input paths converge on the same assembler. A concurrent-input scenario cannot publish an older snapshot over a newer one, and rollback works from Git history.

### Slice 6 — Expand coverage

- [x] Activate reviewed FRED reserves/assets, TGA, daily ON RRP, primary credit,
  swap lines, FIMA repo, bank loans, quarterly lending standards, SOFR99 and its
  tail spread. Match source-specific seasonal adjustment, Wednesday date labels,
  quarter starts and freshness allowances. Disclose reserve/assets coverage mismatch.
- [x] Activate all three real SIFMA monthly inputs using the audited importer.
  Maintainer confirmed monthly gross issuance, all maturities, components included
  in total, and public redistribution permission. Embedded Wind IDs are recovered
  and documented; workbook/CSV values reconcile and aggregate YTD matches SIFMA.
  Publication tests cover addition, documented correction/removal and rejected
  undocumented changes, using temporary Git remotes.
- [x] Activate hidden Treasury yield change with explicit `chg` and ×100 to bp once.
- [x] Activate ICE IG/HY credit spreads and the Cboe VIX index after the maintainer
  confirmed redistribution permission on November 18; keep Treasury bid–ask
  deferred. Preserve FRED's rolling three-year window and month-end weekend dates,
  and retain VIX index levels with explicit missing markers.
- [x] Leave cross-currency basis, CDS, ETFs, depth, positioning and leverage unavailable.
- [x] Review Wind USDX and MOVE identifiers, index levels, date convention and exported histories.
- [x] Record Wind redistribution permission and activate both daily indices in policy version 8.
- [ ] Define FINRA coverage/units and the price-impact proxy methodology before activation.

Implementation and evidence: [Slice 6 source review](source-review-slice-6.md).
Policy version 7 contains 24 activated series (18 automatic, three manual, three
calculated), with 19 displayed charts and five hidden inputs. Versions 4–6 snapshots
remain readable for exact rollback. Full live refresh validated all active automatic
histories; the ICE and VIX inputs were fetched only after the maintainer recorded
redistribution permission.

Before release, commit the definitions and inputs together so manual assembly can
bind to their audited revision, then run the full offline checks and publish from
that commit. Hosted deployment/rollback acceptance remains the Slice 5 release
follow-up; local implementation does not claim it has occurred.

Exit check per new series: source review, historical sample reconciliation,
normalization and date tests, provenance, failure handling, and UI rendering.
Full coverage remains subject to the explicit deferred items above.

## 6. Verification and release record

Use existing Python unittest and Node test runners. Add tests for behaviors that could corrupt observations or publication, rather than tests that only reproduce implementation details.

| Area | Required evidence |
| --- | --- |
| Normalization | Millions → billions; ratio → percent; percent-point difference → bp once; identity conversions |
| Transformations | `chg` request is explicit and distinct from `pch`; missing source periods are not silently replaced by previous valid values |
| Manual integrity | Two-column CSVs; additions; commit-documented revisions/nulling/removals; missing baselines; duplicate dates; missing/invalid registry source references; ownership rejection |
| Automatic history | Single-response counts, 2010 cutoff/later inception, over-limit rejection, provider missing markers, true zeroes, revisions, unchanged responses, truncated/empty failure, bounded retries |
| Derived history | Same-date joins, null inputs, zero denominator, dependency order, revision propagation, stale retained inputs with compatible dates |
| Production UI | Empty/all-null/single-point/short histories; mixed frequencies; holidays; ranges without points; correct comparison labels and sample counts |
| Publication | Snapshot-ID mismatch rejected; partial failure retained; invalid manual/assembled data blocked; concurrent changes handled; rollback verified |
| Isolation | Demo fixture outputs unchanged by production; no synthetic fallback; no credentials in artifacts/logs; no operational chart badges |

Before first publication, record the activated IDs, policy version, snapshot/artifact commit, source reconciliation results, commands/tests run, browser checks, and rollback snapshot in the release PR. Existing checks remain:

```sh
python3 scripts/registry.py
python3 scripts/policies.py
python3 -m unittest discover -s tests -p 'test_*.py'
node --test tests/data.test.mjs
git diff --check
```

Run `python3 scripts/build.py --mode demo` for the existing demo build, and
`python3 scripts/import_manual.py` for committed input validation. Production assembly writes a validated snapshot; the production build copies it
to the output directory after validation. Git snapshots preserve versions captured by this project, not a
reconstructed point-in-time publication-vintage dataset.
