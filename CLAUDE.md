# Aalto AI Social Media Moderation

Three-person Aalto course project building an agentic moderation system. MVP: detect cryptocurrency scams in text-based social media posts. Longer-term vision: general-purpose moderation that can take action and explain its decisions. Designed to align with the EU Digital Services Act — every moderation action must carry a statement of reasons (Art. 17).

This file is loaded automatically by Claude Code in every session. Keep it short and current.

## Tech stack

- **Anthropic SDK** — provider-specific Claude features (citations, files, extended thinking)
- **LiteLLM** — unified LLM interface for everything else (provider switching, eval comparisons)
- **Pydantic** — all structured outputs, configs, and tool schemas
- **Langfuse** — tracing layer; every LLM call wraps through it so traces are consistent across teammates
- **pytest** — tests
- **ruff** — lint + format
- **uv** — environment & dependency management

## How to run things

```bash
uv sync                          # set up environment
pytest                           # run tests
ruff check . && ruff format .    # lint + format
python -m moderation.agent ...   # run the agent (TBD)
python -m moderation.eval ...    # run the eval harness (TBD)
```

Replace the `python -m ...` placeholders as those modules land.

## Coding conventions

- Type hints required everywhere
- Pydantic `BaseModel` for every structured boundary (LLM outputs, configs, tool schemas)
- Default model: `claude-sonnet-4-6` (Sonnet 4.6). Escalate to `claude-opus-4-7` only with an explicit reason; use `claude-haiku-4-5` for cheap classification
- Never bypass LiteLLM with raw `requests` / `httpx` calls to a provider
- Every committed LLM call goes through Langfuse — no untraced calls in the codebase
- Async by default for agent loops; sync only for scripts
- No silent `except Exception: pass` — narrow the catch or let it raise

## Domain glossary

- **Moderation action** — remove / flag / shadow-ban / escalate
- **Explanation** — the DSA Art. 17 statement of reasons attached to every action
- **Scam category** — taxonomy: rugpull, fake giveaway, impersonation, … (final list TBD)
- **Moderator** vs **evaluator** — distinct agents; boundaries TBD

## Definition of done for a moderation feature

- Produces a structured Pydantic decision
- Attaches a DSA-compliant explanation
- Has at least one eval case
- Is traced through Langfuse

## Things to NOT do

- Don't commit `.env`, eval datasets, or Langfuse traces
- Don't hardcode model IDs in business logic — keep them in a single `models.py` constant
- Don't add new dependencies without updating `pyproject.toml`
- Don't write throwaway scripts in the repo root — put them in `scripts/`

## First-time setup

1. Copy `.env.example` → `.env` and fill in `ANTHROPIC_API_KEY`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST`
2. `uv sync`
3. `pytest` to verify

## Links

- [Anthropic SDK docs](https://docs.anthropic.com/)
- [LiteLLM docs](https://docs.litellm.ai/)
- [Langfuse docs](https://langfuse.com/docs)
- [EU Digital Services Act (Regulation 2022/2065)](https://eur-lex.europa.eu/eli/reg/2022/2065/oj)
