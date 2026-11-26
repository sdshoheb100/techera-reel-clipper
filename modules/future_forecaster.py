"""
TechEra AI Engine — Future Demand & Next-Gen Trend Forecaster (v0.1.0)
Combines Bangladesh seasonal buying cycles, live trend velocity from trend_scout,
and adaptive learning memory weights to forecast upcoming high-demand products
and winning Reel formats for the next 30-60 days.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SEASONAL_SIGNALS = {
    # Month -> (Season name BN, Hot product types, Content strategy)
    11: ("শীতের শুরু (Early Winter)", ["Hoodie & Winter Wear", "Mini Room Heater", "Electric Kettle & Hot Water Tap", "Vacuum Flask"], "শীতের আরাম ও ফ্যাশন — প্রথম ৩ সেকেন্ডে প্রোডাক্ট ইউজ ডেমো দেখান"),
    12: ("ভরা শীত (Peak Winter)", ["Premium Hoodie Combo", "Room Heater & Geyser Tap", "Thermos Flask", "Smart Gadgets Gift"], "উইন্টার অফার ও কম্বো ডিল — দাম বড় ফন্টে হাইলাইট করুন"),
    1:  ("শীত ও নতুন বছর (Winter & New Year)", ["Winter Jackets & Hoodies", "Smart Watch & TWS", "Desk & Study Gadgets"], "নিউ ইয়ার ডিসকাউন্ট ও গিফট আইডিয়া ফোকাস করুন"),
    2:  ("বসন্ত ও ভ্যালেন্টাইন (Spring)", ["Smart Watch", "TWS Earbuds", "Sunglasses & Fashion", "Gift Combos"], "কাপল গিফট ও স্টাইলিশ অ্যাক্সেসরিজ ক্লিপ বানান"),
    3:  ("গরমের শুরু (Early Summer)", ["Mini Portable Fan", "Rechargeable Cooling Gadgets", "Power Bank", "Sunglasses"], "গরম থেকে বাঁচার স্মার্ট সমাধান — আগে/পরে (Before/After) ক্লিপ দেখান"),
    4:  ("তীব্র গরম ও ঈদ (Peak Summer)", ["Mini AC & Hand Fan", "Power Bank & Mini UPS", "Fashion & Watch", "TWS Earbuds"], "লোডশেডিং সমাধান (Mini UPS / Power Bank) ও ঈদ কালেকশন ফোকাস করুন"),
    5:  ("গরম ও ঝড়-বৃষ্টি (Summer/Storm)", ["WGP Mini UPS", "20000mAh Power Bank", "Portable Fan", "Waterproof Watch"], "কারেন্ট গেলে ওয়াইফাই চালানোর ডেমো (Mini UPS) সবচেয়ে বেশি ভাইরাল হয়"),
    6:  ("বর্ষা (Monsoon)", ["Waterproof Gadgets", "CCTV Security Camera", "Indoor Kitchen Gadgets", "Gaming Gear"], "বর্ষায় ঘরের নিরাপত্তা (CCTV) ও ইনডোর গ্যাজেট দেখান"),
    7:  ("বর্ষা (Monsoon)", ["WiFi CCTV Camera", "Smart Home Gadgets", "TWS & Neckband", "Kitchen Helpers"], "রিয়েল-লাইফ প্রবলেম সলভিং শর্ট ক্লিপ বানান"),
    8:  ("শরৎ (Early Autumn)", ["Smart Watch", "Mobile Accessories", "Audio & Speakers", "Tech Gadgets"], "আনবক্সিং + সাউন্ড/ডিসপ্লে টেস্ট ক্লিপ দিন"),
    9:  ("উৎসবের মৌসুম (Festive Season)", ["Fashion & Watches", "Gaming Headsets", "Decorating Lights", "Gift Gadgets"], "ফেস্টিভ অফার ও লাইটিং ডেমো ক্লিপ বানান"),
    10: ("শীতের আগমনী (Pre-Winter)", ["Early Hoodies", "Electric Kettle", "Hot Water Shower Tap", "Smart Gadgets"], "শীত আসার আগেই প্রি-অর্ডার/আর্লি বার্ড ভিডিও চালান"),
}


def build_future_forecast(trends_report: dict, memory: dict) -> dict:
    now = datetime.now(timezone.utc)
    month = now.month
    next_month = 1 if month == 12 else month + 1

    cur_season, cur_products, cur_tip = SEASONAL_SIGNALS.get(month, SEASONAL_SIGNALS[11])
    nxt_season, nxt_products, nxt_tip = SEASONAL_SIGNALS.get(next_month, SEASONAL_SIGNALS[12])

    # Rank niches by live trend score * learned memory weight
    weights = memory.get("niche_weights", {})
    niche_scores = {}
    for p in trends_report.get("top_picks", []):
        nk = p.get("niche", "general_viral")
        niche_scores.setdefault(nk, []).append(p.get("trend_score", 50.0))

    rising_niches = []
    for nk, w in weights.items():
        avg_live = sum(niche_scores.get(nk, [60.0])) / max(1, len(niche_scores.get(nk, [60.0])))
        demand_index = round(min(99.0, avg_live * 0.7 + w * 22.0), 1)
        rising_niches.append({
            "niche": nk,
            "learned_weight": w,
            "live_avg_score": round(avg_live, 1),
            "predicted_demand_index": demand_index,
        })
    rising_niches.sort(key=lambda x: x["predicted_demand_index"], reverse=True)

    forecast = {
        "generated_at": now.isoformat(),
        "current_season_bn": cur_season,
        "current_hot_products": cur_products,
        "current_strategy_bn": cur_tip,
        "next_30_days_season_bn": nxt_season,
        "next_30_days_predicted_products": nxt_products,
        "next_30_days_strategy_bn": nxt_tip,
        "rising_niches": rising_niches,
        "recommended_content_upgrades_bn": [
            "মাল্টি-ক্লিপ ফাস্ট কাট (প্রতি ক্লিপ ৩–৪ সেকেন্ড) + প্রথম ২ সেকেন্ডে ভিজ্যুয়াল হুক",
            "মূল অডিও ১০০% বাদ দিয়ে বাংলা ভয়েসওভার + প্রোডাক্টের দাম বড় করে দেখানো",
            "পরবর্তী ভার্সন (v0.2.0) আপগ্রেড: অটো বাংলা AI ভয়েসওভার ও ব্যাকগ্রাউন্ড মিউজিক যুক্ত করা"
        ],
    }

    for out_p in [BASE_DIR / "output" / "future_forecast.json", BASE_DIR / "docs" / "data" / "future_forecast.json"]:
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(json.dumps(forecast, indent=2, ensure_ascii=False), encoding="utf-8")

    return forecast
