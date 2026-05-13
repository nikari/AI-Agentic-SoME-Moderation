# `features/` — Protected Gherkin specifications

This directory holds the **locked contract** for new project behaviour. Each `.feature`
file is a human-approved spec written in Gherkin (Given / When / Then). The
acceptance tests that bind to these files live in `tests/step_defs/`.

## The sacred rule

**Never edit a `.feature` file without explicit human approval.** The Claude Code
harness blocks writes to `features/**` via `.claude/settings.json` — that is the
real lock. Subagent prompts repeat the rule for defense in depth.

If a spec seems wrong, **fix the spec** (with human approval) — don't loosen the
test to match broken code.

## File layout

```
features/
  README.md
  <feature_name>.feature        ← Gherkin spec
tests/
  step_defs/
    __init__.py
    test_<feature_name>.py      ← pytest-bdd step definitions for the .feature
```

One `.feature` per user-visible capability. Many small scenarios beat fewer
complex ones.

## Naming

- File: `snake_case` matching the capability, e.g. `routing_initial.feature`.
- The matching step-defs module: `tests/step_defs/test_routing_initial.py`.
- The step-defs module's first non-import line should be
  `scenarios("../../features/routing_initial.feature")`.

## Writing a new spec

1. Don't write it yourself. Invoke `/spec-writer`, describe the desired behaviour,
   review the proposed Gherkin in chat.
2. When approved, save it manually to `features/<name>.feature`.
3. Invoke `/tdd-developer` with the new file as the target. It will write step
   defs and production code via Red → Green → Refactor.
4. Run `/quality-gate` before committing.

## What good scenarios look like

- **Domain language**, not implementation language.
  Good: `Given a flagged post with confidence 0.95`
  Bad:  `Given report.confidence == 0.95`
- **Observable outcomes** in Then clauses (return values, state, side effects).
  Good: `Then the case status is "blocked"`
  Bad:  `Then _finalize is called with status=BLOCKED`
- **Boundary cases** as their own scenarios (e.g. `confidence 0.30` exact, `0.31`,
  `0.29`).
- One **Feature** per file. Many **Scenarios** per Feature.

## Mapping to the project's domain

Use the vocabulary the codebase uses: `post`, `verdict` (`allowed` / `flagged`),
`confidence`, `violation` with categories (`crypto_scam`, `hate_speech`, …),
`route` (`auto_publish` / `single_review_final` / `hold_await_appeal`), `appeal
route`, `case`, `status` (`published` / `blocked` / `pending`). The
`/spec-writer` agent's prompt has the full glossary.
