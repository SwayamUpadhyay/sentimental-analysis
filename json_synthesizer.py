import json
import time

from groq import Groq
from pydantic import BaseModel, ValidationError, field_validator, Field
from typing import Optional

from rate_limiter import groq_rate_limiter
from templates import PROMPTS


def _sleep(seconds: int) -> None:
    time.sleep(seconds)

class KeywordItem(BaseModel):
    word: str
    size: str        # e.g. "2.25rem"
    color: str       # hex
    weight: int      # font-weight integer e.g. 700


class DemographicItem(BaseModel):
    """User demographic segment."""
    label: str       # e.g. "Gen Z (18-24)"
    pct: int         # integer percentage 0-100
    color: str       # hex


class ClusterItem(BaseModel):
    """Community bubble cluster."""
    label: str       # e.g. "Tech"
    users: str       # e.g. "12.4k"
    size: int        # pixel size of bubble
    color: str       # rgba background
    border: str      # rgba border
    textColor: str   # hex text color
    top: str         # CSS top offset e.g. "10%"
    left: str        # CSS left offset e.g. "20%"


class SentimentBrand(BaseModel):
    """Comparative brand sentiment entry for Market Pulse."""
    name: str
    score: float     # 0.0 - 10.0
    color: str       # hex or named color
    pct: int         # integer percentage 0-100


class TrendingTopic(BaseModel):
    """Trending market topic card."""
    badge: str        # e.g. "High Velocity"
    badgeColor: str   # hex
    title: str
    desc: str
    positive: str     # e.g. "84% Positive"
    icon: str         # Google Material Symbols icon name
    iconColor: str    # hex
    discussions: str  # e.g. "2.4k discussions"
    bg: str           # CSS gradient string


# ─── Statistics Models (Computed in Backend) ──────────────────────────────────

class TimelineItem(BaseModel):
    name: str
    positive: int
    neutral: int
    negative: int

class DonutItem(BaseModel):
    name: str
    value: int
    color: str

class BarChartItem(BaseModel):
    name: str
    value: int
    color: str

class MarketShareItem(BaseModel):
    name: str
    size: int


class PerformanceMetrics(BaseModel):
    """Aggregate analysis performance statistics."""
    totalMentions: int
    avgResponseTime: str    # e.g. "2.4 hours"
    analysisAccuracy: int   # integer 0-100


class LuminaPayload(BaseModel):
    """
    Root model for the complete UI-ready analysis payload.
    Matches the data contract expected by the React frontend.
    """
    brandName: str
    overallScore: float           # 0.0 - 10.0

    keywords: list[KeywordItem]
    demographics: list[DemographicItem]
    clusters: list[ClusterItem]
    platformPosts: list[str]

    sentimentBrands: list[SentimentBrand] = Field(default_factory=list)
    trendingTopics: list[TrendingTopic]
    performanceMetrics: PerformanceMetrics

    # Fields computed purely by stats backend (LLM may ignore)
    donut: list[DonutItem] = Field(default_factory=list)
    timeline: list[TimelineItem] = Field(default_factory=list)
    barChart: list[BarChartItem] = Field(default_factory=list)
    marketShare: list[MarketShareItem] = Field(default_factory=list)

    @field_validator("overallScore")
    @classmethod
    def clamp_score(cls, v: float) -> float:
        """Ensure score stays within 0.0 - 10.0 regardless of LLM output."""
        return max(0.0, min(10.0, v))

    @field_validator("demographics")
    @classmethod
    def clamp_demographics_pct(cls, items: list[DemographicItem]) -> list[DemographicItem]:
        """Clamp individual demographic percentages to 0-100."""
        for item in items:
            item.pct = max(0, min(100, item.pct))
        return items


# ─── Prompt Assembly ──────────────────────────────────────────────────────────

