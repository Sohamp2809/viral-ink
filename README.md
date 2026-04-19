# LinkedIn Post Pilot

An AI agent that curates trending tech content and generates high-quality LinkedIn posts every morning — in **your** voice.

## What it does

Every day at 7 AM, the agent:
1. Scans RSS feeds, news APIs, and AI research for trending content
2. Ranks content by relevance, recency, and virality signals
3. Generates 7-10 LinkedIn posts using your **Persona DNA** — a fingerprint of your authentic writing voice
4. Scores each post's virality potential (0-100%)
5. Delivers everything to your inbox with hook variants and source links

You pick the best post, copy-paste, and publish. 2 minutes over coffee.

## Quick start

```bash
# 1. Clone and enter the project
git clone https://github.com/Sohamp2809/ghostwriter-ai.git
cd ghostwriter-ai

# 2. Set up environment
cp .env.example .env
# Edit .env with your API keys (at minimum: ANTHROPIC_API_KEY)

# 3. Install
pip install -e .

# 4. Onboard — teach the agent your voice
pilot onboard --file my_posts.txt
# Or paste posts interactively: pilot onboard

# 5. Verify your voice match
pilot calibrate

# 6. Run the pipeline
pilot run
```

### Docker

```bash
cp .env.example .env  # edit with your keys
docker compose up
```

## Commands

| Command | What it does |
|---------|-------------|
| `pilot run` | Full pipeline: collect → rank → generate → display |
| `pilot run -n 5 -e` | Generate 5 posts + send email |
| `pilot run -n 3 -p` | Generate 3 posts + preview email in browser |
| `pilot collect` | Just collect and rank content (no generation) |
| `pilot onboard` | Analyze your posts and build your Persona DNA |
| `pilot onboard -f posts.txt` | Load posts from a file (separated by `---`) |
| `pilot calibrate` | Test if generated posts match your voice |
| `pilot schedule` | Start daily scheduler (runs at 5 AM by default) |
| `pilot select ID` | Mark a post as published → queues 48h autopsy reminder |
| `pilot autopsy ID -r 500 -c 30` | Record actual post performance |
| `pilot learn` | Full feedback loop: scoring + persona + memory + hooks |
| `pilot analyze` | Deep pattern analysis across all autopsy data |
| `pilot digest` | Weekly performance summary |

## Persona DNA

The Persona DNA system is what makes posts sound like **you**, not a chatbot. During onboarding, the agent analyzes your sample posts and extracts 12 voice dimensions:

- **Tone**: formality, humor, vulnerability, assertiveness, optimism
- **Structure**: post length, paragraph length, emoji usage, formatting patterns
- **Content patterns**: storytelling ratio, data usage, opinion strength
- **Vocabulary**: technical depth, signature phrases, avoided words

These get converted into natural language rules injected into every generation prompt. The result: posts that match your authentic voice at your best.

Edit `config/persona_dna.yaml` anytime to fine-tune.

## Configuration

All config lives in `config/` as human-readable YAML:

- **`sources.yaml`** — RSS feeds, news API queries, topic priorities
- **`persona_dna.yaml`** — Your voice profile and sample posts
- **`angles.yaml`** — Content angle taxonomy (hot take, story, tutorial, etc.)

## Architecture

```
DAILY PIPELINE (5 AM → 7 AM)

  Layer 1: Content sourcing + trend radar
    RSS feeds → NewsAPI → LinkedIn viral → AI research
    ↓
  Layer 2: Context engine + content memory
    Deduplicate → summarize → rank → check memory → assemble
    ↓
  Layer 3: Multi-agent generation
    Researcher → Writer (with Persona DNA) → Critic → Revision
    ↓
  Layer 4: A/B hook variants + virality scoring
    3 hooks per post × 5-signal scoring engine
    ↓
  Layer 5: Quality gate + email delivery (7 AM)

ASYNC FEEDBACK (48h after publishing)
  Layer 6: Post autopsy → recalibrate scoring → refine persona
```

## Project structure

```
src/
├── cli.py              # CLI entry point
├── main.py             # Pipeline orchestrator
├── persona/            # Voice fingerprinting
│   ├── analyzer.py     # Extract voice dimensions from posts
│   ├── profile_builder.py
│   ├── prompt_injector.py
│   └── calibrator.py
├── collectors/         # Content sources (pluggable)
│   ├── base.py         # BaseCollector interface
│   ├── rss_collector.py
│   └── news_collector.py
├── generator/          # Post generation
│   ├── writer.py
│   └── prompts/
└── utils/
    ├── config.py       # Settings + YAML loading
    ├── llm.py          # LLM abstraction (Anthropic/OpenAI/Ollama)
    └── db.py           # Database models
```

## Adding a new content source

Implement the `BaseCollector` interface:

```python
from src.collectors.base import BaseCollector, ContentItem

class RedditCollector(BaseCollector):
    @property
    def name(self) -> str:
        return "Reddit"

    async def collect(self) -> list[ContentItem]:
        # Your collection logic here
        return [ContentItem(title="...", summary="...", url="...")]
```

Then add it to the pipeline in `src/main.py`.

## Roadmap

### v0.1 — Current release
- [x] **Phase 1**: Foundation + Persona DNA + basic generation
- [x] **Phase 2**: Multi-agent pipeline (researcher → writer → critic → revision)
- [x] **Phase 3**: Trend prediction radar (momentum scoring, HN velocity, Google Trends)
- [x] **Phase 4**: A/B hook variants + 5-signal virality scoring engine
- [x] **Phase 5**: Email delivery + daily scheduler
- [x] **Phase 6**: Post autopsy + self-improving feedback loop (scoring recalibration, persona DNA updates, hook learning, 48h reminder queue)

### v0.2 — Planned
- [ ] **Context engine** — full deduplication, summarization, and relevance ranking (`src/context/`)
- [ ] **Content memory graph** — topic suppression, angle exhaustion tracking, performance-aware ranking (`src/context/memory/`)
- [ ] **LinkedIn collector** — scrape viral posts from LinkedIn feed (`src/collectors/linkedin_collector.py`)
- [ ] **Social trend trackers** — HN comment velocity, Twitter/Reddit mention tracking (`src/collectors/trend_radar/`)
- [ ] **Quality gate** — plagiarism check, voice match enforcement, length validation (`src/delivery/quality_gate.py`)
- [ ] **Advanced scorer signals** — memory-boosted scoring, reference content scoring, trend momentum scoring (`src/scorer/`)
- [ ] **Hook preference tracker** — auto-learn from email click events (`src/hooks/preference_tracker.py`)
- [ ] **Persona auto-updater** — continuous voice refinement from published post feedback (`src/persona/updater.py`)
- [ ] **Docker one-command setup** — full production stack with scheduler as daemon

## Cost

~$15-25/month with Anthropic/OpenAI API. $0 with Ollama (local models).

## License
MIT
