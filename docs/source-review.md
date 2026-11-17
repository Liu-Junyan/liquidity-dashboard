# Pilot source review

Reviewed November 16, 2026 against the linked primary sources. This review completes
Slice 1 specifications, not collection or release certification. `data/registry.csv`
owns source identity and units. `data/source-reviews.json` records a hash of the
reviewed scientific fields, date rule, and Chinese explanation. A changed source,
unit, formula, frequency, or measurement note requires a new review and hash; a
display rename does not. Do not update hashes just to silence a validation failure.

Collection-window update, November 17, 2026: all FRED downloads now request
`2010-01-01` onward in one observations response. Historical inception dates below
describe the provider's coverage, not necessarily the first stored observation.
This changes the download window, not source definitions or measurement units.

## fed-assets

- **Identity:** FRED `WALCL`, Federal Reserve Board H.4.1 consolidated Reserve Bank
  assets after eliminations. Wednesday stock, not weekly average; not seasonally
  adjusted. FRED input is millions of USD; divide by 1,000 into billions.
- **Dates/history:** preserve Wednesday observation dates. The reviewed FRED history
  starts December 18, 2002. The Board normally releases H.4.1 Thursday around
  16:30 Eastern; holidays can shift publication. FRED ingestion can follow later.
- **Revisions:** refetch the full available history in Slice 3; archive captured
  revisions through Git. Current observations are not historical publication vintages.
- **Redistribution:** FRED identifies this Board series as public domain with
  citation requested. Credit the Board, H.4.1, and FRED, with retrieval date.

