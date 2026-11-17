# USD Liquidity Observatory

A Chinese-language dollar-liquidity research prototype, styled with restrained navy, blue charts, thin rules, and editorial typography inspired by the New York Fed Markets Data Dashboard. **The default demo uses synthetic observations; a separate local preview displays the three saved SIFMA issuance inputs.** [data/registry.csv](data/registry.csv) controls dashboard membership, names, grouping, and ordering. The current selection has 23 indicators across 货币层、离岸层、信用层、金融市场层 (9 / 3 / 7 / 4). Rows marked `unavailable` are retained for future use and omitted from the dashboard; blank-category calculation inputs are also hidden.

Each indicator's **查看统计摘要** control shows its trailing 3-month and 1-year means and the latest value's percentile within the selected chart range, with valid sample counts and calculation notes. **展开指标** opens the larger chart, indicator explanation, and source details; no raw-history table is rendered.

## Preview

The demo preview needs Python 3.10+; no Python packages or frontend installation is needed for that build.

```sh
python3 scripts/build.py --mode demo
python3 -m http.server 8000 --directory dist --bind 127.0.0.1
```

Open <http://127.0.0.1:8000/>. Use HTTP rather than opening `index.html` directly, because the application loads ES modules and local JSON files.

To reproduce project-subdirectory hosting, serve the repository root instead and open <http://127.0.0.1:8000/dist/>. Example deep link: `/dist/#category=category-2&range=1y&indicator=dollar-index`.

### Real SIFMA data preview (local only)

```sh
python3 scripts/build.py --mode preview
python3 -m http.server 8001 --directory dist-preview --bind 127.0.0.1
```

Open <http://127.0.0.1:8001/>. The preview opens the credit category with bond,
Treasury, and corporate issuance first. It uses the **committed** manual CSVs,
registry, and category definitions at `HEAD`, after auditing correction reasons.
Refresh/export and commit inputs before rebuilding to see new workbook values.
The current inputs contain 190 monthly observations each, January 2011–October 2026.

Monthly comparisons use the previous month-end and the same month-end one year
earlier; missing values remain missing. All other displayed indicators show
`待接入` with empty charts. The page, details, statistics, and tooltips identify
the real inputs; the page prominently states that source definitions remain
pending review. Source references, coverage, overlap, and monthly versus year-to-date
definitions must be resolved before production activation.

This builds an explicitly unreviewed preview into ignored `dist-preview/`, including
matching catalog/observations and an audit manifest. It does not modify `site/data/`,
`dist/`, manual inputs, or activation policies. The Slice 5 workflow publishes
the reviewed production pilot; this preview stays local. No automatic collection or full
production snapshot assembly is required for this preview.

## Checks

Install the Python dependencies for Excel extraction and its tests first:

```sh
python3 -m pip install -r requirements.txt
python3 scripts/build.py
python3 scripts/registry.py
python3 scripts/policies.py
python3 scripts/import_manual.py
python3 -m unittest discover -s tests -p 'test_*.py'
node --test tests/data.test.mjs
python3 scripts/build.py --mode preview
node --test tests/preview.test.mjs
```

JavaScript checks use Node 22+ and built-in modules; `npm install` is unnecessary. Regenerate the checked-in observations with `python3 scripts/generate_fixtures.py`.

## Source specifications

Edit [data/registry.csv](data/registry.csv), then run `python3 scripts/build.py`. The build regenerates the catalog and demo observations from the CSV, including additions, renames, removals, and `unavailable` exclusions. No separate catalog edit is needed. [The registry guide](data/README.md) explains visibility rules and the 16 columns. `python3 scripts/registry.py --output data/registry.json` optionally exports the complete registry, including hidden entries.

Real-data Slices 1–5 are implemented locally: source review, manual input audits,
FRED collection, normalization, derivation, validated snapshot assembly, and the
production frontend. The five pilot definitions are activated for local assembly,
producing three displayed charts (Fed assets, Fed overnight repo, and SOFR−EFFR).
SOFR/EFFR remain internal inputs. Slice 5 adds scheduled/on-demand publication and rollback;
the first hosted production run remains to be verified after merge.
Desktop Chrome rendering and dialog keyboard behavior have been verified.
Mobile UI polish is deferred at the maintainer's request.

