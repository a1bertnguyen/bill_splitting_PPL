"""
SplitLang Web Application Entry Point (FastAPI + Modern Web Frontend).

Usage:
    python main.py                  # Starts server at http://127.0.0.1:8000 & opens browser
    python main.py --port 8080      # Custom port
    python main.py --no-browser     # Start server without opening browser
"""

from __future__ import annotations

import argparse
import threading
import webbrowser

import uvicorn


def main() -> None:
    parser = argparse.ArgumentParser(description="SplitLang Web App Launcher")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Bind port (default: 8000)")
    parser.add_argument("--no-browser", action="store_true", help="Do not auto-open browser")
    args = parser.parse_args()

    url = f"http://{args.host}:{args.port}"
    print(f"Starting SplitLang Web App at {url}")

    if not args.no_browser:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()

    uvicorn.run("api.server:app", host=args.host, port=args.port, reload=False)


if __name__ == "__main__":
    main()
