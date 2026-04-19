"""
Email Builder — V3. Cleaner, more user-friendly HTML email with stronger guidance.
Designed for Gmail, Outlook, and Apple Mail compatibility.
"""

from __future__ import annotations

import html
import logging
from datetime import datetime, timezone

from src.collectors.trend_radar.momentum import TrendScore
from src.generator.orchestrator import FinalPost

logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# Scoring helpers
# -----------------------------------------------------------------------------
def _score_color(pct: int) -> str:
    if pct >= 80:
        return "#059669"  # emerald
    if pct >= 65:
        return "#4f46e5"  # indigo
    if pct >= 50:
        return "#d97706"  # amber
    return "#dc2626"      # red


def _score_bg(pct: int) -> str:
    if pct >= 80:
        return "#ecfdf5"
    if pct >= 65:
        return "#eef2ff"
    if pct >= 50:
        return "#fffbeb"
    return "#fef2f2"


def _tier_label(pct: int) -> str:
    if pct >= 80:
        return "EXCELLENT"
    if pct >= 65:
        return "GOOD"
    if pct >= 50:
        return "AVERAGE"
    return "WEAK"


def _trend_emoji(phase: str) -> str:
    return {
        "EMERGING": "🔴",
        "PEAKING": "🟡",
        "SATURATED": "⚪",
        "STABLE": "🟢",
    }.get(phase, "")


# -----------------------------------------------------------------------------
# Safe formatting helpers
# -----------------------------------------------------------------------------
def _safe_text(value: object) -> str:
    if value is None:
        return ""
    return html.escape(str(value))


def _safe_html_with_breaks(text: str) -> str:
    safe = _safe_text(text)
    safe = safe.replace("\r\n", "\n")
    safe = safe.replace("\n\n", "<br><br>")
    safe = safe.replace("\n", "<br>")
    return safe


def _safe_attr_list(items: list[str] | None) -> list[str]:
    if not items:
        return []
    return [str(x) for x in items if x]


# -----------------------------------------------------------------------------
# Public builder
# -----------------------------------------------------------------------------
def build_email_html(
    posts: list[FinalPost],
    trends: list[TrendScore],
    date: datetime | None = None,
) -> tuple[str, str]:
    """Build the complete HTML email. Returns (subject, html_body)."""
    if date is None:
        date = datetime.now(timezone.utc)

    date_str = date.strftime("%A, %B %d")
    top_score = posts[0].virality_pct if posts else 0
    subject = f"Your {len(posts)} LinkedIn posts for {date_str} — Top pick: {top_score}%"

    recommendation_section = _build_recommendation_section(posts[0] if posts else None)
    stats_section = _build_stats_bar(posts)
    helper_section = _build_posting_helper_section()
    trend_section = _build_trend_section(trends)
    posts_html = "\n".join(
        _build_post_card(index=i, post=post, total_posts=len(posts))
        for i, post in enumerate(posts, 1)
    )
    empty_state = _build_empty_state() if not posts else ""

    html_body = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta http-equiv="x-ua-compatible" content="ie=edge">
  <title>{_safe_text(subject)}</title>
</head>
<body style="margin:0;padding:0;background:#f4f7fb;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif;-webkit-font-smoothing:antialiased;word-spacing:normal;">

