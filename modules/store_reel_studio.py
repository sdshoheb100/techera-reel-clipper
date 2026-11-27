"""
TechEra AI Engine — Zero-Fail StoreLine Product Reel Studio (v0.2.0)
Fetches live products directly from https://techerabd.storeline.io (NEVER blocked
by YouTube bot-checks!), picks fresh unused products every single run, and renders
a sleek animated 9:16 (1080x1920) vertical Reel with smooth Ken Burns zoom motion,
TechEra BD header, product name, price badge, and 100% copyright-safe audio.
"""

import html as html_mod
import io
import json
import random
import re
import subprocess
import urllib.parse
import urllib.request
from pathlib import Path
from modules.reel_studio import generate_royalty_free_bgm

BASE_DIR = Path(__file__).resolve().parent.parent
WORK_DIR = BASE_DIR / "work"
WORK_DIR.mkdir(exist_ok=True)

CATEGORY_SLUGS = {
    "all": ["winter-collection", "gadgets", "tws-earbuds", "fashion-item", "smart-watch", "cctv-camera"],
    "fashion_design": ["winter-collection", "fashion-item"],
    "tech_gadgets": ["gadgets", "smart-gadgets"],
    "mobile_audio": ["tws-earbuds", "smart-watch", "headphone-speaker"],
    "smart_home_tech": ["cctv-camera", "gadgets"],
}


def _http_get(url: str, timeout: int = 15) -> bytes:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        },
    )
    return urllib.request.urlopen(req, timeout=timeout).read()


def fetch_live_store_products(niche: str = "all", used_slugs: set | None = None, count: int = 3) -> list[dict]:
    """Scrapes fresh product slugs, titles, prices, and direct S3 HD images from techerabd.storeline.io."""
    used_slugs = used_slugs or set()
    cat_slugs = CATEGORY_SLUGS.get(niche, CATEGORY_SLUGS["all"])
    random.shuffle(cat_slugs)

    candidate_slugs = []
    seen = set()
    for cslug in cat_slugs:
        try:
            page_html = _http_get(f"https://techerabd.storeline.io/shop?category={cslug}").decode("utf-8", errors="ignore")
            slugs = re.findall(r'/product/([a-zA-Z0-9_-]+)', page_html)
            for s in slugs:
                if s not in seen and s not in used_slugs:
                    seen.add(s)
                    candidate_slugs.append((cslug, s))
        except Exception as e:
            print(f"WARN: Could not list category {cslug}: {e}")
        if len(candidate_slugs) >= count * 4:
            break

    # If all seen before, allow reuse cleanly
    if len(candidate_slugs) < count:
        for cslug in cat_slugs[:2]:
            try:
                page_html = _http_get(f"https://techerabd.storeline.io/shop?category={cslug}").decode("utf-8", errors="ignore")
                for s in re.findall(r'/product/([a-zA-Z0-9_-]+)', page_html):
                    if s not in seen:
                        seen.add(s)
                        candidate_slugs.append((cslug, s))
            except Exception:
                pass

    random.shuffle(candidate_slugs)
    products = []

    for cslug, pslug in candidate_slugs:
        if len(products) >= count:
            break
        try:
            purl = f"https://techerabd.storeline.io/product/{pslug}"
            phtml = _http_get(purl).decode("utf-8", errors="ignore")

            # Title
            tm = re.search(r"<title>(.*?)</title>", phtml, re.S)
            raw_title = html_mod.unescape(tm.group(1)).strip() if tm else pslug.replace("-", " ").title()
            title = raw_title.split("—")[0].split("|")[0].strip()
            # Keep clean ASCII/printable for FFmpeg drawtext stability
            clean_title = re.sub(r"[^\x20-\x7E]", "", title).strip() or pslug.replace("-", " ").title()

            # Direct S3 image URL from og:image (?src=...)
            im_m = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', phtml)
            img_url = ""
            if im_m:
                og = html_mod.unescape(im_m.group(1))
                qs = urllib.parse.parse_qs(urllib.parse.urlparse(og).query)
                if "src" in qs and qs["src"]:
                    img_url = qs["src"][0]
                else:
                    img_url = og

            # Price from JSON-LD or page text
            price_str = ""
            pm = re.search(r'"price"\s*:\s*"?(\d+(?:\.\d+)?)"?', phtml)
            if pm:
                price_str = f"Tk {int(float(pm.group(1))):,}"

            if img_url:
                products.append({
                    "slug": pslug,
                    "category": cslug,
                    "title": clean_title[:36],
                    "full_title": title,
                    "price": price_str,
                    "image_url": img_url,
                    "product_url": purl,
                })
        except Exception as e:
            print(f"WARN: Skipping product {pslug}: {e}")

    return products


def _get_fontfile_opt() -> str:
    for p in [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
    ]:
        if Path(p).exists():
            return f"fontfile='{p.replace(':', chr(92) + ':')}':"
    return ""


def _esc(s: str) -> str:
    return (
        str(s or "")
        .replace("\\", "\\\\")
        .replace(":", "\\:")
        .replace("'", "")
        .replace("%", "\\%")
    )


