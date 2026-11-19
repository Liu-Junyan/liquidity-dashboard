# Production publication and rollback

Slice 5 implements the pipeline in `.github/workflows/pages.yml`,
`scripts/publish.py`, `scripts/release.py`, and `scripts/check.py`.
The first hosted run and live rollback still need to be observed after this change
reaches `main`. Mobile UI polish is deferred at the maintainer's request.

## Repository setup

The repository is `Liu-Junyan/liquidity-dashboard`; its default branch is `main`.
The maintainer has configured the `FRED_API_KEY` Actions secret and Pages with
**GitHub Actions** as the publishing source. The workflow uses only the built-in
`GITHUB_TOKEN` for Git writes, PR creation and Pages; no personal token is needed.

`DATA_UPDATE_DELIVERY` is an optional repository Actions variable:

| Value | Behavior |
| --- | --- |
| `auto` (default) | Attempt a normal fast-forward push. If it is rejected without a competing branch update, push a data branch and open a PR. |
| `pull-request` | Always propose new data through a PR; publish after merge. |
| `direct` | Require a fast-forward push; fail if branch rules reject it. |

The workflow respects branch rules and never force-pushes. For PR delivery,
**Settings → Actions → General → Workflow permissions → Allow GitHub Actions to
create and approve pull requests** must allow creation. The workflow does not
approve or merge its own PR. If creation is forbidden, the run fails with the
automation branch available for a maintainer to open a PR manually. If branch
rules prohibit all automation branch writes too, repository permissions must be
resolved before publication can proceed.

## Everyday operation

| Trigger | Inputs | Network collection | Publication |
| --- | --- | --- | --- |
| Pull request | PR head, full first-parent history | None; no FRED secret | Offline Python tests, manual audit and demo/production JS checks; no deployment |
| Push to `main` | Latest `main`, including manual edits | None | Validate saved automatic inputs, assemble and publish, or propose a data PR |
| Daily schedule | Latest `main` | FRED refresh | Same assembly and publication path |
| Manual `refresh` | Latest `main` | FRED refresh | Same as scheduled refresh |
| Manual `publish` | Latest `main` | None | Retry publication using saved inputs |
| Manual `rollback` | Earlier artifact commit in `main` history | None | Restore automatic inputs and the exact saved snapshot, validate and publish |

The schedule is `17 7 * * *` UTC, **15:17 Asia/Shanghai**. It is a daily research
refresh, not a promise to match a source release time; GitHub may delay scheduled
runs. For manual runs, open **Actions → Build and deploy dashboard → Run workflow**,
select `main`, and choose the mode. Leave `rollback_commit` empty except for rollback.
Dispatches from other branches cannot publish. If the default branch is renamed,
update the workflow's `push.branches` filter too.

Manual CSV additions need no correction note. Corrections, removed rows, and
nulling an existing value require the existing `Manual-Reason:` commit-message
format. Every input commit is audited, including intermediate changes. Real
SIFMA activation remains Slice 6; its CSV edits are audited but do not create
production charts yet. No FRED request is required to publish a manual edit.

## Artifact identity and races

One `production-pages` job concurrency group covers **collection through Pages
deployment**, with `cancel-in-progress: false`. PR checks have their own group.
GitHub may replace pending runs; each production run fetches the latest branch
after obtaining the lock, so an older queued event cannot republish its event SHA.
See [GitHub concurrency semantics](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency).

The publisher creates a temporary detached worktree from that branch. It audits
inputs, optionally collects, assembles, and runs offline checks. It stages only
`data/automatic/`, `data/snapshot/`, and `data/publication.json`. The automatic
inputs and snapshot enter the same artifact commit. A final production build
uses that clean commit, checks snapshot byte equality, and checks a public-file
allowlist before uploading `dist/` as one Pages artifact.

If `main` advances before the push, discard the candidate and run again from the
new inputs and code (at most three attempts). Pushes are ordinary fast-forwards,
so a race at push also causes reassembly. If `main` advances after our push but
before the final check, skip that deployment. The next default-branch run handles
the newer revision. The lock prevents a newer deployment being overtaken by an
older publication job. A user commit after the final check will be handled by its
queued run; it does not interrupt an in-progress deployment.

`data/publication.json` records the base commit, mode, snapshot ID, optional
rollback target and hashes of all saved automatic/snapshot files. A merged data
PR can deploy its existing artifact without recursively opening another PR.
Any intervening source/manual/UI changes require fresh assembly. Normal artifact
reuse recomputes the snapshot against current inputs. Rollback reuse verifies
exact equality with the chosen historic automatic inputs and snapshot.

