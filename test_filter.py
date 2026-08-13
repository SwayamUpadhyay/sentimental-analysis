
from reddit_scraper import _contains_product, _count_tokens, _is_english, _MAX_TOKENS

PASS = "\u2705 PASS"
FAIL = "\u274c FAIL"

def check(label, result, expected):
    ok = result == expected
    print(f"  {'PASS' if ok else 'FAIL'} | {label}")
    print(f"         got={result}, expected={expected}")
    return ok

total = passed = 0

print("=" * 60)
print("GATE 2 — English language filter (_is_english)")
print("=" * 60)

tests = [
    ("Normal English post",        "I love my Razer Blade 16, battery life is great!",    True),
    ("Arabic script (80%+ non-ASCII)", "شباب اللاب بتاعي جاب بوردة Dell XPS 15",         False),
    ("Italian-heavy post (mostly ASCII)", "Il trionfo di Peter Magyar. Dell XPS non menzionato.", True),  # fails product filter, not language
    ("Mixed Arabic+English brand", "شباب Dell XPS 16 laptop رائع",                         True),   # has enough ASCII
]
for label, text, expected in tests:
    total += 1
    if check(label, _is_english(text), expected): passed += 1

print()
print("=" * 60)
print("GATE 3 — Product-name fuzzy match (_contains_product)")
print("=" * 60)

tests = [
    # Tier 1: Exact full match
    ("Exact: 'Razer Blade 16' in text",          "I just got a Razer Blade 16 and love it",           "Razer Blade 16", True),
    ("Exact: 'Dell Alienware M16' in text",       "The Dell Alienware M16 is my daily driver",         "Dell Alienware M16", True),
    ("Exact: 'Asus ROG Strix G16'",              "Thinking about the Asus ROG Strix G16 thermals",    "Asus ROG Strix G16", True),

    # Tier 2: Suffix match (brand dropped)
    ("Suffix: 'Blade 16' matches 'Razer Blade 16'",      "The Blade 16 thermals are great",             "Razer Blade 16", True),
    ("Suffix: 'Alienware M16' matches 'Dell Alienware M16'", "I have an Alienware M16 R2 and love it", "Dell Alienware M16", True),
    ("Suffix: 'ROG Strix G16' matches 'Asus ROG Strix G16'", "ROG Strix G16 beats the competition",  "Asus ROG Strix G16", True),
    ("Suffix: 'Predator Helios 16' matches 'Acer Predator Helios 16'", "Predator Helios 16 cooling", "Acer Predator Helios 16", True),

    # Tier 3: Deep-suffix match
    ("Deep: 'Strix G16' matches 'Asus ROG Strix G16'",   "The Strix G16 is better than expected",       "Asus ROG Strix G16", True),
    ("Deep: 'Helios 16' matches 'Acer Predator Helios 16'", "Helios 16 cooling review",                 "Acer Predator Helios 16", True),

    # Should REJECT — wrong product
    ("Reject: anime list has no 'Razer Blade 16'",        "Avatar Beastars Attack on Titan Blade of Immortal", "Razer Blade 16", False),
    ("Reject: 'Predator X49' not 'Predator Helios 16'",   "Acer Predator X49 monitor on sale $999",     "Acer Predator Helios 16", False),
    ("Reject: 'MSI GS76' not 'MSI GS66 Stealth'",        "I use my MSI GS76 Stealth daily",             "MSI GS66 Stealth", False),
    ("Reject: 'XPS 15' not 'Dell XPS 16'",               "Dell XPS 15 9570 I7-8750H specs",             "Dell XPS 16", False),
    ("Reject: Italian politics, no product",              "Il trionfo di Peter Magyar. Nessun laptop",   "Dell XPS 16", False),
    ("Reject: sports betting, no Acer",                   "Tampa Bay Lightning 62.1% EV picks today",   "Acer Predator Helios 16", False),
    ("Reject: truck parts list, no Razer",                "Holley atomic 2 efi Hooker Header Exhaust",  "Razer Blade 16", False),
]
for *args, expected in [(l, t, p, e) for l, t, p, e in tests]:
    label, text, product, expected = args[0], args[1], args[2], expected
    total += 1
    if check(label, _contains_product(text, product), expected): passed += 1

print()
print("=" * 60)
print("GATE 4 — Token length gate (_MAX_TOKENS)")
print("=" * 60)

short_post  = "I love my Razer Blade 16. The display is beautiful and battery life is solid."
anime_post  = " ".join([f"Anime{i}" for i in range(200)])  # 200 tokens
truck_post  = " ".join([f"part{i}${i*10}" for i in range(300)])  # 300 tokens

tests = [
    ("Short focused post (PASS)", short_post,  True),
    ("Anime list 200 tokens (REJECT)", anime_post,  False),
    ("Truck parts 300 tokens (REJECT)", truck_post, False),
]
for label, text, should_pass in tests:
    total += 1
    result = _count_tokens(text) <= _MAX_TOKENS
    if check(label + f" [{_count_tokens(text)} tokens]", result, should_pass): passed += 1

print()
print("=" * 60)
print(f"Results: {passed}/{total} tests passed")
print("=" * 60)
if passed == total:
    print("\nAll filters working correctly. Restart your backend server to activate them.")
else:
    print("\nSome tests failed — review output above.")
