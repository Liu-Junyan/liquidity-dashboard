# Real-data integration development plan

Updated: November 16, 2026. Status: planned; no production collector or real-data deployment is enabled.

## 1. Goal and first release

Replace synthetic observations with validated automatic and manual inputs while retaining the existing Chinese-language static dashboard and GitHub Pages hosting. Keep the four research layers, CSV-controlled membership, source-only inputs, chart interactions, and statistics disclosures.

This document defines the implementation sequence. The [mixed-source implementation guide](implementation-brief.md#mixed-source-data-implementation-guide-future-real-data-milestone) remains the requirements reference; the [registry guide](../data/README.md) defines the editable CSV. All commands and new paths described below are proposed unless explicitly identified as existing.

The first production milestone is deliberately small:

- Fed total assets (`fed-assets`, FRED `WALCL`), exercising weekly collection and amount conversion.
- SOFR and EFFR source inputs, producing `sofr-effr-spread`, exercising daily collection and derivation.
- One verified manual series, exercising import, correction history, and publication. Prefer `fed-repo` after defining the exact operations measure; another registry manual series may be selected if its source is ready first.
- Other categorized entries remain visible with `待接入` and empty charts until their implementations pass activation checks. Existing `unavailable` entries remain excluded; source-only inputs remain hidden.

Completion means these series work through collection/import, normalization, derivation, snapshot assembly, frontend rendering, and repeatable publication. Full coverage of all 23 displayed indicators is a later milestone. Trading signals, a database, accounts, and maintenance controls in the browser are outside this release.

## 2. Current state and implementation constraints

| Existing component | Current behavior | Required change |
| --- | --- | --- |
| `data/registry.csv` and `scripts/registry.py` | Membership, specifications, dependency checks, optional JSON export | Add production completeness checks for activated series without requiring all draft sources to be finished |
| `scripts/catalog.py` | Generates weekly demo metadata and synthetic explanations | Generate production metadata separately, using native frequencies and reviewed explanations |
| `scripts/build.py` | Always calls the fixture generator; validator requires demo flags and a shared weekly grid | Explicit demo/production modes; production consumes a validated snapshot without generating observations |
| `site/assets/data.js` | Exact-date 4/13-week comparisons; weekly frequency label | Frequency-specific comparisons and labels; preserve valid sample counts |
| `site/assets/app.js` and `charts.js` | Synthetic wording; dialog indexes first/last points | Production labels, version checks, and safe empty/short-history rendering |
| `.github/workflows/pages.yml` | Builds fixtures on pushes, pull requests, and manual runs | Add collection and snapshot publication after local production validation works |

Use Python 3.10+ and standard-library modules initially. If a dependency becomes necessary, document it and use the environment specified in AGENTS.md. Keep routine tests offline. Do not add extra maintainer-filled registry columns for scheduling, matching, or aggregation policies.

## 3. Calculation and source decisions

### Normalize before evaluating formulas

`source_unit` describes the collector/importer's input scale; `normalized_unit` describes the values supplied to downstream formulas and the website. Raw/source-scale observations and normalized observations must remain distinguishable. Unit labels alone do not execute conversions.

| Series | Planned rule | Example / acceptance result |
| --- | --- | --- |
| `reserve-balances` | Millions → billions: divide by 1,000 | 3,000,000 → 3,000 |
| `bank-total-assets` | Billions → billions: unchanged | 25,000 → 25,000 |
| `reserve-assets-ratio` | `100 * reserve-balances / bank-total-assets`, using normalized inputs | 3,000 / 25,000 → 12 (%) |
| `sofr-effr-spread`, `sofr-tail-spread` | Subtract normalized percent-level inputs; current `%` outputs retain percentage-point scale | 4.10 − 4.00 → 0.10; multiply by 100 only if the output is explicitly changed to bp |
| `treasury-yield-chg` | Request `DGS10` with `units=chg`; current registry specifies `%` → `bp`, so multiply the returned difference by 100 once | Yield 4.00% → 4.10% gives API change 0.10, then normalized change 10 bp |
| `reverse-repo` | Use the updated `RRPONTSYD` mapping; daily billions → billions | No weekly resampling or amount conversion by default |

The reserve/assets CSV formula currently omits `100`; correct it in the source-definition implementation slice before activation. Confirm reserve and bank-asset population coverage and seasonal-adjustment conventions in the explanation; common units alone do not establish identical coverage. Normalize legacy spellings such as `Biliions` through a documented alias or a registry correction before activation.

FRED supports `units=chg` (difference) and `units=pch` (relative percent change). Use `chg` for the agreed Treasury yield measure. The current `notes=units=chg` records intent; implement an explicit request policy keyed by series ID rather than executing or parsing arbitrary notes. Retain `automatic` ownership for this provider-transformed series. Record both the original provider units and applied transformation in provenance. [FRED API: transformations](https://fred.stlouisfed.org/docs/api/fred/series_observations.html#units).

The latest registry's Treasury output is bp. If percent-scale output is preferred later, explicitly change `normalized_unit` to `%`, remove the scaling step, and review dependent price-impact units. Do not silently change that choice during implementation.

### Native dates and derived inputs

- Preserve each source's dates, native frequency, and available history. Observation dates, publication dates, and collection times have separate meanings.
- Join derived inputs on equal observation dates by default, after normalization. Missing inputs and zero denominators yield null. Recompute affected derived history after revisions.
- Do not forward-fill inputs or interpolate. A different alignment needs a named per-indicator rule and an age limit in code.
- Preserve explicit missing values and true zeroes. Do not add weekend or holiday observations to native data. Identify unexpected missing periods using source-specific calendars where needed.
- Use named calculation functions keyed by derived series ID, validated against their declared inputs and formula. Hyphenated IDs are identifiers, not Python subtraction expressions; do not use unrestricted `eval` on registry text. Reject unknown or mismatched calculation definitions before activation.

## 4. Storage, policy, and production contract

Keep `data/registry.csv` authoritative; `data/registry.json` remains an optional generated export and never controls production independently.

| Planned path | Responsibility |
| --- | --- |
| `scripts/policies.py` | Activated-series set; provider request transforms; conversions; date, comparison, and freshness policies |
| `scripts/import_manual.py` | Parse and validate manually maintained inputs and corrections |
| `scripts/collect.py` and `scripts/providers/fred.py` | Fetch, validate, and stage automatic inputs with bounded retries/timeouts |
| `scripts/normalize.py` and `scripts/derive.py` | Convert source-scale values and calculate dependency-ordered outputs |
| `scripts/assemble.py` | Validate the complete candidate dataset and create one snapshot |
| `data/manual/<series-id>.csv` | Maintainer-owned source observations |
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

Use temporary staging directories and atomic replacement after validation. The production build copies a selected snapshot into the output directory without overwriting checked-in demo observations in `site/data/`. Proposed commands should fail clearly for a missing snapshot and never fall back to fixtures.

## 5. Development sequence

Implement the slices in order, with each slice independently reviewable. Do not enable production publication before slice 5 passes its release checks.

### Slice 1 — Source review and policy foundation

- [ ] Populate and verify explicit provider series IDs for pilot automatic sources; URLs remain readable references.
- [ ] Review definitions, units, frequency, coverage/seasonality, publication lag, history, revisions, and public redistribution conditions for each activated source.
- [ ] Fix the reserve/assets formula and document normalization semantics in the registry guide. Preserve the updated bank-assets and ON RRP definitions.
- [ ] Implement policy validation and the version 2 contract; keep the current registry validator usable for incomplete future entries.
- [ ] Resolve the pilot manual series's exact measure, source reference, source unit, and observation-date convention.

Exit check: pilot specifications are complete; unknown conversions, ambiguous transforms, missing implementations, or conflicting ownership cannot be activated. No live credentials are needed for this slice.

### Slice 2 — Manual import and fixture isolation

- [ ] Implement UTF-8 CSV import with `date,value,source_reference,publication_date,correction_note`; blank values become null. Enforce sorted, unique ISO dates, finite numbers, required references, and supported units.
- [ ] Compare manual edits against the previous committed input. Changed values or nulling a prior value require a correction note; removed rows require an explicit reason in the input commit message. New rows need no correction note. CI fetches enough history for this comparison and reports a missing baseline rather than bypassing validation.
- [ ] Enforce ownership: collectors cannot write manual files, and manual files cannot override automatic inputs.
- [ ] Add explicit demo and production build modes. Preserve existing demo commands/tests; production cannot invoke `generate_fixtures.py` or write to its output paths.

Exit check: a manual addition and a documented correction assemble offline; duplicate dates, undocumented corrections/removals, and cross-method writes fail. Production with no snapshot fails without modifying demo files.

### Slice 3 — FRED collection, normalization, and derivation

- [ ] Implement metadata review checks and JSON observations collection for `WALCL`, then `SOFR` and `EFFR`. Store `FRED_API_KEY` in the local environment and later Actions secrets; never record credential-bearing URLs.
- [ ] Fetch complete available histories initially, including pagination and response-count checks, to capture revisions. Unexpected empty/truncated responses fail collection; provider missing markers become null. Keep source-scale values before project normalization.
- [ ] Add bounded retries for transient failures and source-specific freshness expectations. Do not change providers after a failure.
- [ ] Normalize units and implement the pilot spread. Add normalization/derivation cases for reserve/assets and FRED `chg` using recorded or small illustrative test inputs, even if those series are activated later.
- [ ] Retain a series's previous valid input on collection failure. A first-time failed series has no history. Report revisions, removals, unchanged responses, and failures distinctly.

Retained inputs are reusable only when source identity, source units, and provider transformation match the current policy. A source or transformation change needs an explicit migration/refetch; do not relabel old observations as if they came from the new definition. A mismatch in an activated policy blocks assembly until resolved.

Exit check: one real download matches its source; a provider revision changes derived history; an unchanged response preserves values but advances check metadata; one failed fetch retains its history while another source updates. Never manufacture values to complete the pilot.

### Slice 4 — Snapshot assembly and frontend migration

- [ ] Assemble activated automatic/manual inputs and derived outputs into one validated version 2 snapshot. Unconnected categorized numeric entries emit empty arrays; unavailable entries are omitted; unquantified entries stay nonnumeric.
- [ ] Validate IDs, ownership, policy consistency, dates, finite/null values, units, provenance, and shared snapshot identity before replacing the publishable candidate.
- [ ] Update `catalog.py`, production build validation, and the frontend loader together. Remove unconditional synthetic explanations and notices only in production mode, including chart tooltips, accessibility text, statistics, and expanded details.
- [ ] Guard empty selected ranges and single-point histories in overview cards, charts, dataset dates, and expanded-dialog first/last-date access. Distinguish `待接入`, no observations in a selected range, and unquantified explanations.
- [ ] Preserve observation dates beside latest values. Keep collection diagnostics in manifest/Actions reports. Do not add `最近检查`, `人工录入时间`, `自动更新`, `人工维护`, or update-status badges to charts or overview cards.

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

### Slice 5 — Automated publication and rollback

- [ ] Extend CI so pull requests run offline validation and both contracts' tests without secrets or deployment. Manual input changes assemble from last validated automatic inputs without requiring a successful network request.
- [ ] Add daily and on-demand collection on the default branch. A proposed daily schedule is `17 7 * * *` UTC (15:17 Asia/Shanghai), after the previous US business day's releases; this is a daily research refresh, not a release-time guarantee. Scheduled jobs can be delayed. [GitHub Actions scheduling](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule).
- [ ] Serialize all production writers and publication runs in one shared concurrency group; do not cancel a writer midway through promotion. Refresh the default-branch checkout after obtaining the lock. If inputs advance before the snapshot commit, reassemble from the newer inputs rather than force-pushing stale output.
- [ ] Commit validated automatic inputs and snapshot together, then build and deploy from that exact artifact commit. Permit repository writes only in the trusted publication job, subject to branch rules; keep pull requests read-only. If direct writes are disallowed, use a data-update PR and publish after merge.
- [ ] Prevent generated commits from starting recursive collection. Verify this for the token/trigger strategy actually used. Publish in the same authorized workflow rather than assuming a generated commit will trigger another workflow.
- [ ] Deploy the complete Pages artifact as one unit. Fatal validation/build errors leave the previous deployment intact. A recoverable individual source failure may publish retained history, with failures reported in the workflow summary.
- [ ] Document and exercise restoring an earlier committed snapshot and redeploying it without fresh collection. Exclude credentials, private manual exports, and unsupported redistribution from public artifacts.

Exit check: the first production milestone is published successfully; scheduled, on-demand, and manual-input paths converge on the same assembler. A concurrent-input scenario cannot publish an older snapshot over a newer one, and rollback works from Git history.

### Slice 6 — Expand coverage

- [ ] Add remaining reviewed FRED sources, including reserves/assets, daily ON RRP, credit spreads, facility usage, bank loans, VIX, and quarterly lending standards. Apply each source's actual conventions rather than inheriting the pilot's defaults.
- [ ] Add SIFMA monthly inputs after defining the specific tables, measures, and potential overlap among aggregate/Treasury/corporate issuance entries. Add iFind exports only with traceable identifiers, adjustment conventions, and permitted publication scope.
- [ ] Verify the Treasury bid–ask source and instrument definition; the current provider label alone is insufficient.
- [ ] Activate Treasury yield change with the explicit `chg` request and current bp normalization once reviewed. Defer price impact until FINRA coverage, volume units, matching dates, sign/absolute-value convention, and the proxy's interpretation are defined. A yield-change/aggregate-volume ratio must not be presented as a directly measured market-impact coefficient without methodological support.
- [ ] Leave cross-currency basis, CDS, ETFs, depth, positioning, and leverage unavailable until their individual definitions and sources are confirmed.

Exit check per new series: source review, historical sample reconciliation, normalization and date tests, provenance, failure handling, and UI rendering pass before activation. Full coverage is not a prerequisite for the pilot release.

## 6. Verification and release record

Use existing Python unittest and Node test runners. Add tests for behaviors that could corrupt observations or publication, rather than tests that only reproduce implementation details.

| Area | Required evidence |
| --- | --- |
| Normalization | Millions → billions; ratio → percent; percent-point difference → bp once; identity conversions |
| Transformations | `chg` request is explicit and distinct from `pch`; missing source periods are not silently replaced by previous valid values |
| Manual integrity | Additions, documented revisions/removals, duplicate dates, invalid references, and ownership rejection |
| Automatic history | Pagination, provider missing markers, true zeroes, revisions, unchanged responses, truncated/empty failure, bounded retries |
| Derived history | Same-date joins, null inputs, zero denominator, dependency order, revision propagation, stale retained inputs with compatible dates |
| Production UI | Empty/all-null/single-point/short histories; mixed frequencies; holidays; ranges without points; correct comparison labels and sample counts |
| Publication | Snapshot-ID mismatch rejected; partial failure retained; invalid manual/assembled data blocked; concurrent changes handled; rollback verified |
| Isolation | Demo fixture outputs unchanged by production; no synthetic fallback; no credentials in artifacts/logs; no operational chart badges |

Before first publication, record the activated IDs, policy version, snapshot/artifact commit, source reconciliation results, commands/tests run, browser checks, and rollback snapshot in the release PR. Existing checks remain:

```sh
python3 scripts/registry.py
python3 -m unittest discover -s tests -p 'test_*.py'
node --test tests/data.test.mjs
git diff --check
```

Run `python3 scripts/build.py` for the existing demo build. Implementation must document the new production commands when they become available; this plan does not imply they already exist. Git snapshots preserve versions captured by this project, not a reconstructed point-in-time publication-vintage dataset.