The deployed `data/release.json` identifies `artifactCommit`, `sourceInputCommit`,
`snapshotId`, and `restoredFrom`. The artifact SHA is added only after committing;
no commit is required to contain its own hash. Actions summaries show these
identities, per-source outcomes/freshness, collection warnings, and deployment
result. Charts keep their existing observation dates and source notices.

Pushes made with the built-in `GITHUB_TOKEN` do not trigger another push workflow;
publication happens in the same job. Do not replace checkout credentials with a
PAT without reviewing the trigger strategy. GitHub may require a maintainer to
approve checks on a bot-created data PR before merging it. See
[GitHub token-trigger behavior](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow).

## Failures

Fatal input, audit, collection-compatibility, contract or build errors block the
candidate. The current Pages deployment remains intact. An individual FRED failure
can retain compatible history; collection warnings and freshness appear in the
Actions summary. A first-time failed source has no invented history. A missing
API key is a configuration error; use `publish` when an offline retry is intended.

If Git commit succeeds but Pages fails, rerun in `publish` mode to deploy the saved
artifact without recollection. A data PR is not a deployment: merge it and wait
for the default-branch run. Close obsolete unmerged data PRs rather than merging
old candidates after newer updates.

Only the reviewed pilot snapshot, static site assets and release identity are
uploaded. The allowlist rejects extra files and symlinks. `.env`, workbooks,
manual CSVs and raw automatic files are excluded from the Pages artifact.
This does not remove files already tracked in the repository: the existing Wind
workbook and CSVs remain versioned according to the earlier maintainer decision.

## Rollback

1. Find a successful run's **Artifact commit** in its Actions summary or saved
   `data/release.json`. Use the full 40-character SHA from `main` history. It must
   contain a publication record and validated production snapshot with no
   uncommitted source changes. Restored inputs must match that record's hashes.
   Earlier development snapshots that record dirty sources are intentionally rejected.
2. Run **Build and deploy dashboard** on `main`, choose `rollback`, and paste that
   SHA into `rollback_commit`. No FRED request or API-key lookup occurs.
3. The job restores that revision's automatic inputs and three snapshot files,
   validates them with current code, and creates a new commit on top of current
   `main`. The snapshot ID and bytes are preserved. Current frontend code stays
   in use; incompatible historic contracts fail without changing Pages.
4. In PR delivery mode, merge the rollback data PR. Otherwise the job deploys
   directly. Verify the summary and deployed `data/release.json` show the target
   in `restoredFrom` and the selected snapshot ID.
5. The next scheduled `refresh` resumes collection and moves forward normally.
   To keep the rollback in place longer, disable the workflow's schedule until
   the source problem is resolved. A plain `publish` retry retains the rollback.

Rollback covers saved data; a frontend/code regression requires a separate code
revert. An obsolete rollback PR merged after intervening source changes is
reassembled against those current sources; dispatch a new rollback if the exact
historic snapshot is still intended.

## Verification and first-release acceptance

Run `python3 scripts/check.py` with Python dependencies installed and Node 22+ on
`PATH`. The command restores checked-in demo data and writes only ignored build
outputs; production validation uses a temporary snapshot. Tests need no API key.
Publication tests use temporary Git repositories and local bare remotes to
exercise concurrent input/push races, protected-branch fallback, PR merges,
exact rollback, fatal failures, retained histories and artifact exclusions.

Local verification on November 17, 2026 passed 117 Python tests, 26 JavaScript
checks and actionlint 1.7.12. A full publication rehearsal against a local bare
remote used committed source and the saved real inputs, ran all checks, and
verified the built artifact SHA matched the pushed revision. It used no API key
and made no GitHub writes or deployments.

After merging the implementation, observe a successful first production run and
confirm the three pilot charts and `data/release.json` on Pages. Exercise an
on-demand refresh, a saved-input publish, and rollback to a prior successful
artifact, then refresh again. Check a scheduled run when it occurs. Offline
tests do not establish that GitHub permissions or the live deployment work;
these hosted acceptance steps remain pending until observed.

## Slice 6 release preparation

Commit the Slice 6 source definitions, reviews, tests and saved automatic inputs
before running the full check or publication command. The three manual issuance
series are now active, and the assembler requires their current specification to
match the audited committed registry. An uncommitted definition cannot be published.
After that commit, `python scripts/check.py` assembles all 24 active series offline;
`publish` uses saved inputs and `refresh` updates only the 18 automatic sources.

Policy version 7 adds the Cboe VIX index after the two ICE BofA credit-spread series,
without changing the v2 snapshot format. Policy versions 4–6 remain accepted for
exact-byte rollback of their published snapshots. Old required source notices are
preserved. Treasury bid–ask remains inactive, and iFind/price impact still await
definitions. See the
[review and evidence](source-review-slice-6.md). Hosted first-deployment and live
rollback/recovery acceptance remain pending; local Git rehearsals do not replace them.
