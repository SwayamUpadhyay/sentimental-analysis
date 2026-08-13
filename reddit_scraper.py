"""
reddit_scraper.py — Product Analytics Reddit Data Ingestion

Uses Reddit's public JSON API (no OAuth / PRAW required).
Every subreddit and search page is accessible as JSON by hitting:

    https://www.reddit.com/search.json?q=<query>&sort=hot&t=month&limit=<n>

Authentication:
    None required. A descriptive User-Agent is mandatory per Reddit API rules.
    Set 'reddit_user_agent' in settings.json.

Post Quality Gate (fetch-time pipeline):
    Each post goes through four gates before entering the analysis pipeline:

    1.  selftext-only   — Skip title-only posts (no sentiment signal).
    2.  Product-name match — Exact consecutive word-sequence match for the
                           product name in the raw post text. Posts that don't
                           mention the exact product are discarded.
    3.  Token length gate  — Posts > _MAX_TOKENS whitespace-split words are
                           discarded (too verbose / unfocused).
                           Reference: the canonical ~140-word sample post.
    4.  NLP quality gate  — HTML decode, stopword removal, min-length check.

Retry Loop:
    If quality filtering yields fewer than posts_per_product posts, the scraper
    retries with a random 2–5 second sleep until the required count is reached
    or Reddit has no more results.

Rate limiting (Reddit):
    'reddit_sleep_seconds' in settings.json (default 2s) between fetches.

Rate limiting (Groq):
    Competitor discovery uses groq_rate_limiter.wait() (shared singleton).

Entry point:
    scrape(product_name: str, settings: dict, groq_client: Groq) -> dict
"""

import html
import json
import random
import re
import time

import httpx
import nltk
from groq import Groq

from rate_limiter import groq_rate_limiter
from templates import PROMPTS


# ─── NLP Setup ────────────────────────────────────────────────────────────────

def _ensure_nltk_stopwords() -> set[str]:
    """
    Ensure the NLTK English stopwords corpus is available.
    Downloads it silently on first run (~30 KB).
    Returns the stopword set.
    """
    try:
        from nltk.corpus import stopwords
        return set(stopwords.words("english"))
    except LookupError:
        print("[reddit_scraper] 📥 Downloading NLTK stopwords corpus (one-time, ~30 KB)...")
        nltk.download("stopwords", quiet=True)
        from nltk.corpus import stopwords
        return set(stopwords.words("english"))


# Load stopwords once at module import time
_STOP_WORDS: set[str] = _ensure_nltk_stopwords()

# Compiled regex patterns
_RE_HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
_RE_HTML_TAG     = re.compile(r"<[^>]+>")
_RE_URL          = re.compile(r"https?://\S+|www\.\S+")
_RE_SPECIAL      = re.compile(r"[^a-zA-Z0-9\s'\-]")
_RE_WHITESPACE   = re.compile(r"\s+")

# ─── Filter Constants ─────────────────────────────────────────────────────────

# Noise markers from Reddit's API
_NOISE_VALUES = frozenset({"[removed]", "[deleted]", ""})

# Minimum cleaned character length for a post to be usable
_MIN_CLEAN_CHARS = 40

# Maximum token count (whitespace-split words) for a raw post.
# Reference: the canonical MacBook/Alienware study post (sample.json L173) is
# 140 tokens — concise, focused, rich in product signals. Posts longer than
# _MAX_TOKENS tend to be sprawling, off-topic, or listicle-style.
_MAX_TOKENS = 150

# Random sleep range (seconds) between retry scrape attempts
_MIN_RETRY_SLEEP = 2
_MAX_RETRY_SLEEP = 5


# ─── API Constants ────────────────────────────────────────────────────────────

_REDDIT_SEARCH_URL    = "https://www.reddit.com/search.json"
_REDDIT_DEFAULT_SLEEP = 2   # seconds between product fetches
_HTTP_TIMEOUT         = 15  # seconds


# ─── NLP Quality Gate ─────────────────────────────────────────────────────────

