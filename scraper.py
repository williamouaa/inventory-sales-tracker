import re
import requests
from bs4 import BeautifulSoup
from statistics import median
from typing import Any, Dict, List


# Regex to find things like $9.99, $129, $1,234.56, etc.
PRICE_PATTERN = re.compile(r"\$\s*\d{1,3}(?:,\d{3})*(?:\.\d{2})?")


def clean_price(price_str: str) -> float | None:
    """
    Convert a price string like '$129.99' or '$10.50 to $15.00'
    into a float (e.g., 129.99 or 10.50).
    Returns None if it cannot be parsed.
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


def get_item_value(
    search_term: str,
    max_results: int = 20,
    save_debug: bool = False,
) -> Dict[str, Any]:
    """
    Search eBay for `search_term`, collect some prices,
    and return stats about those prices.

    Parameters
    ----------
    search_term : str
        The item to search for.
    max_results : int, optional
        Maximum number of price matches to use (default 20).
    save_debug : bool, optional
        If True, save the raw HTML to ebay_debug.html (default False).

    Returns
    -------
    dict with keys:
        query           - the search term
        raw_prices      - list of '$xx.xx' strings
        cleaned_prices  - list of floats (filtered & cleaned)
        count           - how many prices used
        average_price   - mean of cleaned_prices
        median_price    - median of cleaned_prices
        min_price       - minimum price
        max_price       - maximum price
        error           - error message if something went wrong, else None
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

    try:
        resp = requests.get(url, params=params, headers=headers, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as e:
        # Network / HTTP error – return a result with error info
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

    if save_debug:
        with open("ebay_debug.html", "w", encoding="utf-8") as f:
            f.write(html)

    # Find all dollar-looking prices in the HTML
    matches = PRICE_PATTERN.findall(html)

    # Limit to max_results
    raw_prices = matches[:max_results]

    # Clean and filter prices
    cleaned = [clean_price(p) for p in raw_prices]
    # drop invalid and zero prices (like "$0 shipping")
    cleaned = [c for c in cleaned if c is not None and c > 0]

    count = len(cleaned)

    if count == 0:
        avg = med = min_p = max_p = 0.0
    else:
        avg = sum(cleaned) / count
        med = float(median(cleaned))
        min_p = min(cleaned)
        max_p = max(cleaned)

    return {
        "query": search_term,
        "raw_prices": raw_prices,
        "cleaned_prices": cleaned,
        "count": count,
        "average_price": avg,
        "median_price": med,
        "min_price": min_p,
        "max_price": max_p,
        "error": None,
    }


def get_multiple_items_values(
    terms: List[str],
    max_results: int = 20,
) -> List[Dict[str, Any]]:
    """
    Convenience helper: get stats for multiple items at once.

    Example:
        results = get_multiple_items_values(
            ["iphone 11", "ps4 controller", "nike shoes"]
        )
    """
    results = []
    for term in terms:
        result = get_item_value(term, max_results=max_results)
        results.append(result)
    return results
