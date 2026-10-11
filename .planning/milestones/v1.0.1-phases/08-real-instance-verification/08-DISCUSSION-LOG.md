# Phase 8: Real-Instance Verification - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-10-04
**Phase:** 8-Real-Instance Verification
**Areas discussed:** Test environment, Execution and automation, Evidence format, Scope of the ten Phase 1-3 checks, Failure handling

---

## Test environment
Options: only ~/ha-test (selected) / ha-test plus production for two checks / all production.
**Notes:** Phase 1 #1 (HACS) and #6 (hassio-n2plus) need real hosts, so the owner chose the exception "only these two on a real host".

## Execution and automation
Options: Claude automates, owner only UI (selected) / guided checklist, owner clicks everything / Claude drives browser too.

## Evidence
Options: 08-UAT.md plus evidence folder (selected) / 08-UAT.md inline only / result only.

## Scope of the ten checks
Options: all ten (selected) / UI items only, rest by override / only UAT-01..04.

## Build under test
Options: current branch HEAD with SHA recorded (selected) / tagged v1.0.1-rc1.

## Failure handling
Options: record gap and continue (selected) / stop at first fail / small inline fixes.

## Claude's Discretion
Grouping and order of checks, helper scripts, evidence file naming.

## Deferred Ideas
None.