def _clean_post_text(raw: str) -> str | None:
    """
    Apply the full NLP quality pipeline to a raw Reddit selftext string.

    Returns the cleaned text string, or None if the post should be discarded.

    Pipeline steps:
        1. Null / noise check
        2. HTML entity decode
        3. HTML comment strip  (<!-- SC_OFF --> etc.)
        4. HTML tag strip
        5. URL removal
        6. Special character removal (keep apostrophes + hyphens)
        7. Lowercase
        8. NLTK English stopword removal
        9. Short-token filter  (< 3 chars)
        10. Minimum length gate (< _MIN_CLEAN_CHARS chars → discard)
    """
    if not raw or not isinstance(raw, str):
        return None
    stripped = raw.strip()
    if stripped in _NOISE_VALUES:
        return None

    text = html.unescape(stripped)
    text = _RE_HTML_COMMENT.sub(" ", text)
    text = _RE_HTML_TAG.sub(" ", text)
    text = _RE_URL.sub(" ", text)
    text = _RE_SPECIAL.sub(" ", text)
    text = text.lower()

    tokens = _RE_WHITESPACE.split(text.strip())
    tokens = [t for t in tokens if t not in _STOP_WORDS]
    tokens = [t for t in tokens if len(t) >= 3]

    cleaned = " ".join(tokens).strip()

    if len(cleaned) < _MIN_CLEAN_CHARS:
        return None

    return cleaned


# ─── Product Name Filter, Token Counter & Language Guard ─────────────────────

def _count_tokens(text: str) -> int:
    """
    Count the number of whitespace-separated tokens in raw text.
    Applied to raw selftext BEFORE NLP cleaning so we reject long posts early.
    """
    return len(text.split())


def _is_english(text: str, min_ascii_ratio: float = 0.75) -> bool:
    """
    Heuristic English language gate.

    Rejects posts where a significant fraction of characters are non-ASCII
    (catches Arabic, Chinese, Japanese, Cyrillic, etc.).
    Italian/French use mostly ASCII so they pass this check but are still
    rejected by the product-name filter if they don't mention the product.

    Args:
        text:            Raw selftext string.
        min_ascii_ratio: Minimum fraction of characters that must be in the
                         printable ASCII range (< 128). Default 0.75.
    Returns:
        True if the post is likely English, False otherwise.
    """
    if not text:
        return False
    ascii_count = sum(1 for c in text if ord(c) < 128)
    return (ascii_count / len(text)) >= 0.70


def _contains_product(text: str, product_name: str) -> bool:
    """
    Three-tier fuzzy match — checks if `text` mentions the product.

    Real Reddit behaviour: users often drop the manufacturer prefix and just
    say "Blade 16", "ROG Strix G16", or "Alienware M16" instead of the full
    official name. Three tiers handle this gracefully:

      Tier 1 — Full exact sequence match (highest precision)
               e.g. "razer blade 16" found verbatim in text

      Tier 2 — Suffix match: drop the first (brand) word
               e.g. "blade 16"     matches "Razer Blade 16"
                    "rog strix g16" matches "Asus ROG Strix G16"
                    "alienware m16" matches "Dell Alienware M16"
               Only triggered for product names with ≥3 tokens.

      Tier 3 — Deep-suffix match: drop first TWO words
               e.g. "strix g16"    matches "Asus ROG Strix G16"
               Only triggered for product names with ≥4 tokens and
               when the sub-sequence has ≥2 tokens.

    Args:
        text:         Raw (or lower-cased) post text.
        product_name: The product to match (e.g. "Razer Blade 16").

    Returns:
        True if the product is referenced in the text, False otherwise.
    """
    if not product_name:
        return True

    text_tokens    = text.lower().split()
    product_tokens = product_name.lower().split()
    n = len(product_tokens)

    if n == 0 or not text_tokens:
        return False

    def _has_seq(needle: list, haystack: list) -> bool:
        k = len(needle)
        if k == 0 or len(haystack) < k:
            return False
        for i in range(len(haystack) - k + 1):
            if haystack[i : i + k] == needle:
                return True
        return False

    # Tier 1: full exact consecutive sequence
    if _has_seq(product_tokens, text_tokens):
        return True

    # Tier 2: drop the first (brand) word — suffix of length n-1
    # Only if n≥3 so the suffix is ≥2 tokens (prevents bare single-word matches)
    # e.g. "Blade 16" matches "Razer Blade 16"; "Alienware M16" matches "Dell Alienware M16"
    if n >= 3:
        suffix = product_tokens[1:]
        if _has_seq(suffix, text_tokens):
            return True

    # Tier 3: deep-suffix — drop first TWO words, for 4-token names
    # e.g. "Strix G16" matches "Asus ROG Strix G16"; "Helios 16" matches "Acer Predator Helios 16"
    if n >= 4:
        deep_suffix = product_tokens[2:]
        if len(deep_suffix) >= 2 and _has_seq(deep_suffix, text_tokens):
            return True

    return False


