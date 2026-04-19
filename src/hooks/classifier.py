"""
Hook Classifier — identifies which persuasion technique a hook line uses.
Used to ensure A/B variants use DIFFERENT techniques.
"""

from __future__ import annotations

import re

# Technique patterns (checked in order — first match wins)
_PATTERNS: list[tuple[str, list[str]]] = [
    ("question", [
        r"^(what|how|why|when|where|who|are we|is it|do you|can we|should)\b",
        r"\?$",
    ]),
    ("statistic", [
        r"\d+%", r"\d+x\b", r"\$\d+", r"€\d+", r"\d+ (out of|in|per)\b",
        r"\d+[kmb]\b",
    ]),
    ("contrarian", [
        r"\b(wrong|myth|overrated|isn't|aren't|won't|dead|illusion|flawed)\b",
        r"\b(unpopular|controversial|hot take|contrarian)\b",
        r"\b(stop|quit|don't)\b.*\b(doing|using|believing)\b",
    ]),
    ("prediction", [
        r"\b(will|future|by 20\d\d|next year|coming|soon|inevitable)\b",
        r"\b(predict|forecast|bet|expect)\b",
    ]),
    ("personal_story", [
        r"^(i |my |last |yesterday|a (few|couple) (years|months|weeks))",
        r"\b(learned|realized|discovered|failed|mistake|struggled)\b",
        r"^(when i|imagine|picture this|a decade ago)",
    ]),
    ("bold_statement", [
        r"^(the|this|it's|here's|there's)\b",
        r"\b(everything|nothing|always|never|only|most|biggest|worst|best)\b",
    ]),
]


def classify_hook(hook_line: str) -> str:
    """
    Classify a hook line into a persuasion technique.

    Returns one of: question, statistic, contrarian, prediction,
    personal_story, bold_statement, or 'general'.
    """
    if not hook_line:
        return "general"

    text = hook_line.strip().lower()

    for technique, patterns in _PATTERNS:
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return technique

    return "general"


# All available techniques for the generator to pick from
HOOK_TECHNIQUES = [
    "contrarian",
    "statistic",
    "personal_story",
    "bold_statement",
    "question",
    "prediction",
    "analogy",
    "challenge",
]

TECHNIQUE_DESCRIPTIONS = {
    "contrarian": "Challenge conventional wisdom with a surprising counter-argument",
    "statistic": "Lead with a specific, striking number or data point from the source",
    "personal_story": "Open with a brief personal anecdote or 'I once...' moment",
    "bold_statement": "Make a strong declarative claim that demands attention",
    "question": "Ask a provocative question that makes the reader think",
    "prediction": "Make a forward-looking claim about what will happen",
    "analogy": "Use an unexpected comparison to frame the topic",
    "challenge": "Directly challenge the reader's current approach or beliefs",
}
