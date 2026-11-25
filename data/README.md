# Source registry

**`registry.csv` is the source of truth for dashboard indicators.** Run `python3 scripts/build.py` after editing it. The build regenerates `site/data/catalog.json`, synthetic `site/data/observations.json`, and the static `dist/` directory. Do not edit the generated site JSON to change the indicator list.

## Display rules

- A row appears when it has a `category` and `indicator_id`, and its status is not `unavailable`.
- `unavailable` rows remain in the registry for future use but are omitted from overview counts, chart cards, detail links, and generated observations.
- A blank `category` marks a source-only calculation input. It stays off the dashboard even if `indicator_id` is populated, as in the existing SOFR/EFFR input rows.
- Deleting a row removes it from the dashboard. If it is still a calculation input, remove or update its dependents first; unknown input references remain errors.
- Names, grouping, and indicator order within each category follow the CSV. New IDs need no entry in an old catalog or Markdown inventory.
- The four research-layer definitions live in `categories.json`. An empty layer remains selectable and displays an empty state.

The current CSV has 37 series: 23 displayed indicators (9 monetary, 3 offshore, 7 credit, 4 financial-market), 6 source-only inputs, and 8 unavailable entries. Investment-grade and high-yield credit spreads use separate IDs, `credit-spreads-ig` and `credit-spreads-hy`.

**Dashboard observations remain explicitly synthetic.** The demo connects the registry to dashboard membership and metadata; it does not fetch source data, consume manual observations, execute formulas, or apply `less`/`greater` as judgments about market conditions. The separate manual importer validates candidate inputs without changing the dashboard. Registered source references appear in expanded details as intended sources. The demo still uses a weekly fixture grid; `native_frequency` records the planned source frequency separately. Missing normalized units display `待确认` rather than inheriting an obsolete catalog definition.

## Editing routine

1. Open `registry.csv` as UTF-8, comma-delimited text. Keep IDs as text and preserve the 16 headers. Quoted commas, Chinese text, and multiline notes are supported.
2. Keep stable IDs unique. To display a new indicator, fill `category` with `货币层`, `离岸层`, `信用层`, or `金融市场层` and provide an `indicator_id`. For calculation inputs, leave `category` blank.
3. Set `status=unavailable` to hide a future indicator. Other allowed values are `draft` (also the default for a blank status), `ready`, and `unquantified`. Unquantified visible entries display an explanatory nonnumeric state.
4. Validate with `python3 scripts/registry.py`, then rebuild with `python3 scripts/build.py`. CI rebuilds from the CSV before running tests.

`ready` records the maintainer's intended configuration; it is not proof of source availability or a completed collector. Ready numeric rows require an update method and native frequency; automatic/manual rows also require a provider, and derived rows require known ready inputs and a formula. Source references, provider IDs, units, and comparison notes may still be completed later for nonpilot entries. The separate production policy validator checks reviewed pilot definitions and gates activation on executable implementations.

To export all registry records (including hidden rows and source-only inputs) for future pipeline use:

```sh
python3 scripts/registry.py --output data/registry.json
```

The JSON export is optional, generated, and ignored by Git. It uses `schemaVersion: 1` and a `series` object keyed by `series_id`. Blank cells become `null`; input IDs become arrays. The dashboard build reads the CSV directly, so a stale export cannot control the displayed list.

## Field guide

