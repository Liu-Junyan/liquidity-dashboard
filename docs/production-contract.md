# Production snapshot contract (version 2)

`scripts.contracts.validate_snapshot(catalog, observations, manifest)` validates
serialized objects offline. Slice 4 adds `scripts/assemble.py` and the stronger
`validate_assembled_snapshot`: it verifies the complete content digest, normalized
input hashes, displayed history/calculation consistency, display metadata and source
notices. `build.py --mode production` validates and copies the selected snapshot to
`dist/` without collecting data, invoking fixtures, or modifying `site/data/`.
The existing demo remains schema version 1; scheduling/publication remain Slice 5.

The frontend accepts schema version 1 demo data and schema version 2 production snapshots.

All three documents carry integer `schemaVersion: 2` and the same slug `snapshotId`.
The assembler computes a SHA-256 ID over all three documents without their
`snapshotId` fields (sorted keys, compact UTF-8 JSON). The build verifies this
digest as well as matching IDs/versions. Operational timestamps use ISO UTC (`T…Z` or `T…+00:00`);
observation dates use strict `YYYY-MM-DD`. Numbers are finite JSON numbers (not
booleans or numeric strings), or explicit null. Never serialize NaN/Infinity.

## catalog.json

- `dataset`: `mode: "production"`, `isDemo: false`, `generatedAt`,
  `observationStart`, `observationEnd`. Bounds summarize all stored displayed
  observation dates, including explicit nulls; both are null when all arrays are
  empty. They impose no shared grid, history length, or minimum sample count.
- `categories`: the four registry layer definitions, each with unique `id`, `name`.
- `indicators`: `id`, `seriesId`, `categoryId`, `name`, reviewed `explanation`,
  `unit` (registry normalized-unit string, or `pending` for an unconnected unknown
  unit), `nativeFrequency`, `comparisonPolicy`, `sources` (reference strings),
  and `availability`.
  An empty/nonnumeric definition may have null `nativeFrequency` and no comparisons
  while its specification is incomplete; numeric history requires a known frequency.
- `availability`: `numeric` for history containing any numbers, `empty` for an
  empty/all-null history, `nonnumeric` for an unquantified definition (empty array).
  These are rendering states, not collection-status badges. A selected range can
  have no data even when full-history availability is numeric.
- IDs are unique across categories and indicators. Each displayed series has one
  owner. Unavailable rows are omitted; source-only inputs never become indicators.
  The assembler reconciles membership against the authoritative CSV.
- Comparison objects come from `scripts.policies.COMPARISONS`: native daily/weekly
  4/13 calendar weeks, monthly 1/12 months, quarterly 1/4 quarters, no annual or
  irregular defaults. Daily matching is on/before with a seven-day age cap and
  explicit missing targets preserved. `valueScale: 1` keeps changes in normalized
  output units; any alternate change unit needs a reviewed contract update.

## observations.json

`{"schemaVersion": 2, "snapshotId": "…", "series": {"indicator-id": []}}`

Every displayed ID has exactly one array of `{date, value}` points, sorted strictly
by date. Empty arrays, single points, all-null data and different native calendars
are valid. There are no source-only or unavailable IDs in this map. A malformed,
duplicate, or descending date fails validation; zero remains a number.

## manifest.json

| Field | Contract |
| --- | --- |
| `generatedAt` | Matches the catalog generation timestamp. |
| `sourceInputCommit` | Full Git object ID of the checked-out source inputs (40/64 hex digits), not the later artifact commit. |
| `policyVersion` | Current `scripts.policies.POLICY_VERSION`. |
| `inputHashes` | Map of automatic/manual series IDs to SHA-256 digests of validated **normalized input content**. Source-only inputs belong here too. First-time failed sources have no hash. |
| `provenance` | Map keyed by activated series ID, containing the records below. |
| `outcomes` | Same keys as provenance; contains operational diagnostics, never chart badges. |
| `revisionSummary` | Nonnegative integer counts `added`, `revised`, `removed`; summary diagnostics only, not a revision ledger or vintage dataset. |

Each provenance record contains `specHash` (reviewed registry identity), `method`,
`sourceUnit`, and `normalizedUnit`. Automatic/manual records additionally contain
`sourceReference`, `requestParameters`, and `transformation` (`lin` for untransformed
manual input). Automatic records also preserve `providerUnits` (provider's original
unit description); request parameters must include `series_id` and `units`.
Manual request parameters are always `{}`. Manual observations are maintained as
`date,value` CSVs; the assembler obtains `sourceReference` and units from the
reviewed registry, not per-row metadata. Publication dates and correction notes
are not CSV fields. Correction/removal reasons belong in the input commit message;
`sourceInputCommit` links the snapshot to that history. Operational timestamps
below are pipeline metadata, not dates the maintainer must enter.
Derived records contain a named
`calculation`, `inputHashes` identifying their exact upstream normalized inputs,
and `missingInputs` (normally `[]`). Digests must match the manifest input hashes.
First-time failed upstream sources go into `missingInputs`; such a derivation
cannot produce numeric values. Pilot derivations use direct
source inputs; multi-level derivation provenance needs extension before activation.

