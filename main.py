#!/usr/bin/env python3
"""
TechEra AI Market & Reel Engine — Master Orchestrator (v0.1.0)
Modes:
1. daily_trend_report : Scouts daily trending product videos across all niches, updates learning memory & Mobile App feed.
2. auto_trending_reel : Scouts trends, picks top multi-video clips automatically, renders copyright-safe Reel, updates memory.
3. custom_video_reel  : Takes 1 or more comma-separated URLs from Mobile App, cuts & stitches branded Reel, updates memory.
"""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from modules.future_forecaster import build_future_forecast
from modules.memory_learner import load_memory, record_run, save_memory
from modules.reel_studio import render_multiclip_reel
from modules.trend_scout import scout_daily_trends

BASE_DIR = Path(__file__).resolve().parent
VERSION_PATH = BASE_DIR / "config" / "version.json"
OUT_DIR = BASE_DIR / "output"
OUT_DIR.mkdir(exist_ok=True)


def main():
    version_info = json.loads(VERSION_PATH.read_text(encoding="utf-8"))
    engine_ver = version_info["version"]

    # Mirror version.json to docs/data/ for the Mobile App live version badge
    docs_ver = BASE_DIR / "docs" / "data" / "version.json"
    docs_ver.parent.mkdir(parents=True, exist_ok=True)
    docs_ver.write_text(json.dumps(version_info, indent=2, ensure_ascii=False), encoding="utf-8")

    parser = argparse.ArgumentParser(description=f"TechEra AI Market & Reel Engine v{engine_ver}")
    parser.add_argument("--mode", choices=["daily_trend_report", "auto_trending_reel", "custom_video_reel"], default="daily_trend_report")
    parser.add_argument("--niche", default="all", help="Target niche key or 'all'")
    parser.add_argument("--urls", default="", help="Comma-separated video URLs for custom_video_reel mode")
    parser.add_argument("--product", default="TechEra BD Trending Gadget", help="Product overlay title")
    parser.add_argument("--price", default="", help="Price badge text")
    parser.add_argument("--clip-seconds", type=float, default=4.0, help="Seconds per stitched clip")
    parser.add_argument("--max-clips", type=int, default=3, help="Number of researched videos to stitch")
    args = parser.parse_args()

    print(f"=== {version_info['engine_name']} v{engine_ver} ({version_info['codename']}) ===")
    print(f"Mode: {args.mode} | Niche: {args.niche}")

    mem = load_memory()
    mem["engine_version"] = engine_ver
    reel_meta = None
    used_ids = []
    avg_score = 0.0
    trends_report = {"top_picks": []}

    if args.mode in ("daily_trend_report", "auto_trending_reel"):
        trends_report = scout_daily_trends(mem, target_niche=args.niche)
        picks = trends_report.get("top_picks", [])
        print(f"Trend Scout found {len(picks)} ranked product video recommendations.")

        if args.mode == "auto_trending_reel" and picks:
            chosen = picks[: args.max_clips]
            urls = [c["url"] for c in chosen]
            used_ids = [c["id"] for c in chosen]
            avg_score = sum(c["trend_score"] for c in chosen) / len(chosen)
            title = args.product if args.product != "TechEra BD Trending Gadget" else chosen[0]["title"][:36]
            reel_meta = render_multiclip_reel(
                source_urls=urls,
                out_path=OUT_DIR / "ready_reel.mp4",
                product_name=title,
                price_text=args.price,
                clip_len_each=args.clip_seconds,
                max_clips=args.max_clips,
            )
            record_run(mem, args.mode, chosen[0]["niche"], used_ids, avg_score, reel_created=True)
        else:
            avg_score = (sum(c["trend_score"] for c in picks[:5]) / min(5, len(picks))) if picks else 0.0
            record_run(mem, args.mode, args.niche if args.niche != "all" else "tech_gadgets", [], avg_score, reel_created=False)

    elif args.mode == "custom_video_reel":
        urls = [u.strip() for u in args.urls.split(",") if u.strip()]
        if not urls:
            raise ValueError("Please provide at least one video URL in --urls")
        reel_meta = render_multiclip_reel(
            source_urls=urls,
            out_path=OUT_DIR / "ready_reel.mp4",
            product_name=args.product,
            price_text=args.price,
            clip_len_each=args.clip_seconds,
            max_clips=min(args.max_clips, len(urls)),
        )
        record_run(mem, args.mode, args.niche if args.niche != "all" else "tech_gadgets", urls, 75.0, reel_created=True)

    forecast = build_future_forecast(trends_report, mem)

    run_summary = {
        "engine_version": engine_ver,
        "mode": args.mode,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "trends_found": len(trends_report.get("top_picks", [])),
        "current_season": forecast.get("current_season_bn"),
        "reel": reel_meta,
    }
    (OUT_DIR / "run_summary.json").write_text(json.dumps(run_summary, indent=2, ensure_ascii=False), encoding="utf-8")
    save_memory(mem)

    # Also emit docs/data/bundle.js so docs/index.html works 100% offline via file:// double-click AND on GitHub Pages!
    docs_data_dir = BASE_DIR / "docs" / "data"
    trends_file = docs_data_dir / "daily_trends.json"
    trends_obj = json.loads(trends_file.read_text(encoding="utf-8")) if trends_file.exists() else trends_report
    bundle_obj = {
        "version": version_info,
        "trends": trends_obj,
        "memory": mem,
        "forecast": forecast,
    }
    (docs_data_dir / "bundle.js").write_text(
        "window.TECHERA_DATA = " + json.dumps(bundle_obj, ensure_ascii=False) + ";\n",
        encoding="utf-8",
    )

    print("\n=== RUN COMPLETE ===")
    print(json.dumps(run_summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
