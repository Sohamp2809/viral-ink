"""
Hook Strength Scorer — evaluates how likely a first line is to stop the scroll.

Scoring factors:
- Length (too short = weak, too long = loses attention)
- Technique strength (contrarian/stat > generic statement)
- Specificity (concrete > abstract)
- Emotional pull
"""

from __future__ import annotations

import re

from src.hooks.classifier import classify_hook


# Technique strength rankings (higher = more scroll-stopping)
_TECHNIQUE_SCORES = {
    "contrarian": 85,
    "statistic": 82,
    "personal_story": 78,
    "question": 72,
    "prediction": 75,
    "analogy": 77,
    "challenge": 80,
    "bold_statement": 68,
    "general": 55,
}

# Weak opener patterns that drag the score down
_WEAK_PATTERNS = [
    (r"^(i'?m excited|i'?m thrilled|i'?m happy|i'?m proud)", -25),
    (r"^(in today'?s|in the current|in this day)", -20),
    (r"^(let'?s dive|without further)", -15),
    (r"^(it'?s important to|it goes without saying)", -15),
    (r"^(as we all know|everyone knows)", -10),
    (r"\b(landscape|paradigm|ecosystem)\b", -8),
    (r"\b(excited to share|happy to announce|proud to)", -20),
]

# Strong signal patterns that boost the score
_STRONG_PATTERNS = [
    (r"\d+[%xk$€]", 8),          # specific numbers
    (r"^(stop |quit |don't )", 10),  # commands
    (r"\b(nobody|everyone is wrong|myth|lie|truth)\b", 8),  # contrarian signals
    (r"\b(billion|million|thousand)\b", 5),  # scale
    (r"[—–]", 3),                 # em-dash (signals punchy writing)
]


def score_hook(hook_line: str) -> int:
    """
    Score a hook line's strength from 0-100.

    Args:
        hook_line: The first line of the post

    Returns:
        Integer score 0-100
    """
    if not hook_line or not hook_line.strip():
        return 20

    text = hook_line.strip()

    # Base score from technique
    technique = classify_hook(text)
    score = _TECHNIQUE_SCORES.get(technique, 55)

    # Length penalty
    word_count = len(text.split())
    if word_count < 4:
        score -= 15  # too short to be interesting
    elif word_count > 25:
        score -= 10  # too long, loses attention
    elif 6 <= word_count <= 15:
        score += 5   # sweet spot

    # Check weak patterns
    text_lower = text.lower()
    for pattern, penalty in _WEAK_PATTERNS:
        if re.search(pattern, text_lower):
            score += penalty  # penalty is negative

    # Check strong patterns
    for pattern, bonus in _STRONG_PATTERNS:
        if re.search(pattern, text_lower):
            score += bonus

    # Specificity bonus: proper nouns / named entities
    proper_nouns = re.findall(r"\b[A-Z][a-z]+(?:\s[A-Z][a-z]+)*\b", text)
    if proper_nouns:
        score += min(len(proper_nouns) * 3, 10)

    return max(0, min(100, score))
