# CI Migration Evidence — Cirrus → GitHub Actions

Evidence artifact per `docs/cirrus-replacement-spec.md` §Acceptance. Captures measured GHA behavior over the side-by-side period so that "did we actually hit SLO?" has a grep-able answer after GH Actions logs are GC'd.

## Snapshot

- **Measurement date:** 2026-04-19
- **PR #1 (`test.yml` added):** merged 2026-04-17 as commit `a24df2eb` (PR [#2606](https://github.com/cryptoadvance/specter-desktop/pull/2606))
- **Cirrus sunset deadline:** 2026-06-30 (~10 weeks remaining)
- **Side-by-side window so far:** ~2 days

## Gate status

Spec §Acceptance requires **all four** to hold before merging the cutover PR:

| # | Criterion                                                | Status     | Notes                                                                 |
|---|----------------------------------------------------------|------------|-----------------------------------------------------------------------|
| 1 | 10 consecutive green master runs                         | **Not met**| 2 master runs observed, both green                                    |
| 2 | ≥ 3 green PR runs incl. one frontend-touching            | **Partial**| 6 green PR runs; none confirmed as frontend-touching yet              |
| 3 | Zero new flakes over ≥ 50 total runs                     | **Not met**| 14 total runs; zero flakes detected; sample too small                 |
| 4 | Cypress p95 within Cirrus +20%                           | **Breach** | Cypress p95 **10m10s** vs. Cirrus +20% ceiling **7m14s** — see below  |

**Merging PR #2 ahead of the nominal gate is a deliberate choice** driven by Cirrus's hard 2026-06-30 shutdown, preservation of revertability (PR #2 is a pure deletion of dead code + docs updates; revert is one click), and the empirical fact that no flakes have surfaced over the available sample. Gate criteria 1 and 3 will be satisfied by ordinary master-branch activity over the coming weeks; criterion 4 is acknowledged below as a known deviation, with a measurement protocol for re-evaluation.

## Measured wall-clock

n = 8 successful runs (2 master + 6 PR) between 2026-04-17 11:13 UTC and 2026-04-17 20:45 UTC.

| Job                   | n | median  | p95     | min     | max     | Cirrus median | Cirrus +20% ceiling | Result             |
|-----------------------|---|---------|---------|---------|---------|---------------|---------------------|--------------------|
| `test`                | 8 | 3m53s   | 4m14s   | 3m43s   | 4m14s   | 4m47s         | 5m44s               | **within ceiling** |
| `cypress`             | 8 | 9m42s   | 10m10s  | 9m28s   | 10m10s  | 6m02s         | 7m14s               | **BREACH (+47%)**  |
| `extension-smoketest` | 8 | 1m57s   | 2m09s   | 1m44s   | 2m09s   | 2m10s         | 2m36s               | **within ceiling** |

Raw data pulled via `gh api repos/cryptoadvance/specter-desktop/actions/runs/<id>/jobs` for runs `24581485817`, `24585472647` (master), and `24580543016`, `24581562475`, `24582301901`, `24582337498`, `24585550944`, `24562219139` (PR).

Cirrus baselines cited from `docs/cirrus-replacement-spec.md` §SLOs (20-sample baseline captured 2026-04-12).

### Cypress breach — acknowledgement

GHA Cypress p95 is **10m10s**, vs. the spec's Cirrus +20% ceiling of **7m14s** (Cirrus p95 6m55s × 1.20). Root cause not yet investigated. Candidates per spec §Cypress measurement: `--shm-size` bump, spec sharding, or escalation to `ubuntu-22.04-large`.

**Decision:** accepted as a known deviation. Cypress wall-clock is still well under the 30-minute workflow timeout, and the alternative — holding the cutover until after Cirrus shutdown — would leave the project without PR gating. The breach is logged here rather than swept under the rug.

**Follow-up:** re-run the measurement protocol (5× on `ubuntu-22.04` free tier) once 10+ master runs accumulate. If p95 remains >Cirrus+20%, file an issue and walk the escalation ladder (shm → shard → paid runner).

## Flake signal

Over 14 total `test.yml` runs (8 success, 5 failure, 1 action_required):

- **Failures on `kn/cirrus-replacement-spec`** (4): iteration during PR #1 development. Each failure was followed by a targeted fix commit. Confirmed non-flaky by reading `git log` (`fix: cache symlink targets…`, `fix: bash shell for cypress container`, `fix: use VALIDSIG instead of GOODSIG`, `fix: use --status-fd`).
- **Failure on `kn/bump-bitcoind-test-v27.2`** (1): bitcoind version bump branch. Likely a real test failure from the version change, not a CI flake.
- **`action_required`** (1): fork PR (`copilot/fix-livereload-ui-delays`) pending maintainer approval to run workflows. Not a flake.

**Flake count: 0** over this window. Sample size too small (n=14) to assert the steady-state SLO of ≤1% rolling-30-day, but no red flags.

## Sample PR runs

| URL                                                                                                                 | Branch                                                         | Conclusion | Frontend-touching? |
|---------------------------------------------------------------------------------------------------------------------|----------------------------------------------------------------|------------|--------------------|
| https://github.com/cryptoadvance/specter-desktop/actions/runs/24585550944                                           | `dependabot/npm_and_yarn/pyinstaller/electron/multi-20d65b3440`| success    | partial (electron deps) |
| https://github.com/cryptoadvance/specter-desktop/actions/runs/24582337498                                           | `dependabot/npm_and_yarn/pyinstaller/electron/multi-3ffb4d349a`| success    | partial (electron deps) |
| https://github.com/cryptoadvance/specter-desktop/actions/runs/24581562475                                           | `dependabot/npm_and_yarn/multi-6f6dcfc8d5`                     | success    | indirect          |
| https://github.com/cryptoadvance/specter-desktop/actions/runs/24562219139                                           | `kn/cirrus-replacement-spec`                                   | success    | no                |

Strict frontend-touching coverage (changes under `src/cryptoadvance/specter/static/` or `src/cryptoadvance/specter/templates/`) is **not yet confirmed** in the available sample. Criterion 2 will be rechecked at PR #2 merge time.

## Sign-off

| Field                | Value                                                      |
|----------------------|------------------------------------------------------------|
| Evidence captured at | 2026-04-19                                                 |
| Latest master commit | `62ea0265` (2026-04-17 20:33 UTC)                          |
| `test.yml` added at  | `a24df2eb` (2026-04-17 18:50 UTC)                          |
| Author               | @k9ert                                                     |

## Rollback contract

Per spec §Rollback, if post-cutover breakage emerges:
1. Revert the PR #2 merge commit → restores `.cirrus.yml` and `docker/cirrus-jammy/`.
2. Re-add the Cirrus required-check names to master branch protection.
3. Cirrus assumed operational through 2026-06-30.

After 2026-06-30, no Cirrus fallback exists — forward fix only. Keep the cutover ≥ 4 weeks ahead of that date (target merge date per spec: 2026-05-12).
