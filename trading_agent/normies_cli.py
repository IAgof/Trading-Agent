"""Command-line interface for the Normies Intelligence Agent."""

from __future__ import annotations

import argparse
import json
from typing import Sequence

from .config import Settings, ensure_runtime_dirs
from .normies_client import NormiesClient
from .normies_ingest import offline_demo_signals, scan_range
from .normies_repository import NormiesRepository


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Trading-Agent CLI")
    subparsers = parser.add_subparsers(dest="domain", required=True)

    normies = subparsers.add_parser("normies", help="Normies Intelligence Agent commands")
    normies_sub = normies.add_subparsers(dest="command", required=True)

    scan = normies_sub.add_parser("scan", help="Scan and score an inclusive Normies token range")
    scan.add_argument("--start", type=int, default=0)
    scan.add_argument("--end", type=int, default=25)
    scan.add_argument("--offline-demo", action="store_true", help="Use deterministic demo data instead of HTTP")
    scan.add_argument("--db", help="SQLite database path override")
    scan.add_argument("--no-cache", action="store_true", help="Disable HTTP cache")

    top = normies_sub.add_parser("top", help="Show top scored Normies from the local database")
    top.add_argument("--limit", type=int, default=25)
    top.add_argument("--db", help="SQLite database path override")
    top.add_argument("--json", action="store_true", help="Emit JSON instead of a table")

    explain = normies_sub.add_parser("explain", help="Explain one stored Normie score")
    explain.add_argument("token_id", type=int)
    explain.add_argument("--db", help="SQLite database path override")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    settings = Settings.from_env()
    if getattr(args, "db", None):
        settings = Settings(
            normies_base_url=settings.normies_base_url,
            database_path=__import__("pathlib").Path(args.db),
            cache_dir=settings.cache_dir,
            request_timeout_seconds=settings.request_timeout_seconds,
            requests_per_minute=settings.requests_per_minute,
            user_agent=settings.user_agent,
        )
    ensure_runtime_dirs(settings)
    repo = NormiesRepository(settings.database_path)
    try:
        if args.domain == "normies" and args.command == "scan":
            if args.offline_demo:
                signals = offline_demo_signals(args.start, args.end)
                repo.upsert_many(signals)
            else:
                client = NormiesClient(settings, use_cache=not args.no_cache)
                signals = scan_range(client, repo, args.start, args.end)
            print(f"Scanned {len(signals)} Normies into {settings.database_path}")
            print_table(sorted(signals, key=lambda item: item.composite_score, reverse=True)[:10])
            return 0
        if args.domain == "normies" and args.command == "top":
            rows = repo.top_signals(args.limit)
            if args.json:
                print(json.dumps([signal.__dict__ for signal in rows], indent=2, sort_keys=True))
            else:
                print_table(rows)
            return 0
        if args.domain == "normies" and args.command == "explain":
            signal = repo.get_signal(args.token_id)
            if signal is None:
                parser.error(f"No stored signal for token_id {args.token_id}; run normies scan first")
            print(f"Normie #{signal.token_id} — composite={signal.composite_score:.4f}")
            print(f"Traits: type={signal.type_trait}, eyes={signal.eyes_trait}, accessory={signal.accessory_trait}")
            print("Razones: " + "; ".join(signal.explanation_parts()))
            return 0
    finally:
        repo.close()
    return 1


def print_table(rows: list[object]) -> None:
    print("token_id  composite  rarity  density  canvas  holder  status")
    print("--------  ---------  ------  -------  ------  ------  ------")
    for row in rows:
        print(
            f"{row.token_id:>8}  {row.composite_score:>9.4f}  {row.rarity_score:>6.4f}  "
            f"{row.visual_density_score:>7.4f}  {row.canvas_activity_score:>6.4f}  "
            f"{row.holder_activity_score:>6.4f}  {row.status}"
        )