| Column | What to enter |
| --- | --- |
| `series_id` | Unique stable lowercase ASCII slug, including for hidden and source-only rows. |
| `indicator_id` | Stable dashboard ID for categorized rows. Source-only rows may leave it blank or retain their series ID. |
| `category` | Research layer; leave blank for source-only inputs. |
| `name` | Display name, used verbatim for the chart/overview. Required. |
| `status` | `draft`, `ready`, `unquantified`, or `unavailable`; blank means draft. |
| `update_method` | One of `automatic`, `manual`, or `derived`; required when ready. |
| `provider` | Provider or publishing organization; required for ready automatic/manual rows. A manual provider can be recorded without a public URL. |
| `source_reference` | Optional source URL or publication/table reference. Do not enter credentials. |
| `provider_series_id` | Optional provider code, ticker, release field, or endpoint identifier. |
| `native_frequency` | `daily`, `weekly`, `monthly`, `quarterly`, `annual`, or `irregular`; required when ready. |
| `source_unit` | Original input unit; preserved as source metadata. |
| `normalized_unit` | Display/output unit. Known amount scales and bp/% labels are localized; unknown labels are preserved. Blank displays `待确认`. |
| `comparison_rules` | Your comparison/interpretation notes, including existing `less`, `greater`, or `none` values; currently stored without changing chart calculations or colors. |
| `input_series_ids` | Semicolon-separated registry IDs; required for ready derived rows. Each input must exist. |
| `formula` | Plain-text derived formula; required for ready derived rows. It is not executed by the demo generator. |
| `notes` | Source choices or explanation; shown in expanded indicator details. |

Source references and provider IDs are complementary: a URL identifies a readable publication, while a code identifies a series to a future collector. You can supply either, both, or just the provider while completing a manual source. No missing provider detail is invented by the build.

History selection, publication timing, date handling, aggregation, conversions, and production statistics will be handled in pipeline code rather than extra CSV columns. The current source-unit/normalized-unit fields do not perform numeric conversion on demo data.

## Manual observation files (Slice 2 format)

Use one UTF-8 CSV per manual series at `data/manual/<series-id>.csv`, with exactly
this header:

```csv
date,value
```

- `date`: ISO observation date (`YYYY-MM-DD`), unique and sorted oldest first.
  Monthly observations follow the date convention documented for that series.
- `value`: finite numeric amount in the registry's `source_unit`, without currency
  symbols or thousands separators. Blank means missing; `0` means a reported zero.

The three SIFMA test inputs belong at:

```text
data/manual/bond-issuance.csv
data/manual/treasury-bond-issuance.csv
data/manual/corporate-bond-issuance.csv
```

Record the shared source in the registry's `source_reference`, with worksheet,
column, coverage, and period details in `notes`. Do not repeat source references
in every CSV row or add publication-date/correction-note columns. The current
SIFMA entries use `Billions` for both source and normalized units, matching the
supplied Wind workbook's `Billions $` label. Exact SIFMA/Wind series identifiers,
coverage, and monthly versus year-to-date definitions still need source review
before activation.

For revisions, edit the existing row. Explain changed values, values replaced by
missing, and deleted rows in the input commit message, identifying the series and
affected dates or range. New observations need no correction reason. Git preserves
the previous values; the importer compares against previous committed inputs
and requires a baseline instead of silently skipping correction checks.

The read-only importer validates these candidate inputs; placing them here does
not activate a series or update the dashboard. Source review and activation
checks still apply before production use. A missing source reference is allowed
for unactivated inputs, while any supplied reference must be a sanitized HTTPS
URL or publication citation. Production activation still requires a reviewed
reference and coverage definition, including for the SIFMA inputs.

To inspect the reviewed SIFMA series in the saved snapshot, run
`python3 scripts/build.py --mode production` and serve `dist/`.

```sh
# Validate committed inputs and all first-parent correction history.
python3 scripts/import_manual.py

# Pre-commit validation of local edits against HEAD, with a proposed message.
python3 scripts/import_manual.py --working-tree --message-file /tmp/manual-commit.txt

# Reuse that exact message when committing the workbook and exported CSVs.
git commit -F /tmp/manual-commit.txt
```

Stage the workbook and CSV changes together before committing. Put one or more
lines in the commit message using this exact format (inclusive date ranges):

```text
Refresh issuance inputs

Manual-Reason: bond-issuance 2026-09-30: corrected the saved September total
Manual-Reason: corporate-bond-issuance 2026-01-31..2026-10-31: publisher revised provisional figures
```

