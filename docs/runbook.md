# Operational runbook

Run commands from a full Git checkout on macOS or Linux. Use Python 3.10+ and Node 22+ for the offline checks. CI uses Python 3.12 and Node 22. Install the workbook reader in your Python environment with `python3 -m pip install -r requirements.txt`. The static frontend has no npm installation step.

## Build and check locally

| Task | Command |
| --- | --- |
| Preview the committed production snapshot | `python3 scripts/build.py --mode production` |
| Reassemble from saved FRED inputs and committed manual CSVs | `python3 scripts/assemble.py`, then `python3 scripts/build.py --mode production` |
| Build synthetic demo data | `python3 scripts/build.py --mode demo` |
| Run registry and activation checks, manual audit, Python and JavaScript tests, and both builds | `python3 scripts/check.py` |
| Serve the current build | `python3 -m http.server 8000 --bind 127.0.0.1 --directory dist`, then open <http://127.0.0.1:8000/> |

Assembly writes the tracked `data/snapshot/`. For a local experiment, use `assemble.py --output <directory>` with a dedicated directory outside the repo, then pass it to `build.py --mode production --snapshot <directory>`. The destination may be new, empty, or contain exactly three regular files named `catalog.json`, `observations.json`, and `manifest.json`. Use a path without symlinks, including its parent directories and snapshot files. Run one local build or assembly at a time and keep the destination free of other writers during assembly.

## Update FRED

