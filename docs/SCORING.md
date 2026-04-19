# Virality Scoring — Methodology

## Overview

Every generated post receives a virality prediction score from 0-100%, computed from 5 independent signals. The score represents the agent's best estimate of how likely this post is to get above-average engagement on LinkedIn.

## The 5 Signals

### 1. Hook Strength (20% weight)

Evaluates the opening line's scroll-stopping potential using rule-based analysis:

- **Technique classification**: Contrarian hooks score higher than generic statements
- **Specificity bonus**: Proper nouns, numbers, and concrete details boost the score
- **Length sweet spot**: 6-15 words performs best
- **Weak pattern detection**: "I'm excited to share..." = automatic penalty
- **Strong pattern detection**: Numbers, commands, contrarian signals = bonus

Score range: 0-100. Typical: 55-85.

### 2. Format & Structure (15% weight)

Evaluates how well the post is optimized for LinkedIn's reading experience:

- **Length**: 800-1200 characters is the sweet spot (+15). Under 400 or over 2000 gets penalized.
- **Paragraph density**: 4+ short paragraphs > 1 wall of text
- **Avg paragraph length**: Under 25 words = scannable (+8)
- **Punchy lines**: Single-word emphasis lines get a bonus
- **Hashtag count**: 2-3 is optimal. 5+ looks spammy.
- **No external links**: LinkedIn's algorithm penalizes posts with URLs in the body

Score range: 0-100. Typical: 60-90.

### 3. Engagement Driver (15% weight)

Evaluates how likely the post is to generate comments and shares:

- **CTA quality**: "What strategies have you..." (+15) > "What do you think?" (+5) > no question (-10)
- **Shareability signals**: Frameworks, templates, numbered lists get bonus
- **Emotional resonance**: Vulnerability, lessons learned, breakthroughs
- **Controversy potential**: "Hot take", "agree or disagree" drive comments
- **Strong close**: Short punchy ending with a question > trailing off

Score range: 0-100. Typical: 40-70.

### 4. Critic Quality (30% weight)

The LLM critic's overall assessment across 7 dimensions, converted from 0-10 to 0-100 scale:

- Hook strength, voice match, substance, structure, engagement driver, originality, factual integrity
- This is the highest-weighted signal because the LLM evaluates holistic quality that rule-based scorers can't capture
- The critic also catches AI patterns, fabricated statistics, and avoided words

Score range: 0-100. Typical: 50-80.

### 5. Topic Timeliness (20% weight)

Uses the trend radar's momentum data:

- **EMERGING** trend: 60-100 (best time to post — catching the wave)
- **PEAKING** trend: 40-80 (still good, more competition)
- **SATURATED** trend: 20-40 (everyone posted already)
- **STABLE** / no data: 50 (neutral for evergreen topics)

Score range: 20-100. Typical: 50-100.

## Composite Score

```
virality = (hook × 0.20) + (format × 0.15) + (engagement × 0.15) 
         + (critic × 0.30) + (timeliness × 0.20)
```

## Tiers

| Score | Tier | What it means |
|-------|------|---------------|
| 80-100% | EXCELLENT | Top-tier post, publish with confidence |
| 65-79% | GOOD | Solid post, likely to perform above average |
| 50-64% | AVERAGE | Decent but won't stand out — consider improvements |
| 0-49% | WEAK | Needs significant work or skip entirely |

## Weight Auto-Tuning

After 10+ autopsy reports, `pilot learn` recalibrates weights based on which signals best predict actual engagement:

- If topic_timeliness consistently correlates with high engagement → its weight increases
- If critic_quality over-predicts → its weight decreases
- Weights are stored in `config/scoring_weights.yaml` and can be manually edited

## Transparency

Every score includes:
- **Breakdown**: Individual scores per signal
- **Weights**: How much each signal contributed
- **Reasoning**: Human-readable explanation ("Strong hook. Timely EMERGING trend. Weak CTA.")

No black boxes. If a score seems wrong, you can see exactly why.