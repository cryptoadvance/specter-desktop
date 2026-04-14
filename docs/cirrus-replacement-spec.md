# Cirrus CI Replacement Spec

> Incorporates review findings from Winston (architecture), Amelia (impl),
> Murat (test arch), Mary (requirements), and Ravi (red team) across two
> party-mode rounds plus a security pass. Key decisions: GHCR image
> migration is already complete (landed in `kn/update-node-ci`); cutover
> split across two PRs; acceptance gate is flake-rate based with 30-day
> steady-state budget; branch-protection rename has a runbook; committed
> evidence artifact required at gate-close; Codecov is out of scope.
> **CRITICAL security regression identified and fixed as PR #1 blocker:**
> unverified bitcoind downloads plus `save-always` cache turn a
> supply-chain attack into a persistent backdoor vector — PR #1 must
> update `tests/install_noded.sh` to GPG-verify releases.

## Context

Cirrus CI's free OSS tier shuts down **end of June 2026**. Specter-Desktop
depends on Cirrus for PR gating via `.cirrus.yml` (pytest + Cypress +
extension smoketest). We must migrate before the shutdown or lose PR gating.

Today's CI split (see `AGENTS.md` §CI/CD):

| System         | Purpose                                             | Status          |
|----------------|-----------------------------------------------------|-----------------|
| GitHub Actions | Lint, smoke-build, Docker, **full release pipeline** | Active          |
| Cirrus CI      | pytest + Cypress + extension smoketest on PRs       | **Sunsetting**  |
| GitLab CI      | `check` job only; release flow already migrated off | Vestigial, dead |

**Reframe:** the real root cause is **3-system CI sprawl with no owner**.
Cirrus shutdown is the forcing function to consolidate on GH Actions.

## Goals

1. Preserve PR gating equivalent to Cirrus (pytest, Cypress, extension
   smoketest) before Cirrus goes dark.
2. Zero new private-hardware requirements — stay on public runners.
3. Preserve cache hit rate so PR turnaround doesn't regress beyond SLO
   (see §SLOs).
4. Leave the repo in a state where `.cirrus.yml`, `docker/cirrus-jammy/`,
   `.gitlab-ci.yml`, and `pyinstaller/build-win-ci.bat` can be removed
   cleanly in a follow-up PR.
5. Remove the cross-provider GitLab registry dependency entirely.

## Non-goals

- Re-architecting the test suite.
- Rebalancing the test pyramid (Cypress → pytest migration). Tracked
  separately in §Deferred.
- Moving jobs back to GitLab CI (no PR model).
- Adding Cypress Dashboard or other paid observability SaaS.
- Coverage upload to Codecov or similar. Coverage stays terminal-only,
  matching current Cirrus behavior.
- Introducing new test matrices (OS/python versions) beyond Cirrus parity.

## Target: GitHub Actions

GH Actions already hosts lint, Docker, and the release pipeline, all on
public runners. Consolidating reduces CI systems from three to one.

## Image hosting — already on GHCR

**Already done** by PR #2602 (merged 2026-04-12, commit `3e277689`). That
PR upgraded Node 12→18 and migrated **all three** CI images from GitLab
registry to GHCR:

- `ghcr.io/cryptoadvance/specter-desktop/cirrus-jammy:20260412`
- `ghcr.io/cryptoadvance/specter-desktop/cypress-python-jammy:20260411`
- `ghcr.io/cryptoadvance/specter-desktop/cypress-base-ubuntu-jammy:20260411`

The cross-provider GitLab registry dependency is gone. No mirror workflow
needed. `.cirrus.yml` already references the GHCR paths, so Cirrus and the
new GHA workflow will pull from the same registry during the side-by-side
period.

**Residual ownership gap (small):** the Dockerfiles are built by hand per
`docker/cypress-python-jammy/Readme.md`. When they change (historically
every ~18 months), whoever edits must remember to `docker build && docker push`
to GHCR and bump the tag in `test.yml`. Fix: add one sentence to
`docker/cypress-python-jammy/Readme.md` stating that Dockerfile edits
require re-push to GHCR and a matching tag/digest bump in
`.github/workflows/test.yml`. That's the full remediation — no scheduled
liveness check, no CODEOWNERS fight. The image is too static to justify more.

Deeper hardening (cosign signing, automated build workflow) is tracked in
§Security HIGH as a 30-day follow-up.

