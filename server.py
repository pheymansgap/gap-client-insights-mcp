from mcp.server.fastmcp import FastMCP
import requests
import os
from dotenv import load_dotenv
from typing import List, Dict, Any
from pydantic import BaseModel

# Load environment variables from .env file
load_dotenv()

# Define our return types
class StockPerformance(BaseModel):
    """Model for stock performance data."""
    symbol: str
    price: str
    change_percent: str
    data: Dict[str, str]

class NewsArticle(BaseModel):
    """Model for a news article."""
    title: str
    source: str
    url: str
    data: Dict[str, str]

# 1. Correctly instantiate the server using your working example's structure
mcp = FastMCP(
    name="Client-Intel-Agent",
    host="0.0.0.0",
    port=8080, # We can use the standard 8080 port
    stateless_http=True,
)

# --- Tool 1: Get Stock Performance ---
@mcp.tool()
def get_stock_performance(stock_ticker: str) -> StockPerformance:
    """
    Fetches the latest stock price and performance for a given stock ticker.
    
    :param stock_ticker: The company's stock symbol (e.g., 'WMT' for Walmart).
    :returns: StockPerformance model with stock data.
    """
    print(f"Tool: Received request for stock performance of '{stock_ticker}'")
    
    api_key = os.environ.get("ALPHA_VANTAGE_API_KEY")
    if not api_key:
        raise ValueError("API Key for Alpha Vantage not found. Please set the ALPHA_VANTAGE_API_KEY environment variable.")

    url = f'https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={stock_ticker}&apikey={api_key}'
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        
        quote = data.get('Global Quote')
        if not quote or not quote.get('05. price'):
            raise ValueError(f"Could not retrieve a valid quote for {stock_ticker}. Response: {data}")

        performance_data = {
            "symbol": quote.get('01. symbol'),
            "price": quote.get('05. price'),
            "change_percent": quote.get('10. change percent')
        }
        
        print(f"Tool: Successfully fetched data for {stock_ticker}")
        return StockPerformance(
            symbol=performance_data["symbol"],
            price=performance_data["price"],
            change_percent=performance_data["change_percent"],
            data=performance_data
        )
        
    except Exception as e:
        print(f"Tool Error: Failed to fetch stock data. {e}")
        raise ValueError(f"Failed to fetch stock data: {e}")


# --- Tool 2: Get Financial News ---
@mcp.tool()
def get_financial_news(company_name: str) -> list[NewsArticle]:
    """
    Gets the latest financial news articles for a given company from major news sources.
    
    :param company_name: The name of the company (e.g., 'Walmart').
    :returns: List of NewsArticle models containing titles, sources, and URLs.
    :raises: ValueError if NEWS_API_KEY is missing or API returns an error
    """
    print(f"Tool: Received request for financial news on '{company_name}'")
    
    api_key = os.environ.get("NEWS_API_KEY")
    if not api_key:
        raise ValueError("NEWS_API_KEY not found in environment variables")

    # Configure the API request to get relevant financial news
    base_url = "https://newsapi.org/v2/everything"
    params = {
        'q': company_name,
        'language': 'en',
        'sortBy': 'relevancy',
        'pageSize': 5,
        'domains': 'reuters.com,bloomberg.com,wsj.com,ft.com,cnbc.com',
        'apiKey': api_key
    }

    print(f"Tool: Requesting articles from major financial news sources...")
    
    try:
        # Make the request
        response = requests.get(base_url, params=params)
        response.raise_for_status()
        data = response.json()

        if data.get('status') != 'ok':
            raise ValueError(f"News API Error: {data.get('message', 'Unknown error')}")

        # Process articles
        articles = []
        for article in data.get('articles', []):
            # Skip articles missing required fields
            if not article.get('title') or not article.get('source', {}).get('name'):
                continue
                
            # Clean and structure the data
            article_data = {
                "title": article['title'].strip(),
                "source": article['source']['name'].strip(),
                "url": article.get('url', '').strip()
            }
            
            articles.append(NewsArticle(
                title=article_data["title"],
                source=article_data["source"],
                url=article_data["url"],
                data=article_data  # Include raw data for client
            ))

        result = articles[:5]  # Take up to 5 articles
        print(f"Tool: Found {len(result)} relevant news articles")
        return result
        
    except requests.exceptions.RequestException as e:
        raise ValueError(f"Failed to fetch news: {str(e)}")
    except Exception as e:
        raise ValueError(f"Error processing news data: {str(e)}")


# --- Tool 3: Get General News ---
@mcp.tool()
def get_general_news(company_name: str) -> list[dict]:
    """
    Gets the latest general news articles for a given company.
    
    :param company_name: The name of the company (e.g., 'Walmart').
    """
    print(f"Tool: Received request for general news on '{company_name}'")
    api_key = os.environ.get("NEWS_API_KEY")
    if not api_key:
        raise ValueError("NEWS_API_KEY not found in environment variables.")

    # This search is broader and uses the 'everything' endpoint
    url = (f'https://newsapi.org/v2/everything?q={company_name}'
           '&language=en&sortBy=relevancy&apiKey=' + api_key)
           
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        
        articles = [
            {"title": article['title'], "source": article['source']['name'], "url": article['url']}
            for article in data.get('articles', [])
        ]
        
        print(f"Tool: Found {len(articles)} general news articles.")
        return articles[:5] # Return a max of 5 articles
        
    except requests.exceptions.RequestException as e:
        raise ConnectionError(f"Failed to connect to NewsAPI. {e}")


# --- Main Server Execution ---
if __name__ == "__main__":
    print("Starting the Client Intelligence MCP Server...")
    print("Available Tools:")
    print("- get_stock_performance(stock_ticker)")
    print("- get_financial_news(company_name)") 
    print("- get_general_news(company_name)")

    mcp.run(transport="sse")