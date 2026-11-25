# Data-source specification

The registry defines 23 visible indicators. Production activates 26 series: 18 FRED inputs, five manual inputs, and three calculations. Five active inputs serve calculations or research only, leaving 21 active charts. Treasury bid–ask is deferred. Price impact still needs a FINRA volume definition, instrument coverage, matched dates, and a decision on signed versus absolute yield changes. [Registry](../data/registry.csv) · [Active policies](../scripts/policies.py)

## Editing a definition

Keep the UTF-8 CSV header and stable IDs. The 16 columns fall into four groups.

| Fields | Purpose |
| --- | --- |
| `series_id`, `indicator_id`, `category`, `name`, `status` | Stable input and chart identities, layer, Chinese display name, and readiness. Blank category means internal input. Categorized indicators appear in CSV order. `unavailable` hides a row. `unquantified` allows a visible qualitative indicator. |
| `update_method`, `provider`, `source_reference`, `provider_series_id` | Input owner (automatic, manual, or derived), organization, source URL or publication, and provider code. |
| `native_frequency`, `source_unit`, `normalized_unit`, `comparison_rules` | Source cadence, units before and after conversion, and interpretation notes. Executable comparison policies live in Python and the frontend. |
| `input_series_ids`, `formula`, `notes` | Semicolon-separated dependencies, reviewed formula text, and measurement details. Calculations execute named implementations. |

To change a measurement, review the source, conversion, date convention, and redistribution scope. Update the registry, applicable policy or implementation, and the matching review record with its specification hash and explanation. Display-only edits can reuse the existing review. [Review records](../data/source-reviews.json) · [Registry validator](../scripts/registry.py) · [Source notices](../scripts/notices.py)

## Automatic inputs from FRED

Request current history from 2010-01-01 onward, validating metadata and retrieving one complete observations response per series. Keep native observation dates, revisions, and deletions. A provider missing marker becomes null, a reported zero stays zero, and an absent date stays absent. Git retains earlier captures. The series use levels (`lin`) except for the Treasury yield change. Freshness measures days since the latest numeric observation: daily 7, H.4.1 weekly 14, H.8 weekly 21, and quarterly 150. These are diagnostic thresholds. [FRED client](../scripts/providers/fred.py) · [Normalization](../scripts/normalize.py)

