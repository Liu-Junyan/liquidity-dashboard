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

**Observations remain explicitly synthetic.** This change connects the registry to dashboard membership and metadata; it does not fetch source data, import manual observations, execute formulas, or apply `less`/`greater` as judgments about market conditions. Registered source references appear in expanded details as intended sources. The demo still uses a weekly fixture grid; `native_frequency` records the planned source frequency separately. Missing normalized units display `待确认` rather than inheriting an obsolete catalog definition.

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
SIFMA entries still need those details and verified units: their configured source
and normalized units are both `Trillion`, which is not verification of a SIFMA
table's actual scale. Confirm monthly amounts versus year-to-date totals too.

For revisions, edit the existing row. Explain changed values, values replaced by
missing, and deleted rows in the input commit message, identifying the series and
affected dates or range. New observations need no correction reason. Git preserves
the previous values; the planned importer compares against the previous committed
input and requires a baseline instead of silently skipping correction checks.

The importer is not implemented yet. These files prepare Slice 2 test inputs;
placing them here does not activate a series or update the dashboard. Source
review and activation checks still apply before production use.

## Production foundation (Slice 1)

```sh
python3 scripts/policies.py
```

This offline command checks the five reviewed pilot specifications: `fed-assets`,
`sofr`, `effr`, `sofr-effr-spread`, and automatic FRED `fed-repo`. The existing registry
validator continues to accept incomplete future entries. No collector, importer,
or production publisher is enabled. `python3 scripts/policies.py --check-activation`
deliberately fails until the required implementations are registered in later slices.

The [source review](../docs/source-review.md) records definitions, release and date
conventions, revision treatment, coverage, and redistribution conditions.
`source-reviews.json` binds each review to a hash of the relevant CSV fields. When
changing scientific definitions, review the source again and update the audit
record; merely setting `ready` or changing a hash does not implement the source.
Names/categories/provider codes/unit declarations remain owned by this CSV, not
duplicated into scheduling policies.

### Normalization semantics

`source_unit` is the scale actually delivered by the collector or manual input;
`normalized_unit` is the scale consumed by formulas and displayed by the site.
Raw values must be retained separately from normalized values. For derived rows,
the formula consumes already-normalized inputs and directly yields the declared
output unit; never apply an input conversion again to the calculated output.

| Rule | Example |
| --- | --- |
| Millions → Billions | `3,000,000 / 1,000 = 3,000` |
| Billions → Billions | `25,000` remains `25,000` |
| Reserve/assets percent | `100 * 3,000 / 25,000 = 12` |
| SOFR − EFFR, `%` output | `4.10 - 4.00 = 0.10` percentage points |
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
Manual CSV import still arrives in Slice 2 for other manual series, initially
tested with offline fixtures; no real manual sample is needed to start that slice.

The [version 2 contract](../docs/production-contract.md) and
`scripts/contracts.py` define production artifact validation independently of
the existing demo. Snapshot assembly, production build selection, and frontend
adoption remain later slices; no new production build command exists yet.
