---
name: whole-branch-review
description: Use when a multi-task feature branch needs its final pre-merge review — before opening the PR or answering "ready to merge?" — especially when every per-task review already passed, the test suite is green, or the owner wants to merge today.
---

# Whole-Branch Review

## Overview

A pre-merge branch review is a fan-out pipeline, not a reading pass. Measured on this repo (2026-07-20): three independent solo reviews of the same 26-commit branch returned verdicts YES / YES / NO with near-disjoint findings — the branch's headline-feature defect was Critical in one review, Important in another, and absent from the third. A solo pass *samples* the finding space; only the union covers it. Every cross-task bug in this repo's history (PR #28, quantity-tiers, storn-structure) survived all of its per-task reviews.

## When to Use

- Any branch built as multiple tasks (subagent-driven development), before PR or merge.
- "Per-task reviews passed and tests are green" is the trigger, not the exemption.
- NOT for a single small commit — use /code-review.

## The Pipeline

1. **Gates first — run them, don't trust reports.** Full test suite (full run, never isolated — package-shadow lesson), byte-stable regeneration of EVERY derived artifact the branch touches (rebuild → byte-identical to committed), every validator/verifier, `validate_kg.py` if any data changed. Green gates are the floor, never the verdict.
2. **Fan out finders — one subagent per lens, in parallel** (Workflow tool when available, otherwise parallel Agent dispatches). Each finder gets the branch scope (`git diff main...HEAD`) plus ONE lens from the table below and returns candidate findings, each with file:line and a concrete failure scenario.
3. **Dedup candidates** across lenses (same file/line/claim → one candidate) before verifying.
4. **Adversarially verify every candidate** — a fresh subagent per candidate, prompted to REFUTE it empirically: against the committed artifact, against `git show main:` output, against the owner-reviewed spec (spec-conformant behaviour is not a finding). Three independent refuters for any candidate that would flip the verdict. Only confirmed findings reach the report. Under hard budget pressure: group Minor candidates into shared verifiers and disclose the degradation in APPROACH — never thin a verdict-flipping candidate below multiple independent verifications.
5. **Report contract** — the report has exactly these slots, in order:
   - APPROACH: one paragraph.
   - CONFIRMED FINDINGS: ranked Critical / Important / Minor, each with file:line and failure scenario.
   - REFUTED: one line per dropped candidate, with the refuting evidence.
   - GATES: each gate with its observed result.
   - VERDICT: Ready to merge YES / NO. NO while any confirmed Critical or Important is neither fixed nor explicitly owner-disclosed.

## Finder lenses (this repo's proven bug classes)

| Lens | Hunts |
|---|---|
| Removed behaviour | Anything main styled/produced/checked that the branch silently doesn't — diff the derived artifacts against `git show main:`, not just the source |
| Cross-artifact ordering | Emission, rule, and module order across generated outputs (first-match-wins semantics) |
| Whole-set coverage | Full-union membership: every item/row the old path owned is owned by the new path |
| Dead wiring | Defined-but-unreferenced macros/inputs/config (referenced-but-undefined is already the validators' job) |
| Data grounding | New data bricks: committed validator exists, `source_url` provenance, re-derivable from committed snapshots |
| Conventions | CLAUDE.md disciplines: report-not-fail on editorial data, single-source-of-truth duplication, plain labels |

Add lenses for whatever the branch uniquely touches; the table is the floor, not the ceiling.

## Red flags

| Thought | Reality |
|---|---|
| "All gates are green, so YES" | Gates check only what validators already encode. Both baseline YES verdicts had green gates and missed a Critical. |
| "Per-task reviews passed, a light pass is fine" | Every cross-task bug here passed all its per-task reviews. |
| "I read the whole diff myself" | Measured: one reader covers roughly a third of the real findings. |
| "Regression noticed — probably intended scope" | Intended means disclosed. An undisclosed regression is a finding until the owner accepts it. |