Safe automatic request fields are explicitly allowlisted: `series_id`, `file_type`,
`units`, observation/realtime bounds, ascending `sort_order`, `limit`, and `offset`.
No API keys, headers, full request URLs, resampling, or arbitrary parameters are
allowed. Public URL references use HTTPS without userinfo, query strings or
fragments; plain publication/table references are also supported. A reference
needing date/session context can record it as plain citation text, without a
credential-bearing request URL.

Every outcome has `status`, `latestObservationDate` (latest stored date, which may
have a null value), `lastAttempt`, `lastSuccessfulCheck`, `lastDataChange`. The four
date/time fields are present and nullable, except automatic `lastAttempt`.
Automatic statuses are `updated`, `unchanged`, `retained`, `failed`; manual statuses
are `imported`, `unchanged`, `failed`; derived status is `derived`. `failed` means
no previously validated input (no hash, latest date, success time, or change time).
Successful
automatic checks set the check time to the attempt time. Failed checks cannot
advance it; retained history requires an earlier successful check. Change time
cannot follow check time. No operational timestamp can follow snapshot generation.

## Assembly responsibilities

Slice 3 stores current FRED inputs from `2010-01-01` onward in `data/automatic/<series-id>.json`.
The separate input format and deterministic raw/normalized hash serialization are
documented in the [collection guide](../data/README.md#fred-collection-slice-3).
Every successful refresh replaces the complete requested window and recalculates all
derived history; no vintage or incremental revision processing is implemented.

Contract validation is one gate, not proof of source correctness. Before calling
it, the assembler must load/validate the CSV, call `validate_activation`, verify
input ownership and retained-source compatibility, and reconcile content hashes
against staged files. It must check provenance formulas/dependencies against
policies, execute normalization and same-date calculations, and enforce registry
membership. Keep source-scale observations and hashes in automatic/manual input
artifacts, distinct from normalized input content, using the documented content
hash serialization. A manifest digest alone
does not prove those files exist or match.

For a no-change success, compare to the previous input to preserve last-change
time. For a failure, compare to the previous input to preserve observations and
last-success time. The single-snapshot validator checks ordering and shape; only
the collector verifies these transitions against a previous version.
Use temporary staging and atomic promotion of the entire validated candidate.
The production build must never invoke fixtures or overwrite `site/data/`.


## Slice 4 display and assembly additions

Production indicators also carry `displayUnit` (`kind`, `label`, `precision`),
`isDemo: false`, `inputAvailable`, `observationDateRule`, `source`, and `notices`.
The serialized `unit` remains the registry string; the browser adapts `displayUnit`
to the existing rendering API. `inputAvailable` identifies activated definitions,
independently of numeric/empty availability; failed or all-null activated histories
must not be mislabeled as unconnected definitions. `dataset.publisher` is Junyan Liu.

`normalizedInputs` preserves validated normalized input arrays in the manifest,
including source-only inputs. Build validation hashes these and recomputes derived
displayed histories; source-scale arrays remain in automatic/manual input files.
`diagnostics` records source failure, freshness, and revision summaries outside charts.
`sourceFileHashes` records exact registry, review, category and Python source bytes;
`modifiedSourceFiles` lists differences from the base `sourceInputCommit` during
local development. A release assembly should follow committing those source files.

Monthly/quarterly activation requires a reviewed named date convention: month/quarter
start or end, or a consistent fixed day of month. Missing target periods return `—`;
no period fallback or interpolation is allowed. Daily comparisons use the latest
valid point on/before the target within seven days, except an explicit null on the
target date returns `—`. Summary matching never alters observations or derived joins.

Promotion uses atomic directory exchange on macOS/Linux. Validation and staging
finish first; failed exchanges preserve the old directory. Local writers must run
serially; Slice 5 holds one Actions lock through collection and deployment. The build publishes no credentials,
source workbooks, manual CSVs, or automatic response files into `dist/`.

## Slice 5 release identity

The publication job requires `modifiedSourceFiles: []`. It commits automatic
inputs, the complete snapshot, and `data/publication.json` together. The publication
record has schema version 1 and carries `baseCommit`, `mode`, `snapshotId`,
`restoredFrom` (nullable), and exact file-byte SHA-256 `artifactHashes`. It is a Git
release record, separate from the three-document schema-v2 snapshot.

After committing, the production build adds `dist/data/release.json` containing
`artifactCommit`, `sourceInputCommit`, `snapshotId`, and nullable `restoredFrom`.
Snapshot files must be byte-identical to the selected committed files. The public
artifact has an explicit file allowlist; extra files and symlinks block upload.

Rollback creates a new artifact commit on current `main`, restoring historic
automatic inputs and snapshot bytes without collection. The snapshot retains its
original source commit and ID; the public release record identifies the new
artifact commit and historic rollback target. Current build code must still
validate that snapshot. See the [publication runbook](publication.md).
