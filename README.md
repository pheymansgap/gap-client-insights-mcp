# Client Intelligence MCP Server

An MCP server that provides company research tools for VS Code — stock data, financial news, and structured insights. The host LLM (GitHub Copilot) handles all reasoning and analysis over the raw data.

## Tools

| Tool | Description |
|------|-------------|
| `search_ticker_symbol` | Look up a stock ticker by company name |
| `get_stock_performance` | Real-time price, change, volume, and range |
| `get_financial_news` | Latest from Reuters, Bloomberg, WSJ, FT, CNBC |
| `get_general_news` | Broader news coverage across all sources |
| `get_google_news` | News via Google News RSS (no API key needed) |
| `get_company_insights` | Aggregated stock + news data for LLM analysis |
| `generate_company_briefing` | Full orchestrated briefing in one call |

## Quick Start

```powershell
# Install uv (if not already installed)
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# Install dependencies
uv sync

# Configure API keys
cp .env.example .env
# Edit .env with your keys
```

See [SETUP.md](SETUP.md) for detailed instructions including VS Code configuration.

## Usage

In VS Code with GitHub Copilot Chat:

```
@client-intelligence generate a briefing for Microsoft (MSFT)
@client-intelligence search for the ticker symbol of Tesla
@client-intelligence get stock performance for AAPL
```

## API Keys Required

| Service | Free Tier | Sign Up |
|---------|-----------|---------|
| Alpha Vantage | 25 req/day | https://www.alphavantage.co/support/#api-key |
| NewsAPI | 100 req/day | https://newsapi.org/register |


## Project Structure

```
src/mcp_server.py    # MCP server (the only code file)
scripts/setup.ps1    # Automated setup helper
scripts/verify.py    # Pre-flight configuration check
pyproject.toml       # Dependencies (managed by uv)
.env.example         # Template for API keys
SETUP.md             # Full setup guide
```

## License

MIT
