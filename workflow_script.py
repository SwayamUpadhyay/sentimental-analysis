import json
import time
import sys
import re
import html
import nltk
from typing import List, Dict
from groq import Groq
import httpx

try:
    from nltk.corpus import stopwords
    from nltk.sentiment.vader import SentimentIntensityAnalyzer
    sia = SentimentIntensityAnalyzer()
except LookupError:
    nltk.download('stopwords')
    nltk.download('vader_lexicon')
    from nltk.corpus import stopwords
    from nltk.sentiment.vader import SentimentIntensityAnalyzer
    sia = SentimentIntensityAnalyzer()
stop_words = set(stopwords.words('english'))

with open("settings.json", "r") as f:
    settings = json.load(f)

groq_client = Groq(api_key=settings["groq_api_key"])
MODEL_LIGHT = settings["model_light"]
MODEL_HEAVY = settings["model_heavy"]
POSTS_PER_PRODUCT = 70

def call_llm_with_retry(model, messages, temp, response_format=None, max_retries=6):
    retry_delay = 2
    for attempt in range(max_retries):
        try:
            kwargs = {
                "model": model,
                "messages": messages,
                "temperature": temp,
                "max_tokens": 1024,
            }
            if response_format:
                kwargs["response_format"] = response_format
                
            return groq_client.chat.completions.create(**kwargs)
        except Exception as e:
            err_str = str(e).lower()
            if "429" in err_str or "rate limit" in err_str or "too many requests" in err_str:
                print(f"Rate limited (429). Waiting {retry_delay}s...")
                time.sleep(retry_delay)
                retry_delay *= 2
            else:
                raise e
    raise Exception("Max retries exceeded for LLM call.")

def get_similar_products(product: str) -> List[str]:
    prompt = f"Return a JSON object containing exactly 4 similar or competing product names for '{product}' in a 'competitors' array. Example: {{\"competitors\": [\"ProductA\", \"ProductB\", \"ProductC\", \"ProductD\"]}}"
    try:
        res = call_llm_with_retry(MODEL_LIGHT, [{"role": "user", "content": prompt}], 0.2, {"type": "json_object"})
        text = res.choices[0].message.content.strip()
        comp = json.loads(text).get("competitors", [])
        return comp[:4]
    except Exception as e:
        print(f"Failed to parse competitors: {e}")
        # Fallback names roughly
        return [f"{product} Competitor 1", f"{product} Competitor 2", f"{product} Competitor 3", f"{product} Competitor 4"]

def is_relevant(text: str, product: str) -> bool:
    content = text.lower()
    keywords = [w for w in product.lower().split() if len(w) > 2 and w not in ["the", "pro", "max", "ultra", "plus", "for", "with"]]
    if not keywords:
        return True
    return any(k in content for k in keywords)

def scrape_reddit(product: str, limit: int = 70) -> List[Dict]:
    posts = []
    after = None
    with httpx.Client(timeout=15) as client:
        while len(posts) < limit:
            req_limit = min(100, limit - len(posts))
            # Use t=week for the MVP constraints
            params = {"q": product, "sort": "new", "t": "week", "limit": req_limit, "type": "link"}
            if after:
                params["after"] = after
                
            try:
                resp = client.get("https://www.reddit.com/search.json", params=params, headers={"User-Agent": settings.get("reddit_user_agent", "script/1.0")})
                resp.raise_for_status()
                data = resp.json()
                children = data.get("data", {}).get("children", [])
                
                if not children:
                    break
                
                after = data.get("data", {}).get("after")
                for child in children:
                    text = child["data"].get("selftext", "")
                    title = child["data"].get("title", "")
                    content = text if text and text not in ["[removed]", "[deleted]"] else title
                    
                    if content and content not in ["[removed]", "[deleted]"]:
                        if is_relevant(content, product):
                            posts.append({"original_text": content, "product": product})
                            if len(posts) >= limit:
                                break
                            
                # If after is None or we don't have enough posts, try one more time or break
                if not after:
                    break
                    
            except Exception as e:
                print(f"Error fetching {product}: {e}")
                break
                
            time.sleep(1)
            
    return posts