<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#f4f7fb;margin:0;padding:0;">
  <tr>
    <td align="center" style="padding:32px 16px;">

      <table role="presentation" width="640" cellpadding="0" cellspacing="0" border="0" style="max-width:640px;width:100%;">

        <tr>
          <td style="background:#ffffff;border:1px solid #e2e8f0;border-bottom:none;border-radius:20px 20px 0 0;padding:32px 32px 20px;">
            <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
              <tr>
                <td valign="top">
                  <div style="font-size:11px;font-weight:700;letter-spacing:2px;color:#4f46e5;text-transform:uppercase;margin-bottom:8px;">LinkedIn Post Pilot</div>
                  <div style="font-size:28px;font-weight:800;color:#0f172a;line-height:1.2;">Your LinkedIn posts are ready</div>
                  <div style="font-size:15px;color:#64748b;line-height:1.6;margin-top:8px;">
                    I reviewed today's post candidates and ranked them by virality, structure, and trend timing.
                  </div>
                  <div style="font-size:13px;color:#94a3b8;margin-top:8px;">{_safe_text(date_str)}</div>
                </td>
                <td width="110" align="right" valign="top">
                  <div style="background:#eef2ff;border:1px solid #c7d2fe;border-radius:16px;padding:14px 16px;text-align:center;">
                    <div style="font-size:30px;font-weight:800;color:#4f46e5;line-height:1;">{top_score}%</div>
                    <div style="font-size:10px;font-weight:700;color:#4338ca;letter-spacing:1px;margin-top:4px;">TOP PICK</div>
                  </div>
                </td>
              </tr>
            </table>
          </td>
        </tr>

        {recommendation_section}
        {stats_section}
        {helper_section}
        {trend_section}
        {posts_html}
        {empty_state}

        <tr>
          <td style="background:#ffffff;border:1px solid #e2e8f0;border-top:none;border-radius:0 0 20px 20px;padding:24px 32px;text-align:center;">
            <div style="font-size:13px;color:#64748b;line-height:1.6;">
              Generated by <span style="color:#4f46e5;font-weight:700;">LinkedIn Post Pilot</span><br>
              Pick your favorite post, copy it, and publish it while the topic is still fresh.
            </div>
          </td>
        </tr>

      </table>
    </td>
  </tr>
</table>

</body>
</html>"""

    return subject, html_body


# -----------------------------------------------------------------------------
# Sections
# -----------------------------------------------------------------------------
def _build_recommendation_section(top_post: FinalPost | None) -> str:
    if not top_post:
        return ""

    topic = _safe_text(getattr(top_post, "topic", "your top post"))
    score = getattr(top_post, "virality_pct", 0)

    return f"""
<tr>
  <td style="background:#ffffff;padding:0 32px 18px;border-left:1px solid #e2e8f0;border-right:1px solid #e2e8f0;">
    <div style="background:#eef2ff;border:1px solid #c7d2fe;border-radius:16px;padding:18px 20px;">
      <div style="font-size:11px;font-weight:700;letter-spacing:1.5px;color:#4338ca;text-transform:uppercase;margin-bottom:8px;">My recommendation</div>
      <div style="font-size:18px;font-weight:800;color:#0f172a;line-height:1.4;">I recommend posting <span style="color:#4f46e5;">{topic}</span> today</div>
      <div style="font-size:14px;color:#475569;line-height:1.7;margin-top:8px;">
        This draft scored <strong>{score}%</strong> and gives you the strongest balance of engagement potential, trend relevance, and clarity for LinkedIn.
      </div>
    </div>
  </td>
</tr>"""


def _build_stats_bar(posts: list[FinalPost]) -> str:
    if not posts:
        return ""

    avg = sum(p.virality_pct for p in posts) / len(posts)
    revised = sum(1 for p in posts if getattr(p, "revision_count", 0) > 0)
    angles = len(set(getattr(p, "angle", "") for p in posts if getattr(p, "angle", None)))

    return f"""
<tr>
  <td style="background:#ffffff;padding:0 32px 20px;border-left:1px solid #e2e8f0;border-right:1px solid #e2e8f0;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:14px;">
      <tr>
        <td width="33%" style="padding:16px 0;text-align:center;border-right:1px solid #e2e8f0;">
          <div style="font-size:22px;font-weight:800;color:#0f172a;">{avg:.0f}%</div>
          <div style="font-size:12px;color:#64748b;margin-top:4px;">Average virality</div>
        </td>
        <td width="34%" style="padding:16px 0;text-align:center;border-right:1px solid #e2e8f0;">
          <div style="font-size:22px;font-weight:800;color:#0f172a;">{revised}/{len(posts)}</div>
          <div style="font-size:12px;color:#64748b;margin-top:4px;">Critic revisions</div>
        </td>
        <td width="33%" style="padding:16px 0;text-align:center;">
          <div style="font-size:22px;font-weight:800;color:#0f172a;">{angles}</div>
          <div style="font-size:12px;color:#64748b;margin-top:4px;">Unique angles</div>
        </td>
      </tr>
    </table>
  </td>