# ─── Internal Helpers ─────────────────────────────────────────────────────────

def _make_headers(user_agent: str) -> dict:
    """
    Build browser-like HTTP headers for Reddit's public JSON API.

    Uses a real Chrome User-Agent fingerprint plus Referer/Accept-Language
    to avoid Reddit's bot-detection and 429 rate-limit blocks.
    """
    return {
        "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept":          "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer":         "https://www.reddit.com/",
    }


def _reddit_sleep(seconds: int, label: str = "") -> None:
    """Throttle sleep between Reddit API calls with console feedback."""
    msg = f" ({label})" if label else ""
    print(f"[reddit_scraper] ⏳ Sleeping {seconds}s between Reddit requests{msg}...")
    time.sleep(seconds)


def _fetch_reddit_posts(
    query: str,
    product_name: str,
    limit: int,
    user_agent: str,
    sort: str = "new",
    time_filter: str = "month",
) -> list[dict]:
    """
    Search Reddit's public JSON API for `query`.

    Applies four quality filters to every post:
      1. selftext-only policy (title-only posts discarded)
      2. Product name exact-sequence match (_contains_product)
      3. Token length gate — raw selftext must be ≤ _MAX_TOKENS words
      4. NLP quality gate (_clean_post_text)

    Args:
        query:        Search term (e.g. "iPhone 17").
        product_name: Exact product name to match in the raw post text.
        limit:        Number of quality posts to collect.
        user_agent:   User-Agent header string.
        sort:         'hot' | 'new' | 'top' | 'relevance'
        time_filter:  'hour' | 'day' | 'week' | 'month' | 'year' | 'all'

    Returns:
        List of dicts: [{"text": "...", "utc": 169...}, ...]
    """
    posts: list[dict] = []
    raw_count              = 0
    discarded_title_only   = 0
    discarded_non_english  = 0
    discarded_no_product   = 0
    discarded_too_long     = 0
    discarded_nlp          = 0

    after        = None
    target_limit = limit

    try:
        with httpx.Client(timeout=_HTTP_TIMEOUT) as client:
            while len(posts) < target_limit:
                request_limit = min(100, target_limit - len(posts))
                params = {
                    "q":      query,
                    "sort":   sort,
                    "t":      time_filter,
                    "limit":  request_limit,
                    "type":   "link",   # posts only, not subreddits
                }
                if after:
                    params["after"] = after

                response = client.get(
                    _REDDIT_SEARCH_URL,
                    headers=_make_headers(user_agent),
                    params=params,
                )
                response.raise_for_status()
                data = response.json()

                children = data.get("data", {}).get("children", [])
                if not children:
                    break

                raw_count += len(children)
                after      = data.get("data", {}).get("after")

                for child in children:
                    post_data   = child.get("data", {})
                    selftext    = post_data.get("selftext", "")
                    created_utc = post_data.get("created_utc", 0.0)

                    # ── 1. selftext-only policy ───────────────────────────────────
                    if not selftext or selftext.strip() in _NOISE_VALUES:
                        discarded_title_only += 1
                        continue

                    # ── 2. English language gate ──────────────────────────────────
                    # Rejects posts in Arabic, Chinese, Cyrillic, etc.
                    if not _is_english(selftext):
                        discarded_non_english += 1
                        continue

                    # ── 3. Product-name fuzzy match (3-tier) ──────────────────────
                    # Accepts: exact name, brand-omitted suffix, deep-suffix
                    if not _contains_product(selftext, product_name):
                        discarded_no_product += 1
                        continue

                    # ── 4. Token length gate ──────────────────────────────────────
                    if _count_tokens(selftext) > _MAX_TOKENS:
                        discarded_too_long += 1
                        continue

                    # ── 5. NLP quality gate ───────────────────────────────────────
                    cleaned = _clean_post_text(selftext)
                    if cleaned is None:
                        discarded_nlp += 1
                        continue

                    posts.append({"text": cleaned, "utc": created_utc})
                    if len(posts) >= target_limit:
                        break

                if not after:
                    break

                if len(posts) < target_limit:
                    time.sleep(1)  # backoff between paginated calls

        print(
            f"[reddit_scraper] 📄 '{query}': {raw_count} raw → "
            f"{len(posts)} quality posts kept "
            f"(−{discarded_title_only} no-body, "
            f"−{discarded_non_english} non-english, "
            f"−{discarded_no_product} no-product-name, "
            f"−{discarded_too_long} too-long>{_MAX_TOKENS}tok, "
            f"−{discarded_nlp} NLP-filtered)."
        )

    except httpx.HTTPStatusError as e:
        print(
            f"[reddit_scraper] ⚠️  HTTP {e.response.status_code} for '{query}': "
            f"{e.response.text[:200]}"
        )
    except httpx.RequestError as e:
        print(f"[reddit_scraper] ⚠️  Network error for '{query}': {e}")
    except (KeyError, ValueError) as e:
        print(f"[reddit_scraper] ⚠️  JSON parse error for '{query}': {e}")

    return posts


