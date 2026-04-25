"""Intent extraction sub-package.

Public surface
--------------
``extract_intent``
    Async orchestrator — rule-based first, LLM fallback when confidence < 0.70.
``rule_based_extract``
    Synchronous deterministic parser (useful in tests and the router's
    fast path when no API key is available).
``IntentLlmError``
    Raised by the LLM layer on API failure or bad output.
"""

from .extractor import extract_intent
from .llm import IntentLlmError
from .rules import rule_based_extract

__all__ = ["IntentLlmError", "extract_intent", "rule_based_extract"]