## What to port

Three Cirrus tasks → three GH Actions jobs in a new
`.github/workflows/test.yml`. Trigger: `pull_request` + `push` to master.

### Global workflow-level settings

```yaml
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true
```

Every job must set:
- `timeout-minutes:` (budget below)
- `actions/checkout@v4` with **`fetch-depth: 0`** (NOT default `1`) —
  `tests/test_util_version.py` needs tag history and `git describe` needs
  annotated tags. No separate `git fetch refs/tags/v1.0.0` dance.
- `fail-fast: false` semantics where matrices are used.

### 1. `test` (pytest)

Cirrus today: `test_task` on `cirrus-jammy:20230206`, runs
`pytest --cov=cryptoadvance --junitxml=./testresults.xml` with cached
bitcoind and elementsd.

GH Actions mapping:
- `runs-on: ubuntu-22.04`
- `timeout-minutes: 45`
- System deps installed inline: `libusb-1.0-0-dev libudev-dev
  python3-virtualenv`. No custom image.
- `actions/setup-python@v5` pinned to `3.10`, `cache: pip`, `cache-dependency-path: requirements.txt`.
- **bitcoind/elementsd cache** (see §Caching).
- Install:
  ```
  pip install -r requirements.txt --require-hashes
  pip install -e ".[test]"      # intentionally bypasses hashes, documented
  ```
- Run: `pytest --cov=cryptoadvance --cov-report=term --junitxml=./testresults.xml -p no:cacheprovider --reruns 0`
  - `--reruns 0`: fail fast. Flakiness is debt, not a coping mechanism.
  - Coverage is terminal-only, matching current Cirrus behavior. No upload.
- Artifacts: `testresults.xml`.

### 2. `cypress`

Cirrus today: `cypress_test_task` on `cypress-python-jammy:20230206`,
Cirrus-requested `cpu: 6, memory: 6G`, runs
`./utils/test-cypress.sh --debug run`.

GH Actions mapping:
- `runs-on: ubuntu-22.04` (4 vCPU / 16 GB free). **Do not pre-escalate** to
  `ubuntu-22.04-large`. Measure first (see §Cypress measurement).
- `timeout-minutes: 30` initially; adjust after measurement.
- Container:
  ```yaml
  container:
    image: ghcr.io/cryptoadvance/specter-desktop/cypress-python-jammy@sha256:<digest>
    options: --shm-size=2g    # Cypress OOMs on default 64M /dev/shm
  ```
  Digest captured from the `:20260411` tag at PR #1 time. Pinned by digest,
  not tag, to make future Dockerfile edits visibly require a workflow bump.
- Same bitcoind/elements cache as `test`.
- npm cache via `actions/cache` keyed on `package-lock.json` (not
  `setup-node`; node already ships in the container).
- Cypress retries: `{ runMode: 1, openMode: 0 }` in `cypress.json` — one
  retry max, logged loudly so flakes are visible, not hidden.
- Run: `./utils/test-cypress.sh --debug run`.
- Artifacts: `cypresstest-output.xml`, `cypress/screenshots/**`,
  `cypress/videos/**`.

**Sharding decision:** deferred. If measured wall-clock > 15 min, split
specs across a 2-shard matrix. Don't split pre-emptively.

### 3. `extension-smoketest`

Straight port of Cirrus's `extension_smoketest_task`. Same runner/deps as
`test` job. Preserves the exact bash block: git identity, `ext gen`, server
boot, log-line grep, curl assertion. **Contract must stay byte-compatible**
— this job is the canary for downstream extension developers.

## Images

- **`docker/cirrus-jammy/`** — delete in PR #2. pytest job installs deps
  inline on `ubuntu-22.04`; no custom image needed. The current GHCR tag
  (`cirrus-jammy:20260412`) can stay in GHCR indefinitely as a harmless
  artifact after the Dockerfile is deleted from the repo.
- **`cypress-python-jammy`** + **`cypress-base-ubuntu-jammy`** — already
  on GHCR via PR #2602. Keep Dockerfiles in `docker/`. Add one sentence
  to `docker/cypress-python-jammy/Readme.md`: *"When editing this
  Dockerfile, rebuild and push to
  `ghcr.io/cryptoadvance/specter-desktop/cypress-python-jammy` with a new
  tag, then update the digest pin in `.github/workflows/test.yml`."*

## Caching

GH Actions `actions/cache@v4` keyed on:

