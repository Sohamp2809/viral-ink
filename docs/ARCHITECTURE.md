# LinkedIn Post Pilot — Enhanced Blueprint v2

## What changed from v1

Six enhancements are now core systems, not add-ons:

| # | Enhancement | Where it lives | Why it matters |
|---|------------|----------------|----------------|
| 1 | Persona DNA fingerprint | Onboarding + every generation call | Posts sound like YOU, not a chatbot |
| 2 | Multi-agent debate | Replaces single-shot generation | Dramatically better writing quality |
| 3 | Trend prediction radar | Integrated into content sourcing | Catch waves early, not late |
| 4 | Content memory graph | Built into context engine | Never repeat yourself |
| 6 | A/B hook variants | Added between generation and scoring | Pick the best opening every time |
| 10 | Post autopsy reports | New feedback layer after delivery | Closes the loop — agent gets smarter |

---

## System overview

The agent runs a daily pipeline with 7 layers, plus a one-time onboarding step and an async feedback loop:

```
ONBOARDING (once)
  └── Persona DNA fingerprint

DAILY PIPELINE (5:00 AM → 7:00 AM)
  Layer 1 → Content sourcing + trend radar
  Layer 2 → Context engine + content memory graph
  Layer 3 → Multi-agent generation (researcher → writer → critic → revision)
  Layer 4 → A/B hook variants + virality scoring
  Layer 5 → Quality gate + formatting
  Layer 6 → Email delivery

ASYNC FEEDBACK (48h after each published post)
  Layer 7 → Post autopsy → feeds back into scoring + memory + persona
```

---

## Layer 0 · Persona DNA fingerprint

### Purpose
Extract a quantifiable writing fingerprint from your existing LinkedIn posts so every generated post matches your authentic voice.

### Onboarding flow

**Step 1 — Collect samples**
The user provides 10–20 of their best-performing LinkedIn posts. Three input methods:
- Paste directly into a CLI prompt or web form.
- Upload a CSV/JSON file with post text and engagement metrics.
- Auto-scrape from user's LinkedIn profile (with Playwright + user's cookies or LinkedIn API OAuth).

**Step 2 — Analyze voice dimensions**
Run each post through an LLM analysis call that extracts 12 voice dimensions:

```yaml
# persona_dna.yaml (auto-generated, user can edit)
voice_profile:
  tone:
    formality: 0.35          # 0 = casual, 1 = formal
    humor_frequency: 0.6      # how often humor appears
    vulnerability: 0.7        # willingness to share failures/struggles
    assertiveness: 0.8        # strength of opinions

  structure:
    avg_post_length: 890      # characters
    avg_paragraph_length: 18  # words
    line_break_frequency: 3.2 # breaks per 100 words
    uses_emojis: false
    uses_numbered_lists: true
    uses_single_word_lines: true  # "Period." style emphasis

  content_patterns:
    storytelling_ratio: 0.4   # % of posts that lead with a story
    data_ratio: 0.25          # % that include specific numbers/stats
    opinion_ratio: 0.35       # % that take a clear stance
    question_ending_ratio: 0.6 # % that end with a question

  vocabulary:
    signature_phrases:         # phrases you use often
      - "Here's the thing"
      - "Let me break this down"
      - "hot take:"
    avoided_words:             # words you never use
      - "synergy"
      - "leverage"
      - "game-changer"
    technical_depth: 0.7       # 0 = accessible, 1 = deep technical
```

**Step 3 — Generate voice rules**
Convert the quantified profile into natural language rules that get injected into every generation prompt:

```
Your writing voice rules (derived from your past posts):
- You write casually (formality: 0.35) but with strong opinions (assertiveness: 0.8)
- You frequently share personal failures and lessons learned (vulnerability: 0.7)
- Your posts average 890 characters with short paragraphs (~18 words each)
- You use line breaks every ~30 words for scannability
- You never use emojis but you DO use single-word emphasis lines
- 40% of your posts open with a personal story
- You end 60% of posts with a question to drive comments
- You use phrases like "Here's the thing" and "hot take:" naturally
- You avoid corporate buzzwords: "synergy", "leverage", "game-changer"
- Your technical depth is high — you explain mechanisms, not just outcomes
```

**Step 4 — Validation**
Generate 3 test posts and show them to the user alongside their real posts. Ask: "Can you tell which ones are yours?" If the user can easily distinguish them, refine the profile. This is a one-time calibration that takes ~10 minutes.

