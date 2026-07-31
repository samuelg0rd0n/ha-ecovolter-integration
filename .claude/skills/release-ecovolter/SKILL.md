---
name: release-ecovolter
description: Ships a new version of this Home Assistant / HACS integration end-to-end — merges the open PR, bumps the semantic version in custom_components/ecovolter/manifest.json, waits for CI to pass on main, tags it, and publishes a GitHub release with drafted notes marked as Latest (or Pre-release for betas). Also handles releasing something as a beta first (so only opted-in users are exposed to risk) and later promoting an existing beta to a regular/stable release once it's field-validated. Use this whenever the user wants to release, publish, ship, cut, tag, beta-test, or promote a new version of this integration — phrases like "release this", "cut a new version", "publish v1.1.0", "ship this as a beta", "release it as a beta so I don't break it for everyone", "promote the beta to stable/final", "make the beta official", "bump the version and release", or "merge this PR and put out a release" all mean run this skill, even if they don't mention every step explicitly.
---

# Releasing ha-ecovolter-integration

This repo is a HACS-distributed Home Assistant integration with no publish pipeline —
HACS reads the release directly off GitHub, so "release" means: the right version number
lands in `manifest.json`, a matching `vX.Y.Z` git tag exists, and a GitHub Release is
published pointing at it. There is nothing to build or push to a registry.

Two small scripts do the mechanical, error-prone parts so you don't have to hand-edit
JSON or do semver arithmetic in your head:

- `scripts/next_version.py <current> major|minor|patch [--pre LABEL]` / `--finalize`
- `scripts/bump_manifest_version.sh <new_version> [manifest_path]`

Everything else — reading the diff, judging the bump type, writing release notes — is
judgment work you should do directly.

## The workflow

### 1. Establish where things stand

```
git status
gh pr view --json number,state,mergeable,baseRefName,headRefName 2>&1   # if on a feature branch
gh pr checks <N>                                                        # if a PR exists
```

Two starting points are both normal:
- **On a feature branch with an open PR** — the common case. Merge it as part of this flow.
- **Already on `main`** with nothing to merge — some work in this repo lands as direct
  commits to main (check `git log --oneline -5` if unsure). Skip straight to step 3.

If a PR exists but its checks are red or it has merge conflicts, stop and tell the user —
don't merge broken code just to hit a release deadline.

### 2. Merge the PR

Always merge with a real merge commit (not squash, not rebase) — that's what this repo's
history uses for every prior PR (`Merge pull request #N from ...`), and preserving the
individual commits is more useful than a single squashed one for a project with outside
contributors.

```
gh pr merge <N> --merge
git checkout main && git pull
```

### 3. Decide the version bump

Read the current version:

```
grep version custom_components/ecovolter/manifest.json
```

