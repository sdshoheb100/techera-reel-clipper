"""
TechEra AI Engine — Self-Learning Performance Memory (v0.1.0)
Tracks processed videos, niche weights, hook performance, and generates
data-driven recommendations for what to improve in the next video & next version.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
MEMORY_PATH = BASE_DIR / "data" / "learning_memory.json"


def load_memory() -> dict:
    if MEMORY_PATH.exists():
        try:
            return json.loads(MEMORY_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {
        "engine_version": "0.1.0",
        "total_runs": 0,
        "total_reels_generated": 0,
        "used_video_ids": [],
        "niche_weights": {
            "tech_gadgets": 1.20,
            "fashion_winter": 1.15,
            "home_kitchen": 1.10,
            "mobile_audio": 1.10,
            "general_viral": 1.00,
        },
        "history": [],
        "next_video_tips_bn": [
            "প্রথম ৩ সেকেন্ডে প্রোডাক্টের অ্যাকশন ক্লিপ রাখুন যাতে দর্শক স্ক্রল না করে।",
            "একাধিক অ্যাঙ্গেল (৩-৪টি ছোট ক্লিপ) জোড়া দিলে রিচ ওয়াচ-টাইম বাড়ে।",
            "মূল অডিও ১০০% মিউট রেখে বাংলা ভয়েসওভার ও প্রাইস কার্ড ব্যবহার করুন।"
        ],
        "next_version_suggestions": [
            {"target": "v0.2.0", "feature": "Auto Bengali AI Voiceover (Edge-TTS) + Royalty-Free Music Auto-Ducking"},
            {"target": "v0.3.0", "feature": "Direct Google Drive Auto-Sync so finished Reels appear automatically on your PC"},
            {"target": "v0.4.0", "feature": "Facebook Insights Engagement Feedback Loop (auto-reweight niches by real views/likes)"}
        ],
        "last_updated": None,
    }


def save_memory(mem: dict, mirror_docs: bool = True):
    MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    mem["last_updated"] = datetime.now(timezone.utc).isoformat()
    payload = json.dumps(mem, indent=2, ensure_ascii=False)
    MEMORY_PATH.write_text(payload, encoding="utf-8")

    if mirror_docs:
        docs_mem = BASE_DIR / "docs" / "data" / "learning_memory.json"
        docs_mem.parent.mkdir(parents=True, exist_ok=True)
        docs_mem.write_text(payload, encoding="utf-8")


def record_run(mem: dict, mode: str, niche: str, video_ids: list, avg_score: float, reel_created: bool):
    mem["total_runs"] = mem.get("total_runs", 0) + 1
    if reel_created:
        mem["total_reels_generated"] = mem.get("total_reels_generated", 0) + 1

    used = set(mem.get("used_video_ids", []))
    for vid in video_ids:
        if vid:
            used.add(vid)
    mem["used_video_ids"] = sorted(used)[-500:]

    # Adaptive weight update: reward niches with strong trend velocity scores
    weights = mem.setdefault("niche_weights", {})
    cur_w = float(weights.get(niche, 1.0))
    if avg_score >= 70:
        cur_w = min(2.0, round(cur_w + 0.05, 3))
    elif avg_score < 35 and avg_score > 0:
        cur_w = max(0.7, round(cur_w - 0.03, 3))
    weights[niche] = cur_w

    mem.setdefault("history", []).append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "niche": niche,
        "clips_used": len(video_ids),
        "avg_trend_score": round(avg_score, 1),
        "reel_created": reel_created,
    })
    mem["history"] = mem["history"][-50:]

    # Self-learning tip refresh based on run history
    top_niche = max(weights.items(), key=lambda x: x[1])[0] if weights else "tech_gadgets"
    mem["next_video_tips_bn"] = [
        f"বর্তমান ডাটা অনুযায়ী '{top_niche}' ক্যাটাগরির ট্রেন্ড স্কোর সবচেয়ে শক্তিশালী (Weight: {weights.get(top_niche, 1.0)}x)।",
        f"এখন পর্যন্ত {mem['total_reels_generated']}টি রিলস জেনারেট ও {len(mem['used_video_ids'])}টি সোর্স ক্লিপ ট্র্যাক হয়েছে—ডুপ্লিকেট ক্লিপ অটো-স্কিপ করা হচ্ছে।",
        "৩–৪ সেকেন্ডের দ্রুত কাট (মাল্টি-ক্লিপ ম্যাশআপ) + পরিষ্কার দাম ও বাংলা হুক সর্বোচ্চ এনগেজমেন্ট দেয়।"
    ]
    save_memory(mem)
    return mem