def _discover_competitors(
    product_name: str,
    max_competitors: int,
    groq_client: Groq,
    model_light: str,
) -> list[str]:
    """
    Use model_light LLM to identify real competitor products.

    Rate limiting is handled by groq_rate_limiter.wait() (global singleton).
    Returns a list of product name strings (length ≤ max_competitors).
    Falls back to empty list on any failure.
    """
    print(f"[reddit_scraper] 🤖 Step 0: Discovering competitors for '{product_name}'...")

    prompt = PROMPTS["competitor_discovery"]["template"].format(
        product_name=product_name,
        max_competitors=max_competitors,
    )

    try:
        groq_rate_limiter.wait()
        response = groq_client.chat.completions.create(
            model=model_light,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=256,
            temperature=0.3,
        )
        raw = response.choices[0].message.content.strip()

        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:].strip()

        competitors = json.loads(raw)

        if isinstance(competitors, list):
            competitors = [str(c) for c in competitors if c][:max_competitors]
            print(f"[reddit_scraper] ✅ Competitors identified: {competitors}")
            return competitors
        else:
            raise ValueError("LLM did not return a JSON array.")

    except Exception as e:
        print(
            f"[reddit_scraper] ⚠️  Competitor discovery failed: {e}. "
            "Proceeding without competitors."
        )
        return []


# ─── Public API ───────────────────────────────────────────────────────────────

