# Post Autopsy — The Self-Improving Feedback Loop

## Overview

The autopsy system is what makes LinkedIn Post Pilot different from every other content tool: it learns from your actual results and gets smarter over time.

Most AI content tools generate posts and forget about them. This agent tracks what you publish, records how it performs, analyzes what worked, and feeds those learnings back into every future generation.

## The Feedback Loop

```
Generate → Select → Publish → Wait 48h → Record metrics → Learn
    ↑                                                        |
    └────────────────────────────────────────────────────────┘
    Better scoring weights, persona preferences, content memory
```

## Step-by-Step Workflow

### 1. Select a post

After `pilot run` generates your daily posts, mark the one you publish:

```bash
pilot select 3 --hook B --technique contrarian
```

This does three things:
- Marks post #3 as selected in the database
- Records that you chose hook variant B (contrarian technique)
- Queues a 48-hour autopsy reminder

### 2. Publish on LinkedIn

Copy the post and publish it normally. Wait 48 hours for engagement to stabilize.

### 3. Record performance

Check your LinkedIn analytics and record the numbers:

```bash
pilot autopsy 3 --reactions 450 --comments 28 --shares 12 --impressions 8000
```

The agent will:
- Convert raw metrics to an engagement score (0-100%)
- Compare predicted virality vs actual performance
- Use an LLM to analyze what specifically worked and what didn't
- Save everything to the database

### 4. Run the feedback loop

After 5+ autopsy reports:

```bash
pilot learn
```

This runs 4 updates:

| Step | What it does | Minimum data needed |
|------|-------------|-------------------|
| Recalibrate scoring weights | Adjusts which signals best predict engagement | 10 reports |
| Update persona DNA | Identifies strong/weak angles for your audience | 5 reports |
| Update content memory | Tracks topic-level performance | Any reports |
| Learn hook preferences | Detects which hook techniques you prefer | 10 selections |

### 5. Analyze patterns

For deeper insights:

```bash
pilot analyze --days 30
```

This runs an LLM analysis across all your autopsy data to detect patterns:
- Which angles consistently outperform
- Which topics your audience responds to
- Where the scoring model is most inaccurate
- Structural patterns that correlate with engagement

### 6. Weekly digest

```bash
pilot digest
```

Summary of the last 7 days: total posts, selection rate, prediction accuracy, best/worst performers, and angle performance breakdown.

## Autopsy Reminders

When you run `pilot select`, a 48-hour timer starts. The next time you run `pilot run`, it will remind you:

```
📋 1 autopsy reminder(s)
  Post 3: AI Agent Memory — published 48h+ ago
  Run: pilot autopsy 3 -r <reactions> -c <comments> -s <shares>
```

If email is configured, you'll also get a reminder email.

## Engagement Score Calculation

Raw LinkedIn metrics are converted to a 0-100 score using weighted engagement rate:

```
engagement = (reactions × 1.0) + (comments × 3.0) + (shares × 5.0)
rate = engagement / impressions
```

Comments are weighted 3x and shares 5x because they indicate deeper engagement than reactions.

| Engagement Rate | Score Range | Interpretation |
|----------------|-------------|----------------|
| 10%+ | 90-100 | Exceptional — went viral |
| 5-10% | 70-90 | Excellent performance |
| 2-5% | 40-70 | Above average |
| 0-2% | 0-40 | Below average |

If you don't have impression data, the system estimates from reaction count.

## What Gets Learned

### Scoring Weights
The agent tracks prediction error across posts. If it consistently over-predicts (scores posts high but they underperform), it reduces the weight of the signals causing inflation. If it under-predicts, it boosts signals that correlate with actual performance.

### Persona Preferences
After enough data, the agent knows:
- Your strong angles (e.g. "hot_take posts average 82% engagement for your audience")
- Your weak angles (e.g. "tutorial posts average 41% — your audience prefers opinions over instruction")

These preferences are saved to `persona_dna.yaml` and influence future content selection.

### Hook Preferences
The agent tracks which hook variant (A/B/C) you choose and which techniques (contrarian, question, statistic, etc.) you gravitate toward. Over time, hook generation biases toward your preferred techniques.

### Content Memory
Topic-level performance data is stored in the memory graph. High-performing topics get a subtle boost in future content selection. Low-performing topics get deprioritized.

## Data Storage

All autopsy data is stored in SQLite:
- `autopsy_reports` table: individual post analysis
- `hook_selections` table: hook variant choices
- `pending_autopsies.json`: queue of posts awaiting performance review
- `persona_dna.yaml`: learned preferences (updated by `pilot learn`)
- `scoring_weights.yaml`: calibrated signal weights (updated by `pilot learn`)