def _build_synthesis_prompt(
    sentiment_data: list[dict],
    product_name: str,
    settings: dict,
) -> str:
    """
    Assemble the full JSON synthesis prompt by injecting runtime values
    into the PROMPTS['json_payload_construction'] template.
    """
    colors = settings["design_colors"]
    cluster_labels = ", ".join(settings["community_clusters"])

    # Build a compact, token-efficient sentiment summary
    # Format: [PRODUCT | TARGET/COMPETITOR | SENTIMENT]: text (max 200 chars)
    summary_lines: list[str] = []
    for item in sentiment_data:
        role = "COMPETITOR" if item["is_competitor"] else "TARGET"
        line = (
            f"[{item['product']} | {role} | {item['sentiment']}]: "
            f"{item['text'][:200]}"
        )
        summary_lines.append(line)

    sentiment_text = "\n".join(summary_lines)

    return PROMPTS["json_payload_construction"]["template"].format(
        product_name=product_name,
        color_primary=colors["primary"],
        color_positive=colors["positive"],
        color_negative=colors["negative"],
        color_neutral=colors["neutral"],
        cluster_labels=cluster_labels,
        sentiment_data=sentiment_text,
    )



def _call_groq_heavy(
    prompt: str,
    groq_client: Groq,
    model_heavy: str,
    token_limit: int,
) -> str:

    groq_rate_limiter.wait()  # ← enforce RPM cap before heavy model call
    response = groq_client.chat.completions.create(
        model=model_heavy,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are the Ethereal Analyst. "
                    "Output ONLY valid JSON. No markdown. No explanation text."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        max_tokens=token_limit,
        temperature=0.4,
    )
    return response.choices[0].message.content.strip()


def _strip_markdown_fences(raw: str) -> str:
    """Remove accidental markdown code fences the LLM may wrap JSON in."""
    if raw.startswith("```"):
        parts = raw.split("```")
        # parts[1] contains the content between first pair of fences
        inner = parts[1] if len(parts) > 1 else raw
        if inner.startswith("json"):
            inner = inner[4:].strip()
        return inner.strip()
    return raw



def synthesize(
    sentiment_data: list[dict],
    product_name: str,
    settings: dict,
    groq_client: Groq,
) -> LuminaPayload:
    
    model_heavy: str = settings["model_heavy"]
    token_limit: int = settings["token_limit_heavy"]
    sleep_seconds: int = settings["rate_limit_sleep_seconds"]

    prompt = _build_synthesis_prompt(sentiment_data, product_name, settings)

    for attempt in range(1, 3):
        print(
            f"[json_synthesizer] ⚡ Synthesis attempt {attempt}/2 "
            f"using '{model_heavy}' ({len(sentiment_data)} tagged posts)..."
        )
        try:
            raw = _call_groq_heavy(prompt, groq_client, model_heavy, token_limit)
            _sleep(sleep_seconds)

            cleaned = _strip_markdown_fences(raw)

            parsed = json.loads(cleaned)

            payload = LuminaPayload(**parsed)

            print(
                f"[json_synthesizer] ✅ Payload validated successfully on attempt {attempt}. "
                f"Overall score: {payload.overallScore}/10"
            )
            return payload

        except json.JSONDecodeError as e:
            print(f"[json_synthesizer] ❌ Attempt {attempt} — JSON parse error: {e}")
            if attempt == 1:
                prompt += (
                    f"\n\n⚠️ PREVIOUS ATTEMPT FAILED — JSON PARSE ERROR:\n{str(e)[:400]}\n"
                    "Fix the JSON syntax and output ONLY valid, parseable JSON."
                )
                _sleep(sleep_seconds)

        except ValidationError as e:
            print(f"[json_synthesizer] ❌ Attempt {attempt} — Pydantic validation error:\n{e}")
            if attempt == 1:
                prompt += (
                    f"\n\n⚠️ PREVIOUS ATTEMPT FAILED — SCHEMA VALIDATION ERROR:\n{str(e)[:400]}\n"
                    "Ensure ALL required fields are present with the correct types."
                )
                _sleep(sleep_seconds)

        except Exception as e:
            print(f"[json_synthesizer] ❌ Attempt {attempt} — Unexpected error: {e}")
            _sleep(sleep_seconds)

    raise ValueError(
        f"[json_synthesizer] Both synthesis attempts failed for '{product_name}'. "
        "Check Groq API key, model availability, and prompt integrity."
    )