# Negation words must not be removed for sentiment analysis
negations = {'no', 'not', 'nor', 'against', 'aren', "aren't", 'couldn', "couldn't", 'didn', "didn't", 'doesn', "doesn't", 'hadn', "hadn't", 'hasn', "hasn't", 'haven', "haven't", 'isn', "isn't", 'mightn', "mightn't", 'mustn', "mustn't", 'needn', "needn't", 'shan', "shan't", 'shouldn', "shouldn't", 'wasn', "wasn't", 'weren', "weren't", 'won', "won't", 'wouldn', "wouldn't"}
filtered_stop_words = stop_words - negations

def preprocess_text(text: str) -> str:
    # 1. Unescape html
    text = html.unescape(text.strip())
    # 2. Extract important words (remove URLs)
    text = re.sub(r"https?://\S+|www\.\S+", " ", text)
    # 3. Remove markdown and weird symbols (keep punctuation like !?,.'- which hints at sentiment & sarcasm)
    text = re.sub(r"[*_~`#>|]+", " ", text)
    # 4. Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip().lower()
    
    tokens = tuple(text.split())
    # 5. Stopword removal (but preserve negations!), token must have length >= 2 unless it's a known negation
    tokens = [t for t in tokens if t not in filtered_stop_words and (len(t) >= 2 or t in negations or not t.isalnum())]
    
    # 6. Reduce tokens (we grab up to the first 400 chars, enough for LLM sentiment check)
    return " ".join(tokens)[:400]

def label_lightweight(batch: List[str]) -> List[str]:
    # Label as positive, negative, sarcastic
    results = []
    batch_size = 15
    for i in range(0, len(batch), batch_size):
        chunk = batch[i:i+batch_size]
        prompt = (
            "Analyze the sentiment of the following texts. "
            "For each text, output exactly one word: 'positive', 'negative', or 'sarcastic'.\n\n"
        )
        for idx, text in enumerate(chunk):
            prompt += f"{idx}. {text}\n"
        prompt += "\nRespond with a JSON object containing a single key 'labels' whose value is an array of strings in the exact same order as the inputs. Example: {\"labels\": [\"positive\", \"sarcastic\", \"negative\"]}. ONLY output the valid JSON object."
        
        try:
            res = call_llm_with_retry(MODEL_LIGHT, [{"role": "user", "content": prompt}], 0.1, {"type": "json_object"})
            parsed = res.choices[0].message.content.strip()
            arr = json.loads(parsed).get("labels", [])
            # Match lengths
            while len(arr) < len(chunk): arr.append("neutral")
            for x in arr[:len(chunk)]:
                x_low = str(x).lower()
                if x_low in ["positive", "negative", "sarcastic"]:
                    results.append(x_low)
                else: 
                    results.append("neutral")
        except Exception as e:
            print(f"Lightweight LLM labelling parsing error: {e}")
            results.extend(["neutral"] * len(chunk))
        time.sleep(1)
    return results

def label_heavy(batch: List[str]) -> List[str]:
    # Label as positive, negative
    results = []
    batch_size = 15
    for i in range(0, len(batch), batch_size):
        chunk = batch[i:i+batch_size]
        prompt = (
            "Analyze the sentiment of the following sarcastic texts and determine the true underlying sentiment. "
            "For each text, output exactly one word: 'positive' or 'negative'.\n\n"
        )
        for idx, text in enumerate(chunk):
            prompt += f"{idx}. {text}\n"
        prompt += "\nRespond with a JSON object containing a single key 'labels' whose value is an array of strings in the exact same order as the inputs. Example: {\"labels\": [\"positive\", \"negative\"]}. ONLY output the valid JSON object."
        
        try:
            res = call_llm_with_retry(MODEL_HEAVY, [{"role": "user", "content": prompt}], 0.1, {"type": "json_object"})
            parsed = res.choices[0].message.content.strip()
            arr = json.loads(parsed).get("labels", [])
            while len(arr) < len(chunk): arr.append("negative")
            for x in arr[:len(chunk)]:
                x_low = str(x).lower()
                results.append(x_low if x_low in ["positive", "negative"] else "negative")
        except Exception as e:
            print(f"Heavy LLM labelling parsing error: {e}")
            results.extend(["negative"] * len(chunk))
        time.sleep(1)
    return results

