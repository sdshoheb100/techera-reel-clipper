#!/usr/bin/env python3
"""
TechEra AI Market & Reel Engine — Master Orchestrator (v0.2.0)
Modes:
1. store_product_reel : (DEFAULT, ZERO-FAIL) Picks brand-new unused products from techerabd.storeline.io,
                        renders a sleek animated 9:16 Reel, publishes it directly inside the Mobile App!
2. daily_trend_report : Scouts daily 2026+ Tech & Fashion trends, updates future forecast & Mobile App feed.
3. custom_video_reel  : Takes 1 or more comma-separated direct video URLs, cuts & stitches branded Reel.
4. auto_trending_reel : Scouts trends & attempts multi-clip download (best on PC; falls back to StoreLine Reel if blocked).
"""

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from modules.future_forecaster import build_future_forecast
from modules.memory_learner import load_memory, record_run, save_memory
from modules.reel_studio import render_multiclip_reel
from modules.store_reel_studio import fetch_live_store_products, render_store_product_reel
from modules.trend_scout import scout_daily_trends

BASE_DIR = Path(__file__).resolve().parent
VERSION_PATH = BASE_DIR / "config" / "version.json"
OUT_DIR = BASE_DIR / "output"
DOCS_DATA_DIR = BASE_DIR / "docs" / "data"
DOCS_REELS_DIR = BASE_DIR / "docs" / "reels"
OUT_DIR.mkdir(exist_ok=True)
DOCS_DATA_DIR.mkdir(parents=True, exist_ok=True)
DOCS_REELS_DIR.mkdir(parents=True, exist_ok=True)


