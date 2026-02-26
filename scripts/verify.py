"""Pre-flight check for the Client Intelligence MCP server."""

import os
import sys
from pathlib import Path

def main() -> int:
    # Ensure we load .env from project root
    project_root = Path(__file__).resolve().parent.parent
    env_path = project_root / ".env"

    from dotenv import load_dotenv
    load_dotenv(env_path)

    ok = True

    # --- Packages ---
    print("Packages")
    for pkg, imp in [("mcp", "mcp"), ("requests", "requests"),
                     ("google-genai", "google.genai"),
                     ("pydantic", "pydantic"), ("python-dotenv", "dotenv")]:
        try:
            __import__(imp)
            print(f"  + {pkg}")
        except ImportError:
            print(f"  - {pkg}  (run: uv sync)")
            ok = False

    # --- API keys ---
    print("\nAPI keys")
    for key, label in [("ALPHA_VANTAGE_API_KEY", "Alpha Vantage"),
                       ("NEWS_API_KEY", "NewsAPI"),
                       ("GEMINI_API_KEY", "Gemini")]:
        val = os.environ.get(key)
        if val and "your_" not in val:
            print(f"  + {label}")
        else:
            print(f"  - {label}  (set {key} in .env)")
            ok = False

    # --- Gemini connectivity ---
    print("\nGemini")
    gemini_key = os.environ.get("GEMINI_API_KEY")
    if gemini_key and "your_" not in gemini_key:
        try:
            from google import genai
            genai.Client(api_key=gemini_key)
            print("  + API configured")
        except Exception as e:
            print(f"  - Configuration error: {e}")
            ok = False
    else:
        print("  - Skipped (no key)")

    # --- Server syntax ---
    print("\nServer")
    server_path = project_root / "src" / "mcp_server.py"
    if server_path.exists():
        try:
            compile(server_path.read_text(), str(server_path), "exec")
            print("  + src/mcp_server.py — no syntax errors")
        except SyntaxError as e:
            print(f"  - Syntax error: {e}")
            ok = False
    else:
        print(f"  - src/mcp_server.py not found")
        ok = False

    # --- Result ---
    print()
    if ok:
        print("All checks passed.")
    else:
        print("Some checks failed. See above.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
