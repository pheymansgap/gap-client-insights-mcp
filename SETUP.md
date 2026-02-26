# Setup Guide

## 1. Install uv

```powershell
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

## 2. Install Dependencies

```powershell
uv sync
```

## 3. Get API Keys

| Service | URL |
|---------|-----|
| Alpha Vantage | https://www.alphavantage.co/support/#api-key |
| NewsAPI | https://newsapi.org/register |
| Google Gemini | https://aistudio.google.com/app/apikey |

## 4. Configure Environment

```powershell
cp .env.example .env
notepad .env   # Add your API keys
```

## 5. Verify Setup

```powershell
uv run python scripts/verify.py
```

## 6. Configure VS Code

Open VS Code settings (`Ctrl+,`) → search "mcp" → edit `settings.json`:

```json
{
  "github.copilot.chat.mcpServers": {
    "client-intelligence": {
      "command": "uv",
      "args": [
        "run",
        "--directory", "c:\\path\\to\\gap-client-insights-mcp",
        "python", "src/mcp_server.py"
      ]
    }
  }
}
```

Replace `c:\\path\\to\\gap-client-insights-mcp` with your actual project path.

The server reads API keys from the `.env` file automatically. No need to put them in `settings.json`.

## 7. Restart VS Code

Restart VS Code to load the MCP server, then test:

```
@client-intelligence generate a briefing for Microsoft (MSFT)
```

## Troubleshooting

**Server not found** — Verify the path in `settings.json` is absolute and correct.

**API key errors** — Run `uv run python scripts/verify.py` to check configuration.

**Import errors** — Run `uv sync` to reinstall dependencies.

**Rate limits** — Alpha Vantage: 25 req/day, NewsAPI: 100 req/day on free tiers.