def publish_reel_to_app(out_mp4: Path, title: str, niche: str, meta: dict) -> dict:
    """Copies the rendered MP4 into docs/reels/ and updates docs/data/reels_gallery.json (keeps latest 6)."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    fname = f"reel_{ts}.mp4"
    dest = DOCS_REELS_DIR / fname
    shutil.copy2(out_mp4, dest)

    gallery_path = DOCS_DATA_DIR / "reels_gallery.json"
    gallery = []
    if gallery_path.exists():
        try:
            gallery = json.loads(gallery_path.read_text(encoding="utf-8"))
        except Exception:
            gallery = []

    entry = {
        "filename": fname,
        "rel_url": f"./reels/{fname}",
        "title": title,
        "niche": niche,
        "duration_seconds": meta.get("duration_seconds", 0),
        "size_mb": round(dest.stat().st_size / (1024 * 1024), 2),
        "products": meta.get("products_featured", []),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    gallery.insert(0, entry)

    # Keep only the latest 6 reels to keep the GitHub repo light & fast
    for old in gallery[6:]:
        old_file = DOCS_REELS_DIR / old.get("filename", "")
        if old_file.exists():
            old_file.unlink(missing_ok=True)
    gallery = gallery[:6]

    gallery_path.write_text(json.dumps(gallery, indent=2, ensure_ascii=False), encoding="utf-8")
    return entry


def main():
    version_info = json.loads(VERSION_PATH.read_text(encoding="utf-8"))
    engine_ver = version_info["version"]

    # Mirror version.json to docs/data/
    (DOCS_DATA_DIR / "version.json").write_text(json.dumps(version_info, indent=2, ensure_ascii=False), encoding="utf-8")

    parser = argparse.ArgumentParser(description=f"TechEra AI Market & Reel Engine v{engine_ver}")
    parser.add_argument(
        "--mode",
        choices=["store_product_reel", "daily_trend_report", "auto_trending_reel", "custom_video_reel"],
        default="store_product_reel",
    )
    parser.add_argument("--niche", default="all", help="Target niche key or 'all'")
    parser.add_argument("--urls", default="", help="Comma-separated video URLs for custom_video_reel mode")
    parser.add_argument("--product", default="TechEra BD", help="Header or Product overlay title")
    parser.add_argument("--price", default="", help="Optional price override (leave blank for live store prices)")
    parser.add_argument("--clip-seconds", type=float, default=3.5, help="Seconds per clip/product")
    parser.add_argument("--max-clips", type=int, default=3, help="Number of products/clips per Reel")
    args = parser.parse_args()

    print(f"=== {version_info['engine_name']} v{engine_ver} ({version_info['codename']}) ===")
    print(f"Mode: {args.mode} | Niche: {args.niche}")

    mem = load_memory()
    mem["engine_version"] = engine_ver
    reel_meta = None
    app_reel_entry = None
    trends_report = {"top_picks": []}
    out_mp4 = OUT_DIR / "ready_reel.mp4"

    # Always refresh trends for daily_trend_report & auto_trending_reel
    if args.mode in ("daily_trend_report", "auto_trending_reel"):
        trends_report = scout_daily_trends(mem, target_niche=args.niche)

    if args.mode == "store_product_reel":
        used_slugs = set(mem.get("used_video_ids", []))
        products = fetch_live_store_products(niche=args.niche, used_slugs=used_slugs, count=max(1, min(4, args.max_clips)))
        reel_meta = render_store_product_reel(
            products=products,
            out_path=out_mp4,
            sec_per_product=args.clip_seconds,
            header_text=args.product or "TechEra BD",
            override_price=args.price,
        )
        reel_title = " + ".join(reel_meta["products_featured"][:2])
        app_reel_entry = publish_reel_to_app(out_mp4, reel_title, args.niche, reel_meta)
        record_run(mem, args.mode, args.niche if args.niche != "all" else "tech_gadgets", reel_meta["product_slugs"], 88.0, reel_created=True)

    elif args.mode == "auto_trending_reel":
        picks = trends_report.get("top_picks", [])
        chosen = picks[: args.max_clips]
        try:
            if not chosen:
                raise RuntimeError("No trending picks found")
            urls = [c["url"] for c in chosen]
            title = args.product if args.product not in ("", "TechEra BD", "TechEra BD Trending Gadget") else chosen[0]["title"][:36]
            reel_meta = render_multiclip_reel(
                source_urls=urls,
                out_path=out_mp4,
                product_name=title,
                price_text=args.price,
                clip_len_each=args.clip_seconds,
                max_clips=args.max_clips,
            )
            app_reel_entry = publish_reel_to_app(out_mp4, title, args.niche, reel_meta)
            record_run(mem, args.mode, chosen[0]["niche"], [c["id"] for c in chosen], 85.0, reel_created=True)
        except Exception as e:
            print(f"WARN: Cloud YouTube download blocked ({e}). Auto-falling back to Zero-Fail StoreLine Product Reel!")
            used_slugs = set(mem.get("used_video_ids", []))
            products = fetch_live_store_products(niche=args.niche, used_slugs=used_slugs, count=max(1, min(4, args.max_clips)))
            reel_meta = render_store_product_reel(
                products=products,
                out_path=out_mp4,
                sec_per_product=args.clip_seconds,
                header_text=args.product or "TechEra BD",
                override_price=args.price,
            )
            reel_title = " + ".join(reel_meta["products_featured"][:2])
            app_reel_entry = publish_reel_to_app(out_mp4, reel_title, args.niche, reel_meta)
            record_run(mem, "store_product_reel_fallback", args.niche if args.niche != "all" else "tech_gadgets", reel_meta["product_slugs"], 85.0, reel_created=True)

    elif args.mode == "custom_video_reel":
        urls = [u.strip() for u in args.urls.split(",") if u.strip()]
        if not urls:
            raise ValueError("Please provide at least one video URL in --urls")
        reel_meta = render_multiclip_reel(
            source_urls=urls,
            out_path=out_mp4,
            product_name=args.product,
            price_text=args.price,
            clip_len_each=args.clip_seconds,
            max_clips=min(args.max_clips, len(urls)),
        )
        app_reel_entry = publish_reel_to_app(out_mp4, args.product, args.niche, reel_meta)
        record_run(mem, args.mode, args.niche if args.niche != "all" else "tech_gadgets", urls, 80.0, reel_created=True)

    else:  # daily_trend_report
        picks = trends_report.get("top_picks", [])
        avg_score = (sum(c["trend_score"] for c in picks[:5]) / min(5, len(picks))) if picks else 0.0
        record_run(mem, args.mode, args.niche if args.niche != "all" else "tech_gadgets", [], avg_score, reel_created=False)

    forecast = build_future_forecast(trends_report, mem)
    save_memory(mem)

    # Emit bundle.js with ALL data including reels_gallery so the Mobile App works both offline & online!
    trends_file = DOCS_DATA_DIR / "daily_trends.json"
    gallery_file = DOCS_DATA_DIR / "reels_gallery.json"
    trends_obj = json.loads(trends_file.read_text(encoding="utf-8")) if trends_file.exists() else trends_report
    gallery_obj = json.loads(gallery_file.read_text(encoding="utf-8")) if gallery_file.exists() else []

    bundle_obj = {
        "version": version_info,
        "trends": trends_obj,
        "memory": mem,
        "forecast": forecast,
        "reels": gallery_obj,
    }
    (DOCS_DATA_DIR / "bundle.js").write_text(
        "window.TECHERA_DATA = " + json.dumps(bundle_obj, ensure_ascii=False) + ";\n",
        encoding="utf-8",
    )

    run_summary = {
        "engine_version": engine_ver,
        "mode": args.mode,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "reel": reel_meta,
        "app_reel": app_reel_entry,
    }
    (OUT_DIR / "run_summary.json").write_text(json.dumps(run_summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print("\n=== RUN COMPLETE ===")
    print(json.dumps(run_summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