```
${{ runner.os }}-${{ runner.arch }}-noded-
  ${{ hashFiles('pyproject.toml', 'tests/bitcoin_gitrev_pinned', 'tests/elements_gitrev_pinned', 'tests/install_noded.sh') }}-
  binary
```

`runner.arch` matters — future ARM runners must not poison x86 caches.

Paths: `./tests/bitcoin`, `./tests/elements`.

Populate step: `./tests/install_noded.sh --debug --bitcoin binary` and
`--elements binary` on cache miss (match Cirrus `populate_script`).

Set **`save-always: true`** on the cache step so a mid-job timeout on a
cold cache still persists the partial binaries. Otherwise first-PR-after-
pin-bump on every branch re-pays the full install cost.

**Security-critical:** see §Security. `save-always` + unverified
downloads was a persistent-backdoor vector. PR #1 must update
`install_noded.sh` to GPG-verify releases and re-verify on every cache
restore. This is non-negotiable.

First run after cutover repopulates per branch — one-off ~few-minute cost,
accepted.

## Concurrency, timeouts, retries

| Setting               | Value                                        |
|-----------------------|----------------------------------------------|
| Concurrency group     | `${{ github.workflow }}-${{ github.ref }}`   |
| Cancel in progress    | `true`                                       |
| `test` timeout        | 45 min                                       |
| `cypress` timeout     | 30 min (tune after measurement)              |
| `extension-smoketest` | 15 min                                       |
| pytest reruns         | **0** (fail fast)                            |
| Cypress `runMode` retries | **1** (log loudly)                       |

## Security

Red-team pass (Ravi, 2026-04-12) surfaced one **CRITICAL** regression
introduced by this migration, plus two HIGH findings tracked as follow-ups.

### CRITICAL — bitcoind/elementsd download verification (PR #1 blocker)

**Attack chain:** `tests/install_noded.sh:244` does a bare
`wget https://bitcoincore.org/bin/bitcoin-core-${version}/${binary_file}`
with **no GPG signature verification and no SHA256SUMS check** (same for
Elements at line 241). Under Cirrus this was per-run ephemeral. Under GH
Actions with `actions/cache@v4 save-always: true` — and a cache key that
only hashes the pinned-rev files and the install script, **not** the
binary content — a single poisoned fetch (MITM, DNS/BGP hijack, upstream
compromise) writes a trojaned `bitcoind` into the cache. Every
subsequent run on master and PR branches restores it from cache. The
test runner executes it with the repo checkout mounted.

**Impact:** persistent backdoor across all PR and master runs until the
cache key rotates. Blast radius includes the release pipeline
(`release.yml`), which shares the repo's `GITHUB_TOKEN` boundary and
runs on the same runner pool.

**Regression status:** the `install_noded.sh` bare-wget predates this
migration. Cirrus's per-run ephemerality masked the weakness. Moving to
GHA with `save-always` caching **materially worsens** it from transient
to persistent. We do not inherit the risk silently — we fix it in PR #1.