Run `python3 scripts/collect.py` to download current histories since `2010-01-01` for WALCL,
SOFR, EFFR, and RPONTTLD into `data/automatic/`. It reads `FRED_API_KEY` from the
environment or ignored `.env` (only this setting name is accepted), validates
each complete response, then replaces its candidate input. Each series uses one
observations request, with no pagination. Failed downloads retain
compatible previous history; derived histories are fully recomputed. No vintage
tracking or incremental merging is used. See the [collection guide](data/README.md#fred-collection-slice-3).

`python3 scripts/import_manual.py` validates committed manual inputs and audits
each first-parent commit against its predecessor. CI fetches full history. Before
committing edits, use `python3 scripts/import_manual.py --working-tree
--message-file /tmp/manual-commit.txt` with your proposed commit message. Corrections
and removals need `Manual-Reason: <series-id> YYYY-MM-DD[..YYYY-MM-DD]: <reason>`
lines covering every affected date; additions need no reason. See the
[manual input guide](data/README.md#manual-observation-files-slice-2-format).

`python3 scripts/build.py` remains a demo build for compatibility; `--mode demo`
makes that choice explicit. Build the local production dashboard from saved inputs:

```sh
python3 scripts/assemble.py
python3 scripts/build.py --mode production
node --test tests/production.test.mjs
python3 -m http.server 8000 --bind 127.0.0.1 --directory dist
```

Open `http://127.0.0.1:8000/`. Assembly is offline and needs no API key. It creates
`data/snapshot/{catalog,observations,manifest}.json`; the build accepts an alternate
`--snapshot /path/to/snapshot`. It validates content hashes and recomputes displayed
derivations before copying the selected snapshot to `dist/`. Both snapshot promotion
and production output replacement use atomic directory exchange on macOS/Linux.
Failures preserve the prior output; `site/data/` remains the synthetic demo.
Run one local writer at a time; GitHub production jobs share one publication lock.

The manifest identifies the source commit, exact source-file hashes, and any
uncommitted source changes. Commit source changes and reassemble before a release.
Source notices name **Junyan Liu** as publisher. Unconnected indicators display
`待接入`; SIFMA remains in its separate, explicitly unreviewed local preview.
These local commands do not publish; the Slice 5 workflow handles publication.

Builds version the JavaScript module graph and styles by content, and JSON requests
revalidate cached data. This prevents old demo scripts from reading a new production
snapshot after a rebuild. If an already-open page predates this fix, reload it once
with **Cmd+Shift+R** on macOS (or **Ctrl+Shift+R** on Windows/Linux).

For the three SIFMA issuance inputs, `python3 scripts/export_wind_issuance.py`
uses `openpyxl` to convert saved values from the Wind workbook into `data/manual/*.csv`.
Keep the workbook in versioned `data/sources/wind/bond-issuance.xlsx` and commit
workbook and CSV updates together for use on other machines. See the
[refresh and export instructions](data/README.md#exporting-the-wind-issuance-workbook).
This prepares manual inputs without activating production data.

## Deployment

The remote is `https://github.com/Liu-Junyan/liquidity-dashboard.git`. The maintainer
has configured **GitHub Actions** as the Pages source and added `FRED_API_KEY` as an
Actions secret. The Slice 5 workflow publishes the reviewed production snapshot
from one exact artifact commit. Pushes use saved inputs; scheduled collection runs
daily at **15:17 Asia/Shanghai**. Pull requests run offline checks without secrets
or deployment. Branch-protected repositories can use data-update PRs.

In **Actions → Build and deploy dashboard → Run workflow**, select `main` and choose
`refresh`, `publish` (no collection), or `rollback` (an earlier full artifact SHA).
See the [publication and rollback runbook](docs/publication.md) for branch rules,
failure handling, artifact identity, and first-release acceptance. The first hosted
production deployment and live rollback remain pending verification.

Run all offline Python and JavaScript checks locally with:

```sh
python3 scripts/check.py
```

This restores checked-in demo data, builds all three modes, and leaves the local
production build in `dist/`. Python dependencies and Node 22+ are required.

See [the real-data development plan](docs/real-data-development-plan.md) for implementation slices, normalized-unit formulas, FRED transformations, acceptance checks, and production rollout. [The implementation handoff](docs/implementation-brief.md#6-implemented-prototype-and-design-handoff) retains the prototype design, verification history, and mixed-source requirements.

## Structure

- `site/index.html`, `site/assets/styles.css`: page structure and responsive styling.
- `site/assets/app.js`: configuration-driven rendering, navigation, and details.
- `site/assets/data.js`: exact-date calculations, ranges, formatting, route parsing.
- `site/assets/charts.js`: locally served Apache ECharts 5.6.0 and chart lifecycle.
- `site/assets/zh-CN.js`: interface dictionary; catalog metadata is localized separately.
- `data/registry.csv`: editable dashboard selection and source specifications.
- `data/categories.json`: research-layer names, stable IDs, and descriptions.
- `site/data/catalog.json`: generated indicator metadata and demo dataset metadata.
- `site/data/observations.json`: five years of weekly observations with explicit nulls.
- `scripts/`: fixture generation, validation, static build, and Excel input extraction.
- `data/sources/wind/`: versioned Wind workbooks, outside the published website.
- `requirements.txt`: pinned Python dependency for Excel extraction and its tests.
- `scripts/check.py`, `scripts/release.py`, `scripts/publish.py`: offline verification, release validation, and serialized publication.
- `.github/workflows/pages.yml`: offline PR checks and production collection/publication/rollback.

Apache ECharts is distributed under its bundled [Apache 2.0 license](site/assets/vendor/echarts-LICENSE.txt). No remote fonts, data calls, analytics, or CDN dependencies are required at runtime.
