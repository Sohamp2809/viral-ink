"""
Revision prompt — V2. Forces the writer to eliminate AI patterns
and make specific, impactful changes.
"""

REVISION_PROMPT = """Revise this LinkedIn post. The editor found real problems — fix ALL of them.

ORIGINAL DRAFT:
{original_text}

EDITOR'S FEEDBACK:
{revision_instructions}

SPECIFIC ISSUES TO FIX:
{issues}

AVOIDED WORDS FOUND (remove ALL of these — no exceptions):
{avoided_violations}

{voice_rules}

MANDATORY CHANGES:
1. If the post contains "Here's the thing" — rewrite the entire sentence. Don't just delete the phrase.
2. If the post contains "Let me break this down" — replace with a direct statement. Just SAY the thing.
3. If the post ends with "What do you think?" / "What's your take?" — end with a sharp declaration or a rhetorical question that makes a POINT.
4. If the post reads like a summary — pick ONE specific detail and build the entire post around it.
5. Remove any fabricated statistics.
6. Remove any avoided words and rephrase the surrounding sentence.
7. Vary your sentence lengths — if every sentence is 15-20 words, break some into 4-word fragments and extend others to 25 words.

THE REVISED POST MUST:
- Sound like a human wrote it at 11pm because they couldn't stop thinking about this topic
- Have at least one line that would make someone pause and re-read
- End with something MEMORABLE, not a question

Return valid JSON:
{{
  "post_text": "<the revised LinkedIn post>",
  "hook_line": "<the new first line>",
  "hashtags": ["#tag1", "#tag2"],
  "changes_made": "<brief summary of what you changed>"
}}"""