| Registry ID | FRED series | Measurement, observation date, and normalized unit |
| --- | --- | --- |
| <a name="fed-assets"></a>`fed-assets` | [WALCL](https://fred.stlouisfed.org/series/WALCL) | Consolidated Reserve Bank assets, Wednesday level. USD millions ÷ 1,000 → billions. |
| <a name="reserve-balances"></a>`reserve-balances` | [WRBWFRBL](https://fred.stlouisfed.org/series/WRBWFRBL) | Reserve balances at Federal Reserve Banks, Wednesday level. USD millions ÷ 1,000 → billions. |
| <a name="treasury-account"></a>`treasury-account` | [WDTGAL](https://fred.stlouisfed.org/series/WDTGAL) | Treasury General Account, Wednesday level. USD millions ÷ 1,000 → billions. |
| <a name="discount-window"></a>`discount-window` | [WLCFLPCL](https://fred.stlouisfed.org/series/WLCFLPCL) | Primary credit outstanding, Wednesday level, USD millions. |
| <a name="swap-line"></a>`swap-line` | [SWPT](https://fred.stlouisfed.org/series/SWPT) | Central-bank liquidity swaps outstanding, Wednesday level, USD millions. |
| <a name="fima-repo"></a>`fima-repo` | [H41RESPPALGTRFNWW](https://fred.stlouisfed.org/series/H41RESPPALGTRFNWW) | Foreign-official repos outstanding, week ending Wednesday, USD millions. Historical zeroes are retained. |
| <a name="bank-total-assets"></a>`bank-total-assets` | [TLAACBW027SBOG](https://fred.stlouisfed.org/series/TLAACBW027SBOG) | All commercial banks’ assets, week ending Wednesday, seasonally adjusted, USD billions. Internal denominator. |
| <a name="bank-loans"></a>`bank-loans` | [TOTLL](https://fred.stlouisfed.org/series/TOTLL) | All commercial banks’ loans and leases in bank credit, week ending Wednesday, seasonally adjusted, USD billions. |
| <a name="lending-standards"></a>`lending-standards` | [DRTSCILM](https://fred.stlouisfed.org/series/DRTSCILM) | Net percentage of domestic banks tightening C&I standards for large and middle-market firms. Negative values indicate easing. Quarter-start date labels the survey period. |
| <a name="sofr"></a>`sofr` | [SOFR](https://fred.stlouisfed.org/series/SOFR) | Secured overnight Treasury financing rate, volume-weighted median, transaction date, %. Internal input. |
| <a name="effr"></a>`effr` | [EFFR](https://fred.stlouisfed.org/series/EFFR) | Effective federal funds rate, unsecured overnight market, transaction date, %. Internal input. The current volume-weighted median methodology began in 2016. |
| <a name="sofr99"></a>`sofr99` | [SOFR99](https://fred.stlouisfed.org/series/SOFR99) | 99th percentile of the SOFR transaction distribution, transaction date, %. Internal input. |
| <a name="fed-repo"></a>`fed-repo` | [RPONTTLD](https://fred.stlouisfed.org/series/RPONTTLD) | Total daily overnight repo transactions across Treasury, agency debt, and agency MBS collateral, USD billions. |
| <a name="reverse-repo"></a>`reverse-repo` | [RRPONTSYD](https://fred.stlouisfed.org/series/RRPONTSYD) | Daily overnight reverse-repo transactions against Treasury collateral, USD billions. |
| <a name="treasury-yield-chg"></a>`treasury-yield-chg` | [DGS10](https://fred.stlouisfed.org/series/DGS10) | Internal 10-year yield change. Request FRED `units=chg`, then multiply the percentage-point result by 100 once for bp. |
| <a name="credit-spreads-ig"></a>`credit-spreads-ig` | [BAMLC0A0CM](https://fred.stlouisfed.org/series/BAMLC0A0CM) | ICE BofA US Corporate Index option-adjusted spread, daily close, %. |
| <a name="credit-spreads-hy"></a>`credit-spreads-hy` | [BAMLH0A0HYM2](https://fred.stlouisfed.org/series/BAMLH0A0HYM2) | ICE BofA US High Yield Index option-adjusted spread, daily close, %. Both OAS series use FRED’s rolling three-year window and retain weekend month-end observations. |
| <a name="vix"></a>`vix` | [VIXCLS](https://fred.stlouisfed.org/series/VIXCLS) | Cboe near-term S&P 500 implied volatility, daily close, index points. |

All automatic inputs other than the two H.8 series use the reviewed non-seasonally-adjusted convention. Observation dates can precede release dates. Cite the originating organization and FRED. The New York Fed reference rates and related calculations carry the applicable republication, non-affiliation, and SOFR third-party notices. The maintainer recorded ICE OAS and Cboe VIX redistribution permission on 2026-11-18. [NY Fed reference-rate methodology](https://www.newyorkfed.org/markets/reference-rates/additional-information-about-reference-rates) · [NY Fed terms](https://www.newyorkfed.org/privacy/termsofuse) · [Notice text](../scripts/notices.py)

## Manual inputs from Wind

| Registry ID | Wind EDB ID | Saved observation |
| --- | --- | --- |
| <a name="bond-issuance"></a>`bond-issuance` | G1132499 | SIFMA total US fixed-income issuance, USD billions |
| <a name="treasury-bond-issuance"></a>`treasury-bond-issuance` | G1132494 | SIFMA Treasury issuance, USD billions |
| <a name="corporate-bond-issuance"></a>`corporate-bond-issuance` | G1132496 | SIFMA corporate issuance, USD billions |
| <a name="move"></a>`move` | C7536898 | ICE BofA MOVE Index, one-month implied US bond-yield volatility, index points |
| <a name="dollar-index"></a>`dollar-index` | M0000271 | ICE US Dollar Index (USDX), fixed six-currency geometric basket, March 1973 = 100 |

The three issuance measures are monthly gross issuance across all maturities, dated at calendar month-end. Total issuance includes Treasury and corporate issuance. Adding all three double-counts the components. The maintainer confirmed these definitions and public redistribution through Wind on 2026-11-17. Cite SIFMA and Wind. [SIFMA statistics](https://www.sifma.org/research/statistics/us-fixed-income-securities-statistics)

MOVE and USDX retain the Wind observation date and daily level at scale one. The workbook does not specify a sampling time, time zone, or adjustment convention. Credit Wind for observations and ICE for benchmark definitions. On 2026-11-25 the maintainer confirmed Wind permission for public display and downloadable daily history for both codes. [MOVE definition](https://developer.ice.com/fixed-income-data-services/catalog/ice-data-indices-move-index) · [USDX methodology](https://www.ice.com/publicdocs/futures_us/ICE_Dollar_Index_FAQ.pdf)

## Derived indicators and comparisons

| Registry ID | Calculation on normalized inputs | Interpretation |
| --- | --- | --- |
| <a name="sofr-effr-spread"></a>`sofr-effr-spread` | 100 × (SOFR − EFFR), bp | Compares secured and unsecured overnight funding rates. |
| <a name="sofr-tail-spread"></a>`sofr-tail-spread` | 100 × (SOFR99 − SOFR), bp | Distance between the upper tail and median of the SOFR distribution. |
| <a name="reserve-assets-ratio"></a>`reserve-assets-ratio` | 100 × reserve balances / bank total assets, % | H.4.1 reserves are unadjusted and cover a different population from seasonally adjusted H.8 commercial-bank assets. Interpret as a cross-coverage research ratio. A zero denominator yields null. |

Derived history spans the first through last date on which every input has a numeric value. Within that span, a missing input on a date yields a null. Summary comparisons use 4 and 13 calendar weeks for daily and weekly series, 1 and 12 months for monthly series, and 1 and 4 quarters for quarterly series. Weekly and period comparisons require the target source date. Daily comparisons allow the preceding valid observation within seven days when the target date is absent. An explicit null on the target stays missing. [Derivations](../scripts/derive.py) · [Chart calculations](../site/assets/data.js)