Every changed or removed date must be covered by a reason for its series, including
null-to-number changes, number-to-null changes, and deletion of an entire CSV.
Adding dates needs no reason. Numeric formatting changes (`1`, `1.0`, `1e0`) are
equivalent; decimal values are compared exactly before conversion to JSON numbers.
Blank value cells become null, while empty/all-null histories remain valid inputs.
Invalid numbers, unsupported unit conversions, nonmanual ownership, unknown IDs,
malformed CSVs, duplicate/unsorted dates, and symlink inputs fail validation.
Units come from the registry; values stay in source scale. Import does not perform
normalization or infer units from values, interpolate dates, or require a shared calendar.

The default audit checks each first-parent commit, so an undocumented edit cannot
be hidden by a later revert or unrelated commit. Merge commits are compared with
their first parent and must carry reasons for any resulting corrections.
PR checks use the branch head, not GitHub's synthetic merge commit; preserve the
reason lines when composing the actual merge or squash message. Committed
reasons come only from Git; `--message-file` is for the working-tree preflight.
The Git index is not a candidate mode: preflight reads local files, and CI reads
committed files. `--revision <commit>` checks a historical candidate. The optional
`--base <commit>` trusts an explicitly selected, previously validated first-parent
baseline and audits subsequent commits; do not use it to bypass failed history.
Without it, an empty root commit is the baseline; a root already containing manual
inputs needs an explicit trusted baseline. Missing commits, missing objects, and
shallow clones fail with a fetch-history error. CI uses `fetch-depth: 0`.

The initial workbook/export baseline is commit `7ea1a09`. The Python
`import_manual()` API returns source-scale observations, registry units/reference,
specification hash, the committed input ID, per-commit changes, and aggregate
revision counts over the audited range. Working-tree candidates have no
`sourceInputCommit`; `comparisonCommit` identifies their HEAD baseline. This is
an in-memory candidate result, not a snapshot or a normalized manifest hash.
The importer never writes manual, automatic, demo, or production files. Future
collectors must use the ownership gate before writing automatic inputs.

### Exporting the Wind workbook

Keep the refreshable workbook at `data/sources/wind/Wind-data.xlsx`. Source
workbooks belong in Git so another machine can pull, refresh, and export the same
file. This directory remains outside `site/`, so source workbooks are not included
in the GitHub Pages website.

Pull the latest changes before opening the workbook. Refresh and save it in Excel
with the Wind add-in, close Excel, then export and commit the workbook together
with its CSV changes. Excel lock files (`~$*.xlsx`) are ignored. Git cannot merge
competing workbook edits as text; coordinate updates or choose the correct
workbook version and regenerate the CSVs if a conflict occurs.

Install the pinned Excel reader once in your Python environment:

```sh
python3 -m pip install -r requirements.txt
```

From the repository root, run:

```sh
python3 scripts/export_wind_issuance.py --check
python3 scripts/export_wind_issuance.py
git diff -- data/manual/
```

The script uses Python 3.10+ and `openpyxl` to read saved values. Excel and Wind
are needed to refresh the workbook, but not to extract its saved results. To read
a workbook saved elsewhere:

```sh
python3 scripts/export_wind_issuance.py --input /path/to/Wind-data.xlsx
```

The issuance worksheet defaults to `bond-issuance`. Use `--sheet` to override its name.

- Row 1 contains the Wind control formula, which is never evaluated, and the
  required `Billions $` unit label in B1.
- Row 2 has `指标名称` or `date` in A2 and the three registry series IDs as column
  headers. The exporter matches IDs, so rearranging the three value columns is safe.
- Row 3 onward contains dates in column A and the saved numeric values. Dates
  must be month-end Excel dates or ISO `YYYY-MM-DD` text; source dates are preserved.

