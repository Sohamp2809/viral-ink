"""
Prompt Injector — converts the persona_dna.yaml into natural language writing rules
that get injected into every generation prompt.

This is the bridge between the quantified profile and the LLM's understanding.
"""

from __future__ import annotations

from src.utils.config import load_persona


def _describe_range(value: float, low: str, mid: str, high: str) -> str:
    """Convert a 0-1 float into a human description."""
    if value < 0.33:
        return low
    elif value < 0.66:
        return mid
    return high


def build_voice_rules(persona: dict | None = None) -> str:
    """
    Convert persona DNA config into a natural language prompt block.

    Returns a ~200 word instruction block that gets prepended to writer prompts.
    """
    if persona is None:
        persona = load_persona()

    tone = persona.get("tone", {})
    structure = persona.get("structure", {})
    patterns = persona.get("content_patterns", {})
    vocab = persona.get("vocabulary", {})

    rules = []

    # ── Tone rules ────────────────────────
    formality = tone.get("formality", 0.5)
    rules.append(
        f"- You write {_describe_range(formality, 'casually and conversationally', 'with a balanced professional-casual tone', 'formally and professionally')}"
        f" (formality: {formality:.1f}/1.0)"
    )

    assertiveness = tone.get("assertiveness", 0.5)
    if assertiveness > 0.6:
        rules.append("- You state opinions confidently and directly. You don't hedge with 'maybe' or 'perhaps'.")
    elif assertiveness < 0.4:
        rules.append("- You present ideas as explorations, not declarations. You invite disagreement.")

    vulnerability = tone.get("vulnerability", 0.5)
    if vulnerability > 0.5:
        rules.append("- You're willing to share failures, mistakes, and lessons learned. Authenticity > perfection.")

    humor = tone.get("humor_frequency", 0.3)
    if humor > 0.5:
        rules.append("- You naturally weave in humor and wit. Your posts have personality.")
    elif humor < 0.2:
        rules.append("- You keep the tone serious and substantive. No forced humor.")

    # ── Structure rules ───────────────────
    avg_len = structure.get("avg_post_length", 900)
    rules.append(f"- Target post length: {avg_len} characters (range: {int(avg_len*0.8)}-{int(avg_len*1.3)})")

    para_len = structure.get("avg_paragraph_length", 18)
    rules.append(f"- Keep paragraphs short: ~{para_len} words max. One idea per paragraph.")

    if structure.get("uses_single_word_lines"):
        rules.append("- Use occasional single-word or single-phrase lines for emphasis.")

    if structure.get("uses_emojis") is False:
        rules.append("- Do NOT use emojis. Ever.")
    elif structure.get("uses_emojis"):
        rules.append("- Use emojis sparingly for visual breaks (1-3 per post max).")

    if structure.get("uses_numbered_lists"):
        rules.append("- Numbered lists work well in your style when listing 3+ items.")

    # ── Content pattern rules ─────────────
    story_ratio = patterns.get("storytelling_ratio", 0.3)
    if story_ratio > 0.35:
        rules.append("- You frequently open with a personal anecdote or mini-story before the insight.")

    data_ratio = patterns.get("data_ratio", 0.2)
    if data_ratio > 0.2:
        rules.append("- Include at least one specific number, stat, or data point per post.")

    question_ratio = patterns.get("question_ending_ratio", 0.5)
    if question_ratio > 0.4:
        rules.append("- End most posts with a question to drive comments.")

    # ── Vocabulary rules ──────────────────
    depth = vocab.get("technical_depth", 0.5)
    rules.append(
        f"- Technical depth: {_describe_range(depth, 'Keep it accessible — explain jargon', 'Balance technical and accessible language', 'You can go deep technical — your audience gets it')}"
    )

    sig_phrases = vocab.get("signature_phrases", [])
    if sig_phrases:
        phrases_str = ", ".join(f'"{p}"' for p in sig_phrases[:5])
        rules.append(f"- Naturally incorporate your signature phrases where they fit: {phrases_str}")

    avoided = vocab.get("avoided_words", [])
    if avoided:
        avoided_str = ", ".join(f'"{w}"' for w in avoided[:8])
        rules.append(f"- NEVER use these words/phrases: {avoided_str}")

    # ── Assemble ──────────────────────────
    rules_text = "\n".join(rules)

    return f"""YOUR VOICE — Follow these rules precisely to match the user's authentic writing style:

{rules_text}

Write as this person would at their best — polished but authentic, not robotic."""


def build_sample_posts_block(persona: dict | None = None) -> str:
    """
    Format sample posts as few-shot examples for the writer prompt.
    """
    if persona is None:
        persona = load_persona()

    samples = persona.get("sample_posts", [])
    # Filter placeholders
    real_samples = [
        s for s in samples
        if s and "Paste your" not in s and "sample post" not in s.lower()
    ]

    if not real_samples:
        return ""

    blocks = []
    for i, post in enumerate(real_samples[:3]):
        blocks.append(f"--- Example post {i+1} (MATCH THIS STYLE) ---\n{post.strip()}")

    return "REFERENCE POSTS — These are real posts by the user. Match their voice:\n\n" + "\n\n".join(blocks)