</tr>"""


def _build_posting_helper_section() -> str:
    return """
<tr>
  <td style="background:#ffffff;padding:0 32px 20px;border-left:1px solid #e2e8f0;border-right:1px solid #e2e8f0;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:14px;">
      <tr>
        <td style="padding:16px 18px;">
          <div style="font-size:11px;font-weight:700;letter-spacing:1.5px;color:#0ea5e9;text-transform:uppercase;margin-bottom:8px;">Posting guidance</div>
          <div style="font-size:14px;color:#334155;line-height:1.7;">
            Here is my recommendation: post your top-ranked draft on LinkedIn today to stay engaged with your network, keep consistency high, and build momentum around current trends.
          </div>
          <div style="font-size:13px;color:#64748b;line-height:1.7;margin-top:8px;">
            Best practice: choose one strong hook, post at your usual audience-active time, and reply to early comments within the first hour.
          </div>
        </td>
      </tr>
    </table>
  </td>
</tr>"""


def _build_trend_section(trends: list[TrendScore]) -> str:
    if not trends:
        return ""

    emerging = [t for t in trends if getattr(t, "phase", "") == "EMERGING"][:4]
    peaking = [t for t in trends if getattr(t, "phase", "") == "PEAKING"][:3]
    items = emerging + peaking

    if not items:
        return ""

    pills = " ".join(
        f'<span style="display:inline-block;background:#eef2ff;color:#4338ca;padding:7px 12px;border-radius:999px;font-size:12px;font-weight:600;margin:4px 4px 0 0;border:1px solid #c7d2fe;">{_safe_text(_trend_emoji(getattr(t, "phase", "")))} {_safe_text(getattr(t, "topic", ""))}</span>'
        for t in items
    )

    return f"""
<tr>
  <td style="background:#ffffff;padding:0 32px 20px;border-left:1px solid #e2e8f0;border-right:1px solid #e2e8f0;">
    <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:14px;padding:18px;">
      <div style="font-size:11px;font-weight:700;letter-spacing:1.5px;color:#4f46e5;text-transform:uppercase;margin-bottom:10px;">Trend radar</div>
      <div style="font-size:14px;color:#475569;line-height:1.6;margin-bottom:10px;">These are the topics getting the most momentum right now.</div>
      <div>{pills}</div>
    </div>
  </td>
</tr>"""


def _build_empty_state() -> str:
    return """
<tr>
  <td style="background:#ffffff;padding:0 32px 24px;border-left:1px solid #e2e8f0;border-right:1px solid #e2e8f0;">
    <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:14px;padding:22px;text-align:center;">
      <div style="font-size:17px;font-weight:700;color:#0f172a;">No posts available yet</div>
      <div style="font-size:14px;color:#64748b;line-height:1.7;margin-top:8px;">
        Try running the pipeline again after new trends or source content are collected.
      </div>
    </div>
  </td>