The `market` worksheet uses the same date column and header row. Its `MOVE` and
`USDX` columns supply daily index levels for `move.csv` and `dollar-index.csv`.
An Excel `#N/A` in either market value column exports as a blank observation.

The exporter writes all five files with exactly `date,value`, sorted
oldest first. It preserves Excel numeric values, zeroes, and blank/missing
values (decimal text may be shortened by the Excel reader); it does not round to
Excel's displayed two decimal places, convert units, fill missing months, or add
component series together. The supplied workbook
produced 190 observations per issuance series from January 2011 through October 2026.

Duplicate dates, unknown/duplicate headers, invalid dates or values, other Excel errors,
uncached data formulas, empty/all-missing series, and mismatched registry units or
ownership fail before any CSV is replaced. All outputs are staged first and each
file is replaced atomically; each replacement applies to one file. `--check`
validates without writing, and unchanged exports leave CSV files untouched.
`--output-dir` selects an alternative destination for inspection or tests.

This reads the workbook's last saved values. It cannot refresh Wind or prove that
those values are current. Review the printed date range after refreshing. Re-export
from the workbook for future updates; direct CSV edits would be replaced on the
next export. Review revisions/removals in Git and explain them in the commit
message. GitHub Actions installs the same pinned dependency for the offline tests;
it does not refresh or re-export the workbook during deployment. The importer
enforces Git-baseline corrections separately; production source review, snapshot
assembly, and deployment remain later pipeline steps. This exporter does not
activate these series or write to `site/data/`.

## Production foundation (Slice 1)

```sh
python3 scripts/policies.py
```

This offline command checks the five reviewed pilot specifications: `fed-assets`,
`sofr`, `effr`, `sofr-effr-spread`, and automatic FRED `fed-repo`. The existing registry
validator continues to accept incomplete future entries. The Slice 2 importer
validates manual candidates; Slice 3 supplies local FRED collection.
`python3 scripts/policies.py --check-activation` now verifies all pilot executable
paths. Production activation and publication remain disabled.

The [source review](../docs/source-review.md) records definitions, release and date
conventions, revision treatment, coverage, and redistribution conditions.
`source-reviews.json` binds each review to a hash of the relevant CSV fields. When
changing scientific definitions, review the source again and update the audit
record; merely setting `ready` or changing a hash does not implement the source.
Names/categories/provider codes/unit declarations remain owned by this CSV, not
duplicated into scheduling policies.

## FRED collection (Slice 3)

```sh
python3 scripts/collect.py
# Optional single-source check:
python3 scripts/collect.py --series fed-assets
```

The default refresh selects WALCL, SOFR, EFFR, RPONTTLD and the SOFR−EFFR
calculation. A custom selection containing a derived series must also explicitly
select its dependencies. Credentials come from `FRED_API_KEY` in the environment,
then `FRED_API_KEY` in the ignored repository `.env`. Only this setting name is accepted.
The file is parsed as text, never executed. Use an Actions secret when scheduling
is implemented; do not commit credentials. Other commands/tests need no key.

Each run fetches the entire current history from `2010-01-01` onward, using one
metadata request and one observations request per FRED series. The shared cutoff
is `FRED_OBSERVATION_START` in `scripts/policies.py`; later-starting series retain
their actual inception dates. The collector validates provider metadata, response
counts, history bounds, dates, and finite numbers, then replaces the source's file
at `data/automatic/<series-id>.json`. There are no vintage requests
or incremental merges. `.` becomes null; zero stays zero. Dates are neither
resampled nor filled. Requests use a 20-second timeout and at most three attempts
for network failures, HTTP 429 and transient server errors (1/2-second backoff).
Error messages omit response bodies, request URLs, and credentials.

