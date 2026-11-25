# Dashboard maintenance handoff

The November 25, 2026 review found two issues worth fixing first. Snapshot assembly can erase unrelated files, and recovery can fail for a published snapshot covered by the documented rollback policy. The remaining entries cover data diagnostics and the cost of operating the dashboard solo.

The review inspected source at `9615481` and tested the subsequent data-only revision `e82660d` in an isolated clone. All 121 Python tests and 23 JavaScript checks passed there. The rollback rehearsal used local Git history. GitHub branch rules and live Pages recovery still need separate verification.

Each checkbox tracks one finding. Check it when its acceptance criteria pass and append the fixing commit or PR beside the heading.

## Correctness and recovery

- [ ] **01 · High · Protect existing files at the snapshot destination**

  **Evidence.** Running `assemble.py --output` against a temporary directory containing an unrelated marker file succeeded. Only the three snapshot JSON files survived. The CLI accepts external directories, and promotion exchanges the whole directory with staging. Cleanup then removes the original contents. [Assembly CLI](../scripts/assemble.py) · [Directory promotion](../scripts/artifacts.py)

  **Suggested fix.** Validate the destination before promotion. Accept a new directory, an empty directory, or an existing snapshot containing only the expected regular files. Reject symlinks and directories containing unrelated entries.

  **Acceptance.** A regression test plants a marker beside an existing snapshot, invokes the CLI, and verifies that it fails with every original file intact. A fresh destination and a normal replacement of an existing snapshot both succeed.

- [ ] **02 · High · Make rollback work for a real historical release**

  **Evidence.** On `e82660d`, rollback preparation for `7f8c7c9` (policy version 6) failed with `Displayed history disagrees with normalized inputs/calculation`. The archived SOFR–EFFR series has 4,401 rows including leading nulls. The current derivation produces 2,249. The existing rollback test creates both releases under the same calculation rules. [Release preparation](../scripts/release.py) · [Snapshot validation](../scripts/assemble.py) · [Rollback tests](../tests/test_publish.py)

  **Suggested fix.** For a solo deployment, restore a known-good revision with its matching code and data. If recovery must keep the current frontend, define which historical policies it supports and validate those snapshots with their corresponding calculation rules.

  **Acceptance.** Rehearse the chosen recovery path using the full SHA from `git rev-parse 7f8c7c9`. Verify the restored snapshot ID and observation bytes against that commit, load the dashboard, and exercise the next ordinary publication. Document which code and data the procedure restores.

## Data maintenance

- [ ] **03 · Medium · Avoid replaying unchanged manual inputs on every publish**

  **Evidence.** At `e82660d`, the importer walked 61 first-parent commits. Only two changed `data/manual`. A single full audit took 5.6 seconds locally, and release preparation, assembly, and the check runner each request one. Daily bot commits add work even when every CSV is identical. [Manual importer](../scripts/import_manual.py) · [Release preparation](../scripts/release.py) · [Check runner](../scripts/check.py)

  **Suggested fix.** Process first-parent changes to the manual inputs and their registry definitions. Reuse the resulting audit when assembling the same candidate. Preserve the correction-reason check at each relevant commit, including merges.

  **Acceptance.** Compare the optimized and existing audit results at `e82660d`. Adding an automatic-data-only commit incurs no additional CSV parsing. An intermediate manual correction lacking its reason still fails, even when a later commit reverses it.

- [ ] **04 · Medium · Give revision counts a consistent baseline**

  **Evidence.** The manifest at `e82660d` reports 9,385 additions. It combines 9,378 manual additions accumulated over the repository’s history with seven from the latest automatic collection. Publishing unchanged CSVs counts the manual additions again. [Summary calculation](../scripts/assemble.py) · [Manifest contract](production-contract.md)

  **Suggested fix.** Calculate the release summary against the previous published inputs for both manual and automatic series. Keep the historical manual audit available for tracing individual corrections. Document the baseline for the first publication.

  **Acceptance.** Starting from a published baseline, append one manual observation and revise one automatic observation. The next release reports one addition and one revision. Republishing identical inputs reports zero additions, revisions, and removals.

## Publication workflow

- [ ] **05 · Simplification · Build production once per candidate**

  **Evidence.** The check runner builds production and runs JavaScript checks. The publisher commits the generated data, then builds production a second time before stamping and copying it for Pages. [Check runner](../scripts/check.py) · [Publisher](../scripts/publish.py)

  **Suggested fix.** Carry the checked production directory into the stamping step. Keep the byte comparison against the committed snapshot, the public-file check, and the deployment lock.

  **Acceptance.** A publication rehearsal records one production build per candidate. The artifact commit in `dist/data/release.json` matches the committed revision, and the uploaded catalog, observations, and manifest match the files used for the production checks.

- [ ] **06 · Simplification · Choose one Git delivery path**

  **Evidence.** The workflow supports direct push, pull request, and automatic fallback. In automatic mode, a push failure with an unchanged remote head triggers a data branch and PR attempt. A transient push error can therefore require a manual merge. PR support also adds a write permission and logic for recognizing a merged candidate. [Publisher](../scripts/publish.py) · [Release record reuse](../scripts/release.py) · [Pages workflow](../.github/workflows/pages.yml)

  **Suggested fix.** Confirm the repository’s branch rules. Use direct fast-forward pushes if the automation account may write to the default branch. If the rules require a PR, use PR delivery consistently. Remove the unused path, its configuration, and any permission it alone requires.

  **Acceptance.** Rehearse a scheduled refresh, a saved-input publish, and a competing maintainer push under the selected policy. A concurrent edit survives, a rejected write gives an actionable error, and publication deploys only a validated revision.

- [ ] **07 · Documentation · Update the everyday publication instructions**

  **Evidence.** The runbook says SIFMA issuance is awaiting activation and CSV edits do not create production charts. The README and reviewed production snapshot include all three issuance series. A maintainer following the runbook could overlook a missing update. [Publication runbook](publication.md) · [README](../README.md)

  **Suggested fix.** Replace the obsolete activation note with the current workbook-to-CSV procedure, correction-reason requirement, saved-input publication trigger, and expected chart update. Align the delivery and recovery instructions once items 02 and 06 are settled.

  **Acceptance.** Follow the instructions in a disposable checkout with a sample issuance update. The offline production build shows the expected date and value for the edited series, and the runbook identifies how to verify that observation after publication.