Set `FRED_API_KEY` in the environment or the ignored local `.env`. Run `python3 scripts/collect.py` for a full refresh, or `python3 scripts/collect.py --series fed-assets` for one source. Inspect the collection outcomes and changes in `data/automatic/`, then assemble and build to preview. The local collection command exits nonzero for a retained or failed source, even if other sources updated. Compare the last attempt, last successful check, and last data change in the saved record. A compatible previous history can be retained on a failed request. A first-time failure has an empty history. An incompatible saved source requires a successful fetch. The Actions summary reports failures and freshness by series. [Source conventions](data-sources.md#automatic-inputs-from-fred)

## Update Wind and SIFMA

1. Pull the latest workbook, refresh it in Excel with Wind, preserve missing values as blanks, then save and close it. The versioned source is [Wind-data.xlsx](../data/sources/wind/Wind-data.xlsx). On `bond-issuance`, B1 is `Billions $`, row 2 contains the three registry IDs, and column A contains month-end dates. On `market`, row 2 contains `MOVE` and `USDX` alongside the date column. A market value of Excel `#N/A` exports as blank.
2. Run the following commands. The first validates the cached workbook values. The second exports all five CSVs. Check the date ranges, values, and changes against the workbook. CSVs have exactly `date,value`, with sorted unique ISO dates and finite source-scale values. Blank and zero have distinct meanings.

   ```sh
   python3 scripts/export_wind_issuance.py --check
   python3 scripts/export_wind_issuance.py
   git diff -- data/manual/
   ```

3. Prepare the commit message in a file such as `/tmp/manual-commit.txt`. New dates need only a normal commit message. For corrections, nulling, or removals, include a reason covering each affected date. For example:

   ```text
   Refresh Wind issuance histories

   Manual-Reason: bond-issuance 2026-09-30: SIFMA revised the September total
   ```

   Use `YYYY-MM-DD..YYYY-MM-DD` for an inclusive range. The audit requires full Git history. If a shallow checkout fails the baseline check, fetch its history with `git fetch --unshallow`. The audit compares each commit with its first parent. Preserve applicable reason lines in merge or squash messages.

4. Validate the working tree, stage the workbook and exports together, and commit with the same message. Then assemble and preview from the committed inputs.

   ```sh
   python3 scripts/import_manual.py --working-tree --message-file /tmp/manual-commit.txt
   git add -- data/sources/wind/Wind-data.xlsx data/manual/
   git commit -F /tmp/manual-commit.txt
   python3 scripts/check.py
   ```

5. Inspect the edited date and value in `dist/data/observations.json` under `series[<indicator-id>]`. For a new numeric observation, also verify the chart’s latest date and value. Push the input commit through the usual default-branch workflow. After deployment, check the same observation in the Pages copy of `data/observations.json` and match its snapshot ID to `data/release.json`.

## Publish and verify

Select **GitHub Actions** as the Pages source and configure the repository secret `FRED_API_KEY` for refreshes. For manual runs, open **Actions → Build and deploy dashboard → Run workflow** on `main`. [Workflow definition](../.github/workflows/pages.yml)

| Trigger or mode | What happens |
| --- | --- |
| Pull request | Runs offline checks on the PR head. |
| Push to `main` or manual `publish` | Uses saved inputs. Suitable for manual CSV or frontend changes and deployment retries. |
| Daily schedule or manual `refresh` | Collects FRED and publishes. Scheduled for 07:17 UTC (15:17 Asia/Shanghai). The run may start later. |
| Manual `rollback` | Takes a full artifact commit SHA and attempts to restore its data using current code. |

The job starts from the latest default branch under a single publication lock. It retries assembly when the branch advances, fast-forwards the artifact commit, and skips deployment if a newer commit supersedes the candidate before the final check. `DATA_UPDATE_DELIVERY` selects `direct` (push required), `pull-request` (merge the data PR to deploy), or the default `auto` (try a direct push, then a PR if the push fails and the branch head is unchanged). PR creation requires the repository’s Actions permission to create pull requests. Check branch rules before changing delivery.

For each release, inspect the Actions summary for source outcomes, freshness, artifact SHA, and the Pages deployment result. On the Pages URL, open `data/release.json` and match `artifactCommit` to the successful run and `snapshotId` to the served catalog and observations. A data PR awaits merge and a subsequent default-branch run. [Artifact fields](architecture.md#snapshot-and-release-identity)

## Recover a release

- **Pages failed after the artifact commit.** Run `publish` to retry from saved inputs. If the audit or contract failed before a commit, resolve the reported input, correction reason, or source-definition mismatch and rerun the offline checks.
- **FRED refresh failed.** Inspect the per-source outcomes and last successful check. Correct the key or source compatibility issue before rerunning `refresh`. Use `publish` when you intend to deploy the saved inputs.
- **Restore earlier data.** Find the full 40-character artifact SHA from a successful run on `main`. Select `rollback` and enter it in `rollback_commit`. The job restores the archived automatic inputs and snapshot, validates them with current code, and publishes a new artifact. Verify the target SHA in `restoredFrom` and the original snapshot ID. The next scheduled refresh resumes collection. A frontend regression needs a code revert.
- **Historical rollback fails validation.** Current derivation rules reject some older artifacts, including `7f8c7c9`. A rejected candidate leaves the existing Pages deployment in place. Use a verified compatible artifact for data recovery. Redeploying historical code with matching data is a proposed change tracked below.

## Maintenance tracker

The November 25 review used source revision `9615481` and data revision `e82660d`. Check off an entry after its acceptance check passes and record the fixing revision when available.

- [x] **01 · High · Protect snapshot destinations.** Assembly rejects symlinked paths, partial snapshots, and unexpected entries before replacement. CLI regression tests verify that rejected destinations retain their entries, file contents, and symlink targets and that assembly succeeds for new, empty, and existing snapshot directories. [CLI](../scripts/assemble.py) · [Promotion](../scripts/artifacts.py) · [Tests](../tests/test_assemble.py)
- [ ] **02 · High · Restore a real historical release.** Artifact `7f8c7c9` contains 4,401 SOFR–EFFR rows where current calculation rules produce 2,249. Prefer recovery with matching code and data, or implement the historical policies required by current-frontend recovery. Rehearse that artifact, verify its snapshot ID and observation bytes, load the dashboard, and exercise the following publish. [Release logic](../scripts/release.py) · [Rollback tests](../tests/test_publish.py)
- [ ] **03 · Medium · Reduce manual audit work.** One audit took 5.6 seconds for 61 first-parent commits, only two of which changed manual CSVs. Audit relevant manual and registry changes and reuse the result during assembly. Match the existing audit at `e82660d`, skip CSV parsing for an automatic-only commit, and ensure a later revert cannot hide a correction lacking its reason. [Importer](../scripts/import_manual.py)
- [ ] **04 · Medium · Use one revision-count baseline.** The manifest reported 9,385 additions by combining 9,378 historical manual additions with seven from the latest automatic collection. Compare both input types with the previous release and document the initial baseline. Verify that one append and one correction count once each and that republishing identical inputs reports zero changes. [Assembler](../scripts/assemble.py)
- [ ] **05 · Build production once per candidate.** The check runner builds production and the publisher builds it again after the commit. Stamp the checked output and verify byte equality and the public allowlist. A rehearsal should show one production build, the correct artifact SHA, and the checked snapshot bytes in the Pages artifact. [Check runner](../scripts/check.py) · [Publisher](../scripts/publish.py)
- [ ] **06 · Choose one delivery method.** An ordinary push error in automatic mode can open a data PR. Confirm branch rules, select direct fast-forward pushes or PR delivery, and remove the unused path and permissions. Rehearse a refresh, saved-input publish, and concurrent maintainer push. Verify that competing edits survive and rejected writes report the cause. [Pages workflow](../.github/workflows/pages.yml) · [Publisher](../scripts/publish.py)
- [x] **07 · Correct the issuance update instructions.** The former runbook described active SIFMA charts as pending. The procedure above now covers workbook export, manual correction reasons, publication, and verification. An offline workbook rehearsal produced the sample total of 800.25 billion for November 30, 2026 in the built observations and passed all 13 production JavaScript checks. Revisit delivery and recovery wording when 02 and 06 are resolved. [Wind update procedure](#update-wind-and-sifma)
- [x] **08 · Isolate the issuance test from changing production dates.** The publication test now seeds its temporary repository with a fixed January 2020 issuance observation and exercises the February update. The full offline checks passed with source CSVs ending in October, November, and December 2026, including documented corrections and removals and rejection of an undocumented edit. [Publication test](../tests/test_publish.py)
