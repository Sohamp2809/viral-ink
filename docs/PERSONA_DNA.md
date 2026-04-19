# Persona DNA — How Voice Fingerprinting Works

## The Problem

Every LinkedIn AI tool sounds the same. "Here's the thing." "Let me break this down." "What do you think?" These are AI tells that your audience recognizes instantly.

Persona DNA solves this by extracting a quantified fingerprint of YOUR writing voice and injecting it into every generation call.

## How It Works

### Step 1: Sample Collection

You provide 3-20 of your best LinkedIn posts via:
- `pilot onboard -f my_posts.txt` (file with posts separated by `---`)
- `pilot onboard` (paste interactively)

More posts = more accurate fingerprint. 10+ is ideal.

### Step 2: Voice Analysis

The agent sends your posts to an LLM with a structured analysis prompt that extracts 12 dimensions:

**Tone (4 dimensions)**
- `formality` (0-1): How casual vs. professional you sound
- `humor_frequency` (0-1): How often you use wit or humor
- `vulnerability` (0-1): Willingness to share failures and struggles
- `assertiveness` (0-1): How strongly you state opinions

**Structure (5 dimensions)**
- `avg_post_length`: Your typical character count
- `avg_paragraph_length`: Words per paragraph
- `line_break_frequency`: How often you use strategic line breaks
- `uses_emojis`: Boolean
- `uses_single_word_lines`: "Period." style emphasis

**Content Patterns (4 dimensions)**
- `storytelling_ratio`: How often you lead with stories
- `data_ratio`: How often you include specific numbers
- `opinion_ratio`: How often you take a clear stance
- `question_ending_ratio`: How often you end with questions

**Vocabulary**
- `technical_depth` (0-1): Layperson to deep technical
- `signature_phrases`: Phrases you naturally use
- `avoided_words`: Words you never use

### Step 3: Prompt Injection

These dimensions get converted to natural language rules:

```
YOUR VOICE — Follow these rules precisely:
- You write casually (formality: 0.3/1.0)
- You state opinions confidently. You don't hedge.
- You're willing to share failures and lessons learned.
- Target post length: 900 characters
- Keep paragraphs short: ~18 words max.
- Do NOT use emojis. Ever.
- NEVER use these words: "synergy", "leverage", "game-changer"
```

This block gets prepended to every writer agent call.

### Step 4: Calibration

Run `pilot calibrate` to test the match. The agent generates test posts and scores how well they match your real voice. Aim for 70%+.

### Step 5: Ongoing Refinement

After enough autopsy data (5+ posts), `pilot learn` updates the persona with:
- Strong/weak angles based on actual performance
- Hook technique preferences from your selections
- Content patterns that resonate with your audience

## Configuration

Edit `config/persona_dna.yaml` anytime. The file is human-readable YAML.

### Key Sections

```yaml
tone:
  formality: 0.35      # lower = more casual
  assertiveness: 0.75   # higher = stronger opinions

vocabulary:
  signature_phrases:     # the agent weaves these in naturally
    - "The real question is"
  avoided_words:         # hard-banned from all output
    - synergy
    - leverage

sample_posts:            # 3-5 of your best posts as few-shot examples
  - |
    Your post text here...
```

### Learned Preferences (auto-generated after `pilot learn`)

```yaml
learned_preferences:
  strong_angles: [hot_take, story]
  weak_angles: [tutorial, framework]
  hook_preferences:
    contrarian: 0.35
    question: 0.25
    statistic: 0.20
```

## Tips for Better Voice Matching

1. **Include diverse samples** — Don't just paste your viral posts. Include a story post, a technical post, an opinion post. The agent needs your full range.

2. **Edit after analysis** — After `pilot onboard`, open `persona_dna.yaml` and check if the numbers feel right. If the agent says your formality is 0.8 but you feel more casual, lower it.

3. **Update your avoided words** — If you see the agent using phrases you hate, add them to the list. This is cumulative.

4. **Re-run onboard periodically** — Your voice evolves. Every few months, paste your recent posts and re-analyze.