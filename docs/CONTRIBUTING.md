# Contributing to Viral Ink
 
Thanks for your interest in contributing! Here's how to get started.
 
## Setup
 
```bash
git clone https://github.com/Sohamp2809/viral-ink.git
cd viral-ink
cp .env.example .env  # add your API keys
pip install -e ".[dev]"
pytest tests/ -v
```
 
## Adding a new content source
 
This is the easiest way to contribute. Create a new collector:
 
```python
# src/collectors/my_source_collector.py
from src.collectors.base import BaseCollector, ContentItem
 
class MySourceCollector(BaseCollector):
    @property
    def name(self) -> str:
        return "My Source"
 
    async def collect(self) -> list[ContentItem]:
        # Your collection logic here
        return [ContentItem(title="...", summary="...", url="...")]
```
 
Then add it to the collectors list in `src/main.py`.
 
## Project structure
 
- `src/collectors/` — Content sources (pluggable)
- `src/generator/agents/` — Multi-agent system (researcher, writer, critic)
- `src/persona/` — Voice fingerprinting
- `src/hooks/` — A/B hook variant generation
- `src/scorer/` — Virality scoring engine
- `src/delivery/` — Email delivery and scheduling
- `src/autopsy/` — Post performance tracking and learning
## Guidelines
 
- Run `ruff check .` before submitting
- Add tests for new features in `tests/`
- Keep prompts in `src/generator/prompts/` — treat them as important as code
- Don't hardcode API keys or secrets
## Pull requests
 
1. Fork the repo
2. Create a branch (`git checkout -b feature/my-feature`)
3. Make your changes
4. Run tests (`pytest tests/ -v`)
5. Submit a PR with a clear description