def scrape(product_name: str, settings: dict, groq_client: Groq) -> dict:
    """
    Full Reddit ingestion pipeline for a target product and its competitors.

    Uses Reddit's public JSON API via httpx — no PRAW or OAuth credentials.
    Every post passes four quality gates:
      1. selftext-only policy
      2. Exact product-name token-sequence match
      3. Token length ≤ _MAX_TOKENS  (reference: ~140-token sample post)
      4. NLP cleaning gate

    If quality filtering yields fewer posts than posts_per_product, the scraper
    retries automatically with a random 2–5 second sleep between attempts until
    the required count is reached or Reddit has no more results.

    Pipeline:
        Step 0: LLM identifies competitor names.
        Step 1: Retry loop — scrape main product until posts_per_product posts.
        Step 2: Retry loop — scrape each competitor until posts_per_product posts.

    Args:
        product_name: The main product/brand to analyze (e.g. "iPhone 17").
        settings:     Loaded settings.json dict.
        groq_client:  Initialized Groq SDK client instance.

    Returns:
        {
            "target":      {"name": str, "posts": [{"text": str, "utc": float}, ...]},
            "competitors": {"CompetitorName": {"posts": [...]}, ...}
        }
    """
    posts_per_product: int = settings["posts_per_product"]
    max_competitors: int   = settings["max_competitors"]
    user_agent: str        = settings.get(
        "reddit_user_agent",
        "lumina-backend/1.0 (college project)"
    )
    reddit_sleep: int = settings.get("reddit_sleep_seconds", _REDDIT_DEFAULT_SLEEP)

    print(
        f"[reddit_scraper] 🔌 Smart Reddit scraper active. "
        f"Filters: exact product-name match + ≤{_MAX_TOKENS} tokens + NLP gate. "
        f"Stopwords: {len(_STOP_WORDS)} loaded."
    )

    # ── STEP 0: Competitor Discovery ──────────────────────────────────────────
    competitors = _discover_competitors(
        product_name=product_name,
        max_competitors=max_competitors,
        groq_client=groq_client,
        model_light=settings["model_light"],
    )

    # ── STEP 1: Scrape Main Product (retry loop) ──────────────────────────────
    print(
        f"[reddit_scraper] 📥 Step 1: Collecting {posts_per_product} quality posts "
        f"for '{product_name}' (exact match + ≤{_MAX_TOKENS} tokens)..."
    )
    target_posts: list[dict] = []
    seen_texts: set[str]     = set()
    attempt = 0

    while len(target_posts) < posts_per_product:
        attempt += 1
        batch = _fetch_reddit_posts(
            query=product_name,
            product_name=product_name,
            limit=posts_per_product * 4,   # request 4× to compensate for strict filters
            user_agent=user_agent,
        )

        for p in batch:
            if p["text"] not in seen_texts:
                target_posts.append(p)
                seen_texts.add(p["text"])

        if len(target_posts) >= posts_per_product:
            break

        if not batch:
            print(
                f"[reddit_scraper] ⚠️  No more Reddit results for '{product_name}'. "
                f"Proceeding with {len(target_posts)} posts."
            )
            break

        sleep_sec = random.uniform(_MIN_RETRY_SLEEP, _MAX_RETRY_SLEEP)
        print(
            f"[reddit_scraper] 🔄 Attempt {attempt}: {len(target_posts)}/{posts_per_product} "
            f"posts collected. Retrying in {sleep_sec:.1f}s..."
        )
        time.sleep(sleep_sec)

    target_posts = target_posts[:posts_per_product]
    print(
        f"[reddit_scraper] ✅ Target '{product_name}': "
        f"{len(target_posts)}/{posts_per_product} posts collected."
    )
    _reddit_sleep(reddit_sleep, label=f"after '{product_name}' fetch")

    # ── STEP 2: Scrape Each Competitor (retry loop) ───────────────────────────
    competitor_data: dict = {}
    for idx, comp_name in enumerate(competitors, start=1):
        print(
            f"[reddit_scraper] 📥 Step 2.{idx}: Collecting {posts_per_product} quality posts "
            f"for '{comp_name}'..."
        )
        comp_posts: list[dict] = []
        seen_comp: set[str]    = set()
        attempt = 0

        while len(comp_posts) < posts_per_product:
            attempt += 1
            batch = _fetch_reddit_posts(
                query=comp_name,
                product_name=comp_name,
                limit=posts_per_product * 4,
                user_agent=user_agent,
            )

            for p in batch:
                if p["text"] not in seen_comp:
                    comp_posts.append(p)
                    seen_comp.add(p["text"])

            if len(comp_posts) >= posts_per_product:
                break

            if not batch:
                print(
                    f"[reddit_scraper] ⚠️  No more Reddit results for '{comp_name}'. "
                    f"Proceeding with {len(comp_posts)} posts."
                )
                break

            sleep_sec = random.uniform(_MIN_RETRY_SLEEP, _MAX_RETRY_SLEEP)
            print(
                f"[reddit_scraper] 🔄 Attempt {attempt}: {len(comp_posts)}/{posts_per_product} "
                f"posts. Retrying in {sleep_sec:.1f}s..."
            )
            time.sleep(sleep_sec)

        comp_posts = comp_posts[:posts_per_product]
        print(
            f"[reddit_scraper] ✅ Competitor '{comp_name}': "
            f"{len(comp_posts)}/{posts_per_product} posts collected."
        )
        competitor_data[comp_name] = {"posts": comp_posts}
        if idx < len(competitors):
            _reddit_sleep(reddit_sleep, label=f"after '{comp_name}' fetch")

    total_posts = len(target_posts) + sum(
        len(v["posts"]) for v in competitor_data.values()
    )
    print(
        f"[reddit_scraper] 🏁 Scraping complete. "
        f"1 target + {len(competitor_data)} competitors. "
        f"Total quality posts: {total_posts} "
        f"(goal: {posts_per_product} each)."
    )

    return {
        "target":      {"name": product_name, "posts": target_posts},
        "competitors": competitor_data,
    }
