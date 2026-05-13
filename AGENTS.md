# AGENTS.md

This project uses the **Disciplined Agentic Development** workflow.

- **Subagent definitions:** [`.claude/agents/`](.claude/agents/) — five role-scoped Claude Code agents.
- **Workflow doc:** [CLAUDE.md → Development workflow](CLAUDE.md#development-workflow).
- **Locked specs:** [`features/`](features/) — Gherkin scenarios. **Never edit without human approval.**
- **Quality gate:** `uv run python scripts/crap.py` — must pass before any commit.

For any AI assistant working in this repo:

1. Start new behaviour by invoking `/spec-writer` to draft a Gherkin spec in chat.
2. After the human approves and saves the `.feature` file, hand off to `/tdd-developer` for Red → Green → Refactor.
3. If complexity (CRAP score) goes over 15, hand off to `/crap-refactorer`.
4. Before committing, run `/quality-gate`.

Tool-specific entry points:

- **Claude Code** reads [CLAUDE.md](CLAUDE.md) automatically; subagents live in `.claude/agents/`.
- **Other agents** should treat CLAUDE.md as the canonical project brief.
