

import re
import html as html_module


# ─── Constants ────────────────────────────────────────────────────────────────

# Maximum characters to keep per individual post after cleaning
_MAX_CHARS_PER_POST = 500

# Minimum meaningful post length (discard noise/empty posts below this)
_MIN_CHARS = 10     

# Prefix length used for near-duplicate detection
_DEDUP_PREFIX_LEN = 25

# Compiled regex patterns (compiled once at import time for performance)
_RE_URL = re.compile(r"https?://\S+|www\.\S+")
_RE_HTML_TAG = re.compile(r"<[^>]+>")
_RE_REDDIT_MARKDOWN = re.compile(r"[*_~`#>|]+")
_RE_EMOJI = re.compile(
    "["
    "\U0001F600-\U0001F64F"  # Emoticons
    "\U0001F300-\U0001F5FF"  # Symbols & pictographs
    "\U0001F680-\U0001F6FF"  # Transport & map
    "\U0001F1E0-\U0001F1FF"  # Flags
    "\U00002600-\U000026FF"  # Miscellaneous symbols
    "\U00002700-\U000027BF"  # Dingbats
    "\U0001F900-\U0001F9FF"  # Supplemental symbols
    "\U00002500-\U00002BEF"  # Various technical
    "]+",
    flags=re.UNICODE,
)
_RE_WHITESPACE = re.compile(r"\s+")

# Reddit-specific noise patterns to strip
_RE_REDDIT_NOISE = re.compile(
    r"(\[deleted\]|\[removed\]|&amp;|&lt;|&gt;|&quot;|&#\d+;)",
    re.IGNORECASE,
)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _clean_text(text: str) -> str:
    """
    Strip all noise from a single text string and truncate.

    Pipeline:
        1. HTML entity decode
        2. Remove Reddit [deleted]/[removed] markers and HTML entities
        3. Strip URLs
        4. Strip HTML tags
        5. Strip Reddit markdown syntax
        6. Strip emoji
        7. Collapse whitespace
        8. Truncate to _MAX_CHARS_PER_POST
    """
    if not isinstance(text, str):
        return ""

    # 1. Decode HTML entities (e.g. &amp; → &)
    text = html_module.unescape(text)

    # 2. Remove Reddit noise markers
    text = _RE_REDDIT_NOISE.sub(" ", text)

    # 3. Remove URLs
    text = _RE_URL.sub(" ", text)

    # 4. Remove HTML tags
    text = _RE_HTML_TAG.sub(" ", text)

    # 5. Remove Reddit markdown characters
    text = _RE_REDDIT_MARKDOWN.sub(" ", text)

    # 6. Remove emoji
    text = _RE_EMOJI.sub(" ", text)

    # 7. Collapse all whitespace to single spaces, strip edges
    text = _RE_WHITESPACE.sub(" ", text).strip()

    # 8. Truncate
    return text[:_MAX_CHARS_PER_POST]


def _deduplicate(posts: list[dict]) -> list[dict]:
    """
    Remove near-duplicate posts based on shared normalized prefix.
    Also filters out posts below the minimum character threshold.
    """
    seen_prefixes: set[str] = set()
    unique: list[dict] = []

    for post in posts:
        text = post.get("text", "")
        if len(text) < _MIN_CHARS:
            continue
        prefix = text[:_DEDUP_PREFIX_LEN].lower()
        if prefix not in seen_prefixes:
            seen_prefixes.add(prefix)
            unique.append(post)

    return unique


def _process_posts(posts: list[dict]) -> list[dict]:
    """Clean and deduplicate a list of post dicts."""
    cleaned = []
    for p in posts:
        cleaned_text = _clean_text(p.get("text", ""))
        cleaned.append({"text": cleaned_text, "utc": p.get("utc", 0.0)})
    return _deduplicate(cleaned)


# ─── Public API ───────────────────────────────────────────────────────────────

def preprocess(raw_data: dict) -> dict:
    """
    Clean and normalize all raw Reddit data before LLM inference.

    Args:
        raw_data: {
            "target": {"name": str, "posts": [{"text": str, "utc": float}, ...]},
            "competitors": {
                "CompetitorName": {"posts": [{"text": str, "utc": float}, ...]},
                ...
            }
        }

    Returns:
        Same structure with cleaned, deduplicated, truncated text.
        Token footprint reduced by ~40-60%.
    """
    target = raw_data.get("target", {})
    raw_target_posts = target.get("posts", [])
    cleaned_target_posts = _process_posts(raw_target_posts)

    print(
        f"[preprocessor] Target '{target.get('name', '?')}': "
        f"{len(raw_target_posts)} raw → {len(cleaned_target_posts)} cleaned posts."
    )

    cleaned_competitors: dict = {}
    for comp_name, comp_data in raw_data.get("competitors", {}).items():
        raw_comp_posts = comp_data.get("posts", [])
        cleaned_comp_posts = _process_posts(raw_comp_posts)
        cleaned_competitors[comp_name] = {"posts": cleaned_comp_posts}
        print(
            f"[preprocessor] Competitor '{comp_name}': "
            f"{len(raw_comp_posts)} raw → {len(cleaned_comp_posts)} cleaned posts."
        )

    return {
        "target": {
            "name": target.get("name", ""),
            "posts": cleaned_target_posts,
        },
        "competitors": cleaned_competitors,
    }
