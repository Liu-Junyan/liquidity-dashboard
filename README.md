# USD Liquidity Observatory

A Chinese-language weekly dollar-liquidity research prototype, styled with restrained navy, blue charts, thin rules, and editorial typography inspired by the New York Fed Markets Data Dashboard. **All observations are synthetic.** [data/registry.csv](data/registry.csv) controls dashboard membership, names, grouping, and ordering. The current selection has 23 indicators across 货币层、离岸层、信用层、金融市场层 (9 / 3 / 7 / 4). Rows marked `unavailable` are retained for future use and omitted from the dashboard; blank-category calculation inputs are also hidden.

Each indicator's **查看统计摘要** control shows its trailing 3-month and 1-year means and the latest value's percentile within the selected chart range, with valid sample counts and calculation notes. Raw observations remain available through **展开指标 → 查看数据表**.

## Preview

Python 3.10+ is sufficient; no Python packages or frontend installation is needed.

```sh
python3 scripts/build.py
python3 -m http.server 8000 --directory dist --bind 127.0.0.1
```

Open <http://127.0.0.1:8000/>. Use HTTP rather than opening `index.html` directly, because the application loads ES modules and local JSON files.

To reproduce project-subdirectory hosting, serve the repository root instead and open <http://127.0.0.1:8000/dist/>. Example deep link: `/dist/#category=category-2&range=1y&indicator=dollar-index`.

## Checks

```sh
python3 scripts/build.py
python3 scripts/registry.py
python3 -m unittest discover -s tests -p 'test_*.py'
node --test tests/data.test.mjs
```

JavaScript checks use Node 22+ and built-in modules; `npm install` is unnecessary. Regenerate the checked-in observations with `python3 scripts/generate_fixtures.py`.

## Source specifications

Edit [data/registry.csv](data/registry.csv), then run `python3 scripts/build.py`. The build regenerates the catalog and demo observations from the CSV, including additions, renames, removals, and `unavailable` exclusions. No separate catalog edit is needed. [The registry guide](data/README.md) explains visibility rules and the 16 columns. `python3 scripts/registry.py --output data/registry.json` optionally exports the complete registry, including hidden entries. Real collection, manual import, formula execution, and native-frequency data migration remain future work.

## Deployment

In GitHub repository **Settings → Pages → Build and deployment**, choose **GitHub Actions**. Push to `main` or manually run **Build and deploy dashboard**. Pull requests run checks/builds without deploying. The workflow publishes `dist/` using the Pages environment. This checkout has no configured Git remote; no live deployment has been performed.

See [the implementation handoff](docs/implementation-brief.md#6-implemented-prototype-and-design-handoff) for data contracts, UI labels, verification, and the real-data migration plan.

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
- `scripts/`: standard-library fixture generation, validation, and static build.
- `.github/workflows/pages.yml`: validation and GitHub Pages deployment.

Apache ECharts is distributed under its bundled [Apache 2.0 license](site/assets/vendor/echarts-LICENSE.txt). No remote fonts, data calls, analytics, or CDN dependencies are required at runtime.
