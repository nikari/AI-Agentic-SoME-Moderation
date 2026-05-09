# Aalto AI Social Media Moderation

Three-person Aalto course project building an agentic moderation system. MVP: detect cryptocurrency scams in text-based social media posts. Longer-term vision: general-purpose moderation that can take action and explain its decisions. Designed to align with the EU Digital Services Act — every moderation action must carry a statement of reasons (Art. 17).

This file is loaded automatically by Claude Code in every session. Keep it short and current.

## Pipeline

```
Post → moderate() → [ModerationResult, …] → summarize() → ModerationReport
                                                              │
                                                     route_initial()
                                                              ▼
                                ┌─────────────────────────────┼─────────────────────────────┐
                                ▼                             ▼                             ▼
                          AUTO_PUBLISH               SINGLE_REVIEW_FINAL              HOLD_AWAIT_APPEAL
                          (verdict=allowed)          (flagged, conf ≤ 0.30)          (flagged, conf > 0.30)
                                                                                              │
                                                                                  on appeal:  handle_appeal()
                                                                                              │
                                                                                    route_appeal(conf)
                                                                                              │
                                                       ┌──────────────────────────────────────┼──────────────────────────────────────┐
                                                       ▼                                      ▼                                      ▼
                                              AI_REEVAL (APPEAL_MODEL)             HUMAN_REVIEW                        HUMAN_REVIEW_WITH_PANEL
                                              (conf > 0.90)                        (0.70 < conf ≤ 0.90)                (conf ≤ 0.70)
                                              still > 0.90 → blocked               approve / deny                      approve / deny / 3-person panel
                                              else → re-route by new conf
```

- **`moderate()`** — one or more agents each return a `ModerationResult` (decision, reasoning, severity, scam category, confidence)
- **`summarize()`** — synthesises results into a final `ModerationReport` with a DSA Art. 17 explanation and recommended action
- **`routing.route_initial()`** / **`routing.route_appeal()`** — pure, deterministic routing functions over confidence
- **`appeal.handle_appeal()`** — orchestrates the appeal flow (AI re-eval, human review, optional 3-person panel)
- **`review.py`** — typed stubs for `single_review`, `panel_review`, `notify_sender`. The reviewer functions raise `NotImplementedError` until wired to a real UI; `notify_sender` prints to stdout

## Module layout

```
moderation/
  models.py          ← all model ID constants (import from here, never hardcode)
  schemas.py         ← shared Pydantic types (Post, ModerationResult, ModerationReport, Case, …)
  tracing.py         ← call setup_tracing() once at startup to enable Langfuse
  pipeline.py        ← run_pipeline(post) and run_pipeline_with_routing(post)
  routing.py         ← pure routing decisions over confidence (no I/O)
  appeal.py          ← handle_appeal(post, case): AI re-eval → human → panel
  review.py          ← stub interfaces for human reviewers + notify_sender
  agents/
    moderator.py     ← moderate(post) → list[ModerationResult]   [PERSON 1]
    summarizer.py    ← summarize(post, results) → ModerationReport  [PERSON 2]
tests/
  test_moderator.py
  test_summarizer.py
  test_pipeline.py
  test_routing.py
  test_appeal.py
scripts/
  run_pipeline.py    ← CLI: uv run python scripts/run_pipeline.py "<post text>" [--appeal]
```

## Parallel development

Two people can work independently:

| Person | File | Interface to respect |
|--------|------|----------------------|
| 1 — moderation agents | `moderation/agents/moderator.py` | `async def moderate(post: Post) -> list[ModerationResult]` |
| 2 — summary agent | `moderation/agents/summarizer.py` | `async def summarize(post: Post, results: list[ModerationResult]) -> ModerationReport` |

**Shared contract:** `moderation/schemas.py` — discuss before changing it.

## Tech stack

- **LiteLLM** — unified LLM interface; routes all calls to Google AI Studio (Gemini)
- **Pydantic** — all structured outputs, configs, and tool schemas
- **Langfuse** — tracing layer; every LLM call wraps through it so traces are consistent across teammates
- **pytest** — tests
- **ruff** — lint + format
- **uv** — environment & dependency management

## How to run things

```bash
# First-time setup
cp .env.example .env          # fill in API keys
uv sync                       # install all deps (includes dev group)

# Daily
pytest                        # run tests (no API keys needed — all mocked)
ruff check . && ruff format . # lint + format

# Try the pipeline end-to-end (needs real API keys)
uv run python scripts/run_pipeline.py "Buy MOONTOKEN now — 100x guaranteed!"
uv run python scripts/run_pipeline.py "..." --id post-123 --platform twitter

# Launch the Streamlit UI
uv run streamlit run scripts/app.py
```

## Coding conventions

- Type hints required everywhere
- Pydantic `BaseModel` for every structured boundary (LLM outputs, configs, tool schemas)
- Default model: `gemini/gemini-2.5-flash` (`MODERATOR_MODEL` / `SUMMARIZER_MODEL`). Escalate to `gemini/gemini-2.5-pro` only with an explicit reason (`ESCALATION_MODEL`, also exported as `APPEAL_MODEL` for the appeal AI re-evaluation step); use `gemini/gemini-2.0-flash` for cheap classification (`CLASSIFIER_MODEL`)
- Never bypass LiteLLM with raw `requests` / `httpx` calls to a provider
- Every committed LLM call goes through Langfuse — no untraced calls in the codebase
- Async by default for agent loops; sync only for scripts
- No silent `except Exception: pass` — narrow the catch or let it raise

## Domain glossary

- **Moderation action** — remove / flag / shadow-ban / escalate
- **Explanation** — the DSA Art. 17 statement of reasons attached to every action
- **Scam category** — taxonomy: rugpull, fake giveaway, impersonation, pump_and_dump, phishing, other
- **Moderator** vs **evaluator** — distinct agents; boundaries TBD

## Definition of done for a moderation feature

- Produces a structured Pydantic decision
- Attaches a DSA-compliant explanation
- Has at least one eval case
- Is traced through Langfuse

## Things to NOT do

- Don't commit `.env`, eval datasets, or Langfuse traces
- Don't hardcode model IDs in business logic — keep them in `moderation/models.py`
- Don't add new dependencies without updating `pyproject.toml`
- Don't write throwaway scripts in the repo root — put them in `scripts/`

## First-time setup

1. Copy `.env.example` → `.env` and fill in `GEMINI_API_KEY`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST`
2. `uv sync`
3. `pytest` to verify (all tests are mocked — no API keys needed)

## Links

- [Google AI Studio](https://aistudio.google.com/)
- [LiteLLM docs](https://docs.litellm.ai/)
- [Langfuse docs](https://langfuse.com/docs)
- [EU Digital Services Act (Regulation 2022/2065)](https://eur-lex.europa.eu/eli/reg/2022/2065/oj)
