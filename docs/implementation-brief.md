# USD Liquidity Dashboard — Prototype and Implementation Brief

### 1. Objective and deliverable

Design a Chinese-language dashboard for **weekly research into dollar liquidity**, helping the user investigate conditions relevant to US Treasury trades.

The first milestone is a **visual prototype with clearly labeled synthetic data**, organized into four categories. Real data integration follows after reviewing the interface.

Prepare an English Markdown handoff document, `docs/implementation-brief.md`, containing the agreed design, Chinese labels, data interfaces, implementation milestones, and acceptance criteria.

### 2. Dashboard experience

Use **overview + drill-down**:

```text
美元流动性观察                         演示数据 · 非实时

[ 货币层 ]     [ 离岸层 ]     [ 信用层 ]     [ 金融市场层 ]
  重点指标       重点指标       重点指标       重点指标
  趋势缩略图     趋势缩略图     趋势缩略图     趋势缩略图

所选类别                      YTD | 近1年 | 近5年 | 全部

[ 指标图表 A                  ] [ 指标图表 B                  ]
  最新值 · 近4周变化 · 近13周变化 · 数据日期

展开指标 → 大图 · 指标说明 · 数据来源 · 更新频率 · 数据表
```

- Keep all four category summaries visible; selecting one changes the detailed charts below. Select the first category initially.
- Show one indicator entry per row of the article inventory: 10 monetary, 4 offshore, 9 credit, and 7 financial-market entries. Numeric demonstrations use deterministic weekly observations spanning five years; the unquantified cross-asset selling pattern retains an explicit empty state.
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

For later real-data integration, use **automatic collection + manual inputs → validation → derived indicators → versioned static data → deployment**. Use free public sources and keep API keys in Actions secrets. Retain the last valid observations for individual sources that fail, while allowing other validated updates to publish; invalid assembled datasets must not deploy. The mixed-source implementation guide at the end of this document defines the future contract.

### 4. Verification and acceptance

The prototype is ready for review when:

- All four research layers and 30 article-derived indicator entries render correctly, with one entry per inventory row.
- Category selection, time ranges, expanded details, and data tables work.
- Latest values and changes match the fixtures; missing data is never converted to zero.
- Every view clearly identifies synthetic data.
- Chinese text, charts, and controls remain usable at mobile and desktop widths.
- Direct links and reloads work under a GitHub Pages repository subpath.
- Adding an indicator through configuration displays it without layout changes.
- The handoff document explains local preview, deployment, and how fixtures will later be replaced.

### 5. Assumptions and reference material

