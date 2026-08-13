
import io
import json
from datetime import datetime, timezone
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from groq import Groq

from data_manager import DataStore, MemoryStore
from reddit_scraper import scrape
from preprocessor import preprocess
from aso_router import route
from json_synthesizer import synthesize
from templates import PROMPTS



_SETTINGS_FILE = Path(__file__).parent / "settings.json"


def _load_settings() -> dict:
    with open(_SETTINGS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)



data_store = DataStore()
memory_store = MemoryStore()

_pipeline_status: dict = {
    "status": "idle",       # idle | running | done | error
    "product": None,
    "stage": "",
    "message": "",
    "started_at": None,
    "completed_at": None,
}



app = FastAPI(
    title="Lumina Analytics Backend",
    description=(
        "AI-native market sentiment intelligence pipeline. "
        "Ingests Reddit data, runs Adaptive Sentiment Orchestration (ASO), "
        "and synthesizes UI-ready JSON via Llama 3.1 70B on GroqCloud."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",   # Vite dev server (default)
        "http://localhost:3000",   # Alternative React dev port
        "http://localhost:4173",   # Vite preview
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Request / Response Models ────────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    product: str


class StatusResponse(BaseModel):
    status: str
    product: str | None
    stage: str
    message: str
    started_at: str | None
    completed_at: str | None


# ─── Pipeline Logic ───────────────────────────────────────────────────────────

def _update_status(
    status: str,
    stage: str,
    message: str,
    product: str | None = None,
    completed: bool = False,
) -> None:
    """Thread-safe-ish status update for the global pipeline state dict."""
    global _pipeline_status
    _pipeline_status["status"] = status
    _pipeline_status["stage"] = stage
    _pipeline_status["message"] = message
    if product is not None:
        _pipeline_status["product"] = product
    if completed:
        _pipeline_status["completed_at"] = datetime.now(timezone.utc).isoformat()


def _determine_sentiment_label(score: float) -> str:
    """Map a 0-10 score to a PastResults.jsx sentiment label."""
    if score >= 6.5:
        return "positive"
    if score < 4.0:
        return "critical"
    return "neutral"


def _determine_status_label(score: float) -> str:
    """Map a 0-10 score to a PastResults.jsx status label."""
    if score >= 6.5:
        return "Completed"
    if score < 4.0:
        return "Critical"
    return "Archived"


def run_pipeline(product_name: str) -> None:
    """
    Full analysis pipeline. Executed in the background by FastAPI's BackgroundTasks.

    Stages:
        1. Load settings & init Groq client
        2. Reddit scraping (target + competitors)
        3. Text preprocessing
        4. ASO sentiment routing
        5. JSON synthesis (Llama 3.1 70B)
        6. Persist to DataStore (Data.json) and MemoryStore (memory.json)
    """
    global _pipeline_status

    settings = _load_settings()
    groq_client = Groq(api_key=settings["groq_api_key"])

    try:
        import workflow_script as ws
        import run_batch
        
        # ── Stage 1: Competitors & Scraping ───────────────────────────────────
        _update_status("running", "scraping", f"Discovering competitors for '{product_name}'...", product=product_name)
        competitors = ws.get_similar_products(product_name)
        all_products = [product_name] + competitors
        all_data = []

        _update_status("running", "scraping", f"Scraping approx 70 posts each for: {', '.join(all_products)}...")
        for prod in all_products:
            posts = ws.scrape_reddit(prod, limit=70)
            all_data.extend(posts)

        # ── Stage 2: Preprocessing & Cache Building ───────────────────────────
        _run_pipeline_stages(product_name, all_data)

    except Exception as e:
        error_msg = str(e)
        print(f"[main] ❌ Pipeline failed for '{product_name}': {error_msg}")
        _update_status(
            "error", "failed",
            f"Pipeline error: {error_msg}",
            completed=True,
        )


def _run_pipeline_stages(product_name: str, all_data: list) -> None:
    """
    Shared stages 2-4: preprocessing, batch caching, and first ASO batch.
    Called by both run_pipeline() (Reddit path) and run_pipeline_from_csv() (upload path).
    """
    import workflow_script as ws
    import run_batch

    # ── Stage 2: Preprocessing & Cache Building ───────────────────────────
    _update_status("running", "preprocessing", "Cleaning and normalizing social data...")
    for item in all_data:
        item["preprocessed"] = ws.preprocess_text(item.get("original_text", ""))
    valid_data = [item for item in all_data if item["preprocessed"]]

    with open("Batches.json", "w") as f:
        json.dump(valid_data, f, indent=4)

    # ── Stage 3: Initialize Accumulation State ────────────────────────────
    stats = {
        "total": 0, "positive": 0, "negative": 0, "sarcastic_to_positive": 0, "sarcastic_to_negative": 0,
        "demographics": {"GEN Z (18-24)": 0, "MILLENNIALS (25-40)": 0, "GEN X (41-56)": 0, "BABY BOOMERS (57+)": 0},
        "sentiment_spectrum": {"Ultra Negative": 0, "Negative": 0, "Neutral": 0, "Positive": 0, "Ultra Positive": 0}
    }
    for c in ws.settings.get("community_clusters", []):
        stats[f"community_{c}"] = 0

    with open("sample.json", "w") as f:
        json.dump({"stats": stats, "dataset": [], "_target_product": product_name}, f, indent=4)

    # ── Stage 4: Process First Interactive Batch ──────────────────────────
    _update_status("running", "aso_routing", "Evaluating first autonomous AI batch of 15...")
    run_batch.run_next_batch()

    _update_status(
        "done", "complete",
        "✅ Analysis complete! 15 posts processed successfully.",
        completed=True,
    )
    print(f"[main] ✅ Pipeline complete for '{product_name}'. Batches securely cached.")


def run_pipeline_from_csv(product_name: str, all_data: list) -> None:
    """
    CSV/Excel upload pipeline — skips Reddit scraping.
    `all_data` is a list of dicts: [{"product": str, "original_text": str}, ...]
    already parsed from the uploaded file.
    """
    global _pipeline_status
    try:
        _run_pipeline_stages(product_name, all_data)
    except Exception as e:
        error_msg = str(e)
        print(f"[main] ❌ CSV pipeline failed for '{product_name}': {error_msg}")
        _update_status(
            "error", "failed",
            f"CSV pipeline error: {error_msg}",
            completed=True,
        )


# ─── Endpoints ────────────────────────────────────────────────────────────────

@app.post("/analyze", summary="Start a new product analysis")
async def analyze(request: AnalyzeRequest, background_tasks: BackgroundTasks):
    """
    Kick off the full sentiment analysis pipeline for a product.

    The pipeline runs in the background. Poll GET /status to track progress.
    Result is written to Data.json and accessible via GET /latest.
    """
    global _pipeline_status

    if _pipeline_status["status"] == "running":
        raise HTTPException(
            status_code=409,
            detail=f"A pipeline is already running for '{_pipeline_status['product']}'. "
                   "Wait for it to complete or restart the server.",
        )

    product = request.product.strip()
    if not product:
        raise HTTPException(status_code=400, detail="Product name cannot be empty.")

    # Reset status
    _pipeline_status = {
        "status": "running",
        "product": product,
        "stage": "initializing",
        "message": "Initializing Lumina Analytics pipeline...",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "completed_at": None,
    }

    background_tasks.add_task(run_pipeline, product)

    return {
        "status": "started",
        "product": product,
        "message": "Pipeline started. Poll GET /status for progress.",
    }


@app.get("/status", summary="Poll the current pipeline status")
async def status():
    """
    Returns the current state of the analysis pipeline.

    Status values:
        idle     — No pipeline has been run since server start.
        running  — Pipeline is actively processing.
        done     — Last pipeline completed successfully.
        error    — Last pipeline encountered an error.
    """
    return _pipeline_status


@app.get("/history", summary="Get all past analysis sessions")
async def history():
    """
    Builds per-product session summaries from sample.json dataset.
    Returns ONLY the target product (first column / first product in the dataset).
    Competitor products are used for comparison charts but should not appear here.
    """
    try:
        with open("sample.json", "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return {"total": 0, "sessions": []}
    except (json.JSONDecodeError, ValueError):
        return {"total": 0, "sessions": []}

    try:
        dataset = data.get("dataset", [])
        if not dataset:
            return {"total": 0, "sessions": []}

        # ── Identify the target product ───────────────────────────────────────
        # Stored explicitly when pipeline writes sample.json; fallback to first row.
        target_product = data.get("_target_product") or dataset[0].get("product", "")
        target_product_lower = target_product.lower()

        # ── Only count posts that belong to the TARGET product ────────────────
        target_posts = [
            item for item in dataset
            if item.get("product", "").lower() == target_product_lower
        ]

        if not target_posts:
            return {"total": 0, "sessions": []}

        pos   = sum(1 for p in target_posts if p.get("sentiment") == "positive")
        total = len(target_posts)
        score_0_10   = round((pos / total) * 10, 1) if total > 0 else 5.0
        positive_pct = round((pos / total) * 100)   if total > 0 else 50

        session = {
            "product":      target_product,
            "date":         datetime.now().strftime("%b %d, %Y"),
            "source":       "Reddit" if not data.get("_source") else data["_source"],
            "sourceIcon":   "folder" if data.get("_source") == "CSV" else "forum",
            "iconColor":    "#00675e" if data.get("_source") == "CSV" else "#4a40e0",
            "score":        score_0_10,
            "posts":        total,
            "positive_pct": positive_pct,
            "sentiment":    _determine_sentiment_label(score_0_10),
            "status":       _determine_status_label(score_0_10),
        }

        return {"total": 1, "sessions": [session]}

    except Exception as e:
        print(f"[history] Unexpected error building sessions: {e}")
        return {"total": 0, "sessions": []}


@app.post("/upload-csv", summary="Upload a CSV or Excel file with product reviews")
async def upload_csv(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    """
    Accept a CSV or Excel (.xlsx / .xls) file where:
      - Each COLUMN is one product.
      - Column HEADER (row 0) is the product name.
      - First column  = target product to analyze.
      - Remaining columns = competitor products.
      - Each row (after header) = one review / post text.

    Builds the same data structure as the Reddit scraper and feeds it
    straight into the pipeline stages (preprocessing → ASO → synthesis).
    """
    global _pipeline_status

    if _pipeline_status["status"] == "running":
        raise HTTPException(
            status_code=409,
            detail=f"A pipeline is already running for '{_pipeline_status['product']}'. Wait for it to complete.",
        )

    # ── Parse file ────────────────────────────────────────────────────────────
    filename = file.filename or ""
    ext = Path(filename).suffix.lower()

    if ext not in (".csv", ".xlsx", ".xls"):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Please upload a .csv, .xlsx, or .xls file.",
        )

    contents = await file.read()

    try:
        import pandas as pd
        buf = io.BytesIO(contents)
        if ext == ".csv":
            df = pd.read_csv(buf, dtype=str)
        else:
            df = pd.read_excel(buf, dtype=str)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Could not parse file: {e}")

    if df.empty or len(df.columns) < 1:
        raise HTTPException(status_code=422, detail="File has no columns. Ensure row 1 contains product names as headers.")

    # ── Extract product names from column headers ─────────────────────────────
    columns       = [c.strip() for c in df.columns.tolist()]
    target_product = columns[0]
    if not target_product:
        raise HTTPException(status_code=422, detail="First column header (target product name) is empty.")

    # ── Build all_data list ───────────────────────────────────────────────────
    all_data: list[dict] = []
    for col in columns:
        if not col:
            continue
        reviews = df[df.columns[columns.index(col)]].dropna().tolist()
        for review in reviews:
            text = str(review).strip()
            if text:
                all_data.append({"product": col, "original_text": text})

    if not all_data:
        raise HTTPException(status_code=422, detail="File contains no review text after parsing.")

    target_count     = sum(1 for d in all_data if d["product"] == target_product)
    competitor_count = len(all_data) - target_count
    competitor_names = [c for c in columns[1:] if c]

    print(
        f"[upload-csv] 📂 Parsed '{filename}': target='{target_product}' "
        f"({target_count} rows), competitors={competitor_names} ({competitor_count} rows total)."
    )

    # ── Reset pipeline status ─────────────────────────────────────────────────
    _pipeline_status = {
        "status":      "running",
        "product":     target_product,
        "stage":       "initializing",
        "message":     f"Processing uploaded file for '{target_product}'...",
        "started_at":  datetime.now(timezone.utc).isoformat(),
        "completed_at": None,
    }

    # Pass source marker so history endpoint can label it correctly
    background_tasks.add_task(_run_csv_pipeline_with_marker, target_product, all_data)

    return {
        "status":          "started",
        "product":         target_product,
        "competitors":     competitor_names,
        "total_reviews":   len(all_data),
        "target_reviews":  target_count,
        "message":         "CSV pipeline started. Poll GET /status for progress.",
    }


def _run_csv_pipeline_with_marker(product_name: str, all_data: list) -> None:
    """Wrapper: tags sample.json with _source=CSV then delegates to shared stages."""
    global _pipeline_status
    try:
        import workflow_script as ws
        import run_batch

        _update_status("running", "preprocessing", "Cleaning reviews from uploaded file...", product=product_name)

        for item in all_data:
            item["preprocessed"] = ws.preprocess_text(item.get("original_text", ""))
        valid_data = [item for item in all_data if item["preprocessed"]]

        with open("Batches.json", "w", encoding="utf-8") as f:
            json.dump(valid_data, f, indent=4)

        stats = {
            "total": 0, "positive": 0, "negative": 0,
            "sarcastic_to_positive": 0, "sarcastic_to_negative": 0,
            "demographics": {"GEN Z (18-24)": 0, "MILLENNIALS (25-40)": 0, "GEN X (41-56)": 0, "BABY BOOMERS (57+)": 0},
            "sentiment_spectrum": {"Ultra Negative": 0, "Negative": 0, "Neutral": 0, "Positive": 0, "Ultra Positive": 0}
        }
        for c in ws.settings.get("community_clusters", []):
            stats[f"community_{c}"] = 0

        with open("sample.json", "w", encoding="utf-8") as f:
            json.dump({
                "stats":            stats,
                "dataset":          [],
                "_target_product":  product_name,
                "_source":          "CSV",
            }, f, indent=4)

        _update_status("running", "aso_routing", "Evaluating sentiment from uploaded reviews...")
        run_batch.run_next_batch()

        _update_status("done", "complete", "✅ CSV analysis complete!", completed=True)
        print(f"[main] ✅ CSV pipeline complete for '{product_name}'.")

    except Exception as e:
        error_msg = str(e)
        print(f"[main] ❌ CSV pipeline failed: {error_msg}")
        _update_status("error", "failed", f"CSV pipeline error: {error_msg}", completed=True)


@app.get("/latest", summary="Get the most recent analysis payload")
async def latest():
    """
    Returns the full payload of the most recent completed analysis directly from the AI workflow.
    """
    try:
        with open("sample.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail="No analyses found in sample.json. Run workflow_script.py first.",
        )


@app.post("/next_batch", summary="Process the next 15 accumulated posts")
async def process_next_batch():
    """
    Programmatically pops the next 15 records from Batches.json cache, 
    evaluates using Light/Heavy LLM routing, appends to sample.json, 
    and regenerates Deep Market Analytics.
    """
    import run_batch
    try:
        new_state = run_batch.run_next_batch()
        if "error" in new_state:
            return {"status": "done", "message": new_state["error"]}
        return {"status": "success", "message": "Batch processed successfully.", "payload": new_state}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/keywords", summary="NLP+LLM aspect-level voice analysis")
async def keywords():
    """
    3-stage pipeline:
    Stage 1 — NLTK POS tagging extracts product-aspect nouns from all posts.
    Stage 2 — Context window (±4 tokens around each noun per sentence) preserves
               the sentiment descriptors. Each snippet tagged with post sentiment.
    Stage 3 — Compact LLM prompt: sends (aspect, [context_snippets]) pairs and
               asks model to classify each as "positive" or "negative" about the product.

    Result cached in sample.json['keyword_signals'] keyed by total post count,
    so the LLM is only called when new posts arrive.
    """
    import re
    from collections import Counter, defaultdict

    # ── NLTK setup ──────────────────────────────────────────────────────────────
    try:
        import nltk
        from nltk.corpus import stopwords

        for resource in ['stopwords', 'averaged_perceptron_tagger_eng',
                         'averaged_perceptron_tagger', 'punkt', 'punkt_tab']:
            try:
                if resource.startswith('averaged'):
                    nltk.data.find(f'taggers/{resource}')
                elif resource in ('punkt', 'punkt_tab'):
                    nltk.data.find(f'tokenizers/{resource}')
                else:
                    nltk.data.find(f'corpora/{resource}')
            except LookupError:
                nltk.download(resource, quiet=True)

        from nltk.corpus import stopwords
        from nltk import pos_tag, word_tokenize
        stop_words = set(stopwords.words('english'))
        nltk_ok = True
    except Exception:
        stop_words = set()
        nltk_ok = False

    # ── Load data ───────────────────────────────────────────────────────────────
    try:
        with open("sample.json", "r", encoding="utf-8") as f:
            sample = json.load(f)
    except FileNotFoundError:
        return {"keywords": []}

    dataset = sample.get("dataset", [])
    if not dataset:
        return {"keywords": []}

    target_product = dataset[0].get("product", "").lower()
    total_posts    = sample.get("stats", {}).get("total", len(dataset))

    # ── Cache check — skip LLM if nothing new ───────────────────────────────────
    cached = sample.get("keyword_signals", {})
    if cached.get("computed_at_total") == total_posts and cached.get("keywords"):
        return {"keywords": cached["keywords"]}

    # ── Filter to target product posts ──────────────────────────────────────────
    target_posts = [
        item for item in dataset
        if item.get("product", "").lower() == target_product
    ]
    if not target_posts:
        return {"keywords": []}

    print(f"[keywords] Running NLP+LLM pipeline on {len(target_posts)} target posts…")

    # ── Stopwords we never want as aspects ──────────────────────────────────────
    aspect_stops = stop_words | {
        'one','use','used','using','get','got','make','know','think','come',
        'like','also','even','well','back','give','take','said','going','still',
        'would','could','want','need','will','now','here','there','they','them',
        'their','have','been','with','from','that','this','those','these',
        'been','more','than','about','out','can','all','just','really','much',
        'very','first','then','also','such','some','many','most','other',
        'new','old','good','bad','great','nice','okay','same','way','must',
        'im','ive','dont','cant','wont','isnt','thats','doesnt','didnt',
        'https','www','com','html','amp','reddit','post','thing','time',
        # Extra generic nouns to suppress
        'lot','bit','kind','sort','type','part','fact','case','point','place',
        'side','year','month','day','week','guy','person','people','user','users',
        'anyone','someone','everyone','reason','stuff','issue','problem','question',
        'comment','answer','review','thread','update','version','model','device',
        'product','phone','item','unit','piece','opinion','thought','experience',
    }
    # Remove product name tokens so the product itself isn't a featured aspect
    for tok in target_product.split():
        if len(tok) > 2:
            aspect_stops.add(tok.lower())

    # ── Tech-feature boosting: known product feature terms get extra weight ───────
    # These are promoted to appear earlier even if document frequency is lower.
    TECH_FEATURE_BOOST = {
        'camera','battery','display','screen','processor','performance','speaker',
        'audio','charging','storage','memory','ram','chip','sensor','microphone',
        'keyboard','trackpad','touchpad','lens','zoom','aperture','resolution',
        'brightness','refresh','latency','thermals','heat','cooling','fan',
        'build','design','weight','thickness','size','port','connector','cable',
        'software','firmware','os','interface','ui','ux','app','feature',
        'fingerprint','faceid','scanner','unlock','notch','bezel','frame',
        'aluminum','glass','plastic','metal','hinge','keyboard','switch',
        'wifi','bluetooth','signal','reception','modem','antenna','nfc',
        'acceleration','benchmark','graphics','gpu','cpu','efficiency',
        'endurance','lifespan','durability','waterproof','resistance','rating',
        'price','value','cost','budget','premium','warranty','support',
    }

    # ── Stage 1: POS-tag & extract nouns ────────────────────────────────────────
    # Collect nouns that appear in multiple posts (true product aspects)
    noun_doc_freq: Counter = Counter()   # noun → number of posts it appears in
    noun_total_freq: Counter = Counter() # noun → total occurrences

    for item in target_posts:
        text = item.get("original_msg", "")
        sentences = re.split(r'[.!?\n]+', text)
        seen_in_post = set()
        for sent in sentences:
            try:
                tokens  = word_tokenize(sent) if nltk_ok else sent.split()
                tagged  = pos_tag(tokens)     if nltk_ok else [(t, 'NN') for t in tokens]
            except Exception:
                tagged  = [(t, 'NN') for t in sent.split()]

            for word, tag in tagged:
                w = word.lower()
                # Accept NN (singular noun) and NNS (plural noun) only
                if tag not in ('NN', 'NNS'):
                    continue
                if len(w) < 4 or w in aspect_stops:
                    continue
                # Apply tech-feature boost: count known feature words extra
                boost = 3 if w in TECH_FEATURE_BOOST else 1
                noun_total_freq[w] += boost
                if w not in seen_in_post:
                    noun_doc_freq[w] += boost
                    seen_in_post.add(w)

    # Take top-14 nouns by document frequency (appear in most posts = true aspects)
    top_nouns = [w for w, _ in noun_doc_freq.most_common(14) if noun_doc_freq[w] >= 2]
    if not top_nouns:
        # Fallback: single-occurrence nouns if corpus is tiny
        top_nouns = [w for w, _ in noun_total_freq.most_common(10)]


    # ── Stage 2: Context window extraction ──────────────────────────────────────
    # For each top noun: collect up to 4 short context snippets (±4 tokens, with sentiment)
    aspect_contexts: dict[str, list[str]] = defaultdict(list)

    for item in target_posts:
        text          = item.get("original_msg", "")
        post_sentiment = item.get("sentiment", "negative")
        sentences = re.split(r'[.!?\n]+', text)

        for sent in sentences:
            try:
                tokens = word_tokenize(sent.lower()) if nltk_ok else sent.lower().split()
            except Exception:
                tokens = sent.lower().split()

            for noun in top_nouns:
                if noun not in tokens:
                    continue
                idx     = tokens.index(noun)
                window  = tokens[max(0, idx - 4): idx + 5]  # ±4 tokens
                snippet = " ".join(window).strip()
                if len(snippet) < 6:
                    continue
                tagged_snippet = f"[{post_sentiment.upper()}] {snippet}"
                if len(aspect_contexts[noun]) < 5:   # max 5 snippets per aspect
                    aspect_contexts[noun].append(tagged_snippet)

    # Only keep aspects that actually have context snippets
    aspects_with_context = {n: aspect_contexts[n] for n in top_nouns if aspect_contexts[n]}
    if not aspects_with_context:
        return {"keywords": []}

    # ── Stage 3: LLM classification ─────────────────────────────────────────────
    # Build compact aspect block — only nouns + their context snippets
    aspect_block = ""
    for noun, snippets in list(aspects_with_context.items())[:12]:
        ctxs = " | ".join(snippets[:4])
        aspect_block += f"  {noun.title()}: {ctxs}\n"

    # Use centralized prompt template from PROMPTS registry
    llm_prompt = PROMPTS["keyword_aspect_classification"]["template"].format(
        product_name=target_product.title(),
        aspect_block=aspect_block,
    )


    print(f"[keywords] Sending {len(aspects_with_context)} aspects to LLM for classification…")

    try:
        settings = _load_settings()
        client   = Groq(api_key=settings["groq_api_key"])
        res = client.chat.completions.create(
            model    = settings.get("model_light", "llama-3.1-8b-instant"),
            messages = [{"role": "user", "content": llm_prompt}],
            temperature     = 0.1,
            max_tokens      = 512,
            response_format = {"type": "json_object"},
        )
        raw = json.loads(res.choices[0].message.content.strip())
    except Exception as e:
        print(f"[keywords] LLM error: {e}")
        return {"keywords": []}

    aspects_classified = raw.get("aspects", [])
    if not aspects_classified:
        return {"keywords": []}

    # ── Build frontend-ready keyword objects ─────────────────────────────────────
    pos_colors = ['#00675e', '#00a896', '#005a52', '#34c9b8', '#00897b']
    neg_colors = ['#b90035', '#e05c75', '#930028', '#ff616f', '#c62828']

    pos_items = [a for a in aspects_classified if a.get("sentiment") == "positive"][:5]
    neg_items = [a for a in aspects_classified if a.get("sentiment") == "negative"][:5]

    # Frequency for sizing (use noun_total_freq for the root noun)
    def get_freq(word_label: str) -> int:
        root = word_label.lower().split()[0]
        return noun_total_freq.get(root, 1)

    all_freqs = [get_freq(a["word"]) for a in pos_items + neg_items]
    max_freq  = max(all_freqs, default=1)

    result = []
    for i, a in enumerate(pos_items):
        freq   = get_freq(a["word"])
        w      = 0.55 + 0.45 * (freq / max_freq)
        result.append({
            "word":      a["word"],
            "count":     freq,
            "sentiment": "positive",
            "size":      f"{round(1.1 + w * 1.4, 2)}rem",
            "weight":    500 + int(w * 400),
            "color":     pos_colors[i % len(pos_colors)],
        })
    for i, a in enumerate(neg_items):
        freq   = get_freq(a["word"])
        w      = 0.55 + 0.45 * (freq / max_freq)
        result.append({
            "word":      a["word"],
            "count":     freq,
            "sentiment": "negative",
            "size":      f"{round(1.1 + w * 1.4, 2)}rem",
            "weight":    500 + int(w * 400),
            "color":     neg_colors[i % len(neg_colors)],
        })

    print(f"[keywords] ✅ {len(pos_items)} positive + {len(neg_items)} negative aspects classified.")

    # ── Cache result in sample.json ─────────────────────────────────────────────
    try:
        sample["keyword_signals"] = {
            "computed_at_total": total_posts,
            "keywords":          result,
        }
        with open("sample.json", "w", encoding="utf-8") as f:
            json.dump(sample, f, indent=4)
    except Exception as e:
        print(f"[keywords] Cache write failed: {e}")

    return {"keywords": result}




@app.get("/health", summary="Server health check")
async def health():
    """Simple health check. Returns 200 OK if server is running."""
    return {
        "status": "ok",
        "service": "Lumina Analytics Backend",
        "version": "1.0.0",
        "total_sessions": data_store.count(),
        "pipeline_status": _pipeline_status["status"],
    }