</tr>"""


# -----------------------------------------------------------------------------
# Post card
# -----------------------------------------------------------------------------
def _build_post_card(index: int, post: FinalPost, total_posts: int) -> str:
    virality = getattr(post, "virality", None)
    vpct = getattr(virality, "overall_pct", getattr(post, "virality_pct", 0)) or 0
    color = _score_color(vpct)
    bg = _score_bg(vpct)
    tier = _tier_label(vpct)

    topic = _safe_text(getattr(post, "topic", "Untitled post"))
    angle = str(getattr(post, "angle", "general") or "general")
    source_title = _safe_text(getattr(post, "source_title", "Unknown"))
    char_count = getattr(post, "char_count", 0)
    revision_count = getattr(post, "revision_count", 0)
    metadata = getattr(post, "metadata", {}) or {}

    # Clean post text by removing hashtags from the main copy block.
    text = str(getattr(post, "post_text", "") or "")
    hashtags = _safe_attr_list(getattr(post, "hashtags", []))
    for tag in hashtags:
        text = text.replace(tag, "").strip()
    text = text.rstrip()
    text_html = _safe_html_with_breaks(text)

    tags_html = " ".join(
        f'<span style="display:inline-block;color:#4f46e5;font-size:13px;font-weight:600;margin-right:8px;">{_safe_text(tag)}</span>'
        for tag in hashtags
    )

    # Hook variants
    hooks_html = ""
    hook_variants = getattr(post, "hook_variants", None) or []
    if len(hook_variants) > 1:
        labels = ["🅰", "🅱", "🅲"]
        hook_rows = ""

        for j, hv in enumerate(hook_variants[:3]):
            label = labels[j] if j < len(labels) else f"#{j+1}"
            technique = _safe_text(getattr(hv, "technique", "variant"))
            hook_text = _safe_text(getattr(hv, "text", ""))
            is_original = j == 0
            row_bg = "#f8fafc" if is_original else "#ffffff"
            badge = (
                '<span style="font-size:9px;background:#dcfce7;color:#166534;padding:2px 6px;border-radius:4px;font-weight:700;margin-left:6px;">ORIGINAL</span>'
                if is_original else ""
            )

            hook_rows += f"""
            <tr>
              <td width="38" style="padding:10px 14px;border-bottom:1px solid #e2e8f0;background:{row_bg};vertical-align:top;">
                <span style="font-size:18px;">{label}</span>
              </td>
              <td style="padding:10px 14px;border-bottom:1px solid #e2e8f0;background:{row_bg};">
                <div style="font-size:10px;color:#94a3b8;font-weight:700;text-transform:uppercase;letter-spacing:0.5px;">{technique}{badge}</div>
                <div style="font-size:13px;color:#1e293b;line-height:1.5;margin-top:4px;">{hook_text}</div>
              </td>
            </tr>"""

        hooks_html = f"""
        <div style="margin:16px 0 8px;">
          <div style="font-size:11px;font-weight:700;letter-spacing:1px;color:#4f46e5;text-transform:uppercase;margin-bottom:8px;">Hook variants — pick one</div>
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="border:1px solid #e2e8f0;border-radius:10px;overflow:hidden;">
            {hook_rows}
          </table>
        </div>"""

    # Score breakdown
    breakdown_html = ""
    breakdown = getattr(virality, "breakdown", None) if virality else None
    reasoning = getattr(virality, "reasoning", None) if virality else None
    if breakdown:
        breakdown_items = ""
        for signal, value in breakdown.items():
            label = _safe_text(str(signal).replace("_", " ").title())
            val = int(value)
            bar_width = max(val, 3)
            bar_color = _score_color(val)
            breakdown_items += f"""
            <tr>
              <td style="padding:4px 0;font-size:11px;color:#64748b;width:130px;">{label}</td>
              <td style="padding:4px 8px;">
                <div style="background:#e2e8f0;border-radius:999px;height:8px;width:100%;overflow:hidden;">
                  <div style="background:{bar_color};border-radius:999px;height:8px;width:{bar_width}%;"></div>
                </div>
              </td>
              <td style="padding:4px 0;font-size:11px;font-weight:700;color:#334155;width:40px;text-align:right;">{val}%</td>
            </tr>"""

        reasoning_html = ""
        if reasoning:
            reasoning_html = (
                f'<div style="font-size:12px;color:#64748b;line-height:1.6;margin-top:10px;padding-top:10px;border-top:1px solid #e2e8f0;">{_safe_text(reasoning)}</div>'
            )

        breakdown_html = f"""
        <div style="margin:12px 0;">
          <div style="font-size:11px;font-weight:700;letter-spacing:1px;color:#4f46e5;text-transform:uppercase;margin-bottom:8px;">Score breakdown</div>
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
            {breakdown_items}
          </table>
          {reasoning_html}
        </div>"""

    trend_badge = ""
    trend_phase = metadata.get("trend_phase") if isinstance(metadata, dict) else None
    if trend_phase:
        emoji = _trend_emoji(str(trend_phase))
        trend_badge = (
            f'<span style="display:inline-block;background:#eef2ff;color:#4338ca;font-size:10px;font-weight:700;padding:5px 9px;border-radius:999px;margin-left:6px;border:1px solid #c7d2fe;">{_safe_text(emoji)} {_safe_text(str(trend_phase))}</span>'
        )

    revision_badge = ""
    if revision_count:
        revision_badge = (
            f'<span style="display:inline-block;background:#fef3c7;color:#92400e;font-size:10px;font-weight:700;padding:5px 9px;border-radius:999px;margin-left:6px;">Revised {revision_count}x</span>'
        )

    angle_colors = {
        "hot_take": ("#fef2f2", "#991b1b"),
        "story": ("#f0fdf4", "#166534"),
        "tutorial": ("#eff6ff", "#1e40af"),
        "prediction": ("#faf5ff", "#6b21a8"),
        "comparison": ("#fefce8", "#854d0e"),
        "myth_busting": ("#fff1f2", "#9f1239"),
        "case_study": ("#f0fdfa", "#115e59"),
        "framework": ("#eef2ff", "#3730a3"),
        "data_driven": ("#ecfdf5", "#065f46"),
        "question": ("#fdf4ff", "#86198f"),
    }
    abg, afg = angle_colors.get(angle, ("#f1f5f9", "#475569"))

    return f"""
