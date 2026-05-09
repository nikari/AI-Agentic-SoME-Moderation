"""Single source of truth for LiteLLM model identifiers.

Use MODERATOR_MODEL / SUMMARIZER_MODEL in agent code.
Escalate to ESCALATION_MODEL only with an explicit reason.
Use CLASSIFIER_MODEL for cheap, high-volume classification steps.
"""

MODERATOR_MODEL = "gemini/gemini-2.5-flash"
SUMMARIZER_MODEL = "gemini/gemini-2.5-flash"
CLASSIFIER_MODEL = "gemini/gemini-2.0-flash"
ESCALATION_MODEL = "gemini/gemini-2.5-pro"