### Ongoing refinement
Every time the user selects a post from the email (Layer 6) or provides autopsy feedback (Layer 7), the persona DNA updates slightly. Over weeks, the fingerprint converges to an increasingly accurate representation.

### Implementation

```
src/persona/
├── __init__.py
├── analyzer.py          # Extract voice dimensions from sample posts
├── profile_builder.py   # Generate persona_dna.yaml
├── prompt_injector.py   # Convert profile → natural language rules for LLM
├── calibrator.py        # Validation test generation
└── updater.py           # Incremental refinement from feedback
```

**Key technical decisions:**
- Store the voice profile as YAML (human-readable, editable).
- Use cosine similarity between generated posts and user samples as a "voice match score" — reject posts below 0.7 similarity.
- The prompt injection is a ~200-word block prepended to every writer agent call. It's not in the system prompt (which stays constant) — it's in the user message alongside the context window.

---

## Layer 1 · Content sourcing + trend prediction radar

### Standard collectors (unchanged from v1)
- **Tech blogs:** RSS feeds from HN top 30, TechCrunch, The Verge, MIT Tech Review, a16z, etc.
- **News APIs:** NewsAPI.org / GNews filtered by tech keywords.
- **LinkedIn viral posts:** Scrape top 50–100 creators, extract posts with >500 reactions.
- **AI innovation:** arXiv (cs.AI/CL/LG), Product Hunt daily top 5, GitHub trending.

### NEW: Trend prediction radar

The radar doesn't just measure what IS trending — it detects what's ABOUT TO trend.

**Momentum scoring algorithm:**

```python
def compute_trend_momentum(topic: str, snapshots: list[Snapshot]) -> TrendScore:
    current = snapshots[-1].mentions
    six_hours_ago = snapshots[-6].mentions if len(snapshots) >= 6 else 0
    twenty_four_ago = snapshots[-24].mentions if len(snapshots) >= 24 else 0

    velocity_6h = (current - six_hours_ago) / max(six_hours_ago, 1)
    velocity_prior = (six_hours_ago - twenty_four_ago) / max(twenty_four_ago, 1)
    acceleration = velocity_6h - velocity_prior

    if velocity_6h > 2.0 and acceleration > 0:
        phase = "EMERGING"
    elif velocity_6h > 1.0 and acceleration <= 0:
        phase = "PEAKING"
    elif velocity_6h < 0.5 and current > 1000:
        phase = "SATURATED"
    else:
        phase = "STABLE"

    momentum_score = (velocity_6h * 0.5 + acceleration * 0.3 +
                      min(current / 1000, 1) * 0.2)

    return TrendScore(topic=topic, momentum=momentum_score, phase=phase,
                      velocity=velocity_6h, acceleration=acceleration,
                      current_mentions=current)
```

**How the radar changes content selection:**
- EMERGING topics get a 2x weight boost in the relevance ranking (Layer 2).
- PEAKING topics get normal weight but the agent finds a unique angle.
- SATURATED topics get a 0.5x penalty unless genuinely contrarian.
- The daily email includes a "Trend radar" section showing 3–5 emerging topics.

---

## Layer 2 · Context engine + content memory graph

### Standard context processing
- **Deduplication:** MinHash + LSH, 0.7 Jaccard threshold.
- **Summarization:** Claude Haiku produces 3–5 sentence summaries.
- **Relevance ranking:** 4-signal scoring (recency, virality, topic alignment, novelty).

### NEW: Content memory graph

The memory graph is a persistent knowledge store tracking everything the agent has ever covered.

**Memory-aware content selection rules:**

```python
def apply_memory_filter(candidates, memory):
    for candidate in candidates:
        node = memory.get(candidate.primary_topic)
        if node is None:
            candidate.score *= 1.3  # fresh topic bonus
            continue
        days_since = (now() - node.last_covered).days
        if days_since < 3:
            candidate.score *= 0.1   # hard suppress
        elif days_since < 7:
            candidate.score *= 0.7 if node.angles_remaining else 0.2
        elif days_since >= 21:
            candidate.score *= 1.1   # fresh again
    return sorted(candidates, key=lambda c: c.score, reverse=True)
```

---

## Layer 3 · Multi-agent content generation

Three specialized agents collaborate with a revision loop:

