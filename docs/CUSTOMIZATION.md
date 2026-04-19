# Customization Guide

## Content Sources

### Adding RSS Feeds

Edit `config/sources.yaml`:

```yaml
rss_feeds:
  - name: Your Blog Name
    url: https://example.com/feed.xml
    category: ai           # ai, software, tech, startups
    weight: 1.3             # 1.0 = normal, 1.5 = prioritized
```

### Adding a Custom Collector

Create a new file in `src/collectors/`:

```python
# src/collectors/reddit_collector.py
from src.collectors.base import BaseCollector, ContentItem

class RedditCollector(BaseCollector):
    @property
    def name(self) -> str:
        return "Reddit"

    async def collect(self) -> list[ContentItem]:
        # Your logic here
        return [
            ContentItem(
                title="Post title",
                summary="Post content or description",
                url="https://reddit.com/r/...",
                source_name="Reddit r/MachineLearning",
                category="ai",
            )
        ]
```

Then add it to `src/main.py`:

```python
from src.collectors.reddit_collector import RedditCollector

collectors = [
    RSSCollector(),
    NewsCollector(),
    RedditCollector(),  # add here
]
```

### Topic Filtering

Control what topics the agent writes about in `config/sources.yaml`:

```yaml
target_topics:
  - artificial intelligence
  - machine learning
  - software engineering
  - developer tools
  # Only articles mentioning these topics pass the filter
```

## Persona

### Manual Tuning

After `pilot onboard`, edit `config/persona_dna.yaml`:

```yaml
tone:
  formality: 0.35      # lower for casual, higher for professional
  assertiveness: 0.8    # how strongly you state opinions
  humor_frequency: 0.1  # 0 = no humor, 1 = constantly witty

vocabulary:
  avoided_words:         # add words you hate seeing in your posts
    - synergy
    - leverage
    - ecosystem
    - landscape
    - paradigm
```

### Sample Posts

The 3-5 sample posts in `persona_dna.yaml` are used as few-shot examples in every generation call. Update these periodically with your best recent posts.

## Scoring

### Adjusting Weights

After `pilot learn` creates `config/scoring_weights.yaml`, you can manually tune:

```yaml
weights:
  hook_strength: 0.20
  format_structure: 0.15
  engagement_driver: 0.15
  critic_quality: 0.30      # reduce if critic is too generous
  topic_timeliness: 0.20     # increase if trending topics matter more
```

Weights must sum to 1.0.

## Email

### Gmail SMTP

```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=you@gmail.com
SMTP_PASSWORD=your_app_password
EMAIL_TO=you@gmail.com
```

Generate an app password at https://myaccount.google.com/apppasswords

### Resend

```env
RESEND_API_KEY=re_xxxxx
EMAIL_TO=you@gmail.com
EMAIL_FROM=pilot@yourdomain.com
```

## LLM Provider

Switch providers by changing `.env`:

```env
# OpenAI
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-xxxxx

# Anthropic
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-xxxxx

# Local (free)
LLM_PROVIDER=ollama
OLLAMA_MODEL=llama3.1
```

Mix providers for cost optimization:

```env
LLM_PROVIDER=openai           # GPT-4o for writing (quality)
LLM_CHEAP_PROVIDER=openai     # GPT-4o-mini for analysis (cheap)
```