Evidence: [series metadata](https://fred.stlouisfed.org/series/WALCL),
[history](https://fred.stlouisfed.org/data/WALCL),
[H.4.1 release description](https://www.federalreserve.gov/releases/h41/about.htm).

## sofr

- **Identity:** FRED `SOFR`; New York Fed secured overnight Treasury repo financing
  rate, a volume-weighted median. Coverage includes tri-party, GCF and eligible
  FICC-cleared bilateral transactions; special collateral treatment follows the
  administrator's methodology. Percent, daily, not seasonally adjusted; identity conversion.
- **Dates/history:** FRED history begins April 3, 2018. Retain the underlying
  transaction date, not the next business day's publication date. Publication is
  approximately 08:00 Eastern; FRED's check time is not the release time.
- **Revisions:** the administrator describes same-day corrections around 14:30
  Eastern and methodology/contingency policies. Refetch history; preserve provider
  missing markers as null, including holiday markers. Never fill absent dates.
- **Redistribution:** copyrighted reference-rate data; citation and the New York
  Fed's reference-rate notices apply, including to related information/derivations.

Evidence: [FRED metadata](https://fred.stlouisfed.org/series/SOFR),
[history](https://fred.stlouisfed.org/data/SOFR),
[administrator](https://www.newyorkfed.org/markets/reference-rates/sofr),
[methodology and revisions](https://www.newyorkfed.org/markets/reference-rates/additional-information-about-reference-rates).

## effr

- **Identity:** FRED `EFFR`; unsecured overnight federal funds rate. The current
  method uses a volume-weighted median of FR 2420 transactions. The source records
  a March 1, 2016 methodology/publication change; do not describe the entire history
  as having an unchanged methodology. Percent, daily, not seasonally adjusted;
  identity conversion.
- **Dates/history:** FRED history begins July 3, 2000. Observation date is the
  transaction date; next-business-day publication is approximately 09:00 Eastern.
- **Revisions:** same-day correction policy with extraordinary exceptions; collect
  full history and retain explicit missing values, independently of SOFR coverage.
- **Redistribution:** the same reference-rate attribution and notice requirements
  as SOFR apply.

Evidence: [FRED metadata](https://fred.stlouisfed.org/series/EFFR),
[history](https://fred.stlouisfed.org/data/EFFR),
[administrator](https://www.newyorkfed.org/markets/reference-rates/effr),
[methodology and revisions](https://www.newyorkfed.org/markets/reference-rates/additional-information-about-reference-rates).

## sofr-effr-spread

Project calculation: same-date normalized SOFR minus EFFR. Use the union of input
observation dates, producing null wherever either input is missing or null. No
forward-fill, nearest-date joins, or resampling. The earliest numeric result can
only occur within the inputs' overlapping history. Input revisions require
recalculation. Output retains the registry `%` label but is a **percentage-point
difference**: 4.10 − 4.00 = 0.10, not 10. Provenance must identify both normalized
input hashes. Explain that secured and unsecured market populations differ; the
spread is contextual information, not a pure credit-risk measure.

## fed-repo

**Source changed November 16, 2026 at the maintainer's request:** use automatic
FRED `RPONTTLD` instead of manually aggregating NY Fed results. This replaces
the interim Treasury-only selection with the provider's overnight total across
**Treasury securities, federal agency debt, and agency MBS**. The chart name
now states that it is a total. The release is NY Fed Temporary Open Market
Operations, not the Board's H.4.1 balance-sheet release.

- **Identity/units:** NY Fed temporary open-market repo transactions, aggregated
  daily by FRED; daily, not seasonally adjusted, already billions of USD. Request
  `units=lin` and use identity normalization. Do not divide by 1,000 or add the
  collateral component series to this total. Coverage is overnight operations;
  term repo transactions are outside this series.
- **Dates/history:** preserve FRED observation dates and missing markers. The
  history table starts January 3, 2000. Observation dates are distinct from FRED
  update timestamps; do not invent an intraday publication guarantee. Slice 3
  must establish a freshness policy from live release checks before activation.
- **Revisions/missing values:** retrieve full history in Slice 3 and retain
  captured revisions in Git. Preserve reported zeroes; `.` becomes null. Do not
  infer zero from an absent date or fill weekends/holidays. This measures daily
  transactions, not outstanding balances.
- **Redistribution:** FRED marks the series copyrighted with citation required.
  Attribute NY Fed as source and FRED as distributor; recheck applicable terms
  before publication.

Evidence: [canonical metadata](https://fred.stlouisfed.org/series/RPONTTLD),
[history](https://fred.stlouisfed.org/data/RPONTTLD).
The history table reports 8.990 billion on January 3, 2000; the series page shows
0.001 on November 12, 2026, zero on November 13, and missing on November 11.
These are reconciliation examples, not imported production observations. No
manual history was imported, so there is no stored history to migrate or splice.

## Public presentation requirements

The [New York Fed terms](https://www.newyorkfed.org/privacy/termsofuse) permit use
subject to their conditions, with additional requirements for reference rates.
Attribute the original source and title, identify project transformations, and
avoid implying endorsement. Before Slice 5 publication, Slice 4 must include the
specified reference-rate republication notice and non-affiliation disclaimer,
completed with this project's publisher name, prominently with the relevant
presentation. Preserve the applicable SOFR third-party-data notice. The terms
page supplies the exact wording; these notes summarize obligations rather than
replace that wording. Cite FRED as distributor for FRED-fetched data. Repo results
remain subject to the general content conditions. Recheck terms before release.

## Definitions intentionally not activated

The reserve/assets formula now reads `100 * reserve-balances / bank-total-assets`
and consumes normalized billions. [WRBWFRBL](https://fred.stlouisfed.org/series/WRBWFRBL)
is an unadjusted H.4.1 reserve-balances measure; the existing
[TLAACBW027SBOG](https://fred.stlouisfed.org/series/TLAACBW027SBOG) denominator is a
seasonally adjusted H.8 commercial-bank asset measure. Their labels describe
different populations and seasonal treatments. The ratio is not yet certified as
a matched-population balance-sheet share. Resolve and disclose that limitation
before activation; the existing bank-assets mapping is preserved.

The updated daily ON RRP definition is preserved. The Treasury change request is
explicitly `chg`, with `%` → `bp` scaling once, as specified by
[FRED's observation API](https://fred.stlouisfed.org/docs/api/fred/series_observations.html).
Neither that source nor reserve/assets is activated by this review.

## Implementation and release gates

`python3 scripts/policies.py` validates the five pilot definitions without network
access or credentials. `ready` still permits incomplete nonpilot registry entries.
`ACTIVE_SERIES` remains empty. Slice 3 registers executable collector,
normalization, and calculation paths; `--check-activation` now passes offline.
Assembly must select all dependencies and pass activation validation. No reviewed
entry automatically starts collecting. Only the explicit `scripts/collect.py`
command reads the environment/local `.env` key and makes FRED requests.

Slice 3 compares live provider IDs, frequency, source units, and adjustment
metadata with this review and retrieves the full 2010-onward window with count/bounds
checks. Conservative freshness diagnostics allow 14 calendar days for WALCL and
7 for each daily source, using the latest numeric date. They tolerate normal
release lags/holidays, warn without rejecting complete histories, and do not infer
missing dates or fill values. These are research-refresh thresholds, not precise
release-calendar checks. Production publication remains gated on Slices 4–5,
including source notices, browser checks, and rollback verification.

## Slice 3 live reconciliation

On November 17, 2026, `python3 scripts/collect.py` downloaded and validated the
following full histories before the 2010 cutoff was introduced. Counts include explicit missing observations. History
bounds and first observations were compared with the public FRED tables linked
below; this is sample reconciliation, not an independent audit of every value.

| Source | Count | First date / source-scale value | Last date |
| --- | ---: | --- | --- |
| [WALCL](https://fred.stlouisfed.org/data/WALCL) | 1,248 | 2002-12-18 / 719,542 million USD | 2026-11-11 |
| [SOFR](https://fred.stlouisfed.org/data/SOFR) | 2,249 | 2018-04-03 / 1.83% | 2026-11-13 |
| [EFFR](https://fred.stlouisfed.org/data/EFFR) | 6,880 | 2000-07-03 / 7.03% | 2026-11-13 |
| [RPONTTLD](https://fred.stlouisfed.org/data/RPONTTLD) | 7,011 | 2000-01-03 / 8.990 billion USD | 2026-11-16 |

WALCL's first normalized value is 719.542 billion USD. RPONTTLD remains in
billions. SOFR−EFFR was recomputed over 6,880 union dates, with nulls outside
same-date numeric overlap. A second live full refresh returned `unchanged` for
all four sources, preserving values and change times while advancing successful
check times. Offline tests additionally verify revision/removal propagation and
partial-failure retention. These candidate files do not activate production or
replace any demo/preview website data.

After applying the shared 2010 cutoff, another live refresh saved 880 WALCL,
2,249 SOFR, 4,401 EFFR, and 4,402 RPONTTLD observations. SOFR's later inception
was preserved. The refresh removed only pre-2010 observations; all overlapping
values were unchanged. The original metadata inception dates remain in the
input files, alongside `requestParameters.observation_start: "2010-01-01"`.