Pagination is not implemented. The observations request uses `limit=100000` and
`offset=0`; the returned array must match the reported count. Empty, truncated,
or over-limit responses fail collection and preserve compatible previous inputs.
Metadata keeps the provider's original inception date, which can precede 2010.
Stored observations cannot precede the cutoff or inception and must reach the
metadata end date. If inception is within the requested window, its first date
must be present; otherwise the count check establishes response completeness.
The first date need not equal January 1, since that may not be a source date.
The cutoff applies to FRED downloads, not maintainer-owned manual inputs.

Automatic files are candidate inputs, not website assets. Their input schema
version is 1, independently of production snapshot schema version 2. Each contains:

- Source identity/specification hash, source and normalized units, explicit FRED
  transformation, reviewed provider metadata, and sanitized request parameters.
- Complete **source-scale** `observations` within the requested window, plus `sourceHash`. Values returned for
  a provider `chg` request are already differences, before project bp scaling.
- `outcome`: latest stored date, last attempt, successful check, and data-change
  times, with `updated`, `unchanged`, `retained`, or first-time `failed` status.
- Three `revisionSummary` counts against the preceding file and a freshness
  diagnostic. No revision ledger or per-date audit is maintained for FRED.

`sourceHash` hashes the observations array serialized as UTF-8 JSON with sorted
object keys, compact separators, finite numbers, and no trailing newline.
`scripts.normalize.content_hash` also hashes normalized arrays independently for
derived provenance. `normalize` always takes source-scale input; `derive` takes
normalized input and recalculates the complete same-date union. Missing inputs
and zero denominators produce null. The collector returns these outputs in memory; `scripts/assemble.py` independently
recomputes them from saved inputs into a production snapshot.

On failure, preserve compatible previous values and successful/change timestamps,
advancing only the attempt time. Other sources may update. First-time failures
have empty observations and no source hash; the CLI returns nonzero for any failed
or retained source so partial failures stay visible. Changed source definitions
require reviewed registry/policy edits and a successful full refetch; failed
refetches cannot reuse incompatible history. Corrupt cached files fail validation.

The collector validates the entire in-memory candidate before staging writes and
atomically replaces each automatic file. It cannot write manual inputs. This is
separate from the assembler’s atomic snapshot promotion; writer
serialization remains Slice 5. Run only one local collector at a time.
The pilot is activated for local assembly. Scheduled collection and production
deployment remain disabled. Replacing the entire requested window incorporates FRED corrections on the
next run; Git retains ordinary file history for rollback, without vintage tracking.

### Normalization semantics

`source_unit` is the scale actually delivered by the collector or manual input;
`normalized_unit` is the scale consumed by formulas and displayed by the site.
Raw values must be retained separately from normalized values. For derived rows,
the formula consumes already-normalized inputs and yields a value in the declared source unit.
The two SOFR spreads convert this difference from percentage points to bp once.

| Rule | Example |
| --- | --- |
| Millions → Billions | `3,000,000 / 1,000 = 3,000` |
| Billions → Billions | `25,000` remains `25,000` |
| Reserve/assets percent | `100 * 3,000 / 25,000 = 12` |
| SOFR − EFFR and SOFR99 − SOFR, bp output | `(4.10 - 4.00) × 100 = 10` bp |
| Provider `chg`, `%` → `bp` | A returned difference of `0.10` becomes `10` bp once |

The bank-assets definition stays in billions and ON RRP stays daily/billions.
The `bank-loans` typo `Biliions` is corrected; the production conversion resolver
also documents that spelling as a legacy alias. Unknown conversions fail rather
than pass through. Policy code names the Treasury `chg` request explicitly;
`notes=units=chg` is documentation, never executable configuration. Formula text
is matched to a known calculation definition, never evaluated with `eval`.

The repo input now uses FRED `RPONTTLD`: daily overnight repo totals across
Treasury securities, federal agency debt, and agency MBS, already in billions,
with an identity conversion and preserved source dates. This replaces the earlier manual all-collateral aggregation; it is not an
outstanding balance. See the source review for coverage and missing-value handling.
Manual CSV import is implemented in Slice 2 for other manual series and tested
with isolated offline fixtures; it does not change the repo pilot's ownership.