def label_user_profile(batch: List[str]) -> List[Dict]:
    results = []
    batch_size = 15
    communities = settings.get("community_clusters", [])
    community_list_str = ", ".join(communities)
    demographics = ["GEN Z (18-24)", "MILLENNIALS (25-40)", "GEN X (41-56)", "BABY BOOMERS (57+)"]
    demo_list_str = ", ".join(demographics)
    for i in range(0, len(batch), batch_size):
        chunk = batch[i:i+batch_size]
        prompt = (
            f"Analyze the following texts and map each to exactly one community ({community_list_str}) "
            f"and exactly one age demographic ({demo_list_str}). Use content clues like slang or life stage. "
            "If none fit perfectly, guess the closest or use 'Casual Users' and 'MILLENNIALS (25-40)'.\n\n"
        )
        for idx, text in enumerate(chunk):
            prompt += f"{idx}. {text}\n"
        prompt += "\nRespond with a JSON object containing a single key 'profiles' whose value is an array of objects. Example: {\"profiles\": [{\"community\": \"Tech\", \"demographic\": \"GEN Z (18-24)\"}]}. ONLY output the valid JSON array in exactly the same order."
        
        try:
            # Using Heavy LLM for deeper text analysis on profiles as requested
            res = call_llm_with_retry(MODEL_HEAVY, [{"role": "user", "content": prompt}], 0.2, {"type": "json_object"})
            parsed = res.choices[0].message.content.strip()
            arr = json.loads(parsed).get("profiles", [])
            while len(arr) < len(chunk): arr.append({"community": "Casual Users", "demographic": "MILLENNIALS (25-40)"})
            for x in arr[:len(chunk)]:
                comm = next((c for c in communities if c.lower() == str(x.get("community", "")).lower()), "Casual Users")
                
                r_demo = str(x.get("demographic", "")).upper()
                demo = "MILLENNIALS (25-40)"
                if "Z" in r_demo and "GEN" in r_demo: demo = "GEN Z (18-24)"
                elif "X" in r_demo and "GEN" in r_demo: demo = "GEN X (41-56)"
                elif "BOOMER" in r_demo: demo = "BABY BOOMERS (57+)"
                elif "MILLENNIAL" in r_demo: demo = "MILLENNIALS (25-40)"
                
                results.append({"community": comm, "demographic": demo})
        except Exception as e:
            print(f"Profile LLM labelling parsing error: {e}")
            results.extend([{"community": "Casual Users", "demographic": "MILLENNIALS (25-40)"}] * len(chunk))
        time.sleep(1)
    return results

def generate_batches(valid_data, batch_size=15):
    by_product = {}
    for item in valid_data:
        prod = item["product"]
        if prod not in by_product:
            by_product[prod] = []
        by_product[prod].append(item)
    
    products = list(by_product.keys())
    
    while True:
        batch = []
        for prod in products:
            # We take 3 posts per product to make a batch of 15 if there are 5 products
            batch.extend(by_product[prod][:3])
            by_product[prod] = by_product[prod][3:]
        
        if not batch:
            break
        yield batch

