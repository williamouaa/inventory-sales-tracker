import re
from statistics import median
from typing import Any, Dict, List

import requests
from bs4 import BeautifulSoup

# ------------ config & helpers ------------

# Matches things like: $9.99, US $129.99, $1,234.56, 99.00, etc.
PRICE_PATTERN = re.compile(r"(?:US\s*)?\$\s*\d{1,3}(?:,\d{3})*(?:\.\d{2})?")

# Common accessory / junk keywords to skip
ACCESSORY_KEYWORDS = [
    "case",
    "charger",
    "cable",
    "screen protector",
    "protector",
    "adapter",
    "dock",
    "stand",
    "mount",
    "holder",
    "skin",
    "cover",
    "glass",
    "tempered",
    "wallet",
    "strap",
    "band",
    "cord",
    "hub",
    "battery",
    "power bank",
    "charging pad",
]

# Very common words we ignore when matching query to title
QUERY_STOPWORDS = {"for", "the", "a", "an", "and", "or", "new", "brand"}


def clean_price(price_str: str) -> float | None:
    """Convert 'US $129.99' or '$10.50 to $15.00' into a float."""
    if not price_str:
        return None

    # If it's a range like '$10.50 to $15.00', take the first part
    if "to" in price_str:
        price_str = price_str.split("to")[0].strip()

    # Remove 'US', '$', commas and spaces
    price_str = price_str.replace("US", "").replace("$", "").replace(",", "").strip()

    # Keep only the first "word" that looks like a number
    parts = price_str.split()
    if parts:
        price_str = parts[0]

    try:
        return float(price_str)
    except ValueError:
        return None


def normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9\s]", " ", text.lower())


def tokenize(text: str) -> List[str]:
    return [t for t in normalize(text).split() if t]


def important_query_tokens(query: str) -> List[str]:
    """Tokens we require to be present in the title for an 'exact model' match."""
    tokens = tokenize(query)
    return [t for t in tokens if t not in QUERY_STOPWORDS]


def looks_like_accessory(title: str) -> bool:
    t = title.lower()
    return any(word in t for word in ACCESSORY_KEYWORDS)


def title_exact_match(title: str, query: str) -> bool:
    """
    Exact-model behavior: every important query token must appear in the title.
    e.g. 'iphone 11' -> title must contain BOTH 'iphone' and '11'.
    """
    title_tokens = set(tokenize(title))
    q_tokens = important_query_tokens(query)
    if not q_tokens:
        return True
    return all(t in title_tokens for t in q_tokens)


# ------------ main scraper ------------

def get_item_value_sold_new(search_term: str, max_results: int = 5) -> Dict[str, Any]:
    """
    Use requests + BeautifulSoup to search eBay for `search_term`:
      - SOLD items only
      - NEW condition only
      - Uses the most recent `max_results` sold items (default 5)
      - Requires every important query token in the title
      - Filters out obvious accessories
    """
    url = "https://www.ebay.com/sch/i.html"

    params = {
        "_nkw": search_term,
        "LH_Sold": "1",
        "LH_Complete": "1",
        "LH_ItemCondition": "1000",  # New
        "_sop": "13",                # End date: recent first
    }

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }

    try:
        resp = requests.get(url, params=params, headers=headers, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as e:
        return {
            "query": search_term,
            "raw_prices": [],
            "cleaned_prices": [],
            "count": 0,
            "average_price": 0.0,
            "median_price": 0.0,
            "min_price": 0.0,
            "max_price": 0.0,
            "error": str(e),
        }

    html = resp.text
    soup = BeautifulSoup(html, "html.parser")

    # DEBUG: saves HTML
    with open("ebay_debug.html", "w", encoding="utf-8") as f:
        f.write(html)

    # ---- LISTING SELECTION ----
    # New SOLD layout uses card containers; class usually contains 'card-container'
    listings = soup.select("div[class*='card-container']")

    # Fallback to old-style layout if nothing found
    if not listings:
        listings = soup.select("li.s-item")
    if not listings:
        listings = soup.select("div.s-item__info.clearfix")
    if not listings:
        listings = soup.select("div.s-item__info")

    print(f"[DEBUG] Found {len(listings)} potential listings for '{search_term}'")

    raw_prices: List[str] = []

    for idx, li in enumerate(listings):
        # --- Title extraction ---
        # Strategy: first <a> with an /itm/ link (that should be the listing title)
        title_link = li.select_one("a[href*='/itm/']")
        if not title_link:
            continue

        title_text = title_link.get_text(strip=True)
        if not title_text:
            continue

        # Skip generic promo tiles
        if "shop on ebay" in title_text.lower():
            continue

        # Exact-model match & accessory filter
        if not title_exact_match(title_text, search_term):
            continue
        if looks_like_accessory(title_text):
            continue

        # --- Price extraction ---
        # Grab all text inside this card and search for a $price pattern
        card_text = li.get_text(" ", strip=True)
        m = PRICE_PATTERN.search(card_text)
        if not m:
            continue

        price_str = m.group()

        print(f"[DEBUG] Title #{idx}: {title_text}  |  Price text: {price_str}")

        raw_prices.append(price_str)

        if len(raw_prices) >= max_results:
            break

    cleaned = [clean_price(p) for p in raw_prices]
    cleaned = [c for c in cleaned if c is not None and c > 0]

    count = len(cleaned)

    if count == 0:
        avg = med = min_p = max_p = 0.0
        error = "No matching sold NEW listings found."
    else:
        avg = sum(cleaned) / count
        med = float(median(cleaned))
        min_p = min(cleaned)
        max_p = max(cleaned)
        error = None

    return {
        "query": search_term,
        "raw_prices": raw_prices,
        "cleaned_prices": cleaned,
        "count": count,
        "average_price": avg,
        "median_price": med,
        "min_price": min_p,
        "max_price": max_p,
        "error": error,
    }


# ------------ quick test harness ------------

if __name__ == "__main__":
    test_terms = ["iphone 12", "jordan 1", "pokemon etb"]

    for term in test_terms:
        print("==========")
        print("Query:", term)
        result = get_item_value_sold_new(term)
        print("Error:", result["error"])
        print("Raw prices:", result["raw_prices"])
        print("Cleaned prices:", result["cleaned_prices"])
        print("Count:", result["count"])
        print("Average:", result["average_price"])
        print("Median:", result["median_price"])
        print("Min:", result["min_price"])
        print("Max:", result["max_price"])
