"""
TechEra AI Engine — Daily Market Expert & Multi-Niche Trend Scout (v0.1.0)
Researches trending product videos across Tech Gadgets, Fashion/Winter,
Home & Kitchen, Mobile/Audio, and Viral products using yt-dlp search metadata.
Scores and ranks today's top recommendations for the Mobile App dashboard.
"""

import json
import math
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
NICHES_PATH = BASE_DIR / "config" / "niches.json"


def _search_yt_metadata(query: str, limit: int = 5) -> list:
    cmd = [
        sys.executable, "-m", "yt_dlp",
        f"ytsearch{limit}:{query}",
        "--dump-json",
        "--flat-playlist",
        "--no-warnings",
        "--skip-download",
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=35)
        if res.returncode != 0:
            return []
        entries = []
        for line in res.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except Exception:
                pass
        return entries
    except Exception:
        return []


def score_candidate(entry: dict, niche_weight: float) -> float:
    views = entry.get("view_count") or 0
    duration = entry.get("duration") or 30
    # Log-scale view score (0..65)
    view_score = min(65.0, math.log10(max(10, views)) * 10.5)
    # Duration bonus: ideal short product demo is 10..65 seconds
    if 10 <= duration <= 65:
        dur_score = 25.0
    elif 6 <= duration <= 120:
        dur_score = 15.0
    else:
        dur_score = 5.0
    raw = (view_score + dur_score) * niche_weight
    return round(min(100.0, raw), 1)


def scout_daily_trends(memory: dict, target_niche: str = "all", per_niche_limit: int = 4) -> dict:
    niches_cfg = json.loads(NICHES_PATH.read_text(encoding="utf-8"))["niches"]
    used_ids = set(memory.get("used_video_ids", []))
    niche_weights = memory.get("niche_weights", {})

    selected_niches = (
        list(niches_cfg.keys())
        if target_niche in ("all", "", None)
        else [target_niche] if target_niche in niches_cfg else list(niches_cfg.keys())
    )

    recommendations = []
    seen_ids = set()

    for n_key in selected_niches:
        cfg = niches_cfg[n_key]
        weight = float(niche_weights.get(n_key, cfg.get("base_weight", 1.0)))
        queries = cfg.get("search_queries", [])
        hooks = cfg.get("hook_templates_bn", [])
        niche_hits = []

        for q in queries[:2]:
            entries = _search_yt_metadata(q, limit=per_niche_limit)
            for e in entries:
                vid = e.get("id")
                if not vid or vid in seen_ids or vid in used_ids:
                    continue
                seen_ids.add(vid)
                url = e.get("url") or f"https://www.youtube.com/watch?v={vid}"
                if not url.startswith("http"):
                    url = f"https://www.youtube.com/watch?v={vid}"
                sc = score_candidate(e, weight)
                niche_hits.append({
                    "id": vid,
                    "title": (e.get("title") or "Trending Product Video")[:90],
                    "url": url,
                    "niche": n_key,
                    "niche_label_bn": cfg.get("label_bn", n_key),
                    "views": e.get("view_count") or 0,
                    "duration": e.get("duration") or 0,
                    "channel": e.get("channel") or e.get("uploader") or "",
                    "trend_score": sc,
                    "recommended_hook_bn": hooks[len(niche_hits) % len(hooks)] if hooks else "",
                })

        niche_hits.sort(key=lambda x: x["trend_score"], reverse=True)
        recommendations.extend(niche_hits[:3])

    recommendations.sort(key=lambda x: x["trend_score"], reverse=True)

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "target_niche": target_niche,
        "total_recommendations": len(recommendations),
        "top_picks": recommendations[:12],
    }

    # Save to output/ and docs/data/ so the Mobile App displays today's trends live
    for out_p in [BASE_DIR / "output" / "daily_trends.json", BASE_DIR / "docs" / "data" / "daily_trends.json"]:
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    # Also write readable Markdown summary
    md_lines = [
        f"# TechEra AI Market Expert — Daily Trending Recommendations",
        f"- Generated: `{report['generated_at']}`",
        f"- Total Ranked Picks: **{len(report['top_picks'])}**\n",
        "| # | Niche | Score | Views | Title | Hook (BN) |",
        "| :---: | :--- | :---: | :---: | :--- | :--- |",
    ]
    for i, item in enumerate(report["top_picks"], 1):
        md_lines.append(
            f"| {i} | {item['niche_label_bn']} | **{item['trend_score']}** | {item['views']:,} | [{item['title'][:45]}]({item['url']}) | {item['recommended_hook_bn']} |"
        )
    (BASE_DIR / "output" / "daily_trends.md").write_text("\n".join(md_lines), encoding="utf-8")
    return report
