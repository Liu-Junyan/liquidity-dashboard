# Production snapshot contract (version 2)

Slice 1 implements `scripts.contracts.validate_snapshot(catalog, observations,
manifest)`. It validates serialized objects offline; it does not fetch, assemble,
write, or deploy anything. The existing demo remains schema version 1. The
production build and browser loader will render this contract together in Slice 4.
Slice 2 adds `build.py --mode production`: it checks the snapshot directory and
validates this contract, then fails explicitly until the Slice 4 rendering path
exists. It never invokes fixtures or changes `site/data/` or `dist/`.

The local `build.py --mode preview` command is separate from this contract. Its
schema-v2 envelope uses `dataset.mode: "manual-preview"`, `isDemo: false`, and
`sourceReview: "pending"`, plus a matching snapshot ID in catalog, observations,
and manifest. `scripts/preview.py` assembles only the three committed SIFMA inputs;
other visible series have empty histories. Units retain the existing frontend
display object, and the manifest records input paths, specification hashes, and
the source commit. It deliberately has no production activation, normalized input
hashes, or production outcomes. `validate_snapshot` rejects it as production.
The frontend accepts this preview envelope and the existing demo contract; it
still rejects production envelopes until the full Slice 4 migration is complete.

All three documents carry integer `schemaVersion: 2` and the same slug `snapshotId`.
A producer chooses a unique ID for a complete candidate; the validator rejects
mixed IDs/versions. Operational timestamps use ISO UTC (`T…Z` or `T…+00:00`);
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
  The future assembler reconciles membership against the authoritative CSV.
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
| `revisionSummary` | Nonnegative integer counts `added`, `revised`, `removed`. |

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

## Assembly responsibilities in later slices

Contract validation is one gate, not proof of source correctness. Before calling
it, the assembler must load/validate the CSV, call `validate_activation`, verify
input ownership and retained-source compatibility, and reconcile content hashes
against staged files. It must check provenance formulas/dependencies against
policies, execute normalization and same-date calculations, and enforce registry
membership. Keep source-scale observations and hashes in automatic/manual input
artifacts, distinct from normalized input content; document deterministic content
hash serialization when those formats are implemented. A manifest digest alone
does not prove those files exist or match.

For a no-change success, compare to the previous input to preserve last-change
time. For a failure, compare to the previous input to preserve observations and
last-success time. The single-snapshot validator checks ordering and shape; only
the later collector can verify these transitions against a previous version.
Use temporary staging and atomic promotion of the entire validated candidate.
The production build must never invoke fixtures or overwrite `site/data/`.
