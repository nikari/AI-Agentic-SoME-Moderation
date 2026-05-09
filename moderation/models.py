"""Single source of truth for LiteLLM model identifiers.

Use MODERATOR_MODEL / SUMMARIZER_MODEL in agent code.
Escalate to ESCALATION_MODEL only with an explicit reason.
Use CLASSIFIER_MODEL for cheap, high-volume classification steps.
"""

MODERATOR_MODEL = "anthropic/claude-sonnet-4-6"
SUMMARIZER_MODEL = "anthropic/claude-sonnet-4-6"
CLASSIFIER_MODEL = "anthropic/claude-haiku-4-5-20251001"
ESCALATION_MODEL = "anthropic/claude-opus-4-7"
