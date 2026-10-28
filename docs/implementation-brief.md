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
