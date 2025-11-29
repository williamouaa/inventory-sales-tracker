import re
import requests
from bs4 import BeautifulSoup


# Regex to find things like $9.99, $129, $1,234.56, etc.
PRICE_PATTERN = re.compile(r"\$\s*\d{1,3}(?:,\d{3})*(?:\.\d{2})?")


def clean_price(price_str: str):
    """
    Convert a price string like '$129.99' or '$10.50 to $15.00'
    into a float (e.g., 129.99 or 10.50).
    """
    if not price_str:
        return None

    # If it's a range like '$10.50 to $15.00', take the first part
    if "to" in price_str:
        price_str = price_str.split("to")[0].strip()

    # Remove $ and commas and spaces
    price_str = price_str.replace("$", "").replace(",", "").strip()

    # Keep only the first "word" that looks like a number
    parts = price_str.split()
    if parts:
        price_str = parts[0]

    try:
        return float(price_str)
    except ValueError:
        return None


def get_item_value(search_term: str):
    """
    Search eBay for `search_term`, collect some prices,
    and return raw prices, cleaned prices, and the average.
    """
    url = "https://www.ebay.com/sch/i.html"
    params = {"_nkw": search_term}

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }

    resp = requests.get(url, params=params, headers=headers, timeout=30)
    resp.raise_for_status()

    html = resp.text

       # Find all dollar-looking prices in the HTML
    matches = PRICE_PATTERN.findall(html)

    # Take first 10 matches
    raw_prices = matches[:10]

    cleaned = [clean_price(p) for p in raw_prices]
    # drop invalid and $0 prices (like "$0 shipping")
    cleaned = [c for c in cleaned if c is not None and c > 0]

    average = sum(cleaned) / len(cleaned) if cleaned else 0.0

    return {
        "query": search_term,
        "raw_prices": raw_prices,
        "cleaned_prices": cleaned,
        "count": len(cleaned),
        "average_price": average,
    }
