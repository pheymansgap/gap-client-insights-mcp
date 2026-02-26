"""
Client Intelligence MCP Server

Provides company research tools via the Model Context Protocol (MCP):
  - Stock ticker lookup
  - Real-time stock performance data
  - Financial & general news retrieval
  - AI-powered company analysis (Gemini)
  - Orchestrated company briefings
"""

import os
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import Any, Dict
from urllib.parse import quote_plus

import requests
from dotenv import load_dotenv
from google import genai
from google.genai.errors import ClientError
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel

load_dotenv()

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_gemini_key = os.environ.get("GEMINI_API_KEY")
if not _gemini_key:
    raise RuntimeError("GEMINI_API_KEY is required. Add it to your .env file.")

_gemini = genai.Client(api_key=_gemini_key)
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

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


def _generate(prompt: str) -> str:
    """Call Gemini and return the generated text, retrying on rate limits."""
    for attempt in range(4):
        try:
            response = _gemini.models.generate_content(
                model=GEMINI_MODEL, contents=prompt
            )
            return response.text.strip()
        except ClientError as e:
            if "RESOURCE_EXHAUSTED" in str(e.status) and attempt < 3:
                wait = 2 ** attempt * 15  # 15s, 30s, 60s
                time.sleep(wait)
            else:
                raise


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
def summarize_company_insights(stock_data: dict, news_articles: list, company_name: str) -> dict:
    """Generate an AI-powered analysis of a company's stock and news.

    Args:
        stock_data: Stock performance metrics dictionary.
        news_articles: List of article dicts with title, source, url.
        company_name: Company being analyzed.

    Returns:
        AI summary, key metrics, and structured insight data.
    """
    stock_ctx = (
        f"Stock: {stock_data.get('symbol', 'N/A')}\n"
        f"Price: ${stock_data.get('price', 0):.2f}\n"
        f"Change: {stock_data.get('change_percent', 'N/A')}\n"
        f"Day Range: ${stock_data.get('low', 0):.2f} - ${stock_data.get('high', 0):.2f}\n"
        f"Volume: {stock_data.get('volume_millions', 0):.2f}M shares\n"
        f"Trading Day: {stock_data.get('latest_trading_day', 'N/A')}"
    )
    news_ctx = "\n".join(
        f"- {a.get('title', '')} ({a.get('source', '')})" for a in news_articles[:5]
    )

    prompt = (
        f"You are a financial analyst. Analyze the following data for {company_name}:\n\n"
        f"STOCK PERFORMANCE:\n{stock_ctx}\n\n"
        f"RECENT NEWS:\n{news_ctx}\n\n"
        "Provide a concise 3-4 sentence analysis covering:\n"
        "1. Current stock performance and trading activity\n"
        "2. Key themes from recent news\n"
        "3. Brief outlook or considerations for investors\n\n"
        "Be professional, factual, and balanced. No buy/sell recommendations."
    )

    return {
        "summary": _generate(prompt),
        "company": company_name,
        "stock_symbol": stock_data.get("symbol", "N/A"),
        "current_price": stock_data.get("price", 0),
        "change_percent": stock_data.get("change_percent", "N/A"),
        "analysis_timestamp": datetime.now().isoformat(),
        "news_count": len(news_articles),
        "key_metrics": {
            "price_movement": "positive" if stock_data.get("change", 0) > 0 else "negative",
            "volume": stock_data.get("volume_millions", 0),
            "volatility": stock_data.get("day_range_percent", 0),
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
    data_sources = ["Alpha Vantage", "Gemini"]
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

    analysis = summarize_company_insights(sd, news, company_name)

    # --- Build formatted markdown briefing --------------------------------
    price = sd.get("price", 0)
    change = sd.get("change", 0)
    change_pct = sd.get("change_percent", "N/A")
    sign = "+" if change >= 0 else ""
    day_range = f"${sd.get('low', 0):.2f} – ${sd.get('high', 0):.2f}"
    vol = sd.get("volume_millions", 0)
    trading_day = sd.get("latest_trading_day", "N/A")

    news_lines = "\n".join(
        f"{i}. [{a['title']}]({a['url']}) — {a['source']}"
        for i, a in enumerate(news, 1)
    )
    if not news_lines:
        news_lines = "_No recent news articles found._"

    sources_str = ", ".join(data_sources)
    summary_text = analysis.get("summary", "")

    formatted_briefing = (
        f"## {company_name} ({stock_ticker}) — Company Briefing\n\n"
        f"### Stock Performance\n"
        f"| Metric | Value |\n"
        f"|---|---|\n"
        f"| **Price** | ${price:.2f} |\n"
        f"| **Change** | {sign}${change:.2f} ({change_pct}) |\n"
        f"| **Day Range** | {day_range} |\n"
        f"| **Volume** | {vol:.2f}M shares |\n"
        f"| **Trading Day** | {trading_day} |\n\n"
        f"### Recent News\n"
        f"{news_lines}\n\n"
        f"### Analysis\n"
        f"{summary_text}\n\n"
        f"---\n"
        f"*Sources: {sources_str}*"
    )

    return {
        "company": company_name,
        "ticker": stock_ticker,
        "generated_at": datetime.now().isoformat(),
        "formatted_briefing": formatted_briefing,
        "stock_performance": {
            "symbol": sd.get("symbol"),
            "price": price,
            "change": change,
            "change_percent": change_pct,
            "day_range": f"${sd.get('low'):.2f} - ${sd.get('high'):.2f}",
            "volume_millions": vol,
            "latest_trading_day": trading_day,
        },
        "news_headlines": news,
        "ai_analysis": {
            "summary": summary_text,
            "key_metrics": analysis.get("key_metrics"),
        },
        "metadata": {
            "news_articles_found": len(news),
            "data_sources": data_sources,
        },
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run(transport="stdio")
