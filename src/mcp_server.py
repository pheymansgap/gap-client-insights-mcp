"""
Client Intelligence MCP Server

Provides company research tools via the Model Context Protocol (MCP):
  - Stock ticker lookup
  - Real-time stock performance data
  - Financial & general news retrieval
  - Company insights aggregation
  - Orchestrated company briefings

The host LLM (e.g. GitHub Copilot) handles all reasoning and analysis
over the raw data returned by these tools — no external LLM API needed.
"""

import os
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import Any, Dict
from urllib.parse import quote_plus

import requests
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel

# Always load .env from the project root (one level above this script),
# regardless of the working directory VS Code uses to launch the server.
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(_project_root, ".env"))

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

class StockPerformance(BaseModel):
    symbol: str
    price: float
    change: float
    change_percent: str
    open_price: float
    high: float
    low: float
    previous_close: float
    volume: int
    latest_trading_day: str
    data: Dict[str, Any]


class NewsArticle(BaseModel):
    title: str
    source: str
    url: str
    data: Dict[str, str]


# ---------------------------------------------------------------------------
# MCP server
# ---------------------------------------------------------------------------

mcp = FastMCP(name="Client-Intelligence")


def _require_env(name: str) -> str:
    """Return an environment variable or raise with a helpful message."""
    val = os.environ.get(name)
    if not val:
        raise ValueError(f"{name} is not set. Add it to your .env file.")
    return val


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@mcp.tool()
def search_ticker_symbol(company_name: str) -> dict:
    """Search for a company's stock ticker symbol by name.

    Args:
        company_name: Company name to look up (e.g. 'Microsoft', 'Apple').

    Returns:
        Best-match ticker, company name, and up to 5 alternative suggestions.
    """
    api_key = _require_env("ALPHA_VANTAGE_API_KEY")
    url = f"https://www.alphavantage.co/query?function=SYMBOL_SEARCH&keywords={company_name}&apikey={api_key}"

    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    matches = resp.json().get("bestMatches", [])

    if not matches:
        return {
            "found": False,
            "query": company_name,
            "message": f"No ticker found for '{company_name}'.",
            "suggestions": [],
        }

    best = matches[0]
    suggestions = [
        {
            "ticker": m.get("1. symbol", ""),
            "name": m.get("2. name", ""),
            "type": m.get("3. type", ""),
            "region": m.get("4. region", ""),
        }
        for m in matches[:5]
    ]

    return {
        "found": True,
        "ticker": best.get("1. symbol", ""),
        "company_name": best.get("2. name", ""),
        "type": best.get("3. type", ""),
        "region": best.get("4. region", ""),
        "query": company_name,
        "suggestions": suggestions,
        "message": f"Found ticker '{best.get('1. symbol')}' for '{best.get('2. name')}'",
    }


@mcp.tool()
def get_stock_performance(stock_ticker: str) -> StockPerformance:
    """Fetch real-time stock performance data for a ticker.

    Args:
        stock_ticker: Stock symbol (e.g. 'MSFT', 'AAPL').

    Returns:
        Price, change, volume, daily range, and derived metrics.
    """
    api_key = _require_env("ALPHA_VANTAGE_API_KEY")
    url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={stock_ticker}&apikey={api_key}"

    resp = requests.get(url, timeout=10)
    resp.raise_for_status()

    quote = resp.json().get("Global Quote")
    if not quote or not quote.get("05. price"):
        raise ValueError(f"No valid quote for '{stock_ticker}'.")

    price = float(quote["05. price"])
    open_price = float(quote.get("02. open", 0))
    high = float(quote.get("03. high", 0))
    low = float(quote.get("04. low", 0))
    volume = int(quote.get("06. volume", 0))
    change = float(quote.get("09. change", 0))
    change_pct = quote.get("10. change percent", "0%")
    prev_close = float(quote.get("08. previous close", 0))
    trading_day = quote.get("07. latest trading day", "")
    symbol = quote.get("01. symbol", stock_ticker)

    day_range = high - low
    data = {
        "symbol": symbol,
        "price": price,
        "change": change,
        "change_percent": change_pct,
        "open": open_price,
        "high": high,
        "low": low,
        "previous_close": prev_close,
        "volume": volume,
        "volume_millions": round(volume / 1_000_000, 2),
        "latest_trading_day": trading_day,
        "day_range": round(day_range, 2),
        "day_range_percent": round((day_range / low * 100) if low else 0, 2),
        "price_vs_open_change": round(((price - open_price) / open_price * 100) if open_price else 0, 2),
    }

    return StockPerformance(
        symbol=symbol,
        price=price,
        change=change,
        change_percent=change_pct,
        open_price=open_price,
        high=high,
        low=low,
        previous_close=prev_close,
        volume=volume,
        latest_trading_day=trading_day,
        data=data,
    )


