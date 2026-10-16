---
title: Make ci.yml and validate.yml run on branch pushes again
created: 2026-10-12
area: ci
source: phase 09 plan 02 (D-04 amendment)
blocked_until: v1.0.1 tag exists (a workflow change before the tag would move the anchor SHA, D-01/D-02)
---

## Problem

`.github/workflows/ci.yml` and `.github/workflows/validate.yml` declare `on.push` with only
`tags-ignore: ["v*.*.*"]`. When a push filter defines only tags or tags-ignore, GitHub Actions does
not run the workflow for branch pushes. Since 2f786d8 (plan 04-01, part of v1.0.0) no push to main
or any other branch has triggered CI or Validate. Pull requests, workflow_dispatch and the release
path (release.yml via workflow_call) still work.

Found in 09-02: the owner's push of the v1.0.1 bump SHA produced no run; the gate was met through
an owner-approved D-04 amendment (workflow_dispatch). Record:
`.planning/phases/09-v1-0-1-release/09-evidence/release/d04-amendment.txt`.

## Fix

Add a branches filter next to tags-ignore in both files:

```yaml
on:
  push:
    branches: ["**"]
    # A version tag runs these checks once, through release.yml
    tags-ignore:
      - "v*.*.*"
```

## Done when

- A plain branch push to main creates a CI and a Validate run with event `push`.
- A `v*.*.*` tag push still creates no direct CI/Validate run (only release.yml).
- Owner may delete the leftover temp branch `ci/v1.0.1-bump` on origin.
