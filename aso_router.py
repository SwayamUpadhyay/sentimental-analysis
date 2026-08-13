
from datetime import datetime, timezone
import nltk

def _ensure_vader():
    try:
        from nltk.sentiment.vader import SentimentIntensityAnalyzer
        return SentimentIntensityAnalyzer()
    except LookupError:
        print("[aso_router] 📥 Downloading NLTK vader_lexicon (one-time)...")
        nltk.download("vader_lexicon", quiet=True)
        from nltk.sentiment.vader import SentimentIntensityAnalyzer
        return SentimentIntensityAnalyzer()

# Initialize analyzer globally
_analyzer = _ensure_vader()

def _get_sentiment_label(compound: float) -> str:
    """Map VADER compound score to simplified label."""
    if compound >= 0.05:
        return "POSITIVE"
    elif compound <= -0.05:
        return "NEGATIVE"
    return "NEUTRAL"

def _map_to_10_scale(compound_avg: float) -> float:
    """Map compound average (-1.0 to 1.0) to a 0.0 - 10.0 scale."""
    # -1.0 -> 0.0, 0.0 -> 5.0, 1.0 -> 10.0
    return round(((compound_avg + 1.0) / 2.0) * 10.0, 1)

def route(cleaned_data: dict, settings: dict, groq_client=None) -> tuple[list[dict], dict]:
    
    print("[aso_router] 🧠 Routing posts via NLTK VADER (Stats Mode)...")

    tagged = []
    
    # Tracking for aggregations
    daily_stats = {}  
    overall_counts = {"POSITIVE": 0, "NEUTRAL": 0, "NEGATIVE": 0}
    spectrum_counts = {"Critical": 0, "Negative": 0, "Neutral": 0, "Positive": 0, "Euphoric": 0}
    
    brand_scores = {} 
    
    colors = settings.get("design_colors", {})
    color_map = {
        "POSITIVE": colors.get("positive", "#00675e"),
        "NEGATIVE": colors.get("negative", "#b90035"),
        "NEUTRAL": colors.get("neutral", "#595c5e")
    }

    # Helper to process a post
    def _process(post_list, product_name, is_target):
        brand_scores[product_name] = brand_scores.get(product_name, [])
        for i, p in enumerate(post_list):
            text = p.get("text", "")
            utc = p.get("utc", 0.0)
            
            if not text: continue
            
            scores = _analyzer.polarity_scores(text)
            compound = scores["compound"]
            label = _get_sentiment_label(compound)
            
            brand_scores[product_name].append(compound)
            overall_counts[label] += 1
            
            # Spectrum chart tracking
            if compound >= 0.5: spectrum_counts["Euphoric"] += 1
            elif compound >= 0.05: spectrum_counts["Positive"] += 1
            elif compound <= -0.5: spectrum_counts["Critical"] += 1
            elif compound <= -0.05: spectrum_counts["Negative"] += 1
            else: spectrum_counts["Neutral"] += 1

            # Daily timeline tracking
            if utc > 0:
                try:
                    dt = datetime.fromtimestamp(utc, tz=timezone.utc)
                    day_str = dt.strftime("%b %d")
                    if day_str not in daily_stats:
                        daily_stats[day_str] = {"positive": 0, "neutral": 0, "negative": 0}
                    
                    if label == "POSITIVE": daily_stats[day_str]["positive"] += 1
                    elif label == "NEGATIVE": daily_stats[day_str]["negative"] += 1
                    else: daily_stats[day_str]["neutral"] += 1
                except Exception:
                    pass
            
            tagged.append({
                "product": product_name,
                "text": text,
                "sentiment": label,
                "is_competitor": not is_target,
            })

    # 1. Target
    target = cleaned_data.get("target", {})
    target_name = target.get("name", "Unknown")
    _process(target.get("posts", []), target_name, True)

    # 2. Competitors
    for comp_name, comp_data in cleaned_data.get("competitors", {}).items():
        _process(comp_data.get("posts", []), comp_name, False)

    # Compile Final Stats 
    
    # Timeline
    timeline_arr = []
    sorted_days = sorted(daily_stats.keys(), key=lambda d: datetime.strptime(d, "%b %d"))
    for d in sorted_days:
        timeline_arr.append({
            "name": d,
            "positive": daily_stats[d]["positive"],
            "neutral": daily_stats[d]["neutral"],
            "negative": daily_stats[d]["negative"]
        })

    # Donut Chart
    donut_arr = [
        {"name": "Positive", "value": overall_counts["POSITIVE"], "color": color_map["POSITIVE"]},
        {"name": "Neutral", "value": overall_counts["NEUTRAL"], "color": color_map["NEUTRAL"]},
        {"name": "Negative", "value": overall_counts["NEGATIVE"], "color": color_map["NEGATIVE"]},
    ]

    # Bar Chart (Community Analysis Spectrum)
    bar_color_map = {
        "Critical": "#b90035",
        "Negative": "#e0345e",
        "Neutral": "#595c5e",
        "Positive": "#009988",
        "Euphoric": "#00675e"
    }
    barChart_arr = []
    for k in ["Critical", "Negative", "Neutral", "Positive", "Euphoric"]:
        barChart_arr.append({
            "name": k,
            "value": spectrum_counts[k],
            "color": bar_color_map[k]
        })

    # Market Share Treemap (calculated from share of total posts)
    total_posts = sum(len(lst) for lst in brand_scores.values())
    marketShare_arr = []
    if total_posts > 0:
        for b_name, b_list in brand_scores.items():
            marketShare_arr.append({"name": b_name, "size": len(b_list)})

    # Sentiment Brands List (Target Product first always)
    sentimentBrands_arr = []
    
    def _brand_obj(name, is_target):
        lst = brand_scores.get(name, [])
        score = 5.0
        if lst:
            score = _map_to_10_scale(sum(lst) / len(lst))
        
        return {
            "name": name,
            "score": score,
            "color": "linear-gradient(90deg,#4a40e0,#00675e)" if is_target else "rgba(89,92,94,0.35)",
            "pct": int(score * 10)
        }

    # Add Target first
    sentimentBrands_arr.append(_brand_obj(target_name, True))
    
    # Add Competitors
    for comp_name in cleaned_data.get("competitors", {}).keys():
        sentimentBrands_arr.append(_brand_obj(comp_name, False))
        
    stats = {
        "brandScore": sentimentBrands_arr[0]["score"] if sentimentBrands_arr else 5.0,
        "timeline": timeline_arr,
        "donut": donut_arr,
        "barChart": barChart_arr,
        "marketShare": marketShare_arr,
        "sentimentBrands": sentimentBrands_arr
    }

    print(f"[aso_router] ✅ VADER Stats complete. Tagged {len(tagged)} posts. Target Score: {stats['brandScore']}/10")
    return tagged, stats