@mcp.tool()
def get_financial_news(company_name: str) -> list[NewsArticle]:
    """Get latest financial news from Reuters, Bloomberg, WSJ, FT, and CNBC.

    Args:
        company_name: Company name (e.g. 'Microsoft').

    Returns:
        Up to 5 relevant articles with title, source, and URL.
    """
    api_key = _require_env("NEWS_API_KEY")
    params = {
        "q": company_name,
        "language": "en",
        "sortBy": "relevancy",
        "pageSize": 5,
        "domains": "reuters.com,bloomberg.com,wsj.com,ft.com,cnbc.com",
        "apiKey": api_key,
    }

    resp = requests.get("https://newsapi.org/v2/everything", params=params, timeout=10)
    resp.raise_for_status()
    body = resp.json()

    if body.get("status") != "ok":
        raise ValueError(f"NewsAPI error: {body.get('message', 'unknown')}")

    articles = []
    for a in body.get("articles", []):
        title = (a.get("title") or "").strip()
        source = (a.get("source", {}).get("name") or "").strip()
        if not title or not source:
            continue
        url = (a.get("url") or "").strip()
        articles.append(NewsArticle(title=title, source=source, url=url, data={"title": title, "source": source, "url": url}))

    return articles[:5]


@mcp.tool()
def get_general_news(company_name: str) -> list[dict]:
    """Get latest general news articles for a company from all sources.

    Args:
        company_name: Company name (e.g. 'Apple').

    Returns:
        Up to 5 articles with title, source, and URL.
    """
    api_key = _require_env("NEWS_API_KEY")
    from_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    url = (
        f"https://newsapi.org/v2/everything?q={company_name}"
        f"&language=en&sortBy=relevancy&from={from_date}&apiKey={api_key}"
    )

    resp = requests.get(url, timeout=10)
    resp.raise_for_status()

    return [
        {"title": a["title"], "source": a["source"]["name"], "url": a["url"]}
        for a in resp.json().get("articles", [])
    ][:5]


@mcp.tool()
def get_google_news(query: str) -> list[dict]:
    """Fetch recent news from Google News RSS feed for a given query.

    No API key required. Returns up to 10 articles with title, source,
    URL, and published date.

    Args:
        query: Search query (e.g. 'Omnicom Group').

    Returns:
        List of news article dicts.
    """
    encoded = quote_plus(query)
    rss_url = f"https://news.google.com/rss/search?q={encoded}&hl=en-US&gl=US&ceid=US:en"

    resp = requests.get(
        rss_url,
        timeout=10,
        headers={"User-Agent": "Mozilla/5.0 (compatible; MCPServer/1.0)"},
    )
    resp.raise_for_status()

    root = ET.fromstring(resp.content)
    articles: list[dict] = []

    for item in root.iter("item"):
        title_el = item.find("title")
        link_el = item.find("link")
        source_el = item.find("source")
        pub_el = item.find("pubDate")

        title = title_el.text.strip() if title_el is not None and title_el.text else ""
        link = link_el.text.strip() if link_el is not None and link_el.text else ""
        source = (
            source_el.text.strip()
            if source_el is not None and source_el.text
            else "Google News"
        )
        pub_date = pub_el.text.strip() if pub_el is not None and pub_el.text else ""

        if title and link:
            articles.append(
                {"title": title, "source": source, "url": link, "published": pub_date}
            )

    return articles[:10]


@mcp.tool()
def get_company_insights(stock_data: dict, news_articles: list, company_name: str) -> dict:
    """Aggregate stock data and news into a structured insights bundle.

    Returns raw data for the host LLM to analyze — no external AI call.

    Args:
        stock_data: Stock performance metrics dictionary.
        news_articles: List of article dicts with title, source, url.
        company_name: Company being analyzed.

    Returns:
        Structured company data with stock metrics, news, and derived signals.
    """
    return {
        "company": company_name,
        "stock_symbol": stock_data.get("symbol", "N/A"),
        "current_price": stock_data.get("price", 0),
        "change": stock_data.get("change", 0),
        "change_percent": stock_data.get("change_percent", "N/A"),
        "open": stock_data.get("open", 0),
        "high": stock_data.get("high", 0),
        "low": stock_data.get("low", 0),
        "previous_close": stock_data.get("previous_close", 0),
        "volume_millions": stock_data.get("volume_millions", 0),
        "day_range": stock_data.get("day_range", 0),
        "day_range_percent": stock_data.get("day_range_percent", 0),
        "price_vs_open_change": stock_data.get("price_vs_open_change", 0),
        "latest_trading_day": stock_data.get("latest_trading_day", "N/A"),
        "timestamp": datetime.now().isoformat(),
        "news_count": len(news_articles),
        "news_articles": [
            {"title": a.get("title", ""), "source": a.get("source", ""), "url": a.get("url", "")}
            for a in news_articles[:10]
        ],
        "key_metrics": {
            "price_movement": "positive" if stock_data.get("change", 0) > 0 else "negative",
            "volume_millions": stock_data.get("volume_millions", 0),
            "volatility_percent": stock_data.get("day_range_percent", 0),
        },
    }