- The article’s four categories and indicators have been extracted from the supplied [WeChat article text](../wechat.txt) and applied to the site catalog; see the article framework below. Each indicator inventory row maps to one dashboard entry. Numeric data remains synthetic; source series and measurement conventions are not yet finalized.
- English is the default for implementation instructions; the delivered interface is Chinese.
- The dashboard is intended primarily for personal research, with public static hosting.
- Use the [OFR Short-term Funding Monitor](https://www.financialresearch.gov/short-term-funding-monitor/) as a reference for grouped charts and interpretive guidance, and the [New York Fed Markets Data Dashboard](https://www.newyorkfed.org/markets/data-hub) as a reference for organizing market data. Their categories do not replace the article’s framework.

#### Article framework: four categories and their indicators

Source: [wechat.txt](../wechat.txt), supplied on October 28, 2026. The inventory below summarizes the article’s four layer sections, particularly their **观测** (observation) subsections. English descriptions explain the Chinese labels used by the article. These are article-derived research definitions; provider series, currencies, tenors, units, and aggregation rules still need to be selected for implementation. No live-data availability has been verified.

| Order | Category / Chinese label | Article section title | Research focus |
| --- | --- | --- | --- |
| 1 | Monetary layer / 货币层 | 货币层：美元流动性之源 | Availability of base dollar funding, financing prices, and redistribution between financial institutions. |
| 2 | Offshore layer / 离岸层 | 离岸层：美元的全球再分配 | Cross-border dollar circulation and non-US institutions’ access to dollar funding. |
| 3 | Credit layer / 信用层 | 信用层：金融体系与实体部门的联结 | Whether funding translates into private credit and financing for businesses and households. |
| 4 | Financial-market layer / 金融市场层 | 金融市场层：流动性的终点，也是反馈的起点 | Trading capacity, volatility, and the feedback from positioning, leverage, and forced selling. |

**1. Monetary layer — 货币层**

The article prioritizes funding prices over quantities, using central-bank facility usage to confirm severe stress.

| Indicator / Chinese label | Role in the article | What it observes |
| --- | --- | --- |
| SOFR−EFFR / SOFR与EFFR利差 | Primary funding-price measure | Repo funding pressure relative to the federal funds market. |
| SOFR−OIS / SOFR与OIS利差 | Primary funding-price measure | Secured funding premium relative to the OIS reference. The OIS tenor/convention is not specified. |
| SOFR 99th percentile−SOFR / SOFR99分位−SOFR | Funding dispersion and tail pressure | Whether high-end repo rates diverge from the central SOFR rate. |
| Bank reserve balances / 银行准备金 | Supporting quantity | Reserve availability; the article cautions against a universal fixed safe level. |
| Reserves / commercial-bank total assets / 准备金占商业银行总资产比例 | Supporting relative quantity | Reserve adequacy relative to the banking system’s size. |
| Federal Reserve balance sheet / 美联储资产负债表 | Reserve-supply context | Balance-sheet expansion or contraction and its effect on reserves. |
| Treasury General Account balance / TGA余额 | Reserve-distribution context | Treasury cash movements that affect banking-system reserves. |
| Overnight reverse repo balance / ON RRP余额 | Reserve-distribution context | Allocation of liquidity between reverse repo and bank reserves. |
| Discount window usage / 贴现窗口用量 | Stress confirmation | Bank reliance on central-bank funding. |
| Federal Reserve repo operations / 美联储正回购用量 | Stress confirmation | Central-bank funding supplied against collateral to ease repo-market shortages. |

**2. Offshore layer — 离岸层**

The article uses the dollar index as an outcome indicator, cross-currency basis as the direct funding-pressure measure, and official facilities as confirmation of extreme conditions.

| Indicator / Chinese label | Role in the article | What it observes |
| --- | --- | --- |
| Cross-currency basis / 交叉货币基差 | Primary funding-price measure | Implied dollar funding cost through FX swaps relative to same-tenor dollar OIS/SOFR. Currency pair, tenor, and quotation convention are not specified. |
| US dollar index / 美元指数（DXY） | Supporting outcome measure | Dollar strength; the article cautions that strength alone does not establish offshore funding stress. |
| Central-bank dollar swap-line usage / 央行美元流动性互换工具用量（Swap Line） | Stress confirmation | Official dollar provision through foreign central banks when private funding is impaired. |
| FIMA Repo Facility usage / 外国和国际货币当局回购工具用量 | Stress confirmation | Official dollar borrowing against Treasury collateral, reducing the need to sell Treasuries for cash. |

Cross-border bank financing contraction and access to FX-swap funding are additional diagnostic context in the article’s **溯源** discussion; it does not prescribe a particular bank-flow series. Swap Line and FIMA are two distinct facilities, not duplicate swap indicators.

**3. Credit layer — 信用层**

The article pairs high-frequency credit prices with evidence that borrowers can actually obtain financing.

| Indicator / Chinese label | Role in the article | What it observes |
| --- | --- | --- |
| Credit spreads / 信用利差 | Primary price measure | Credit risk pricing and funding costs, particularly high-yield (HY) spreads; investment-grade (IG) conditions help assess how far stress has spread. |
| Credit default swap spreads / 信用违约互换价差（CDS） | Primary price measure | Market pricing of default risk, including bank CDS in the historical cases. |
| BDC-related ETF prices / BDC相关ETF价格表现 | Supporting market proxy | Pricing of higher-risk nonbank and private-credit-related exposures. No ETF ticker is specified. |
| CLO-related ETF prices / CLO相关ETF价格表现 | Supporting market proxy | Pricing of collateralized loan obligation exposures. No ETF ticker is specified. |
| Bond issuance volume / 债券发行量 | Financing availability | Whether primary-market funding is open, distinguishing HY from IG issuers. |
| Net issuance of risky debt / 风险债务净发行 | Financing availability | Net new risky-debt funding reaching borrowers. |
| Primary-market freeze / zero-issuance days / 一级市场冻结天数／零发行天数 | Financing availability | Duration of issuance interruptions and whether freezes spread to higher-quality issuers. |
| Bank lending standards / 银行贷款标准 | Supporting credit-supply measure | Banks’ willingness to lend and tightening or easing of access to credit. |
| Bank credit / loan growth / 银行信贷增速／银行贷款增速 | Supporting quantity | Realized lending, including commercial and industrial loans. Early crisis growth can reflect precautionary credit-line drawdowns rather than improving conditions. |

The category’s explanatory and **溯源** sections also discuss policy rates, loan demand, ISM manufacturing PMI, corporate free cash flow and capital expenditure, CET1 capital adequacy and SLR/eSLR constraints, leverage, debt-servicing capacity, and refinancing needs. These are context for locating vulnerabilities, rather than additional primary liquidity-price measures. The article highlights leveraged loans, private credit, and commercial real estate as areas to examine; these sectors are not separate dashboard categories.

**4. Financial-market layer — 金融市场层**

The article monitors equities, bonds, commodities, and foreign exchange through three dimensions: volatility, market depth, and positioning/leverage.

| Indicator / Chinese label | Role in the article | What it observes |
| --- | --- | --- |
| Asset-market volatility / 股、债、商、汇波动率 | Initial stress signal | Abnormal price fluctuations across asset classes. VIX is explicitly named in the equity-market case study; other volatility index names are not specified. |
| Bid–ask spread / 买卖价差（Bid-Ask） | Trading capacity | Wider spreads indicate worse trading conditions in the Treasury example. |
| Market depth / 市场深度（Market Depth） | Trading capacity | Available capacity to absorb trades; the article specifically discusses 10-year Treasury depth. |
| Price impact / 价格冲击（Price Impact） | Trading capacity | How strongly trading moves prices; higher impact accompanies impaired Treasury liquidity. |
| Positioning / 仓位与头寸 | Crowding and unwind risk | Concentrated positions and position reductions; examples include yen noncommercial net shorts and swap-spread trade unwinds. |
| Leverage / 杠杆水平与去杠杆进展 | Forced-selling risk | Exposure to margin calls and the progress of deleveraging. The article does not prescribe a single leverage series. |
| Cross-asset co-movement / 跨资产同步抛售 | Stress propagation | Simultaneous declines in stocks, Treasuries, and gold, rising volatility, and falling depth across markets. This is an observed pattern, not an article-defined composite index. |

Margin calls, VaR constraints, fund redemptions, and forced liquidations explain the feedback mechanism and help interpret positioning changes. The article does not define standalone quantitative series for each mechanism.

For the dashboard, preserve the distinction between primary prices, supporting quantities, and facility usage in indicator explanations. The site now includes all 30 inventory rows as individual entries; combined variables are not expanded into currency, asset, tenor, issuer, or HY/IG sub-series. SOFR and EFFR levels are inputs to the monetary spread indicators. The former repo-volume and dealer-Treasury-position examples have been removed. The broader article-defined positioning entry has its own ID and provisional measurement note. Historical case-study statistics and trading-rule thresholds are not adopted as dashboard alerts or recommendations.

### 6. Implemented prototype and design handoff

Implemented on October 28, 2026. The repository now contains a standalone static site; no live financial data is requested. The implementation uses the New York Fed page as a visual reference: navy masthead/navigation, serif Chinese page title, restrained blue lines, thin dividers, compact numeric summaries, and a white background. The prototype uses its own identity and does not imply Federal Reserve affiliation.

**Page structure:** permanent four-category overview → selected category charts → data/reading notes. Overview cards show the first configured indicator as the primary value and one-year sparkline, one secondary indicator, and the category’s total indicator count. The complete inventory appears in the detail charts below. Detail cards render every configured indicator in the selected category. Native buttons support keyboard selection; native modal dialogs trap focus, close with Escape, and return focus to the triggering control. Charts have labeled data-table alternatives. No directional red/green coloring or composite judgments are used.

Responsive breakpoints: overview uses four columns above 900px, two from 601–900px, and one at 600px and below. Indicator charts use two columns above 600px and one below. Tables scroll independently and preserve column headings. Reduced-motion preferences suppress chart animation.

#### Chinese interface labels

| Purpose | Label |
| --- | --- |
| Page title | 美元流动性观察 |
| Prototype notice | 演示数据 · 非实时 |
| Overview | 流动性概览 |
| Research layers | 货币层 / 离岸层 / 信用层 / 金融市场层 |
| Time controls | YTD / 近1年 / 近5年 / 全部 |
| Metrics | 最新值 / 近4周变化 / 近13周变化 / 观测日期 |
| Indicator controls | 展开指标 / 查看统计摘要 / 收起统计摘要; 查看数据表 in expanded details |
| Summary statistics | 近3个月均值 / 近1年均值 / 当前值历史分位 |
| Metadata | 指标说明 / 当前数据来源 / 后续拟接入来源 / 更新频率 |
| Collection timestamp | 演示数据生成时间 |
| Reading notes | 数据与阅读说明 |

The catalog follows the 30 Chinese indicator labels in section 5 exactly and preserves their order and research roles. There are 10 entries in 货币层, 4 in 离岸层, 9 in 信用层, and 7 in 金融市场层. SOFR/EFFR levels, repo volume, and the old dealer-position example are no longer separate dashboard entries. Unspecified currency pairs, tenors, ETFs, credit segments, and asset classes remain combined into one entry per article row.

Twenty-nine entries have illustrative numeric fixtures. Their units and conventions are explicitly provisional in each explanation: dollar amounts, basis-point spreads, percentage ratios, index points, ETF prices, day/contract counts, leverage multiples, and price impact. The broad balance-sheet entry temporarily demonstrates total assets. These choices are interface examples, not verified provider-series definitions. `跨资产同步抛售` is retained as an unquantified observation pattern with all-null fixtures and an explanatory empty state; no composite index is invented. All provider sources are currently marked pending, so the interface displays plain source text rather than unverified provider links.

#### Files and minimum data interfaces

This subsection describes the implemented synthetic prototype only. Its weekly grid, shared date interval, demo-only validation, and directly maintained site JSON are not requirements for production data. The future mixed-source guide below replaces those assumptions when real-data integration is implemented.

`site/data/catalog.json` separates category definitions and indicator metadata from `site/data/observations.json`. `schemaVersion: 1` identifies the current contract. Stable IDs are lowercase ASCII slugs and independent of display labels.

```json
{
  "schemaVersion": 1,
  "dataset": {
    "id": "synthetic-article-framework-v2",
    "isDemo": true,
    "observationStart": "2021-10-27",
    "observationEnd": "2026-10-28",
    "collectedAt": "2026-10-28T00:00:00Z"
  },
  "categories": [
    {"id": "category-1", "order": 1, "name": "货币层", "description": "美元流动性之源"}
  ],
  "indicators": [
    {
      "id": "reserve-balances",
      "categoryId": "category-1",
      "name": "银行准备金",
      "role": "辅助数量",
      "explanation": "Synthetic demonstration, not an official observation.",
      "unit": {"kind": "amount", "label": "十亿美元", "precision": 1},
      "frequency": "weekly",
      "source": {"name": "数据源与口径待确认", "url": null, "status": "pending"},
      "isDemo": true
    }
  ]
}
```

The shortened example illustrates the shape; validation requires four populated categories. `unit.kind` supports `amount`, `rate`, `spread`, `ratio`, `index`, `price`, `count`, `multiple`, `scalar`, and `unquantified`. Rate levels are expressed in percentage points (e.g. `4.25` means 4.25%) and their changes convert to bp. Spread levels already use bp and are never multiplied by 100; ratio changes use percentage points. All other changes preserve their native unit. `source` accepts either a verified HTTPS URL or `url: null` with `status: "pending"`. The UI separately identifies the current data source as a local synthetic fixture.

```json
{
  "reserve-balances": [
    {"date": "2021-10-27", "value": 4000.0},
    {"date": "2021-11-03", "value": null}
  ]
}
```

Each series uses a sorted, uninterrupted weekly date grid, spanning the dataset interval. Numeric indicators must contain at least one valid observation; `unquantified` entries must contain only nulls. Absent observations must have explicit `null` values. The checked-in fixture has 262 dates per series and is reproducible with `python3 scripts/generate_fixtures.py`. No random seeds, clocks, credentials, or network calls affect fixture generation.

The latest metric uses the latest non-null observation and displays **that observation's date**. Four- and thirteen-week comparisons use the exact date 28/91 days before that latest valid date. A missing comparison produces `—`, never a comparison against another date. Rate differences multiply by 100 to produce basis points. Missing chart observations remain visible gaps (`connectNulls: false`); tables label them as missing. The new positioning fixture deliberately omits the final observation; reverse repo deliberately omits the four-week comparison.

Time windows are anchored to `dataset.observationEnd`, not the browser clock. YTD starts on January 1 of the dataset-end year (UTC) and uses `range=ytd` in deep links; it applies to charts, expanded details, and data tables. One/five years use calendar-year boundaries; all history includes the complete fixture. Because the fixture starts one day before the five-year cutoff, the five-year range has 261 observations and all history has 262. Sparklines always use the latest calendar year. Each category remembers its selected range during the browser session; each category initially uses five years.

The chart-card disclosure now shows summary statistics rather than raw observations. The 3M and 1Y means are arithmetic means of available weekly values within the trailing three calendar months and twelve calendar months ending on the latest valid observation date (inclusive); month-end cutoffs clamp to the last valid day of the target month. These fixed lookbacks do not change with the chart range. Means remain in native units, including percentage levels for rates. The current value's percentile uses valid observations in the selected chart range: `100 × count(value <= latest value) / count(valid observations)`, including the latest value and all ties. This empirical cumulative rank has a maximum of 100%; it is not an investment rating. Nulls are excluded, real zero values are retained, and an empty sample displays `—`. Each metric displays its valid observation count, and the disclosure states the methodology and date. Incomplete windows use the available sample. Raw data tables remain available in expanded details as the chart alternative.

Summary-statistics verification: nine JavaScript regression checks passed, including tied ranks, empty samples, missing/latest observations, zero values, leap-day/year boundaries, and month-end cutoffs. Browser review confirmed keyboard disclosure toggling, unchanged means when switching chart ranges, recalculated percentiles, rate means in percentage units, retained detail tables, and a 320px phone layout without horizontal overflow.

Adding an indicator requires only an entry in `catalog.indicators` and its series in `observations.json`; layout, tables, dialogs, and summary rendering are generated from configuration. The build validates unique IDs, metadata, category references, timezone-aware collection timestamps, HTTPS or explicitly pending sources, finite numeric values, explicit nulls, unquantified patterns, weekly cadence, and matching observation keys.

#### Local preview and deployment

Python 3.10+ is required; all Python scripts use the standard library. Node 22+ is needed only for JavaScript regression checks and is provisioned by CI. No npm installation or frontend build framework is required.

```sh
python3 scripts/build.py
python3 -m http.server 8000 --directory dist --bind 127.0.0.1
```

Open `http://127.0.0.1:8000/`. To verify repository-subpath hosting, serve the repository root and open `/dist/`. Do not open the HTML using `file://`, because the app fetches local JSON and uses JavaScript modules.

Navigation uses hashes such as `#category=category-2&range=1y&indicator=cross-currency-basis`. Reloading and browser history restore the selected category, range, and open detail dialog without server route support. Invalid route values safely fall back to the first category/five-year range; an indicator deep link resolves its own category. Assets and data URLs are relative to the site directory.

The Python build validates input before replacing `dist/`, copies the site and pinned ECharts 5.6.0 bundle/license, and creates `.nojekyll`. The tracked GitHub Actions workflow runs Python and JavaScript checks and uploads `dist/`. Pull requests only validate; pushes to `main` and manual workflow runs can deploy using the `github-pages` environment. Configure repository Settings → Pages → GitHub Actions before the first deployment. This local checkout has no Git remote; live publication is not part of the completed local verification.

#### Milestones and acceptance review

1. **Prototype implementation:** completed in this repository: four research layers, 30 indicator entries, local fixtures, responsive overview/drill-down, accessible controls, tables, deep links, validation, and Pages workflow.
2. **Article alignment:** completed: all 30 inventory rows are mapped to the four research layers, with no sub-series expansion. Next review the provisional numeric definitions, information density, and reading workflow before real-data selection.
3. **Real-data integration:** implement collection and validation only after the interface and source/aggregation choices are agreed.

Regression commands:

```sh
python3 -m unittest discover -s tests -p 'test_*.py'
node --test tests/data.test.mjs
python3 scripts/build.py
```

Acceptance checks include fixture reproducibility; exact-date native-unit and basis-point calculations; explicit gaps; stale latest values; calendar windows; malformed and direct hash links; and adding an indicator through configuration. Browser review covers all categories, range switching, tables, expanded metadata, keyboard dismissal/focus, responsive columns, and reloads beneath a project-style subdirectory. The GitHub-hosted workflow itself requires a connected repository and Pages configuration to verify.

Article-alignment verification: five Python contract checks and ten JavaScript regression checks passed. The inventory check compares every catalog label and its order against the 30 Markdown rows, with category counts of 10/4/9/7. Chrome verified all 30 rendered entries, provisional source text without broken links, the unquantified pattern’s chart/detail/statistics states, a new YTD indicator deep link and reload beneath `/dist/`, negative-basis summary statistics, and 320px phone layouts with long labels and units. The build and whitespace checks passed; no application console errors were observed.

Original prototype verification (before the article alignment): four Python contract checks and six JavaScript regression checks passed; the static build and `git diff --check` passed. Chrome review passed at 1440px desktop, 768px tablet, and 390px/320px phone widths without horizontal page overflow. All eight indicators, one-year (53 rows) and all-history (262 rows) tables, basis-point display, missing/latest observation dates, keyboard range activation, Escape/focus return, and direct expanded-dialog reloads beneath `/dist/` were exercised. No application errors were observed; browser-extension connection errors were unrelated to the dashboard. JavaScript checks were executed by importing the assertion suite in the available Node REPL because the shell has no Node binary on its PATH; CI provisions Node explicitly.

#### Mixed-source data implementation guide (future real-data milestone)

This guide specifies future implementation work; the collectors, manual-input pipeline, and production data contract are not implemented by this documentation update. The existing prototype and its regression fixtures remain unchanged.

Use **automatic collection + manual inputs → validation and normalization → derived indicators → versioned snapshot → static build → GitHub Pages**. The browser reads generated local JSON, never provider APIs or editable input files. Git-backed files are sufficient initially; no database or browser-based administration interface is required.

##### Registry, ownership, and storage

Create a source registry separate from the generated display catalog. Use these proposed repository locations:

| Location | Purpose | Writer |
| --- | --- | --- |
| `data/registry.json` | Source definitions, measurement conventions, and transformation rules keyed by stable series ID | Maintainer |
| `data/automatic/<series-id>.json` | Last validated automatic observations and provenance | Collector pipeline |
| `data/manual/<series-id>.csv` | Manually maintained source observations | Maintainer |
| `data/snapshot/` | Current validated normalized dataset, derived series, and run manifest; previous versions retained in Git | Assembly pipeline |
| `site/data/` | Generated catalog, observations, and machine-readable operational metadata for the website | Build pipeline |

The registry must include each series's stable ID, update method (`automatic`, `manual`, or `derived`), source reference, provider series identifier where applicable, native frequency, observation-date convention, source unit, normalized unit, and configured history interval. Include publication-lag expectations, optional aggregation, comparison rules, and conversion rules. Derived entries additionally specify input IDs and their formula. Source-only inputs, such as individual rate levels used in a spread, need not become dashboard entries.

Assign exactly one update method to each series. Reject duplicate ownership, unknown inputs, and cyclic derivations. Collectors may write only automatic inputs; manual files must never be overwritten by collection. Do not introduce implicit manual overrides or switch to a different provider after a fetch failure. A source change requires an explicit registry edit and a review of historical comparability.

Candidate sources include FRED and direct Federal Reserve, New York Fed, Treasury Fiscal Data, and OFR releases. Confirm each selected series's definition, availability, redistribution terms, units, seasonal adjustment, dates, publication lag, and revision behavior before activating it. Article-level indicator names alone are not sufficient source definitions.

##### Manual entry and corrections

Use UTF-8 CSV with one file per manual series and these columns:

| Field | Requirement |
| --- | --- |
| `date` | Required ISO observation date (`YYYY-MM-DD`), following the registry's period convention |
| `value` | Numeric value in the configured source unit; blank means explicitly missing, never zero |
| `source_reference` | Required URL or traceable publication reference, including a page/table where useful |
| `publication_date` | Optional ISO date of the source release; do not substitute the entry date |
| `correction_note` | Optional for new observations; required when changing or removing a previously recorded observation |

Maintain one row per observation date and sort rows chronologically. Add new rows for new periods; edit the existing row for a revision instead of adding a duplicate. Record the reason for a removed row in the commit message, since its CSV note will no longer be present. Validate corrections against the previous committed input. Git records previous values, authorship, and edit history; the pipeline records the input commit and its timestamp as entry provenance, separately from observation/publication dates.

The maintenance routine is: edit the CSV → commit or open a pull request → review validation results → merge to the default branch → regenerate and publish. Pull requests validate without deploying. Manual edits trigger assembly from the last validated automatic inputs and do not require a successful fresh API request. Do not edit generated site JSON to correct data.

##### Automatic collection, revisions, and scheduling

Add a daily GitHub Actions schedule and an on-demand `workflow_dispatch` trigger. Store FRED and other API credentials solely in Actions secrets; redact credentials from logs and never include them in snapshots or public assets. Add a default-branch trigger for manual input and registry changes. Serialize snapshot-writing and deployment jobs so overlapping scheduled and manual runs cannot overwrite newer inputs; avoid recursive collection triggered by generated-data commits.

Initially, fetch the full configured history for each automatic series on every collection run, including pagination where necessary. This captures historical revisions as well as new observations. Validate the complete response before replacing that series's stored input. Treat unexpected empty/truncated responses as collection failures, and report historical changes or removals explicitly in the run summary. A complete, valid response that contains no changes still counts as a successful check.

Normalize provider missing-value markers to explicit missing values and preserve real zeroes. Record per-series source identity, latest observation date, last attempt time, last successful check time, and last data-change time. Use timezone-aware UTC timestamps for operational events. A failed check must not advance the last-success timestamp. Configure freshness expectations per series so monthly publication, holidays, and normal release delays are not treated as daily update failures.

##### Native frequencies and derived indicators

Store each source's observations at its native daily, weekly, monthly, quarterly, or irregular frequency. Do not impose a shared start/end date or uninterrupted weekly grid. Observation dates describe the measured period, not when the pipeline downloaded it. Distinguish normal non-observation dates from missing expected observations; do not insert zeroes or invent observations to fill a calendar.

Any display aggregation must be explicit in the registry: target period, period-end convention, aggregation method (last observation, average, or sum), and treatment of incomplete periods. Preserve native inputs even when a display series is aggregated. Weekly research does not imply weekly source data.

Compute derived indicators only after validating and normalizing their inputs. Join inputs on matching observation dates by default; if an input is missing, the derived value is missing. Any alternative alignment requires an explicit per-indicator rule with an age limit. Never silently forward-fill inputs or combine different observation periods. Document dimensional conversions before applying formulas: for example, a difference between rate levels expressed in percent is multiplied by 100 to yield basis points; spreads already in basis points are not multiplied again. Recalculate affected history when an input is revised, and retain input snapshot references with the derived result.

Configure comparison periods and matching rules per indicator. Daily/weekly series may retain 4- and 13-week changes with an explicitly documented calendar-matching rule; monthly/quarterly series need comparisons appropriate to their release periods. A missing or excessively old comparison returns `—`. Update comparison labels to describe the calculation actually used. Review averages and percentiles for native-frequency data; state whether statistics use native observations or an explicitly aggregated series, and never increase sample counts by filling missing dates.

##### Validation, failure handling, and atomic publication

Stage all updates before modifying the publishable snapshot. Validate registry references, ownership, observation ordering, duplicate dates, finite values or explicit missing values, units, provenance, configured transformations, and the assembled output contract. Unexpected data movements should be reported for review, not silently clipped or changed.

If an automatic series fails collection or source validation, retain that series's last validated observations and original successful timestamps. Other valid series may still update. If no valid history exists, emit an unavailable series with an empty observation array. Derivations may use retained inputs only under their documented date-alignment rules; missing compatible inputs produce missing results. Report collection failures in the workflow summary even when publication succeeds with retained data.

Invalid manual edits, invalid registry/calculation rules, or an invalid assembled dataset block publication and leave the previous deployment intact. A fatal build or deployment error likewise leaves the previous published snapshot in place. Do not equate a recoverable individual source failure with a structural dataset failure.

Commit validated automatic inputs and the assembled snapshot to Git, recording the source-input commit, snapshot ID, generation time, per-series outcomes, and revision summary in its manifest. Exclude secrets and credential-bearing request URLs. Build the website from that exact committed snapshot and deploy the complete Pages artifact as one unit; never update catalog and observations independently. Retain earlier snapshots through Git history for audit and rollback. This records versions captured by this project; it does not reconstruct historical publication vintages or establish a point-in-time backtesting dataset.

##### Chart presentation and migration

**Do not add `最近检查`, `人工录入时间`, `自动更新`, `人工维护`, or update-status badges to charts or overview cards.** Keep operational timestamps, collection failures, and maintenance diagnostics in machine-readable metadata and GitHub Actions reports. Retain the existing observation date beside the latest value, showing the date of that actual observation even when data is retained after a failure. Existing source explanations may remain in expanded details; no new operational-status UI is required.

Introduce a versioned production contract that supports native frequencies, different history lengths, unavailable/empty series, per-series provenance, and generated outputs. Update backend validation and frontend parsing, date windows, comparison calculations, frequency labels, statistics, and empty-state rendering together. The prototype's weekly-grid assertions and demo-only checks remain valid for fixture tests, not for production inputs. Label the two contracts explicitly and keep their datasets separate.

Keep deterministic synthetic fixtures in demo/test mode and prevent the fixture generator from writing production outputs. In production, an unconnected indicator displays `待接入` with an empty chart state; it must not fall back to synthetic observations. The unquantified cross-asset pattern remains nonnumeric unless a measurement definition is separately agreed. Remove fixed synthetic notices only for the production dataset after source/provenance handling is implemented; merely setting `isDemo` to false is insufficient.

##### Implementation order and future acceptance cases

Implement the registry and manual importer first, then one automatic collector, normalization/derivations, versioned snapshot assembly, and scheduled publication. Migrate the frontend to the production contract before enabling real data. Expand indicator coverage only after each measurement convention is confirmed.

The real-data milestone must verify:

- A manual addition appears after publication; a correction requires a reason and preserves the previous value in Git. Duplicate dates and conflicting ownership fail validation, and automatic collection cannot modify manual files.
- A historical provider revision updates stored and derived history; a successful unchanged response updates check metadata without changing observations.
- A partial collection failure retains the affected series while another valid series publishes. First-time unavailable series render empty states; invalid assembled data or build failure preserves the prior deployment.
- Daily, monthly, and irregular series preserve their dates and distinct history lengths. Missing values remain missing, true zeroes survive, and missing comparisons or incompatible derived inputs yield no fabricated result.
- Percent-to-basis-point and other configured conversions are correct; already-normalized spreads are not converted twice. Summary counts reflect actual observations.
- Manual-input pushes, daily schedules, and on-demand runs use the same validation/assembly path. Concurrent runs cannot publish older inputs over newer ones, and generated commits do not create workflow loops.
- Catalog and observations come from the same snapshot, prior versions are recoverable, and public artifacts/logs contain no credentials.
- Production never displays synthetic fallback data. Charts and overview cards retain observation dates without any of the prohibited maintenance timestamps or status badges.

These are future acceptance requirements, not checks performed by this documentation-only change.