**Fix (must land in PR #1):**
1. Update `tests/install_noded.sh` to download `SHA256SUMS` and
   `SHA256SUMS.asc` alongside the binary tarball.
2. Import the Bitcoin Core release signing keys (fanquake, achow101)
   into a temporary `GNUPGHOME` and verify `SHA256SUMS.asc`.
3. Verify the tarball hash matches the entry in `SHA256SUMS`. Abort on
   mismatch.
4. Same treatment for ElementsProject downloads (`install_noded.sh:241`)
   using Elements release signing keys.
5. Run the verification step **on cache hit as well** (not only cache
   miss), so a tampered cache entry fails closed instead of being
   trusted on restore.
6. Commit the expected `SHA256SUMS` content (or its content hash) to the
   repo so post-restore verification has a trusted reference. Bump it
   alongside `tests/bitcoin_gitrev_pinned` / `tests/elements_gitrev_pinned`.

### HIGH — Cypress image integrity chain (30-day follow-up)

**Attack chain:** `cypress-python-jammy` is built and pushed by hand.
Maintainer-laptop compromise at push time → attacker uploads a trojaned
image under legitimate GHCR credentials. Next Dockerfile edit, a
maintainer computes the digest from the compromised local build and
pins it in `test.yml`. Cypress runs as root inside, with the repo
checkout mounted.

**Not a PR #1 blocker.** Image has been untouched for 18 months; edit
frequency bounds exposure. Tracked as a separate hardening issue.

**Fix (separate PR, target: within 30 days of cutover):**
1. Automate image build in a workflow triggered on `docker/**` path
   filter, using default `GITHUB_TOKEN` with `packages: write`.
2. Cosign keyless-sign the pushed image via GitHub OIDC.
3. `test.yml` verifies the signature via `cosign verify` before
   consuming the container. Removes maintainer laptops from the trust
   path entirely.

### HIGH (acknowledged) — Release pipeline shares token boundary

`.github/workflows/release.yml` ships specterd, pip package, and
Electron artifacts to real users. It lives in the same repo as
`test.yml` and shares the same `GITHUB_TOKEN` boundary and runner pool.
Any RCE in a test workflow runs on a runner that can read `release.yml`.
This migration does not change that exposure — but **fixing CRITICAL #1
above also de-risks the release pipeline**, since the same runner pool
consumes the same (now verified) binaries.

No spec change beyond this acknowledgment. Full release pipeline
hardening is out of scope.

### LOW findings (accepted / backlog)

- **Branch protection cutover gap:** minutes-wide, runbook adequate,
  accept.
- **`GITHUB_TOKEN` on fork PRs:** default read-only, no
  `pull_request_target`, no third-party actions, no secrets exposed.
  Clean.
- **First-party actions pinned to major (`@v4`/`@v5`) not SHA:** GitHub
  org compromise is a tier-1 ecosystem event. Defense-in-depth backlog
  item, not blocking.

## Test quality — flake detection, quarantine, steady-state

Not in Cirrus today. Adding now, at minimum viable.

- **Flake signal:** parse JUnit XML for retry markers after each run; when
  a Cypress spec retries-to-green, emit a GH Actions warning annotation
  and append a line to a tracking gist (`flake-log.md`). No dashboard yet.
- **Quarantine policy:** any spec flagged flaky twice in 14 days gets
  `@skip(reason="flaky", issue="#NNNN")` with a linked GH issue and a
  **2-week SLA** to fix-or-delete.
- **Retry budget:** Cypress `runMode: 1`. Anything needing more is quarantined.
- **Steady-state flake SLO (post-cutover):** rolling 30-day rerun rate
  must stay **≤ 1%** across all jobs. Same JUnit parser feeds a daily cron
  job that computes the window and auto-opens a P2 issue on breach. This
  turns flake detection from a one-shot cutover gate into a living quality
  signal — without it we'll be right back here in six months.

## Cypress performance — measurement protocol

**Before** approving any runner upgrade:
1. Run the Cypress suite 5× on `ubuntu-22.04` free tier.
2. Record wall-clock p50 / p95 via `/usr/bin/time -v` wrapping the script.
3. Compare to last 5 Cirrus runs' wall-clock.
4. Ship it if p95 is within **Cirrus +20%**.
5. Only if p95 exceeds +20% or hits the 30-min timeout, evaluate in order:
   (a) `--shm-size` bump, (b) spec sharding across 2 jobs,
   (c) `ubuntu-22.04-large` (paid — requires approval).

## Migration plan — two PRs

### PR #1 — Add GH Actions workflow (side-by-side)

1. **Security blocker:** update `tests/install_noded.sh` per §Security
   CRITICAL fix (GPG-verify `SHA256SUMS.asc`, verify tarball hash,
   re-verify on cache restore). Commit trusted reference hashes
   alongside `tests/bitcoin_gitrev_pinned` /
   `tests/elements_gitrev_pinned`. This must land in the same PR as the
   workflow.
2. Capture the `cypress-python-jammy` image digest from the `:20260411`
   GHCR tag. Write it into `test.yml`.
3. Add `.github/workflows/test.yml` with all three jobs.
4. Add the one-sentence rebuild-and-push note to
   `docker/cypress-python-jammy/Readme.md`.
5. **Do not touch** `.cirrus.yml`, `.gitlab-ci.yml`, or branch protection.
6. Land the PR. Both CI systems now run on every PR.
7. Iterate on the workflow until the acceptance gate (§Acceptance) passes.
8. Commit the evidence artifact to `docs/ci-migration-evidence.md` once
   the gate is met.

### PR #2 — Cutover + cleanup

Only merge when PR #1 meets the acceptance gate.

1. Delete `.cirrus.yml` and `docker/cirrus-jammy/`.
2. Delete `.gitlab-ci.yml` and `pyinstaller/build-win-ci.bat`.
3. Audit and prune dead GitLab-only code paths in `utils/release.sh`,
   `utils/release_helper.py`, `utils/github.py`.
4. Drop Cirrus + GitLab sections from `docs/continuous-integration.md`.
5. Update `AGENTS.md` CI/CD section.
6. **Rename required status checks** in GitHub branch protection (see
   §Branch protection). This is a separate manual step, documented in the
   PR body.

Splitting the cleanup out of PR #1 preserves fast revertability: if
anything melts in week 1 of side-by-side, PR #1 is trivially revertable
because it touches only additive files.

## Branch protection & required checks

**Scariest silent-failure mode.** If the required-check name on master
branch protection still says `Cirrus CI / test_task` after cutover,
*nothing is gating PRs anymore* and no alert fires.

Runbook (must execute as part of PR #2 merge):

1. Before merging PR #2: list current required checks via
   `gh api repos/cryptoadvance/specter-desktop/branches/master/protection`.
2. Record the Cirrus check names.
3. Merge PR #2.
4. Immediately update branch protection: remove Cirrus check names, add
   the new GH Actions check names (`test`, `cypress`, `extension-smoketest`).
5. Open a throwaway test PR to verify all three new checks are required
   and gating.
6. Only then announce cutover complete.

## Secrets inventory

No new secrets required. The workflow only uses the default
auto-provided `GITHUB_TOKEN` (for `ghcr.io` push during the one-shot image
mirror and for any standard action plumbing).

Historical GitLab secrets (`GH_BIN_UPLOAD_PW`, `TWINE_PASSWORD`,
`GPG_PASSPHRASE`, `SSH_SPECTEREXT_DEPLOY_KEY`, `SSH_SPECTERSTATIC_DEPLOY_KEY`)
are already unused per AGENTS.md. PR #2 should not touch them (release
pipeline lives elsewhere).

## Stakeholder comms

This is CI plumbing, not a release. Scope is narrow:

- **Extension developers:** smoketest contract preserved byte-for-byte.
  No comms needed unless the job fails post-cutover.
- **`docs/continuous-integration.md`:** updated in PR #2 to reflect the
  new CI topology. That's the extent of external-facing docs.

## SLOs / acceptance criteria

### PR wall-clock SLO

**Baseline captured 2026-04-12** from the Cirrus GraphQL API
(`https://api.cirrus-ci.com/graphql`), last 20 successful master-branch
builds. Cirrus runs all three tasks in parallel, so total build wall-clock
≈ longest task (cypress).

| Task                      | n  | median | p95    | min    | max    | GHA ceiling (+25%) |
|---------------------------|----|--------|--------|--------|--------|--------------------|
| `test_task`               | 20 | 4m47s  | 5m35s  | 4m23s  | 5m37s  | **5m59s**          |
| `cypress_test_task`       | 20 | 6m02s  | 6m55s  | 5m27s  | 8m15s  | **7m32s**          |
| `extension_smoketest_task`| 20 | 2m10s  | 2m27s  | 1m55s  | 2m39s  | **2m43s**          |

- **Tolerance:** per-job wall-clock on GH Actions must not exceed the
  "GHA ceiling" column (Cirrus median + 25%).
- **Action on breach:** investigate before cutover; do not ship PR #2 until
  resolved.

**Implications for Cypress measurement protocol:** current Cirrus cypress
p95 is 6m55s — well under the 30-min timeout and not remotely at risk of
hitting paid-runner territory. The "4 vCPU vs 6" concern is almost
certainly a non-issue in practice. Measurement protocol stands, but expect
it to pass on free runners.

### Flake rate ceiling

- **Baseline:** measured during side-by-side (unknown today).
- **Ceiling:** post-cutover flake rate ≤ Cirrus baseline. Any regression
  is a cutover blocker.

### Cost ceiling

- GH Actions minutes on public OSS runners are effectively free. No hard
  cap needed unless we escalate to `-large` runners (then: $X/month ceiling
  requires explicit approval from project lead).

### Acceptance gate for cutover (PR #2 merge criteria)

All four must hold:
1. **10 consecutive green runs** of the new workflow on master-branch
   schedule (nightly) or via manual dispatch.
2. **At least 3 green PR runs**, including one that touches `src/cryptoadvance/specter/static/` or frontend templates.
3. **Zero new flakes** detected over at least 50 total runs (PR + master).
4. Cypress p95 wall-clock within **Cirrus +20%** per measurement protocol.

"Green on 3 PRs" alone is insufficient — flake rate is the real KPI.

### Evidence artifact (mandatory)

Before merging PR #2, a committed **evidence artifact** must exist at
`docs/ci-migration-evidence.md` containing, at minimum:

- Measured wall-clock median + p95 per job over the 10+ master runs
- Flake count over the 50+ runs window (expected: 0)
- URLs to 3+ sample PR runs including the frontend-touching one
- Date and commit SHA at measurement time

This exists so that six months from now "did we actually hit SLO?" has a
grep-able answer instead of a hope. GH Actions logs are GC'd; the evidence
doc is not. Ten minutes to write, permanent value.

## Rollback procedure

If anything breaks post-cutover:

1. **Workflow-level breakage in PR #1 phase:** disable the GH Actions
   workflow via `workflow_dispatch` off-switch or delete the file; Cirrus
   still gates PRs. Zero user impact.
2. **Post-cutover breakage (PR #2 merged):** revert PR #2. This restores
   `.cirrus.yml` and `docker/cirrus-jammy/`. Re-add Cirrus checks to branch
   protection. Cirrus is assumed still alive up to shutdown date.
3. **Post-Cirrus-shutdown breakage:** no Cirrus fallback exists. Forward
   fix only. This is why PR #2 must merge **≥ 4 weeks before shutdown**.

## Timeline

| Date        | Milestone                                       |
|-------------|-------------------------------------------------|
| 2026-04-12  | Cirrus baseline captured (§SLOs); GHCR migration merged (PR #2602) |
| 2026-04-13  | Spec finalized post red-team pass               |
| 2026-04-14  | Open PR #1 (security fix + workflow + cache)    |
| 2026-04-21  | PR #1 green on first PR run                     |
| 2026-05-05  | Acceptance gate met (10 green + flake-clean)    |
| 2026-05-12  | **PR #2 merged + branch protection updated**    |
| 2026-05-19  | One full release cycle on new CI (if a tag cuts)|
| 2026-06-30  | Cirrus shutdown (~7 week buffer after cutover)  |

## Deferred (explicit non-goals for this migration)

- **Test pyramid rebalance.** Cypress likely owns flows that belong in
  pytest + a Flask test client. Q3 epic, not this PR. Logged here so it's
  not lost.
- **Cypress Dashboard / paid observability.** Vendor lock, not worth the
  cost at current scale. JUnit + artifacts cover 90% of the value.
- **Coverage upload / Codecov / coverage-delta gating.** Out of scope for
  this migration. Matches current Cirrus (which also doesn't upload). If
  we want trend data later, it's a standalone follow-up PR with its own
  bus-factor discussion and token plumbing.
- **Local-contributor reproducibility of the Cypress image.** Nice to
  have; separate runbook, post-cutover.
- **Cypress image cosign signing + build automation.** Tracked in
  §Security HIGH. Separate PR within 30 days of cutover, not blocking.
- **Release pipeline hardening.** Out of scope; §Security HIGH
  acknowledges shared token boundary.
- **First-party action SHA pinning.** Defense-in-depth backlog.

## Risks (updated)

1. **Supply-chain backdoor via unverified bitcoind (CRITICAL).** Resolved
   by the PR #1 blocker fix in §Security. Without that fix, this spec is
   unmergeable.
2. **Cypress perf on 4 vCPU.** Largely resolved by baseline data: Cirrus
   cypress p95 is 6m55s, so the suite is not heavyweight. Residual risk is
   that GH Actions 4-vCPU runners could push it past the +25% ceiling
   (7m32s). Mitigation: measurement protocol in §Cypress measurement.
   Escape hatch documented, not pre-purchased.
2. **Branch protection silent-ungate.** Scariest risk; has a runbook now
   (§Branch protection).
3. **ghcr.io image rebuild drift.** Once mirrored, whoever edits
   `docker/cypress-python-jammy/Dockerfile` must remember to rebuild and
   re-push. Mitigation: README runbook + digest pinning makes staleness
   visible (workflow won't auto-upgrade).
4. **First-run cache miss storm.** One-off few-minute cost. Accepted.

## Unresolved questions

None. All prior questions resolved or descoped.
