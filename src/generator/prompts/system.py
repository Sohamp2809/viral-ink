"""
Shared prompt templates used across multiple agents.
Agent-specific prompts live in their own files:
  researcher_prompt.py, writer_prompt.py, critic_prompt.py, revision_prompt.py
"""

# Template for formatting a single content item in the context window
CONTEXT_TEMPLATE = """--- [{i}] {title} ---
Source: {source} | Published: {published}
{summary}
"""
