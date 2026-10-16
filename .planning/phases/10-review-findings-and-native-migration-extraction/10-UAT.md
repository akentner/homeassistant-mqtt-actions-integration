---
status: testing
phase: 10-review-findings-and-native-migration-extraction
source: [10-VERIFICATION.md]
started: 2026-10-16T15:20:00Z
updated: 2026-10-16T15:20:00Z
---

## Current Test

number: 1
name: Owner decision on review WR-01 (kept_duplicates warning persistence)
expected: |
  A recorded decision in 10-REVIEW-DISPOSITION.md. If kept non-persistent: reword the README and
  troubleshooting rationale "because Home Assistant does not keep the text of this warning across a
  restart", which presents an integration choice as an HA limitation. If changed: is_persistent=True,
  docs and test_the_docs_describe_the_kept_duplicates_warning updated.
awaiting: user response

## Tests

### 1. Owner decision on review WR-01 (kept_duplicates warning persistence)
expected: Keep the warning non-persistent (a dismissal returns after every Home Assistant restart while a kept duplicate exists) and reword the docs rationale, or create it with is_persistent=True so a dismissal of an unchanged list survives restarts, with docs and doc test updated. Decision recorded in 10-REVIEW-DISPOSITION.md.
result: [pending]

### 2. Repairs dialog rendering on a bench instance (en and de)
expected: With one customized MQTT duplicate kept enabled next to its native twin, and one next to a native twin the user disabled, Settings > Repairs shows one non-fixable warning "Duplicate MQTT entities stay enabled" / "Doppelte MQTT-Entitäten bleiben aktiviert", no Fix button, entity ids rendered readably per reason, the dash for an empty reason, the advice to disable rather than delete (note IN-05: count-1 wording "1 MQTT entities"); it goes away after the duplicate is disabled and the integration restarts.
result: [pending]

## Summary

total: 2
passed: 0
issues: 0
pending: 2
skipped: 0
blocked: 0

## Gaps