<tr>
  <td style="background:#ffffff;padding:0 32px;border-left:1px solid #e2e8f0;border-right:1px solid #e2e8f0;">
    <div style="background:#ffffff;padding:0 0 24px 0;border-top:1px solid #f1f5f9;">

      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-top:24px;">
        <tr>
          <td valign="top">
            <div style="font-size:12px;color:#94a3b8;margin-bottom:6px;">Post {index} of {total_posts}</div>
            <div style="font-size:20px;font-weight:800;color:#0f172a;margin-bottom:8px;">{topic}</div>
            <div>
              <span style="display:inline-block;background:{abg};color:{afg};font-size:10px;font-weight:700;padding:5px 10px;border-radius:999px;text-transform:uppercase;letter-spacing:0.5px;">{_safe_text(angle.replace('_', ' '))}</span>
              {trend_badge}
              {revision_badge}
            </div>
          </td>
          <td width="95" align="right" valign="top">
            <div style="background:{bg};border-radius:16px;padding:14px 16px;text-align:center;border:1px solid {color}33;">
              <div style="font-size:32px;font-weight:800;color:{color};line-height:1;">{vpct}%</div>
              <div style="font-size:10px;font-weight:700;color:{color};letter-spacing:1px;margin-top:4px;">{tier}</div>
            </div>
          </td>
        </tr>
      </table>

      <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:14px;padding:20px;margin:18px 0 14px 0;">
        <div style="font-size:11px;font-weight:700;letter-spacing:1px;color:{color};text-transform:uppercase;margin-bottom:10px;">Draft preview</div>
        <div style="font-size:14px;color:#1e293b;line-height:1.75;">{text_html}</div>
        <div style="margin-top:12px;">{tags_html}</div>
      </div>

      <div style="background:#eff6ff;border:1px solid #bfdbfe;border-radius:12px;padding:14px 16px;margin-bottom:14px;">
        <div style="font-size:13px;font-weight:700;color:#1d4ed8;margin-bottom:4px;">Recommendation</div>
        <div style="font-size:13px;color:#334155;line-height:1.6;">
          Use this post if you want a strong balance of clarity, engagement, and trend relevance on LinkedIn.
        </div>
      </div>

      {hooks_html}
      {breakdown_html}

      <div style="font-size:11px;color:#94a3b8;margin-top:14px;padding-top:12px;border-top:1px solid #e2e8f0;">
        {char_count} chars · Source: {source_title}
      </div>

    </div>
  </td>
</tr>"""