def _run(cmd, desc):
    print(f"\n==> {desc}")
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print("STDERR:", res.stderr[-1200:])
        raise RuntimeError(f"Failed: {desc}")
    return res.stdout


def render_store_product_reel(
    products: list[dict],
    out_path: Path,
    sec_per_product: float = 3.5,
    header_text: str = "TechEra BD",
    override_price: str = "",
) -> dict:
    """Renders a sleek animated 9:16 (1080x1920) Reel showcasing 1-4 live TechEra BD products."""
    if not products:
        raise RuntimeError("No StoreLine products available to render.")

    font_opt = _get_fontfile_opt()
    segments = []

    for idx, prod in enumerate(products, 1):
        # Download product image (supports AVIF/WEBP/JPEG/PNG via FFmpeg directly!)
        raw_img = WORK_DIR / f"prod_{idx}.img"
        img_bytes = _http_get(prod["image_url"], timeout=15)
        raw_img.write_bytes(img_bytes)

        # Convert to clean 1080x1080 PNG via FFmpeg (handles AVIF/WEBP reliably on both Linux & Windows)
        norm_png = WORK_DIR / f"prod_{idx}.png"
        _run(
            ["ffmpeg", "-y", "-i", str(raw_img), "-vf", "scale=1080:1080:force_original_aspect_ratio=decrease,pad=1080:1080:(ow-iw)/2:(oh-ih)/2:color=white", str(norm_png)],
            f"Normalizing product image #{idx}: {prod['title']}",
        )

        seg_out = WORK_DIR / f"store_seg_{idx}.mp4"
        frames = int(sec_per_product * 30)
        brand_txt = _esc(header_text)
        title_txt = _esc(prod["title"])
        price_val = override_price.strip() if override_price.strip() else prod.get("price", "")
        price_txt = _esc(price_val)
        cta_txt = _esc("Order Now: techerabd.storeline.io")

        # Animated dark-gradient canvas + subtle Ken Burns zoom on the product card + crisp typography
        vf = (
            "[0:v]split=2[bg][fg];"
            "[bg]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=28:8,eq=brightness=-0.35[bgb];"
            f"[fg]zoompan=z='min(zoom+0.0014,1.14)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s=940x940:fps=30[fgz];"
            "[bgb][fgz]overlay=(W-w)/2:390:shortest=1,"
            "drawbox=x=0:y=0:w=1080:h=210:color=0x0f172a@0.88:t=fill,"
            "drawbox=x=0:y=1430:w=1080:h=490:color=0x0f172a@0.92:t=fill,"
            f"drawtext={font_opt}text='{brand_txt}':fontcolor=0x38bdf8:fontsize=62:x=(w-text_w)/2:y=55,"
            f"drawtext={font_opt}text='TRENDING COLLECTION':fontcolor=white:fontsize=30:x=(w-text_w)/2:y=138,"
            f"drawtext={font_opt}text='{title_txt}':fontcolor=white:fontsize=46:x=(w-text_w)/2:y=1485,"
            + (f"drawtext={font_opt}text='{price_txt}':fontcolor=0x10b981:fontsize=68:x=(w-text_w)/2:y=1575," if price_txt else "")
            + f"drawtext={font_opt}text='{cta_txt}':fontcolor=0xfde68a:fontsize=34:x=(w-text_w)/2:y=1720,"
            "format=yuv420p[vout]"
        )

        _run(
            [
                "ffmpeg", "-y",
                "-loop", "1", "-t", f"{sec_per_product:.2f}", "-i", str(norm_png),
                "-filter_complex", vf,
                "-map", "[vout]",
                "-t", f"{sec_per_product:.2f}",
                "-c:v", "libx264", "-preset", "fast", "-crf", "22", "-r", "30", "-an",
                str(seg_out),
            ],
            f"Rendering animated product clip #{idx} ({sec_per_product:.1f}s)",
        )
        segments.append(seg_out)

    # Concat all product clips & attach 100% royalty-free background music (NO voiceover)
    concat_list = WORK_DIR / "store_concat.txt"
    concat_list.write_text("\n".join(f"file '{s.as_posix()}'" for s in segments), encoding="utf-8")
    total_dur = sec_per_product * len(segments)
    bgm_path = generate_royalty_free_bgm(total_dur, WORK_DIR / "store_bgm.m4a")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    _run(
        [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0", "-i", str(concat_list),
            "-i", str(bgm_path),
            "-map", "0:v", "-map", "1:a",
            "-map_metadata", "-1",
            "-c:v", "copy", "-c:a", "copy", "-shortest",
            str(out_path),
        ],
        f"Finalizing {len(segments)}-product StoreLine Reel with BGM -> {out_path.name}",
    )

    return {
        "products_featured": [p["title"] for p in products],
        "product_slugs": [p["slug"] for p in products],
        "clips_stitched": len(segments),
        "duration_seconds": round(total_dur, 1),
        "output_bytes": out_path.stat().st_size,
    }