def main():
    product_name = input("Enter product name: ").strip()
    if not product_name:
        product_name = "iPhone 15"
    
    print(f"Finding similar products for '{product_name}'...")
    competitors = get_similar_products(product_name)
    print("Competitors found:", competitors)

    all_products = [product_name] + competitors
    all_data = []

    for prod in all_products:
        print(f"Scraping {POSTS_PER_PRODUCT} posts for '{prod}'...")
        posts = scrape_reddit(prod, limit=POSTS_PER_PRODUCT)
        print(f"Found {len(posts)} valid posts for '{prod}'")
        all_data.extend(posts)

    print("Preprocessing all posts...")
    for item in all_data:
        item["preprocessed"] = preprocess_text(item["original_text"])

    valid_data = [item for item in all_data if item["preprocessed"]]

    print(f"Saving {len(valid_data)} collected items to Batches.json...")
    with open("Batches.json", "w") as f:
        json.dump(valid_data, f, indent=4)
        
    dataset = []
    stats = {
        "total": 0, "positive": 0, "negative": 0, "sarcastic_to_positive": 0, "sarcastic_to_negative": 0, 
        "demographics": {"GEN Z (18-24)": 0, "MILLENNIALS (25-40)": 0, "GEN X (41-56)": 0, "BABY BOOMERS (57+)": 0},
        "sentiment_spectrum": {"Ultra Negative": 0, "Negative": 0, "Neutral": 0, "Positive": 0, "Ultra Positive": 0}
    }
    for c in settings.get("community_clusters", []):
        stats[f"community_{c}"] = 0

    print("\nStarting batch generation and processing...")
    for idx, batch_data in enumerate(generate_batches(valid_data, 15)):
        print(f"\n==========================================")
        print(f"   Processing Batch {idx + 1} ({len(batch_data)} posts)")
        print(f"==========================================")
        
        texts = [item["preprocessed"] for item in batch_data]
        
        print(">> Running Lightweight LLM...")
        labels_light = label_lightweight(texts)
        for item, label in zip(batch_data, labels_light):
            item["light_label"] = label
            
        sarcastic_indices = [i for i, item in enumerate(batch_data) if item["light_label"] == "sarcastic"]
        sarcastic_texts = [batch_data[i]["preprocessed"] for i in sarcastic_indices]
        
        if sarcastic_indices:
            print(f">> Running Heavy LLM on {len(sarcastic_indices)} sarcastic posts...")
            heavy_labels = label_heavy(sarcastic_texts)
            for i, heavy_label in zip(sarcastic_indices, heavy_labels):
                batch_data[i]["final_label"] = heavy_label
                
        print(">> Running User Profiling LLM (Community + Demographic)...")
        user_profiles = label_user_profile(texts)
        for item, prof in zip(batch_data, user_profiles):
            item["community"] = prof["community"]
            item["demographic"] = prof["demographic"]

        print("\n--- Batch Results ---")
        for i, item in enumerate(batch_data):
            label = item.get("final_label", item["light_label"])
            if label not in ["positive", "negative"]:
                label = "negative"
                
            orig = item["original_text"].replace('\n', ' ')
            if len(orig) > 70: orig = orig[:67] + "..."
            
            comm = item.get("community", "Casual Users")
            demo = item.get("demographic", "MILLENNIALS (25-40)")
            print(f"[{label.upper():^8}|{comm[:8]:^8}|{demo[:5]:^5}] {item['product'][:15]:<15} | {orig}")
            
            if item["light_label"] == "sarcastic":
                if label == "positive": stats["sarcastic_to_positive"] += 1
                else: stats["sarcastic_to_negative"] += 1
                
            # --- Non-AI & AI Combined Spectrum Analysis ---
            vader_score = sia.polarity_scores(item["original_text"])["compound"]
            ai_score = 1.0 if label == "positive" else (-1.0 if label == "negative" else 0.0)
            spectrum = (vader_score + ai_score) / 2
            
            if spectrum < -0.6: bucket = "Ultra Negative"
            elif spectrum < -0.2: bucket = "Negative"
            elif spectrum <= 0.2: bucket = "Neutral"
            elif spectrum <= 0.6: bucket = "Positive"
            else: bucket = "Ultra Positive"
            
            dataset.append({
                "product": item["product"],
                "original_msg": item["original_text"],
                "sentiment": label,
                "community": comm,
                "demographic": demo,
                "spectrum_score": spectrum,
                "spectrum_bucket": bucket
            })
            stats[label] = stats.get(label, 0) + 1
            stats[f"community_{comm}"] = stats.get(f"community_{comm}", 0) + 1
            stats["demographics"][demo] += 1
            stats["sentiment_spectrum"][bucket] += 1
            stats["total"] += 1
            
        # Write interim dataset safely each time
        with open("sample.json", "w") as f:
            json.dump({"stats": stats, "dataset": dataset}, f, indent=4)
            
        # Re-save Batches.json so the newly generated tags persist incrementally
        with open("Batches.json", "w") as f:
            json.dump(valid_data, f, indent=4)
            
        user_input = input("\nProcess next batch? (y/n): ").strip().lower()
        if user_input != 'y':
            print("Stopping processing early...")
            break
            
    print("\nGenerating Deep Market Analytics (Vitality, Verticals & Narratives)...")
    original_target_msgs = [d["original_msg"] for d in dataset if d["product"].lower() == product_name.lower()]
    market_intelligence = {}
    
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
        {{ "title": "Vertical Name", "description": "Short description", "badge": "HIGH VELOCITY" }}
    ]
}}
Generate exactly 3 key highlights, exactly 1 market velocity metrics object, and exactly 3 trending market verticals based on the themes in the text. Make sure outputs are highly realistic representations of the underlying user reviews provided.
Reviews to analyze:
"""
        for idx, msg in enumerate(original_target_msgs[:40]):
            insight_prompt += f"- {msg[:200]}...\n"
        try:
            res = call_llm_with_retry(MODEL_HEAVY, [{"role": "user", "content": insight_prompt}], 0.3, {"type": "json_object"}, max_retries=3)
            market_intelligence = json.loads(res.choices[0].message.content.strip())
            
            # Post-processing Market Verticals via targeted scraping per user request
            if "market_verticals" in market_intelligence:
                print("\nAnalysing true data for Market Verticals...")
                for vertical in market_intelligence["market_verticals"]:
                    title = vertical.get("title", "")
                    search_query = f"{product_name} {title}"
                    print(f"Scraping exactly 10 posts for vertical: '{search_query}'...")
                    vert_posts = scrape_reddit(search_query, limit=10)
                    
                    if not vert_posts:
                        vertical["positive_percent"] = 50
                        print(f" -> Not enough Reddit data found. Defaulting to 50%")
                        continue
                        
                    # Preprocess & label lightweight
                    vert_texts = [preprocess_text(p["original_text"]) for p in vert_posts]
                    vert_texts = [t for t in vert_texts if t]
                    
                    if not vert_texts:
                        vertical["positive_percent"] = 50
                        print(f" -> No valid preprocessed text. Defaulting to 50%")
                        continue
                        
                    vert_labels = label_lightweight(vert_texts)
                    pos_count = sum(1 for l in vert_labels if l == "positive")
                    calculated_percent = int((pos_count / max(1, len(vert_labels))) * 100)
                    vertical["positive_percent"] = calculated_percent
                    print(f" -> Real positive sentiment for '{title}' calculated: {calculated_percent}%")
                    
        except Exception as e:
            print(f"Failed to generate deep analytics: {e}")
            market_intelligence = {"error": "Deep analytics generation failed."}
    else:
        market_intelligence = {"error": "No data analyzed yet for the original product."}
        
    print("\n--- Final Statistics ---")
    for k, v in stats.items():
        if isinstance(v, dict):
            print(f"{k}:")
            for sub_k, sub_v in v.items(): print(f"  {sub_k}: {sub_v}")
        else:
            print(f"{k}: {v}")
            
    print("\n--- Deep Market Analytics ---")
    print(json.dumps(market_intelligence, indent=2))
    
    # Save final JSON with deep analytics
    with open("sample.json", "w") as f:
        json.dump({
            "stats": stats, 
            "market_intelligence": market_intelligence, 
            "dataset": dataset
        }, f, indent=4)
    print("Workflow stopped. Final output structured in 'sample.json'.")

if __name__ == "__main__":
    main()