The [version 2 contract](../docs/production-contract.md) and
`scripts/contracts.py` define production artifact validation independently of
the existing demo. `python3 scripts/build.py --mode production` checks for a
snapshot at `data/snapshot/` (or `--snapshot <directory>`) and validates its contract.
It fails without changing demo files or existing build output when the snapshot is
missing/invalid. A valid assembled snapshot now builds successfully. The default build and
`--mode demo` retain the existing demo behavior.


### Production snapshot assembly (Slice 4)

Run `python3 scripts/assemble.py`, then `python3 scripts/build.py --mode production`.
The assembler validates current registry/review/policy compatibility, cached input
hashes, metadata, units and source dates, normalizes exactly once, and recomputes
SOFR−EFFR on the same-date union. No network request or fixture generation occurs.
A missing automatic file blocks assembly; a recorded first-time failed source has
no history; a compatible retained source remains usable. Other draft indicators
stay empty. No SIFMA series is activated by this command.

The complete three-document candidate is validated before promotion with an atomic
macOS/Linux directory exchange. A failed validation/exchange leaves the prior
snapshot unchanged. `--output` accepts `data/snapshot` or a directory outside the
repository, protecting source input directories from accidental replacement.
The production build atomically replaces `dist/` and never changes `site/data/`.

The manifest stores normalized source inputs (including hidden SOFR/EFFR), their
hashes, derived dependencies, source hashes, sanitized request provenance, and
collection outcomes. These diagnostics are not chart status badges. Snapshot IDs
hash the complete documents excluding the ID itself. Source-file hashes and
`modifiedSourceFiles` distinguish local code/specification edits from the recorded
base `sourceInputCommit`; commit those changes and reassemble before release.
A future reviewed manual activation requires committed, audited CSVs and an explicit
month/quarter start/end or fixed-day policy; local uncommitted CSV edits are rejected.

### Publication and rollback (Slice 5)

GitHub Actions uses the same assembler for saved-input pushes and daily/on-demand
FRED refreshes. Manual edits are audited without requiring a network request.
Automatic inputs and snapshots are committed together; one production lock covers
collection through deployment. Data-update PRs are available for protected branches.
`data/publication.json` records the candidate's base commit and artifact hashes;
the deployed `data/release.json` identifies the exact artifact commit.

To roll back, run the workflow on `main` with mode `rollback` and a full prior
artifact SHA. This restores both automatic inputs and snapshot files without
collection, preserving the historic snapshot ID. It creates a new commit instead
of rewriting history. See the [publication runbook](../docs/publication.md) for
setup, failure handling, rollback verification and resuming collection.

## Slice 6 coverage and manual publication

The [reviewed expansion](../docs/source-review-slice-6.md) activates 18 automatic
inputs, three manual issuance inputs and three calculations. `collect.py` now
refreshes all active automatic inputs, including the two ICE BofA credit-spread
series (rolling three-year history) and the daily Cboe VIX index. `treasury-yield-chg`
requests FRED `chg` and normalizes once to bp, remaining hidden.
H.8 assets/loans retain seasonal adjustment; SLOOS retains quarter-start labels.

The issuance source references now identify Wind EDB G1132499 (total), G1132494
(Treasury) and G1132496 (corporate). The maintainer confirmed monthly gross
issuance across all maturities, with Treasury/corporate included in total, and
public redistribution permission. Never sum the three overlapping series.

For subsequent Wind refreshes, preserve source missing values as blank instead of
exporting them as zero. All current 570 saved observations are positive. The CSV
importer cannot detect missing values already converted to zero upstream.
Commit the workbook, exported CSVs and reviewed registry changes before assembly.
The manual audit reads committed input definitions; it intentionally rejects an
uncommitted specification change even if the CSV values have not changed.