Look at what actually changed since the last tag (`git log <last-tag>..HEAD --oneline`,
or the PR's commits/diff) and judge the bump the way semver intends:

- **patch** — bug fixes, docs, test-only changes, internal refactors with no behavior change
- **minor** — new functionality that's backward compatible (new entity, new option, new sensor)
- **major** — breaking change (removed/renamed entity, changed config schema, dropped HA
  version support) — rare for an integration this size, but don't rule it out

This repo doesn't enforce Conventional Commits, so don't pattern-match on commit prefixes
alone — actually read what the PR does. If it's ambiguous, propose a bump type and the
resulting version number to the user and confirm before proceeding; getting this wrong
is annoying to unwind after a tag is public.

For a **beta release**, add `--pre beta` (or whatever label the user asked for) to get
`X.Y.Z-beta.N`. To **promote an existing beta to a regular/stable release** ("promote to
final", "make it official" — same thing, just different wording people reach for), use
`--finalize` instead of a bump type. Examples:

```
scripts/next_version.py 1.0.0 minor                  # -> 1.1.0
scripts/next_version.py 1.0.0 minor --pre beta        # -> 1.1.0-beta.0
scripts/next_version.py 1.1.0-beta.0 --pre beta       # -> 1.1.0-beta.1 (next beta, same base)
scripts/next_version.py 1.1.0-beta.1 --finalize       # -> 1.1.0
```

See "Beta releases" below before picking a beta version string — the exact format is
load-bearing, not cosmetic.

### 4. Bump the manifest and push to main

```
scripts/bump_manifest_version.sh <new_version>
git add custom_components/ecovolter/manifest.json
git commit -m "chore(ecovolter): bump version to <new_version>"
git push origin main
```

This matches the style of prior version-bump commits in this repo's history
(`chore(ecovolter): bump version to 1.0.0`).

### 5. Wait for CI to go green on main

The push triggers `.github/workflows/check_and_test.yaml` (mypy, ruff, pytest, HACS
validation, hassfest). Don't tag or publish until it passes — a red release ships a
broken integration straight to every HACS user who updates.

```
gh run list --branch main --limit 1
gh run watch <run-id> --exit-status
```

If it fails, stop and surface the failure to the user rather than tagging anyway.

### 6. Draft release notes

Match the tone of past releases (see `gh release view v1.0.0 --json body` for reference):
short, plain-language prose aimed at end users configuring an integration, not developers.

- Lead with a one-line summary of what this release is about.
- A `## Highlights` bullet list for anything user-visible (new sensors/entities, behavior
  changes, notable fixes) — bold the short name of each item.
- Thank external contributors by GitHub handle and PR number if anyone other than the
  maintainer contributed since the last release (check `git log <last-tag>..HEAD --format='%an'`
  against PR authors) — e.g. "Thanks @gmarti (#6)."
- Add a line like "Requires Home Assistant 2025.11.0 or newer." only if this release
  actually raises the minimum supported version — don't invent a requirement that isn't real.
- Skip sections that don't apply. A one-line fix release doesn't need a Highlights list.

Show the drafted notes to the user and get their go-ahead (or edits) before publishing —
these are public-facing and harder to revise gracefully once users have read them.

### 7. Tag and publish

```
git tag -a v<new_version> -m "v<new_version>"
git push origin v<new_version>
```

For a **stable** release:

```
gh release create v<new_version> --title v<new_version> --notes-file <notes> --latest
```

For a **beta** release, also mark it `--prerelease` — this keeps GitHub's own UI honest
(it won't steal the "Latest" badge from the newest stable release), but note that this flag
is cosmetic, not the safety mechanism. See "Beta releases" below for what actually gates it.

```
gh release create v<new_version> --title v<new_version> --notes-file <notes> --prerelease
```

### 8. Confirm

Report back the release URL (`gh release view v<new_version> --json url -q .url`), the tag,
and the final manifest version. HACS picks up new releases automatically — there's nothing
further to push or deploy.

## Beta releases

This repo is maintained mostly solo but used by other people, so betas exist to let risky
changes reach real devices without exposing everyone: a beta is opt-in via HACS's per-repo
"show beta versions" toggle, off by default. If the user says something like "release this
as a beta, I don't have a way to test it myself" or "I'm not confident this won't break
things for other people," that's this flow — no code changes required, it's entirely about
how the release is versioned and tagged.

**The mechanism that actually matters:** HACS decides whether a release is a beta by
parsing the version string itself (via the `awesomeversion` library) — not from GitHub's
"Set as a pre-release" checkbox, and not from release notes. Confirmed directly against the
`awesomeversion` package installed in this repo's `.venv`: a suffix like `-beta.N` (what
`next_version.py --pre beta` produces), or PEP440-style `bN`, both parse with `.beta == True`.
The `-beta.N` form is what this skill uses, since it's what's already in this repo's tag
history (`v1.0.0-beta.0`, `v0.1.0-beta.1`, etc.) — don't switch styles without a reason to.

Because the *version string* is what gates it, the git tag and the `manifest.json` version
must carry that same beta suffix — this skill's step 3–7 flow already keeps them in lockstep
(tag `v<new_version>` always matches the manifest's `<new_version>` exactly), so as long as
you don't hand-edit either one separately, this stays correct automatically.

**Promoting a beta to stable:** once the user is satisfied (they've run it themselves, or a
beta user reported back), run `--finalize` to strip the suffix and go through the same
merge-less version of the flow (steps 3–8, skip step 2 since there's no PR left to merge) —
bump the manifest to the plain version, push, wait for CI, tag, and publish as `--latest`
without `--prerelease`. Don't just flip the existing beta release's flag in the GitHub UI;
HACS needs an actual stable-versioned tag/release to serve to non-beta users. For release
notes on the promotion, it's fine to consolidate what shipped across the beta iterations
into one summary rather than repeating each beta's notes verbatim.

Since the user is also a HACS user of their own integration, mention that they can flip
their own repo's "show beta versions" switch if they want the new beta to show up for
their own instance to test — that toggle is the actual staging gate here, doubling as
"install it on my own system before anyone else does."

## Things worth double-checking, not assuming

- If the PR touches `manifest.json` itself (e.g. adding a new `requirements` entry),
  make sure your version-bump commit doesn't clobber that change — bump on top of it,
  don't overwrite the file wholesale.
- If `hacs.json` or `manifest.json` need updates unrelated to the version (new dependency,
  new domain field), that's a separate concern from this workflow — flag it, don't fold
  silent unrelated edits into the release commit.
- A version can only be tagged once. If `v<new_version>` already exists, something upstream
  (the bump-type judgment, or a stale local checkout) went wrong — stop and re-check rather
  than force-pushing over an existing tag.