@mcp.tool()
def generate_company_briefing(company_name: str, stock_ticker: str) -> dict:
    """Generate a full company intelligence briefing.

    Orchestrates stock data retrieval, news gathering, and AI analysis
    into a single comprehensive report.

    Args:
        company_name: Company name (e.g. 'Microsoft').
        stock_ticker: Stock symbol (e.g. 'MSFT').

    Returns:
        Complete briefing with stock data, news headlines, and AI analysis.
    """
    stock_result = get_stock_performance(stock_ticker)
    sd = stock_result.data

    # --- News: cascade through sources until we have articles ----------
    data_sources = ["Alpha Vantage"]
    news: list[dict] = []

    # 1. Financial news (premium domains via NewsAPI)
    try:
        fin_result = get_financial_news(company_name)
        news = [{"title": a.title, "source": a.source, "url": a.url} for a in fin_result]
        if news:
            data_sources.append("NewsAPI")
    except Exception:
        pass  # fall through to next source

    # 2. Google News RSS (free, broad coverage)
    try:
        gn_articles = get_google_news(f"{company_name} {stock_ticker}")
        if gn_articles:
            data_sources.append("Google News")
            # Deduplicate by title prefix (first 60 chars)
            existing_prefixes = {n["title"][:60].lower() for n in news}
            for a in gn_articles:
                if a["title"][:60].lower() not in existing_prefixes:
                    news.append({"title": a["title"], "source": a["source"], "url": a["url"]})
                    existing_prefixes.add(a["title"][:60].lower())
    except Exception:
        pass  # continue without Google News

    # 3. General news fallback (all NewsAPI domains) if still empty
    if not news:
        try:
            gen_news = get_general_news(company_name)
            news = gen_news[:5]
            if news:
                data_sources.append("NewsAPI")
        except Exception:
            pass

    # Cap at 10 articles for the briefing
    news = news[:10]

    insights = get_company_insights(sd, news, company_name)

    return {
        "company": company_name,
        "ticker": stock_ticker,
        "generated_at": datetime.now().isoformat(),
        "stock_performance": {
            "symbol": sd.get("symbol"),
            "price": sd.get("price", 0),
            "change": sd.get("change", 0),
            "change_percent": sd.get("change_percent", "N/A"),
            "day_range": f"${sd.get('low', 0):.2f} - ${sd.get('high', 0):.2f}",
            "volume_millions": sd.get("volume_millions", 0),
            "latest_trading_day": sd.get("latest_trading_day", "N/A"),
        },
        "news_headlines": news,
        "insights": insights,
        "metadata": {
            "news_articles_found": len(news),
            "data_sources": data_sources,
        },
        "format_instructions": BRIEFING_FORMAT_TEMPLATE,
    }


# ---------------------------------------------------------------------------
# Output format template
# ---------------------------------------------------------------------------

BRIEFING_FORMAT_TEMPLATE = """
Present the briefing using EXACTLY this structure. Do NOT skip or reorder sections.

## {company} ({ticker}) — Company Briefing
**Date:** {date}

---

### Stock Performance
| Metric | Value |
|--------|-------|
| **Price** | ${price} |
| **Change** | {change} ({change_percent}) |
| **Day Range** | {day_range} |
| **Open** | ${open} |
| **Previous Close** | ${previous_close} |
| **Volume** | {volume}M |
| **Price vs Open** | {price_vs_open}% |
| **Intraday Volatility** | {volatility}% |

Write 2-3 sentences interpreting the stock data: trend direction, strength of move, volume context.

---

### Key News & Analyst Activity
Group articles into themed subsections (e.g. "Analyst upgrades", "Market analysis", "Other").
Each article MUST be a clickable markdown link in this format:
- [Article Title](url) — Source Name

---

### Summary
Write a 3-5 sentence synthesis covering:
1. Overall market sentiment (bullish/bearish/neutral)
2. Key catalysts or risks from the news
3. Notable institutional or analyst activity
4. Forward outlook

**Data sources:** {sources} | **Articles found:** {count}
"""


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

@mcp.prompt()
def company_briefing_prompt(company_name: str, stock_ticker: str) -> str:
    """Prompt template for generating a formatted company briefing.

    Use this prompt, then call the generate_company_briefing tool with
    the same company_name and stock_ticker to get the data.
    """
    return (
        f"Generate a company intelligence briefing for {company_name} ({stock_ticker}). "
        f"Call the generate_company_briefing tool with company_name='{company_name}' "
        f"and stock_ticker='{stock_ticker}', then format the response following the "
        f"format_instructions field in the tool result EXACTLY. "
        f"Every news article MUST be a clickable markdown link. "
        f"Do NOT skip any section. Do NOT reorder sections."
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run(transport="stdio")
