import asyncio
import os
import traceback
from dotenv import load_dotenv
from mcp import ClientSession
from mcp.client.sse import sse_client
import json

# Load API keys from our .env file into environment variables
load_dotenv()

async def run_intelligence_briefing(company_name: str, stock_ticker: str):
    """
    Connects to the MCP server and runs the full workflow to generate a client briefing.
    """
    # Use the same port you defined in your server.py (e.g., 8080)
    server_url = "http://localhost:8080/sse"
    print(f"Connecting to MCP server at {server_url}...")

    try:
        async with sse_client(server_url) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                print("Connection successful.")

                # (The tool listing and gathering part remains the same)
                tools_result = await session.list_tools()
                print("\n## Available Tools on Server:")
                for tool in tools_result.tools:
                    print(f"- {tool.name}")
                
                print(f"\n## Gathering Intelligence for {company_name} ({stock_ticker})...")

                stock_task = session.call_tool("get_stock_performance", arguments={"stock_ticker": stock_ticker})
                news_task = session.call_tool("get_financial_news", arguments={"company_name": company_name})

                # The 'return_exceptions=True' is key for debugging
                results = await asyncio.gather(stock_task, news_task, return_exceptions=True)

                stock_result = results[0]
                news_result = results[1]

                # Debug: Print raw response shapes
                print("\n## Raw API Responses:")
                print("\nStock Result:")
                print(f"Type: {type(stock_result)}")
                print(f"Content type: {type(stock_result.content) if not isinstance(stock_result, Exception) else 'N/A'}")
                if not isinstance(stock_result, Exception) and stock_result.content:
                    print(f"First content item type: {type(stock_result.content[0])}")
                    print(f"First content item attrs: {dir(stock_result.content[0])}")
                    print(f"Raw content: {stock_result.content[0]}")
                
                print("\nNews Result:")
                print(f"Type: {type(news_result)}")
                print(f"Content type: {type(news_result.content) if not isinstance(news_result, Exception) else 'N/A'}")
                if not isinstance(news_result, Exception) and news_result.content:
                    print(f"First content item type: {type(news_result.content[0])}")
                    print(f"First content item attrs: {dir(news_result.content[0])}")
                    print(f"Raw content: {news_result.content[0]}")

                # --- Step 3: Synthesize and print the report ---
                print("\n" + "="*50)
                print("📊 CLIENT INTELLIGENCE BRIEFING 📊")
                print("="*50)

                # Debug: print raw response shapes
                print("\n🔍 DEBUG: Raw API Responses:")
                print("Stock Result:", repr(stock_result))
                if hasattr(stock_result, 'content'):
                    print("Stock Content:", repr(stock_result.content))
                print("\nNews Result:", repr(news_result))
                if hasattr(news_result, 'content'):
                    print("News Content:", repr(news_result.content))
                print("="*50)

                # Print stock info, but check for errors first
                print("\n📈 Market Snapshot:")
                if isinstance(stock_result, Exception):
                    print(f"  ERROR fetching stock data: {stock_result}")
                else:
                    try:
                        # Get data either from structuredContent or parse JSON text
                        if hasattr(stock_result, 'structuredContent') and stock_result.structuredContent:
                            stock_data = stock_result.structuredContent
                        else:
                            import json
                            stock_text = stock_result.content[0].text
                            stock_data = json.loads(stock_text)
                        
                        print(f"  Symbol: {stock_data.get('symbol')}")
                        price = stock_data.get('price')
                        if price:
                            print(f"  Price: ${float(price):.2f}")
                        print(f"  Change: {stock_data.get('change_percent')}")
                    except Exception as e:
                        print(f"  ERROR parsing stock data: {e}")

                # Print news info, checking for errors first
                print("\n📰 Key Financial News:")
                if isinstance(news_result, Exception):
                    print(f"  ERROR fetching news data: {news_result}")
                else:
                    try:
                        # Check both content and structuredContent
                        news_articles = []
                        if news_result.content:
                            for article in news_result.content:
                                if hasattr(article, 'text'):
                                    try:
                                        import json
                                        article_data = json.loads(article.text)
                                        # Handle both data wrapper and direct format
                                        if 'data' in article_data:
                                            news_articles.append(article_data['data'])
                                        else:
                                            news_articles.append(article_data)
                                    except json.JSONDecodeError:
                                        print(f"  ERROR: Could not parse article JSON: {article.text[:100]}...")
                                        continue
                        elif hasattr(news_result, 'structuredContent'):
                            if isinstance(news_result.structuredContent, list):
                                news_articles = news_result.structuredContent
                            elif isinstance(news_result.structuredContent, dict) and 'result' in news_result.structuredContent:
                                news_articles = news_result.structuredContent['result']
                        
                        if news_articles:
                            for article in news_articles:
                                print(f"- {article.get('title')} ({article.get('source')})")
                        else:
                            print("- No financial news articles found.")
                    except Exception as e:
                        print(f"  ERROR parsing news data: {e}")
                
                print("\n" + "="*50)

    except Exception as e:
        print(f"\n--- CLIENT-SIDE ERROR ---")
        print(f"An error occurred: {e}")
        # Print full traceback for deeper debugging (TaskGroup sub-exceptions)
        traceback.print_exc()
        # If this exception wraps others, show their context/cause
        if getattr(e, '__cause__', None):
            print('\n--- __cause__ ---')
            traceback.print_exception(type(e.__cause__), e.__cause__, e.__cause__.__traceback__)
        if getattr(e, '__context__', None):
            print('\n--- __context__ ---')
            traceback.print_exception(type(e.__context__), e.__context__, e.__context__.__traceback__)
        print("Please ensure the server.py is running and the URL is correct.")



if __name__ == "__main__":
    # --- Your Turn: Define the target company here ---
    company_to_research = "Microsoft"
    company_ticker = "MSFT"
    
    asyncio.run(run_intelligence_briefing(company_to_research, company_ticker))