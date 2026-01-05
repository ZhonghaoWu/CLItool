#!/usr/bin/env python3
import argparse
import csv
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from statistics import mean
from typing import Dict, List, Optional

WATCHLIST_PATH = os.path.expanduser("~/.cli_watchlist.json")
YAHOO_QUOTE_URL = "https://query1.finance.yahoo.com/v7/finance/quote"


@dataclass
class Quote:
    symbol: str
    price: float
    currency: Optional[str]


def load_watchlist(path: str = WATCHLIST_PATH) -> List[str]:
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, list):
        raise ValueError(f"Invalid watchlist format in {path}")
    return [str(item).upper() for item in data]


def save_watchlist(tickers: List[str], path: str = WATCHLIST_PATH) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(sorted(set(tickers)), handle, indent=2)


def fetch_quotes(tickers: List[str]) -> Dict[str, Quote]:
    if not tickers:
        return {}
    params = urllib.parse.urlencode({"symbols": ",".join(tickers)})
    url = f"{YAHOO_QUOTE_URL}?{params}"
    request = urllib.request.Request(url, headers={"User-Agent": "CLItool/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Failed to fetch quotes: {exc}") from exc

    results = payload.get("quoteResponse", {}).get("result", [])
    quotes: Dict[str, Quote] = {}
    for entry in results:
        symbol = entry.get("symbol")
        price = entry.get("regularMarketPrice")
        if symbol and price is not None:
            quotes[symbol.upper()] = Quote(
                symbol=symbol.upper(),
                price=float(price),
                currency=entry.get("currency"),
            )
    return quotes


def print_summary(quotes: Dict[str, Quote]) -> None:
    if not quotes:
        print("No quotes available.")
        return
    prices = [quote.price for quote in quotes.values()]
    print("\nSummary")
    print("=======")
    print(f"Count: {len(prices)}")
    print(f"Min:   {min(prices):.2f}")
    print(f"Max:   {max(prices):.2f}")
    print(f"Avg:   {mean(prices):.2f}")


def print_quotes(quotes: Dict[str, Quote]) -> None:
    if not quotes:
        return
    print("\nQuotes")
    print("======")
    for symbol in sorted(quotes):
        quote = quotes[symbol]
        currency = f" {quote.currency}" if quote.currency else ""
        print(f"{quote.symbol:6} {quote.price:10.2f}{currency}")


def export_csv(quotes: Dict[str, Quote], path: str) -> None:
    if not quotes:
        print("No quotes to export.")
        return
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["symbol", "price", "currency", "timestamp"])
        timestamp = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        for quote in quotes.values():
            writer.writerow([quote.symbol, quote.price, quote.currency or "", timestamp])
    print(f"CSV exported to {path}")


def add_tickers(args: argparse.Namespace) -> None:
    existing = load_watchlist()
    additions = [ticker.upper() for ticker in args.tickers]
    save_watchlist(existing + additions)
    print(f"Added {len(additions)} ticker(s) to watchlist.")


def remove_tickers(args: argparse.Namespace) -> None:
    existing = load_watchlist()
    to_remove = {ticker.upper() for ticker in args.tickers}
    updated = [ticker for ticker in existing if ticker not in to_remove]
    save_watchlist(updated)
    removed_count = len(existing) - len(updated)
    print(f"Removed {removed_count} ticker(s) from watchlist.")


def list_watchlist(_: argparse.Namespace) -> None:
    watchlist = load_watchlist()
    if not watchlist:
        print("Watchlist is empty. Add tickers with the 'add' command.")
        return
    print("Watchlist:")
    for ticker in watchlist:
        print(f"- {ticker}")


def refresh_watchlist(args: argparse.Namespace) -> None:
    watchlist = load_watchlist()
    if not watchlist:
        print("Watchlist is empty. Add tickers with the 'add' command.")
        return
    quotes = fetch_quotes(watchlist)
    print_quotes(quotes)
    print_summary(quotes)
    if args.csv:
        export_csv(quotes, args.csv)


def fetch_now(args: argparse.Namespace) -> None:
    tickers = [ticker.upper() for ticker in args.tickers]
    quotes = fetch_quotes(tickers)
    print_quotes(quotes)
    print_summary(quotes)
    if args.csv:
        export_csv(quotes, args.csv)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Track a personal stock watchlist with live prices.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    add_parser = subparsers.add_parser("add", help="Add tickers to your watchlist")
    add_parser.add_argument("tickers", nargs="+", help="Ticker symbols to add")
    add_parser.set_defaults(func=add_tickers)

    remove_parser = subparsers.add_parser("remove", help="Remove tickers from your watchlist")
    remove_parser.add_argument("tickers", nargs="+", help="Ticker symbols to remove")
    remove_parser.set_defaults(func=remove_tickers)

    list_parser = subparsers.add_parser("list", help="List your saved watchlist")
    list_parser.set_defaults(func=list_watchlist)

    refresh_parser = subparsers.add_parser(
        "refresh", help="Refresh data for your saved watchlist")
    refresh_parser.add_argument(
        "--csv", metavar="PATH", help="Export results to CSV")
    refresh_parser.set_defaults(func=refresh_watchlist)

    fetch_parser = subparsers.add_parser(
        "fetch", help="Fetch quotes for tickers without saving")
    fetch_parser.add_argument("tickers", nargs="+", help="Ticker symbols to fetch")
    fetch_parser.add_argument(
        "--csv", metavar="PATH", help="Export results to CSV")
    fetch_parser.set_defaults(func=fetch_now)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    try:
        args.func(args)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
