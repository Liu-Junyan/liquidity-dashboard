# USD Liquidity Dashboard — Prototype and Implementation Brief

### 1. Objective and deliverable

Design a Chinese-language dashboard for **weekly research into dollar liquidity**, helping the user investigate conditions relevant to US Treasury trades.

The first milestone is a **visual prototype with clearly labeled synthetic data**, organized into four categories. Real data integration follows after reviewing the interface.

Prepare an English Markdown handoff document, `docs/implementation-brief.md`, containing the agreed design, Chinese labels, data interfaces, implementation milestones, and acceptance criteria.

### 2. Dashboard experience

Use **overview + drill-down**:

```text
美元流动性观察                         演示数据 · 非实时

[ 类别一 ]     [ 类别二 ]     [ 类别三 ]     [ 类别四 ]
  重点指标       重点指标       重点指标       重点指标
  趋势缩略图     趋势缩略图     趋势缩略图     趋势缩略图

所选类别                            近1年 | 近5年 | 全部

[ 指标图表 A                  ] [ 指标图表 B                  ]
  最新值 · 近4周变化 · 近13周变化 · 数据日期

展开指标 → 大图 · 指标说明 · 数据来源 · 更新频率 · 数据表
```

- Keep all four category summaries visible; selecting one changes the detailed charts below. Select the first category initially.
- Show two demonstration indicators per category, with deterministic weekly observations spanning five years.
- Default charts to five years. Time-range controls affect the selected category’s charts; overview sparklines show the latest year.
- Express changes in the indicator’s native units; use basis points for rates. Missing comparison observations display `—`.
- Distinguish observation dates from collection times. Missing observations remain gaps.
- Use a light background, restrained blue chart lines, readable Chinese typography, and generous chart space. Rising values do not automatically mean “good.”
- Arrange summaries across four columns on wide screens, two on tablets, and one on phones. Detailed charts use two columns on desktop and one on mobile.
- Include keyboard-accessible controls and a data-table alternative to charts.

Exclude composite scores, trading recommendations, alerts, accounts, and portfolio tracking from this milestone.

### 3. Implementation approach

