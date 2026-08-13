"""
templates.py — Product Analytics LLM Prompt Registry

Each entry in PROMPTS is a structured dict (expressed as Python/JSON) that defines:
  - intent      : What this prompt is trying to accomplish.
  - model       : Which model tier should handle it (model_light or model_heavy).
  - output      : Exact description of what the LLM MUST return (schema / format).
  - template    : The actual prompt string — use .format(**kwargs) to inject values.

Usage:
    from templates import build_prompt
    prompt_str = build_prompt("competitor_discovery",
                              product_name="iPhone 16",
                              max_competitors=3)

    # Or access the raw structure:
    from templates import PROMPTS
    entry   = PROMPTS["intent_classification"]
    intent  = entry["intent"]      # what this call does
    schema  = entry["output"]      # what the LLM must return
    prompt  = entry["template"].format(text=my_text)
"""

from typing import Any


# ─── Prompt Registry ─────────────────────────────────────────────────────────
#
# Each key maps to a structured prompt definition.
# "template" is the only string that reaches the LLM; the rest is metadata.
#
PROMPTS: dict[str, dict[str, Any]] = {

    # ──────────────────────────────────────────────────────────────────────────
    # COMPETITOR DISCOVERY
    # ──────────────────────────────────────────────────────────────────────────
    "competitor_discovery": {
        "intent": (
            "Identify the top real, direct-competing product names for a given "
            "product so the scraper can fetch Reddit data for comparison."
        ),
        "model": "model_light",
        "output": {
            "type": "json_array",
            "description": "A JSON array of product name strings — nothing else.",
            "example": '["Samsung Galaxy S25", "Google Pixel 9", "OnePlus 13"]',
            "rules": [
                "No markdown, no explanation, no extra text.",
                "Real, well-known product names only.",
                "Do NOT include the original product in the list.",
            ],
        },
        "template": (
            "You are a market research assistant.\n"
            "Given a product name, identify up to {max_competitors} real, direct "
            "competing products currently available in the market.\n\n"
            "Output ONLY a valid JSON array of product name strings.\n"
            "No explanation, no markdown, no extra text whatsoever.\n"
            "Use real, well-known product names only.\n"
            "Do NOT include the original product itself in the list.\n\n"
            'Example output: ["Competitor A", "Competitor B", "Competitor C"]\n\n'
            "Product: {product_name}"
        ),
    },

    # ──────────────────────────────────────────────────────────────────────────
    # INTENT CLASSIFICATION
    # ──────────────────────────────────────────────────────────────────────────
    "intent_classification": {
        "intent": (
            "Classify the emotional intent of a Reddit post about a product. "
            "Questions and advice-seeking posts signal dissatisfaction or uncertainty "
            "(NEGATIVE). Clear declarative statements of praise are POSITIVE. "
            "The ASO router uses this label to route neutral/complex posts to the "
            "heavy model for deeper analysis."
        ),
        "model": "model_light",
        "output": {
            "type": "single_token",
            "description": "Exactly one word from the allowed label set.",
            "allowed_values": ["POSITIVE", "NEGATIVE", "NEUTRAL", "COMPLEX"],
            "rules": [
                "No punctuation, no explanation, no extra text.",
                "POSITIVE: A declarative statement expressing clear satisfaction, praise, "
                "or recommendation about a product feature — NOT a question.",
                "NEGATIVE: The post is a question seeking advice/validation, OR expresses "
                "clear dissatisfaction, complaint, or frustration.",
                "NEUTRAL: Factual, balanced, or purely informational — not emotional.",
                "COMPLEX: Mixed, ambiguous, ironic, or sarcastic — impossible to classify clearly.",
                "CRITICAL RULE: If the text contains a question (ends with '?' or uses "
                "phrases like 'should I', 'would you', 'is it worth', 'can anyone', "
                "'anyone else', 'help me') — always classify as NEGATIVE regardless of tone.",
            ],
        },
        "template": (
            "You are a precision intent classifier for Reddit posts about products.\n\n"
            "CLASSIFICATION RULES:\n"
            "  POSITIVE  — A declarative statement (NOT a question) expressing clear "
            "satisfaction, praise, or recommendation about a product or feature.\n"
            "  NEGATIVE  — The post is asking for advice/help/validation (question format), "
            "OR expresses dissatisfaction, frustration, complaints, or problems.\n"
            "  NEUTRAL   — Purely factual, informational, balanced — no emotional charge.\n"
            "  COMPLEX   — Ambiguous, mixed, ironic, or sarcastic — hard to classify.\n\n"
            "CRITICAL RULE:\n"
            "  If the text contains a question mark (?), or uses phrases like "
            "'should I', 'would you recommend', 'is it worth', 'can anyone', "
            "'anyone have experience', 'help me', 'what do you think' — "
            "classify as NEGATIVE because it signals uncertainty or dissatisfaction.\n\n"
            "Output ONLY the single label word. No punctuation. No explanation.\n\n"
            "Text: {text}"
        ),
    },

    # ──────────────────────────────────────────────────────────────────────────
    # SARCASM DETECTION
    # ──────────────────────────────────────────────────────────────────────────
    "sarcasm_detection": {
        "intent": (
            "Detect whether a COMPLEX-flagged post uses sarcasm or irony so "
            "the ASO router can flip the sentiment label before counting."
        ),
        "model": "model_light",
        "output": {
            "type": "single_token",
            "description": "Exactly one word — either SARCASM or LITERAL.",
            "allowed_values": ["SARCASM", "LITERAL"],
            "rules": [
                "No punctuation, no explanation, no extra text.",
                "SARCASM means the text says the opposite of what it means.",
            ],
        },
        "template": (
            "You are an expert sarcasm and irony detector for social media text.\n"
            "Determine if the following text uses sarcasm or irony.\n\n"
            "Output ONLY one of: SARCASM or LITERAL\n"
            "No explanation. No punctuation. No extra text.\n\n"
            "Text: {text}"
        ),
    },

    # ──────────────────────────────────────────────────────────────────────────
    # KEYWORD / ASPECT CLASSIFICATION
    # (Word cloud — feature-sentiment tagging)
    # ──────────────────────────────────────────────────────────────────────────
    "keyword_aspect_classification": {
        "intent": (
            "Given a list of product-aspect nouns extracted from Reddit posts "
            "(via NLTK POS-tagging) together with surrounding context snippets, "
            "classify whether users speak about each aspect positively or negatively. "
            "Only genuine product features/specs should survive — generic words must "
            "be dropped. The result feeds the Voice Analysis word cloud on the "
            "Intelligence Dashboard."
        ),
        "model": "model_light",
        "output": {
            "type": "json_object",
            "description": (
                "A single JSON object with an 'aspects' array. Each element "
                "must have 'word' (human-readable feature label, title-case, "
                "≤3 words) and 'sentiment' (exactly 'positive' or 'negative')."
            ),
            "example": {
                "aspects": [
                    {"word": "Battery Life",    "sentiment": "positive"},
                    {"word": "Camera Quality",  "sentiment": "positive"},
                    {"word": "Heating Issue",   "sentiment": "negative"},
                    {"word": "Display",         "sentiment": "positive"},
                    {"word": "Software Bugs",   "sentiment": "negative"},
                ]
            },
            "rules": [
                "Include ONLY product features, specs, or characteristics.",
                "EXCLUDE generic/abstract words (e.g. 'thing', 'time', 'people').",
                "If an aspect is not a product feature, omit it entirely.",
                "No markdown, no backticks, no extra text outside the JSON.",
                "'sentiment' must be lowercase 'positive' or 'negative'.",
            ],
        },
        "template": (
            "You are a product analyst. Below are product aspects extracted from "
            "Reddit posts about '{product_name}', with short context snippets tagged "
            "[POSITIVE] or [NEGATIVE] (the post-level sentiment).\n\n"
            "TASK: Classify whether users speak about each aspect positively or "
            "negatively overall based on the context snippets.\n\n"
            "STRICT OUTPUT RULES:\n"
            '1. Return ONLY a raw JSON object — no markdown, no backticks.\n'
            '2. Format: {{"aspects": [{{"word": "Battery Life", "sentiment": "positive"}}, ...]}}\n'
            "3. Include ONLY real product features/specs (e.g. Battery Life, "
            "Camera Quality, Display, Performance, Charging Speed, Build Quality).\n"
            "4. OMIT any aspect that is not a tangible product feature "
            "(e.g. skip 'people', 'time', 'thing', 'review', 'version').\n"
            "5. 'sentiment' must be exactly \"positive\" or \"negative\".\n"
            "6. 'word' must be title-case, ≤3 words.\n\n"
            "Aspects and their user-context snippets:\n"
            "{aspect_block}"
        ),
    },

    # ──────────────────────────────────────────────────────────────────────────
    # JSON PAYLOAD CONSTRUCTION
    # (Full intelligence report — Llama 3.1 70B)
    # ──────────────────────────────────────────────────────────────────────────
    "json_payload_construction": {
        "intent": (
            "Synthesize sentiment-tagged Reddit data for a product and its "
            "competitors into a single structured JSON intelligence report that "
            "the React frontend (Lumina Analytics) renders across all dashboard "
            "pages. The output must conform exactly to the LuminaPayload Pydantic "
            "schema validated by json_synthesizer.py."
        ),
        "model": "model_heavy",
        "output": {
            "type": "json_object",
            "description": (
                "A single JSON object matching the LuminaPayload schema. "
                "Every field is required. No markdown fences. No extra text."
            ),
            "schema_summary": {
                "brandName":        "string — the target product name",
                "overallScore":     "float 0.0–10.0 — aggregate sentiment score",
                "keywords": [
                    {
                        "word":      "string — a product feature or spec (NOT a generic word)",
                        "size":      "string — CSS rem value e.g. '2.25rem'",
                        "color":     "string — hex color from design palette",
                        "weight":    "integer — font weight e.g. 700",
                        "sentiment": "string — 'positive' or 'negative' about this feature",
                    }
                ],
                "demographics": [{"label": "string", "pct": "integer 0-100", "color": "hex"}],
                "clusters":     [
                    {
                        "label": "string", "users": "string e.g. '12.4k'",
                        "size": "integer px", "color": "rgba", "border": "rgba",
                        "textColor": "hex", "top": "CSS %", "left": "CSS %",
                    }
                ],
                "platformPosts":    ["string verbatim quote", "...", "..."],
                "sentimentBrands":  [{"name": "string", "score": "float 0-10", "color": "hex", "pct": "integer"}],
                "trendingTopics": [
                    {
                        "badge": "string", "badgeColor": "hex",
                        "title": "string", "desc": "string",
                        "positive": "string e.g. '84% Positive'",
                        "icon": "string Material Symbol name",
                        "iconColor": "hex", "discussions": "string",
                        "bg": "CSS gradient string",
                    }
                ],
                "performanceMetrics": {
                    "totalMentions": "integer",
                    "avgResponseTime": "string",
                    "analysisAccuracy": "integer 0-100",
                },
            },
            "rules": [
                "Output ONLY valid JSON. No markdown code fences, no explanation.",
                "Every field in schema_summary is REQUIRED — do not omit any.",
                "keywords must ONLY contain product features/specs mentioned in Reddit posts.",
                "Do NOT use generic words like 'product', 'thing', 'people' as keywords.",
                "Each keyword must include a 'sentiment' field: 'positive' or 'negative'.",
                "Use ONLY the design system colors provided — never invent random hex codes.",
                "All sentiment scores: 0.0 to 10.0 scale.",
                "Demographics percentages must sum to exactly 100.",
                "Community clusters must use ONLY the allowed cluster labels provided.",
                "Populate ≥5 keywords, ≥3 demographics, ≥3 clusters, 3 platform posts, "
                "all competitors as sentimentBrands, ≥3 trending topics.",
            ],
        },
        "template": (
            'You are an elite market analyst AI known as the "Ethereal Analyst".\n'
            'You will receive aggregated, sentiment-tagged Reddit data for the product '
            '"{product_name}" and its competitors.\n\n'

            "YOUR TASK: Synthesize this data into a precise JSON intelligence report.\n\n"

            "══ CRITICAL RULES ══\n"
            "1. Output ONLY valid JSON. No markdown code fences, no explanation text.\n"
            "2. Every field listed in the schema is REQUIRED. Do not omit any field.\n"
            "3. Use ONLY these design system colors — never invent random colors:\n"
            "     Primary/Brand:     {color_primary}\n"
            "     Positive/Good:     {color_positive}\n"
            "     Negative/Critical: {color_negative}\n"
            "     Neutral/Muted:     {color_neutral}\n"
            "4. All sentiment scores use a 0.0 to 10.0 scale.\n"
            "5. Demographics percentages must sum to exactly 100.\n"
            "6. Community clusters must use ONLY these labels: {cluster_labels}.\n"
            "7. Populate ≥5 keywords, ≥3 demographics, ≥3 clusters, 3 platform posts, "
            "all competitors as sentimentBrands, ≥3 trending topics.\n"
            "8. keywords MUST be product features or specs mentioned in the Reddit data "
            "(e.g. camera, battery, display, performance, price). "
            "Do NOT include generic words like 'product', 'thing', 'people', 'time'.\n"
            "9. Each keyword MUST include a 'sentiment' field set to 'positive' or 'negative' "
            "based on whether users praise or criticise that feature.\n\n"

            "══ SENTIMENT DATA INPUT ══\n"
            "{sentiment_data}\n\n"

            "══ REQUIRED JSON STRUCTURE ══\n"
            "{{\n"
            '  "brandName": "{product_name}",\n'
            '  "overallScore": <number 0.0-10.0>,\n'
            '  "keywords": [\n'
            '    {{"word": "Camera Quality", "size": "2.25rem", "color": "#hex", '
            '"weight": 700, "sentiment": "positive"}}\n'
            "  ],\n"
            '  "demographics": [\n'
            '    {{"label": "Gen Z (18-24)", "pct": <integer 0-100>, "color": "#hex"}}\n'
            "  ],\n"
            '  "clusters": [\n'
            "    {{\n"
            '      "label": "Tech", "users": "12.4k", "size": 120,\n'
            '      "color": "rgba(74,64,224,0.15)", "border": "rgba(74,64,224,0.4)",\n'
            '      "textColor": "#4a40e0", "top": "10%", "left": "20%"\n'
            "    }}\n"
            "  ],\n"
            '  "platformPosts": ["verbatim quote 1", "verbatim quote 2", "verbatim quote 3"],\n'
            '  "sentimentBrands": [\n'
            '    {{"name": "string", "score": <0.0-10.0>, "color": "#hex", "pct": <integer>}}\n'
            "  ],\n"
            '  "trendingTopics": [\n'
            "    {{\n"
            '      "badge": "High Velocity", "badgeColor": "#hex",\n'
            '      "title": "string", "desc": "string",\n'
            '      "positive": "84% Positive", "icon": "trending_up",\n'
            '      "iconColor": "#hex", "discussions": "string",\n'
            '      "bg": "linear-gradient(135deg, rgba(74,64,224,0.1), rgba(0,103,94,0.05))"\n'
            "    }}\n"
            "  ],\n"
            '  "performanceMetrics": {{\n'
            '    "totalMentions": <integer>,\n'
            '    "avgResponseTime": "string e.g. 2.4 hours",\n'
            '    "analysisAccuracy": <integer 0-100>\n'
            "  }}\n"
            "}}"
        ),
    },
}


# ─── Convenience Helper ───────────────────────────────────────────────────────

def build_prompt(key: str, **kwargs) -> str:
    """
    Retrieve the formatted template string for a given prompt key.

    Args:
        key:     One of the PROMPTS dict keys.
        **kwargs: Variable substitutions for the template's {placeholders}.

    Returns:
        The final prompt string ready to send to the LLM.

    Raises:
        KeyError: If `key` is not found in PROMPTS.
    """
    entry = PROMPTS[key]
    return entry["template"].format(**kwargs)