1. **Researcher** (Haiku) — selects 7–10 content opportunities with angle + thesis
2. **Writer** (Sonnet) — drafts each post following persona DNA + sample posts; runs 7–10x in parallel
3. **Critic** (Haiku) — scores 6 dimensions; verdict = PUBLISH / REVISE / REJECT
4. **Revision** (Sonnet) — writer revises based on critic's specific instructions; ~5 revision calls/day

**Cost per daily run: ~$0.30–0.45 | ~$10–14/month**

---

## Layer 4 · A/B hooks + virality scoring

For each post, generate 2 alternative openings (Hook B, Hook C) using different techniques:
contrarian, statistic, confession, prediction, rhetorical question, mini-story.

**5-signal virality score:**
- Reference content performance: 30% (EMERGING sources get 1.3x)
- Hook strength: 20% (score all 3 variants, use max)
- Format/structure: 15% (length, paragraph density, voice match)
- Topic timeliness: 20% (uses trend radar momentum directly)
- Engagement driver: 15% (CTA quality, memory historical performance boost)

---

## Layer 5 · Quality gate

- Plagiarism: cosine similarity to source < 0.85
- Voice match: embedding similarity to user samples ≥ 0.65
- Length: 600–1500 chars
- Register topic+angle in memory graph (even if not published)
- Move URLs to "post in comments" suggestion

---

## Layer 6 · Email delivery

Daily email at 7:00 AM with trend radar section, 7–10 posts sorted by virality score with 3 hook variants each, and "I'll use this" click tracking that starts the 48h autopsy timer.

---

## Layer 7 · Post autopsy

48h after selection: scrape LinkedIn performance → LLM analysis → feeds back into:
- Scoring weights (recalibrate every 2 weeks via Pearson correlation)
- Content memory (update avg_performance per topic)
- Persona DNA (update hook technique preferences)
- Weekly autopsy digest email (Sunday evening)

---

## Database schema

```sql
CREATE TABLE memory_nodes (
    id SERIAL PRIMARY KEY,
    topic VARCHAR(255) UNIQUE NOT NULL,
    category VARCHAR(100),
    times_covered INTEGER DEFAULT 0,
    last_covered TIMESTAMP,
    angles_used JSONB DEFAULT '[]',
    angles_remaining JSONB DEFAULT '[]',
    avg_performance FLOAT,
    tags JSONB DEFAULT '[]',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE trend_snapshots (
    id SERIAL PRIMARY KEY,
    topic VARCHAR(255) NOT NULL,
    source VARCHAR(50) NOT NULL,
    mention_count INTEGER NOT NULL,
    captured_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE generated_posts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pipeline_date DATE NOT NULL,
    topic VARCHAR(255),
    angle VARCHAR(50),
    trend_phase VARCHAR(20),
    post_text TEXT NOT NULL,
    hook_a TEXT, hook_b TEXT, hook_c TEXT,
    virality_score FLOAT,
    score_breakdown JSONB,
    critic_verdict VARCHAR(20),
    voice_match_score FLOAT,
    was_selected BOOLEAN DEFAULT FALSE,
    hook_variant_used CHAR(1),
    selected_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE autopsy_reports (
    id SERIAL PRIMARY KEY,
    post_id UUID REFERENCES generated_posts(id),
    reactions INTEGER,
    comments INTEGER,
    shares INTEGER,
    impressions INTEGER,
    actual_engagement_score FLOAT,
    prediction_error FLOAT,
    what_worked TEXT,
    what_didnt TEXT,
    lesson TEXT,
    analyzed_at TIMESTAMP DEFAULT NOW()
);
```

---

## Implementation roadmap (12 weeks)

| Phase | Weeks | Milestone |
|-------|-------|-----------|
| 1 | 1–2 | Persona DNA + basic collectors + single-agent generation |
| 2 | 3–4 | Multi-agent pipeline + content memory graph |
| 3 | 5–6 | Trend radar + all collectors |
| 4 | 7–8 | A/B hooks + full 5-signal scoring engine |
| 5 | 9 | Email delivery + quality gate + cron scheduling |
| 6 | 10–11 | Post autopsy + feedback loop |
| 7 | 12 | Open source polish + docs + Docker one-command setup |

---

## Key design principles

1. **The agent gets smarter every week** — autopsy → calibration loop
2. **Transparency over black boxes** — every score has a breakdown, weights in YAML
3. **Your voice, not the agent's** — persona DNA + voice match score in critic
4. **Catch waves, not tails** — EMERGING topics prioritized
5. **Never repeat yourself** — content memory graph
6. **Choice over automation** — user picks from 7–10 options, agent never auto-posts