- Use HTML, CSS, and JavaScript modules, following the simple static-site approach of [SGSRank](https://github.com/Liu-Junyan/SGSRank).
- Use [Apache ECharts](https://echarts.apache.org/handbook/en/get-started/) for charts, with a pinned copy served alongside the site.
- Separate category definitions, indicator metadata, observations, and rendering logic. Adding indicators must not require changing page layouts.
- Define the minimum data interface:
  - **Category:** stable ID, display order, localized name and description.
  - **Indicator:** stable ID, category ID, localized name and explanation, unit, frequency, source metadata, and demonstration-data flag.
  - **Observations:** dated numeric values or explicit missing values.
- Put interface text in a `zh-CN` dictionary and use locale-aware number/date formatting. Keep stable IDs independent of Chinese labels. English translation and a language switcher are deferred.
- Build static output with Python and deploy through GitHub Actions to [GitHub Pages](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages). Use relative asset paths and hash-based navigation so project-subdirectory hosting and reloads work.
- Prototype data comes entirely from local fixtures; no credentials or external data requests are needed.

For later real-data integration, document the intended flow: **scheduled GitHub Actions collection → validation → static data files → deployment**. Use free public sources, keep API keys in Actions secrets, and preserve the last successful dataset when collection fails.

### 4. Verification and acceptance

The prototype is ready for review when:

- All four categories and eight sample indicators render correctly.
- Category selection, time ranges, expanded details, and data tables work.
- Latest values and changes match the fixtures; missing data is never converted to zero.
- Every view clearly identifies synthetic data.
- Chinese text, charts, and controls remain usable at mobile and desktop widths.
- Direct links and reloads work under a GitHub Pages repository subpath.
- Adding an indicator through configuration displays it without layout changes.
- The handoff document explains local preview, deployment, and how fixtures will later be replaced.

### 5. Assumptions and reference material

- The article’s exact category names and indicators remain unverified because its WeChat page could not be retrieved. Use explicit placeholders, `类别一` through `类别四`, for the prototype; do not invent article content.
- English is the default for implementation instructions; the delivered interface is Chinese.
- The dashboard is intended primarily for personal research, with public static hosting.
- Use the [OFR Short-term Funding Monitor](https://www.financialresearch.gov/short-term-funding-monitor/) as a reference for grouped charts and interpretive guidance, and the [New York Fed Markets Data Dashboard](https://www.newyorkfed.org/markets/data-hub) as a reference for organizing market data. Their categories do not replace the article’s framework.

### 6. Implemented prototype and design handoff

Implemented on October 28, 2026. The repository now contains a standalone static site; no live financial data is requested. The implementation uses the New York Fed page as a visual reference: navy masthead/navigation, serif Chinese page title, restrained blue lines, thin dividers, compact numeric summaries, and a white background. The prototype uses its own identity and does not imply Federal Reserve affiliation.

**Page structure:** permanent four-category overview → selected category charts → data/reading notes. Overview cards show the first configured indicator as the primary value and one-year sparkline, with remaining indicators listed beneath it. Detail cards render every configured indicator in the selected category. Native buttons support keyboard selection; native modal dialogs trap focus, close with Escape, and return focus to the triggering control. Charts have labeled data-table alternatives. No directional red/green coloring or composite judgments are used.

Responsive breakpoints: overview uses four columns above 900px, two from 601–900px, and one at 600px and below. Indicator charts use two columns above 600px and one below. Tables scroll independently and preserve column headings. Reduced-motion preferences suppress chart animation.

#### Chinese interface labels

| Purpose | Label |
| --- | --- |
| Page title | 美元流动性观察 |
| Prototype notice | 演示数据 · 非实时 |
| Overview | 流动性概览 |
| Placeholder categories | 类别一 / 类别二 / 类别三 / 类别四 |
| Time controls | YTD / 近1年 / 近5年 / 全部 |
| Metrics | 最新值 / 近4周变化 / 近13周变化 / 观测日期 |
| Indicator controls | 展开指标 / 查看统计摘要 / 收起统计摘要; 查看数据表 in expanded details |
| Summary statistics | 近3个月均值 / 近1年均值 / 当前值历史分位 |
| Metadata | 指标说明 / 当前数据来源 / 后续拟接入来源 / 更新频率 |
| Collection timestamp | 演示数据生成时间 |
| Reading notes | 数据与阅读说明 |

Eight explicitly labeled examples are included: reserve balances, overnight reverse repo balances, SOFR, EFFR, Treasury General Account balances, Federal Reserve total assets, repo volume, and dealer Treasury positions. These examples and their category assignments were selected to exercise interface behaviors. They are **not verified article content**. Rate examples use percentage levels and basis-point changes; amount examples use billions of USD (`十亿美元`).

#### Files and minimum data interfaces

`site/data/catalog.json` separates category definitions and indicator metadata from `site/data/observations.json`. `schemaVersion: 1` identifies the current contract. Stable IDs are lowercase ASCII slugs and independent of display labels.

```json
{
  "schemaVersion": 1,
  "dataset": {
    "id": "synthetic-weekly-v1",
    "isDemo": true,
    "observationStart": "2021-10-27",
    "observationEnd": "2026-10-28",
    "collectedAt": "2026-10-28T00:00:00Z"
  },
  "categories": [
    {"id": "category-1", "order": 1, "name": "类别一", "description": "框架待确认"}
  ],
  "indicators": [
    {
      "id": "reserve-balances",
      "categoryId": "category-1",
      "name": "准备金余额（示例）",
      "explanation": "Synthetic demonstration, not an official observation.",
      "unit": {"kind": "amount", "label": "十亿美元", "precision": 1},
      "frequency": "weekly",
      "source": {"name": "Intended source", "url": "https://www.federalreserve.gov/releases/h41/"},
      "isDemo": true
    }
  ]
}
```

The shortened example illustrates the shape; validation requires four populated categories. `unit.kind` is `amount` or `rate`; rate values are expressed in percentage points (e.g. `4.25` means 4.25%). `source` identifies an intended future source; the UI separately states that the current source is a local synthetic fixture.

```json
{
  "reserve-balances": [
    {"date": "2021-10-27", "value": 4000.0},
    {"date": "2021-11-03", "value": null}
  ]
}
```

Each series uses a sorted, uninterrupted weekly date grid, spanning the dataset interval. Absent observations must have explicit `null` values. The checked-in fixture has 262 dates per series and is reproducible with `python3 scripts/generate_fixtures.py`. No random seeds, clocks, credentials, or network calls affect fixture generation.

The latest metric uses the latest non-null observation and displays **that observation's date**. Four- and thirteen-week comparisons use the exact date 28/91 days before that latest valid date. A missing comparison produces `—`, never a comparison against another date. Rate differences multiply by 100 to produce basis points. Missing chart observations remain visible gaps (`connectNulls: false`); tables label them as missing. Dealer positions deliberately omit the final observation; reverse repo deliberately omits the four-week comparison.

Time windows are anchored to `dataset.observationEnd`, not the browser clock. YTD starts on January 1 of the dataset-end year (UTC) and uses `range=ytd` in deep links; it applies to charts, expanded details, and data tables. One/five years use calendar-year boundaries; all history includes the complete fixture. Because the fixture starts one day before the five-year cutoff, the five-year range has 261 observations and all history has 262. Sparklines always use the latest calendar year. Each category remembers its selected range during the browser session; each category initially uses five years.

The chart-card disclosure now shows summary statistics rather than raw observations. The 3M and 1Y means are arithmetic means of available weekly values within the trailing three calendar months and twelve calendar months ending on the latest valid observation date (inclusive); month-end cutoffs clamp to the last valid day of the target month. These fixed lookbacks do not change with the chart range. Means remain in native units, including percentage levels for rates. The current value's percentile uses valid observations in the selected chart range: `100 × count(value <= latest value) / count(valid observations)`, including the latest value and all ties. This empirical cumulative rank has a maximum of 100%; it is not an investment rating. Nulls are excluded, real zero values are retained, and an empty sample displays `—`. Each metric displays its valid observation count, and the disclosure states the methodology and date. Incomplete windows use the available sample. Raw data tables remain available in expanded details as the chart alternative.

Summary-statistics verification: nine JavaScript regression checks passed, including tied ranks, empty samples, missing/latest observations, zero values, leap-day/year boundaries, and month-end cutoffs. Browser review confirmed keyboard disclosure toggling, unchanged means when switching chart ranges, recalculated percentiles, rate means in percentage units, retained detail tables, and a 320px phone layout without horizontal overflow.

Adding an indicator requires only an entry in `catalog.indicators` and its series in `observations.json`; layout, tables, dialogs, and summary rendering are generated from configuration. The build validates unique IDs, metadata, category references, timezone-aware collection timestamps, safe HTTPS source links, finite numeric values, explicit nulls, weekly cadence, and matching observation keys.

#### Local preview and deployment

Python 3.10+ is required; all Python scripts use the standard library. Node 22+ is needed only for JavaScript regression checks and is provisioned by CI. No npm installation or frontend build framework is required.

```sh
python3 scripts/build.py
python3 -m http.server 8000 --directory dist --bind 127.0.0.1
```

Open `http://127.0.0.1:8000/`. To verify repository-subpath hosting, serve the repository root and open `/dist/`. Do not open the HTML using `file://`, because the app fetches local JSON and uses JavaScript modules.

Navigation uses hashes such as `#category=category-2&range=1y&indicator=sofr`. Reloading and browser history restore the selected category, range, and open detail dialog without server route support. Invalid route values safely fall back to the first category/five-year range; an indicator deep link resolves its own category. Assets and data URLs are relative to the site directory.

The Python build validates input before replacing `dist/`, copies the site and pinned ECharts 5.6.0 bundle/license, and creates `.nojekyll`. The tracked GitHub Actions workflow runs Python and JavaScript checks and uploads `dist/`. Pull requests only validate; pushes to `main` and manual workflow runs can deploy using the `github-pages` environment. Configure repository Settings → Pages → GitHub Actions before the first deployment. This local checkout has no Git remote; live publication is not part of the completed local verification.

#### Milestones and acceptance review

1. **Prototype implementation:** completed in this repository: four categories, eight indicators, local fixtures, responsive overview/drill-down, accessible controls, tables, deep links, validation, and Pages workflow.
2. **Interface review:** user confirms category names/mapping, example indicator choices, information density, and reading workflow. No article taxonomy is inferred.
3. **Real-data integration:** implement collection and validation only after the interface and source/aggregation choices are agreed.

Regression commands:

```sh
python3 -m unittest discover -s tests -p 'test_*.py'
node --test tests/data.test.mjs
python3 scripts/build.py
```

Acceptance checks include fixture reproducibility; exact-date native-unit and basis-point calculations; explicit gaps; stale latest values; calendar windows; malformed and direct hash links; and adding an indicator through configuration. Browser review covers all categories, range switching, tables, expanded metadata, keyboard dismissal/focus, responsive columns, and reloads beneath a project-style subdirectory. The GitHub-hosted workflow itself requires a connected repository and Pages configuration to verify.

Verification performed: four Python contract checks and six JavaScript regression checks passed; the static build and `git diff --check` passed. Chrome review passed at 1440px desktop, 768px tablet, and 390px/320px phone widths without horizontal page overflow. All eight indicators, one-year (53 rows) and all-history (262 rows) tables, basis-point display, missing/latest observation dates, keyboard range activation, Escape/focus return, and direct expanded-dialog reloads beneath `/dist/` were exercised. No application errors were observed; browser-extension connection errors were unrelated to the dashboard. JavaScript checks were executed by importing the assertion suite in the available Node REPL because the shell has no Node binary on its PATH; CI provisions Node explicitly.

#### Future collection and replacement plan

Use **scheduled GitHub Actions collection → validation → static JSON files → deployment**. Candidate free public sources are Federal Reserve H.4.1, New York Fed reference rates/operations/dealer statistics, Treasury Fiscal Data, and OFR. Confirm availability, series definitions, licensing, time zones, publication lags, and revision policies before implementation. Agree on weekly aggregation explicitly: end-of-week/latest available levels, weekly averages, and weekly sums have different meanings.

Collectors should normalize units, align weekly dates, preserve gaps, record observation and collection timestamps separately (per series where necessary), and stage files before validation. Validate required series, finite values, duplicate dates, cadence, unit consistency, provenance, and unexpected staleness. Keep API keys solely in Actions secrets; public static files must never contain credentials.

Only replace the previously published dataset after every required collection and validation step succeeds. On failure, fail the collection job, retain the last successful dataset/deployment, and record failure details in Actions logs. Do not overwrite valid files with empty responses or advance collection timestamps for unsuccessful pulls. First publish validated snapshots atomically, then build/deploy those exact files.

The current prototype intentionally requires `isDemo: true` and shows fixed demo notices. The real-data milestone must update validation to support provenance, replace the hardcoded synthetic notices/source labels with metadata-driven labels, and review collection metadata and all source links. Merely setting `isDemo` to false is insufficient. Keep synthetic fixtures for regression testing and visibly separate any mixed demo/real series.
