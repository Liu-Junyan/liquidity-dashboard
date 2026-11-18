# Slice 6 source review

Reviewed November 17–18, 2026. Registry specifications are bound to
`data/source-reviews.json`; changing measurement fields requires renewed review.
The active set contains 23 series: 17 automatic inputs, three manual inputs and
three derived outputs, producing 18 displayed indicators. Five inputs stay hidden.
ICE credit spreads were activated on November 18 after the maintainer confirmed
redistribution permission; VIX remains inactive by the maintainer's explicit
decision, and Treasury bid–ask is deferred. Existing unavailable entries remain
excluded.

## Source conventions

All automatic inputs request current history from 2010 onward, with no resampling,
forward filling, vintage reconstruction or alternative provider. Missing markers
remain null and true zeroes remain zero. Every complete response replaces the
prior history; revisions and deletions are counted, and Git retains prior captures.
Provider metadata must match ID, source units, frequency and the reviewed seasonal
adjustment. Both Wednesday conventions validate every stored observation date;
quarterly input dates must be quarter starts. Freshness is diagnostic, not rejection:
7 days for daily sources, 14 for H.4.1, 21 for H.8 and 150 for quarterly labels.
These allowances accommodate release/ingestion lags, not promised release times.

### sofr99

[FRED SOFR99](https://fred.stlouisfed.org/series/SOFR99) is the NY Fed SOFR
transaction distribution's 99th percentile, percent, daily, NSA. It begins April 3,
2018. Preserve transaction dates rather than next-business-day publication dates.
Reference-rate revisions, methodology and republication notices follow the
[NY Fed terms](https://www.newyorkfed.org/privacy/termsofuse) and the existing SOFR
review. This is a distribution percentile, not a confidence interval.

### sofr-tail-spread

Same-date SOFR99 minus SOFR, in percentage points under the existing `%` label.
Use the union of source dates, null when either input is absent, and no second
scale conversion. Recompute all history and record both normalized input hashes.
NY Fed notices cover the inputs and related project calculation.

### reserve-balances

[FRED WRBWFRBL](https://fred.stlouisfed.org/series/WRBWFRBL): Board H.4.1 reserve
balances with Federal Reserve Banks, Wednesday stock, NSA, millions of USD.
Divide by 1,000 into billions. H.4.1 normally releases Thursday; preserve the
Wednesday observation date. Board public-domain data; credit Board and FRED.

### bank-total-assets

[FRED TLAACBW027SBOG](https://fred.stlouisfed.org/series/TLAACBW027SBOG): Board H.8
commercial-bank total assets, weekly ending Wednesday, **SA**, billions unchanged.
The [H.8 release](https://www.federalreserve.gov/releases/h8/about.htm) normally
publishes Friday and estimates commercial-bank balance sheets. Its population
excludes thrifts and credit unions. Retain the maintainer-selected mapping.
Seasonal estimates and benchmark revisions can change historical observations.
Board public-domain data; credit Board and FRED.

### reserve-assets-ratio

Normalize reserves into billions before calculating `100 * reserves / assets`.
The numerator is NSA H.4.1; the denominator is SA H.8 with a different population.
The chart is explicitly named a **cross-coverage research ratio**, with the
mismatch disclosed in its explanation and notices. It is not a matched-population
balance-sheet share. Match exact Wednesday dates; null for missing/zero denominator.
Do not seasonally adjust the numerator or substitute the denominator implicitly.

### treasury-account

[FRED WDTGAL](https://fred.stlouisfed.org/series/WDTGAL): Board H.4.1 Treasury
General Account, Wednesday stock, NSA, millions divided by 1,000 into billions.
This is weekly, not a daily Treasury cash balance. H.4.1 timing/revision rules and
Board/FRED attribution apply.

### reverse-repo

[FRED RRPONTSYD](https://fred.stlouisfed.org/series/RRPONTSYD): NY Fed overnight
reverse-repo transactions against Treasury securities, aggregated daily by FRED,
NSA, billions unchanged. Excludes other collateral and term operations. Preserve
provider dates, missing markers and zeroes; do not infer activity from absent dates.
Use NY Fed content terms, original-source title and FRED attribution.

### discount-window

[FRED WLCFLPCL](https://fred.stlouisfed.org/series/WLCFLPCL): Board H.4.1 **primary
credit only**, Wednesday stock, NSA, millions unchanged. Excludes secondary and
seasonal credit; the chart explanation narrows the generic discount-window label.
H.4.1 timing/revision rules and Board/FRED attribution apply.

### swap-line

[FRED SWPT](https://fred.stlouisfed.org/series/SWPT): Board H.4.1 central-bank
liquidity swaps, Wednesday outstanding stock, NSA, millions unchanged, not weekly
new operations. H.4.1 timing/revision rules and Board/FRED attribution apply.

### fima-repo

[FRED H41RESPPALGTRFNWW](https://fred.stlouisfed.org/series/H41RESPPALGTRFNWW):
Board H.4.1 foreign-official repurchase agreements, Wednesday stock, NSA, millions
unchanged. FRED labels the frequency **Weekly, Ending Wednesday**, unlike WALCL's
“As of” label. Preserve earlier provider zeroes; they do not imply today's facility
existed throughout the history. Credit Board and FRED.

### bank-loans

[FRED TOTLL](https://fred.stlouisfed.org/series/TOTLL): Board H.8 loans and leases
in bank credit at all commercial banks, weekly ending Wednesday, **SA**, billions
unchanged. Broader than C&I loans alone. H.8 release lag, seasonal/benchmark revisions,
and Board/FRED attribution apply.

### lending-standards

[FRED DRTSCILM](https://fred.stlouisfed.org/series/DRTSCILM): SLOOS domestic banks'
net percentage tightening C&I standards for large/middle-market firms, quarterly,
NSA, percent unchanged. Negative values mean net easing. FRED dates are quarter
starts, not availability dates; do not use this history as a point-in-time signal.
Compare previous quarter and same quarter last year. Credit Board and FRED.
The [history table](https://fred.stlouisfed.org/data/DRTSCILM) independently confirms
2010-01-01 = -5.5 and quarter-start labeling.

### treasury-yield-chg

[FRED DGS10](https://fred.stlouisfed.org/series/DGS10): Board H.15 daily ten-year
constant-maturity Treasury yield, NSA, original provider units percent. Explicitly
request [`units=chg`](https://fred.stlouisfed.org/docs/api/fred/series_observations.html#units),
then multiply the returned percentage-point difference by 100 once to bp. Do not
re-difference or bridge missing source periods locally. For November 13, 2026,
5.15 − 5.10 = 0.05 percentage points, normalized to 5 bp. The input stays hidden
while price impact remains undefined. Credit Board and FRED and disclose transform.

### credit-spreads-ig

[FRED BAMLC0A0CM](https://fred.stlouisfed.org/series/BAMLC0A0CM): ICE BofA US
Corporate Index option-adjusted spread, daily close, NSA, percent unchanged. This is
an index OAS, not a single-bond spread or a Treasury yield difference. FRED publishes
a **rolling three-year window** (currently 2023-11-20 onward), so the collector
accepts an inception later than the 2010 request window while still rejecting any
history starting before the declared source start. Month-end observations may fall
on weekends (for example 2024-03-31); preserve those source calendar dates without
a weekday rule, resampling, interpolation or vintage reconstruction. ICE Data
Indices, LLC data; cite ICE and FRED. The maintainer confirmed redistribution
permission on November 18, 2026.

### credit-spreads-hy

[FRED BAMLH0A0HYM2](https://fred.stlouisfed.org/series/BAMLH0A0HYM2): ICE BofA US
High Yield Index option-adjusted spread, daily close, NSA, percent unchanged. Same
rolling three-year window, weekend month-end dates, missing markers and attribution
as the investment-grade series above. High-yield OAS is not comparable in level to
the investment-grade OAS and the two series are not combined.

## Manual issuance sources

### bond-issuance

### treasury-bond-issuance

### corporate-bond-issuance

The maintainer confirmed public redistribution permission and the following
measurement definitions on November 17: **monthly, all maturities, gross issuance**;
Treasury and corporate are included in total. Definitions are maintainer-confirmed,
not independently certified instrument descriptions. The source is
[SIFMA US Fixed Income Securities Statistics](https://www.sifma.org/research/statistics/us-fixed-income-securities-statistics),
supplied through `data/sources/wind/bond-issuance.xlsx`, sheet `bond-issuance`.
The workbook's embedded Wind EDB metadata identifies:

| Registry ID | Wind ID | Workbook column | January 2011 | October 2026 |
| --- | --- | --- | ---: | ---: |
| bond-issuance | G1132499 | B | 597.6 | 773.423182 |
| treasury-bond-issuance | G1132494 | C | 181.7 | 160.826448 |
| corporate-bond-issuance | G1132496 | D | 145.4 | 139.83131 |

Values are USD billions, unchanged. Each file has 190 calendar-month-end rows,
January 2011–October 2026. The saved workbook and exported CSVs agree for every row.
The total's January–October 2026 sum is 10,312.509128 billion, matching SIFMA's
published 10,312.5 billion after rounding. This reconciles the aggregate but does
not independently verify every component, maturity boundary or historical revision.
The three charts are overlapping views; never sum all three.

The workbook has a blank-to-zero export setting, but all 570 current observations
are strictly positive: there are no saved zero/blank observations to reinterpret.
For subsequent refreshes, configure Wind to preserve source missing values as
blanks and verify units/definitions before exporting. The importer preserves blanks
as null and accepts real zeroes; it cannot recover missingness already lost upstream.
Do not execute the embedded Wind formula or rewrite workbook metadata in Python.

Manual input corrections, nulling and removals require the existing commit reason
format. Registry definitions and input CSVs must be committed before assembly;
working-tree definitions cannot silently replace the audited committed specification.
Credit SIFMA and Wind, with the permission confirmation recorded here. This
confirmation does not extend to Cboe data; the separate ICE confirmation covers
only the two ICE BofA OAS series.

## Deferred sources and maintainer follow-up

- **VIX:** explicit maintainer decision to leave inactive.
  [VIX](https://fred.stlouisfed.org/series/VIXCLS) is Cboe copyrighted daily-close
  index data; technical availability through FRED is not treated as permission.
- **iFind dollar index/MOVE:** permission confirmed, but identifiable source series,
  instrument definitions, observation units/dates, adjustment conventions and input
  files remain missing. Supply original export descriptions or table references;
  a provider name alone cannot identify a measure.
- **Treasury bid–ask:** deferred at the maintainer's request; no source substitution.
- **Price impact/FINRA:** still need instrument coverage, volume units, matched dates,
  signed versus absolute yield change and a defensible proxy interpretation.
- Cross-currency basis, CDS, ETFs, depth, positioning and leverage stay unavailable.

## Live collection and acceptance

A complete live refresh on November 17 validated the 15 then-active automatic
inputs. The existing four pilot histories were unchanged; the eleven new sources
were fetched successfully. All were current under their source-specific freshness allowances.
The table below records source-scale samples, including missing observations in
counts. Latest samples were reconciled with the linked FRED series pages above.

| New automatic source | Count | First date/value | Latest date/value |
| --- | ---: | --- | --- |
| bank-loans | 879 | 2010-01-06 / 6412.7555 | 2026-11-04 / 14234.6714 |
| bank-total-assets | 879 | 2010-01-06 / 11660.9993 | 2026-11-04 / 26180.6879 |
| discount-window | 880 | 2010-01-06 / 19143.0 | 2026-11-11 / 9268.0 |
| fima-repo | 880 | 2010-01-06 / 0.0 | 2026-11-11 / 0.0 |
| lending-standards | 68 | 2010-01-01 / -5.5 | 2026-10-01 / 1.7 |
| reserve-balances | 880 | 2010-01-06 / 1021324.0 | 2026-11-11 / 2969977.0 |
| reverse-repo | 4402 | 2010-01-01 / null | 2026-11-16 / 0.182 |
| sofr99 | 2249 | 2018-04-03 / 2.0 | 2026-11-13 / 3.97 |
| swap-line | 880 | 2010-01-06 / 10272.0 | 2026-11-11 / 171.0 |
| treasury-account | 880 | 2010-01-06 / 166555.0 | 2026-11-11 / 912134.0 |
| treasury-yield-chg | 4401 | 2010-01-01 / null | 2026-11-13 / 0.05 |

Acceptance completed November 17: 123 Python tests and 27 JavaScript checks passed
(10 demo, 8 preview, 9 production). Regression coverage includes SA metadata drift,
Wednesday conventions, quarterly negative/zero/null values and freshness, Treasury
`chg` scaling, tail-spread missing inputs, inactive-source gates, and manual
addition/correction/removal publication. Existing pilot policy-version-4 snapshot
bytes validate under the expanded reader for rollback.

A disposable clone with the real saved inputs assembled 21 active series and 16
numeric charts, then published to a **local bare Git remote**, building/stamping
artifact `eeac5d3f1085ccc75a14266b27a184aa0355e6f5`. This hash belongs only to the
local rehearsal, not GitHub. Public artifact membership validation passed. Desktop
Chrome confirmed quarterly and monthly charts, native comparison labels, expanded
source explanations and Escape handling. Page methodology now covers mixed sources.
Mobile polish and hosted deployment/rollback remain deferred or pending as recorded
in the development plan. Demo observations, the Wind workbook and manual CSVs are
unchanged; only automatic candidates were refreshed in the source checkout.

### ICE credit spread activation (November 18)

A targeted collection fetched both ICE inputs without touching the other stored
histories. Each returned 792 daily observations spanning 2023-11-20 to 2026-11-16,
including eleven weekend month-end dates and the provider's missing markers
(IG 9, HY 8). Both were current under the 7-day daily freshness allowance and
normalize as identity percentages. The assembled policy-version-6 snapshot contains
23 active series and 18 numeric charts. Python and JavaScript checks cover the
three-year inception, weekend source dates, NSA metadata rejection and the required
ICE notice.
