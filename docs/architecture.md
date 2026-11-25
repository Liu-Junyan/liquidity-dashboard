# Architecture

The dashboard has two runtime components. Python prepares a versioned snapshot and builds a static site. The browser reads the catalog and observations from that site and renders charts locally. Only the collector contacts FRED. Wind updates enter through the maintainer’s saved workbook. [Source definitions](data-sources.md) · [Build and publication commands](runbook.md)

## From source to chart

| Stage | Reads → writes | Responsibility |
| --- | --- | --- |
| Define | [registry CSV](../data/registry.csv), [categories](../data/categories.json), [review records](../data/source-reviews.json) | The registry owns identities, ordering, ownership, and measurement fields. Reviews bind the measurement fields to a specification hash, date convention, and Chinese explanation. [Policies](../scripts/policies.py) select the reviewed series with an implemented collector, importer, or formula. |
| Collect | FRED → `data/automatic/<series-id>.json` | Save source-scale history, request parameters, metadata, revision counts, and the outcome of each check. [Collector](../scripts/collect.py) |
| Import | Saved workbook → `data/manual/<series-id>.csv` → audited observations | The exporter reads Excel’s cached values. The importer validates source-scale CSVs and audits corrections against first-parent Git history. [Exporter](../scripts/export_wind_issuance.py) · [Importer](../scripts/import_manual.py) |
| Assemble | Saved inputs + registry and policies → `data/snapshot/` | Normalize units, align derived series on observation dates, build the catalog, and validate the complete snapshot before promoting it. [Assembler](../scripts/assemble.py) · [Derivations](../scripts/derive.py) |
| Build | `site/` + selected snapshot → `dist/` | Production validates the snapshot, copies the static assets, and versions CSS and module URLs by content. Demo mode regenerates weekly synthetic fixtures in `site/data/`. The CLI defaults to demo. [Builder](../scripts/build.py) |
| Publish | Latest default-branch revision → Git artifact commit → Pages | One Actions job holds the publication lock from collection through deployment. It audits and tests a disposable checkout, commits generated inputs and snapshot, builds and stamps the artifact, and uploads the allowed files in `dist/`. [Workflow](../.github/workflows/pages.yml) · [Publisher](../scripts/publish.py) |

## Snapshot and release identity

Production uses three schema-v2 JSON documents with a shared content-derived `snapshotId`. The same series may have different registry and display IDs. Use the **indicator ID** to find a chart’s points and the **series ID** to trace its inputs.

| Document | What to inspect |
| --- | --- |
| `catalog.json` | Dataset bounds, categories, and displayed indicators with their units, comparison rules, sources, and notices. `inputAvailable` identifies an activated definition. `availability` distinguishes numeric, empty, and nonnumeric histories. |
| `observations.json` | One array per displayed indicator, ordered by unique ISO observation date. Values are finite numbers or explicit nulls. Empty arrays are valid. |
| `manifest.json` | Source commit and file hashes, policy version, normalized inputs and hashes, calculation provenance, collection outcomes, freshness, and revision counts. Hidden calculation inputs can be traced here. |

`revisionSummary` compares normalized manual and automatic inputs with the most recent publication recorded on the branch. The manifest names that snapshot in `revisionBaselineSnapshotId`. On the first publication the ID is null and all input dates count as additions. Each series and date counts once. A date appearing or disappearing counts as added or removed. A value change on an existing date counts as revised, including a change to or from null. Derived charts contribute no additional counts. FRED diagnostics describe the latest collection for each series. Reusing a snapshot preserves its original manifest and reports zero new changes in the run summary.

The production build checks membership, hashes, notices, and displayed calculations. Only site assets, the snapshot, and the release identity enter the Pages upload. Source workbooks, manual CSVs, and raw FRED responses stay in Git. Local assembly records modified source files. Publication requires a clean source revision. The Git record `data/publication.json` holds the base commit and artifact file hashes. The deployed `data/release.json` adds the artifact commit and identifies the source commit, snapshot ID, and any rollback target. [Snapshot validation](../scripts/contracts.py) · [Release stamping](../scripts/release.py)

## Browser

The four research layers and their stable category IDs come from the category definitions. A visible indicator whose source is pending can have a chart card with an empty history.

The app fetches the catalog and observations relative to its module URL, checks that the snapshot IDs match, and draws charts with the bundled ECharts library. Hash links carry the category, time range, and expanded indicator. The expanded chart has its own temporary range. Cards show the latest numeric observation and native-frequency comparisons. Statistics use the latest valid date for trailing means and the selected chart range for the historical percentile. Expanded details carry the full explanation and source notices. [Application](../site/assets/app.js) · [Data and statistics](../site/assets/data.js) · [Charts](../site/assets/charts.js) · [Chinese interface text](../site/assets/zh-CN.js) · [ECharts license](../site/assets/vendor/echarts-LICENSE.txt)
