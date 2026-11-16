# Pilot source review

Reviewed November 16, 2026 against the linked primary sources. This review completes
Slice 1 specifications, not collection or release certification. `data/registry.csv`
owns source identity and units. `data/source-reviews.json` records a hash of the
reviewed scientific fields, date rule, and Chinese explanation. A changed source,
unit, formula, frequency, or measurement note requires a new review and hash; a
display rename does not. Do not update hashes just to silence a validation failure.

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

**Confirmed with the maintainer November 16, 2026:** daily total accepted overnight
repo amounts. The chart name now makes the overnight accepted-amount definition
explicit. This is a project aggregation of published operation results.

- Select **Repo**, **Overnight** results, including small-value exercises. Exclude
  term repos, reverse repos and FIMA. Use the provider's Overnight classification;
  Friday-to-Monday maturity does not turn an overnight operation into a term repo.
- For each New York operation date, sum accepted amounts across every reported
  session and Treasury/agency/MBS collateral types. Count each operation once;
  never add a total to its own collateral breakdown. Do not net maturing operations.
- Manual input reads the website's **billions of USD** display and stores that
  same unit. A future API exporting dollars requires a separately reviewed adapter.
  Do not silently reuse this input-scale assumption for such an API.
- `date` is the displayed operation date in New York, not maturity date or UTC
  import date. `publication_date` is the result's publication date; record the
  observed date rather than inventing an exact release timestamp. Results follow
  the operation's completion; wait for all sessions before entering a daily total.
- A reported zero is zero. An incomplete day's results are null, not a partial
  sum. No result/no operation is not evidence of zero. Do not add weekends or
  holidays. Keep a date-filtered result reference identifying the sessions used
  (plain-text date/session context alongside the public source URL is sufficient).
- Manual history starts with the first verified imported date, not a claimed
  continuous archive. Historical backfill needs the same session and unit checks.
  Corrections retain their source references and correction notes in Git.

Evidence: [operation results](https://www.newyorkfed.org/markets/desk-operations/repo),
[dashboard with units and sessions](https://www.newyorkfed.org/markets/data-hub),
[operation FAQ](https://www.newyorkfed.org/markets/repo-agreement-ops-faq).
As a source-scale spot check, the November 13, 2026 dashboard showed zero accepted
for all three collateral types in both sessions: daily total 0 billion. This review
does not create a production observation or fabricate a historical sample.

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
`ACTIVE_SERIES` and `IMPLEMENTATIONS` are empty until the importer/collector and
normalization/calculation paths exist. `--check-activation` intentionally fails
in Slice 1. Later slices must register real callables, select all dependencies,
and pass activation validation before assembly. No reviewed entry automatically
starts collecting. The `.env` key is not read or needed in this slice.

Slice 3 must compare live provider IDs, frequency, source units, and adjustment
metadata with this review, retrieve complete histories with count checks, and
reconcile sample values before enabling an automatic source. Freshness diagnostics
must account for the above release conventions and source calendars, rather than
treating holidays as missing observations. Production publication remains gated
on Slices 2–5, including source notices, browser checks, and rollback verification.
