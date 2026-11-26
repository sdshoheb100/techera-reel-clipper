#!/usr/bin/env python3
import argparse
import json
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
WORK_DIR = BASE_DIR / "work"
OUT_DIR = BASE_DIR / "output"
WORK_DIR.mkdir(exist_ok=True)
OUT_DIR.mkdir(exist_ok=True)

def run_cmd(cmd, desc):
    print(f"\n==> {desc}")
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print("STDERR:", res.stderr[-1500:])
        raise RuntimeError(f"Failed step: {desc}")
    return res.stdout

def download_video(url: str) -> Path:
    out_tmpl = str(WORK_DIR / "source.%(ext)s")
    for old in WORK_DIR.glob("source.*"):
        old.unlink(missing_ok=True)
    cmd = [
        sys.executable, "-m", "yt_dlp",
        "--no-playlist",
        "-f", "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/b[ext=mp4]/b",
        "--merge-output-format", "mp4",
        "-o", out_tmpl,
        url,
    ]
    run_cmd(cmd, f"Downloading video from {url}")
    candidates = list(WORK_DIR.glob("source.*"))
    if not candidates:
        raise FileNotFoundError("yt-dlp did not produce a downloaded video file.")
    return candidates[0]

def get_duration(video_path: Path) -> float:
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(video_path),
    ]
    out = run_cmd(cmd, "Probing video duration").strip()
    try:
        return float(out)
    except ValueError:
        return 15.0

def build_reel(src_path: Path, out_path: Path, clip_seconds: int = 12, product_name: str = "TechEra BD Gadget", price_text: str = ""):
    duration = get_duration(src_path)
    start_sec = 1.5 if duration > (clip_seconds + 3) else 0.0
    actual_len = min(float(clip_seconds), max(3.0, duration - start_sec))

    def esc(s: str) -> str:
        return s.replace("\\", "\\\\").replace(":", "\\:").replace("'", "").replace("%", "\\%")

    brand_txt = esc("TechEra BD")
    prod_txt = esc(product_name[:38])
    price_txt = esc(price_text[:20]) if price_text else ""

    vf_parts = [
        "[0:v]split=2[bg][fg]",
        "[bg]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=20:5,eq=brightness=-0.12[bgb]",
        "[fg]scale=1080:1520:force_original_aspect_ratio=decrease[fgs]",
        "[bgb][fgs]overlay=(W-w)/2:(H-h)/2[base]",
        "[base]drawbox=x=0:y=0:w=1080:h=160:color=black@0.55:t=fill,"
        "drawbox=x=0:y=1680:w=1080:h=240:color=black@0.65:t=fill,"
        f"drawtext=text='{brand_txt}':fontcolor=white:fontsize=54:x=(w-text_w)/2:y=52,"
        f"drawtext=text='{prod_txt}':fontcolor=white:fontsize=42:x=(w-text_w)/2:y=1725"
        + (f",drawtext=text='{price_txt}':fontcolor=0x38bdf8:fontsize=52:x=(w-text_w)/2:y=1805" if price_txt else "")
        + "[vout]",
    ]
    filter_complex = ";".join(vf_parts)

    cmd = [
        "ffmpeg", "-y",
        "-ss", f"{start_sec:.2f}",
        "-t", f"{actual_len:.2f}",
        "-i", str(src_path),
        "-f", "lavfi", "-t", f"{actual_len:.2f}", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
        "-filter_complex", filter_complex,
        "-map", "[vout]",
        "-map", "1:a",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-shortest",
        str(out_path),
    ]
    run_cmd(cmd, f"Rendering 9:16 Reel ({actual_len:.1f}s) -> {out_path.name}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--product", default="TechEra BD Gadget")
    parser.add_argument("--price", default="")
    parser.add_argument("--seconds", type=int, default=12)
    args = parser.parse_args()

    src = download_video(args.url)
    out_file = OUT_DIR / "ready_reel.mp4"
    build_reel(src, out_file, clip_seconds=args.seconds, product_name=args.product, price_text=args.price)
    meta = {
        "source_url": args.url,
        "product": args.product,
        "price": args.price,
        "clip_seconds": args.seconds,
        "output_size_bytes": out_file.stat().st_size,
    }
    (OUT_DIR / "metadata.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"DONE! Saved {out_file} ({meta['output_size_bytes'] / (1024*1024):.2f} MB)")

if __name__ == "__main__":
    main()
