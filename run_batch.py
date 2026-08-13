import json
import os
from datetime import date
import workflow_script as ws

def run_next_batch():
    print("Fetching next batch...")
    if not os.path.exists("Batches.json"): return {"error": "No batches left"}
    with open("Batches.json", "r") as f: valid_data = json.load(f)
    if not valid_data: return {"error": "No batches left"}
    
    # Manual batch extraction instead of generator to perfectly map state
    by_product = {}
    for item in valid_data:
        prod = item["product"]
        if prod not in by_product: by_product[prod] = []
        by_product[prod].append(item)
    
    batch_data = []
    products = list(by_product.keys())
    for prod in products:
        batch_data.extend(by_product[prod][:3])
        by_product[prod] = by_product[prod][3:]
        
    if not batch_data: return {"error": "No batches left"}
    
    remaining_data = []
    for prod in products: remaining_data.extend(by_product[prod])
    
    # Load state
    with open("sample.json", "r", encoding="utf-8") as f:
        state = json.load(f)
        stats = state["stats"]
        dataset = state["dataset"]
        
    # Process batch
    print(f"\n==========================================")
    print(f"   Processing Batch ({len(batch_data)} posts)")
    print(f"==========================================")
    
    print(">> Running Lightweight LLM...")
    texts = [item["preprocessed"] for item in batch_data]
    labels_light = ws.label_lightweight(texts)
    for item, label in zip(batch_data, labels_light):
        item["light_label"] = label
        
    sarcastic_indices = [i for i, item in enumerate(batch_data) if item["light_label"] == "sarcastic"]
    sarcastic_texts = [batch_data[i]["preprocessed"] for i in sarcastic_indices]
    if sarcastic_indices:
        print(f">> Running Heavy LLM on {len(sarcastic_indices)} sarcastic posts...")
        heavy_labels = ws.label_heavy(sarcastic_texts)
        for i, heavy_label in zip(sarcastic_indices, heavy_labels):
            batch_data[i]["final_label"] = heavy_label
            
    print(">> Running User Profiling LLM (Community + Demographic)...")
    user_profiles = ws.label_user_profile(texts)
    for item, prof in zip(batch_data, user_profiles):
        item["community"] = prof["community"]
        item["demographic"] = prof["demographic"]
        
    print("\n--- Batch Results ---")
    for item in batch_data:
        label = item.get("final_label", item["light_label"])
        if label not in ["positive", "negative"]: label = "negative"
        comm = item.get("community", "Casual Users")
        demo = item.get("demographic", "MILLENNIALS (25-40)")
        
        if item["light_label"] == "sarcastic":
            if label == "positive": stats["sarcastic_to_positive"] += 1
            else: stats["sarcastic_to_negative"] += 1
            
        orig = item["original_text"].replace('\n', ' ')
        if len(orig) > 70: orig = orig[:67] + "..."
        print(f"[{label.upper():^8}|{comm[:8]:^8}|{demo[:5]:^5}] {item['product'][:15]:<15} | {orig}")
            
        vader_score = ws.sia.polarity_scores(item["original_text"])["compound"]
        ai_score = 1.0 if label == "positive" else (-1.0 if label == "negative" else 0.0)
        spectrum = (vader_score + ai_score) / 2
        
        if spectrum < -0.6: bucket = "Ultra Negative"
        elif spectrum < -0.2: bucket = "Negative"
        elif spectrum <= 0.2: bucket = "Neutral"
        elif spectrum <= 0.6: bucket = "Positive"
        else: bucket = "Ultra Positive"
        
        today = str(date.today())  # e.g. "2026-04-12"
        dataset.append({
            "product": item["product"],
            "original_msg": item["original_text"],
            "sentiment": label,
            "community": comm,
            "demographic": demo,
            "spectrum_score": spectrum,
            "spectrum_bucket": bucket,
            "date": today
        })
        stats[label] = stats.get(label, 0) + 1
        stats[f"community_{comm}"] = stats.get(f"community_{comm}", 0) + 1
        stats["demographics"][demo] += 1
        stats["sentiment_spectrum"][bucket] += 1
        stats["total"] += 1

        # Daily timeline for target product only
        product_name_early = batch_data[0]["product"] if batch_data else "Unknown"
        if item["product"] == product_name_early:
            daily_tl = state.setdefault("daily_timeline", {})
            day_entry = daily_tl.setdefault(today, {"date": today, "positive": 0, "negative": 0, "total": 0})
            day_entry["total"] += 1
            if label == "positive": day_entry["positive"] += 1
            else: day_entry["negative"] += 1
        
    # Generate market intelligence (LLM only — no extra Reddit scraping per vertical,
    # which previously caused every batch to stall for 3-10 extra minutes)
    print("\nGenerating Deep Market Analytics (Vitality, Verticals & Narratives)...")
    product_name = dataset[0]["product"] if dataset else "Unknown"
    original_target_msgs = [d["original_msg"] for d in dataset if d["product"].lower() == product_name.lower()]
    market_intelligence = state.get("market_intelligence", {})
    
    if original_target_msgs:
        insight_prompt = f"""
Based on the following user reviews for '{product_name}', act as a professional market analyst and generate a JSON object with this exact structure:
{{
    "key_highlights": [
        {{ "title": "Ecosystem Lock-in", "description": "Segment shows 40% higher retention when paired with accessories." }},
        {{ "title": "Price Elasticity", "description": "High tolerance for premium pricing if justified." }},
        {{ "title": "Urgent Pivot", "description": "Growing dissatisfaction with software stability." }}
    ],
    "market_velocity": {{
        "value": "8.4x",
        "growth": "+12% WoW",
        "description": "Enthusiast adoption rate is outpacing general market entry by a factor of 8 this quarter."
    }},
    "market_verticals": [
        {{ "title": "Vertical Name", "description": "Short description", "badge": "HIGH VELOCITY", "positive_percent": 65 }}
    ]
}}
Generate exactly 3 key highlights, exactly 1 market velocity metrics object, and exactly 3 trending market verticals (each with a realistic positive_percent 0-100 based on the reviews) based on the themes in the text. Make sure outputs are highly realistic representations of the underlying user reviews provided.
Reviews to analyze:
"""
        for idx, msg in enumerate(original_target_msgs[:40]): insight_prompt += f"- {msg[:200]}...\n"
        try:
            res = ws.call_llm_with_retry(ws.MODEL_HEAVY, [{"role": "user", "content": insight_prompt}], 0.3, {"type": "json_object"}, max_retries=3)
            market_intelligence = json.loads(res.choices[0].message.content.strip())
        except Exception as e:
            print(f"[run_batch] Market intelligence generation failed: {e}")
            
    state["stats"] = stats
    state["dataset"] = dataset
    state["market_intelligence"] = market_intelligence
    # daily_timeline is already updated in-place on state

    with open("Batches.json", "w") as f: json.dump(remaining_data, f, indent=4)
    with open("sample.json", "w") as f: json.dump(state, f, indent=4)
    print(f"\n✅ Batch complete. {len(batch_data)} posts processed. Total in sample.json: {state['stats']['total']}")
    return state

if __name__ == "__main__":
    run_next_batch()
