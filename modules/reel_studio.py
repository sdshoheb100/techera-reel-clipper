"""
TechEra AI Engine — Multi-Clip Copyright-Safe Reel Studio (v0.1.0)
Downloads 1 to N researched videos, cuts crisp 3-5s highlight segments from each,
stitches them into a dynamic 9:16 (1080x1920) vertical Reel with:
- 100% muted original audio (eliminating music copyright claims)
- Subtle speed/color grading polish + blurred vertical fill
- TechEra BD top header + product title & price badge
"""

import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
WORK_DIR = BASE_DIR / "work"
OUT_DIR = BASE_DIR / "output"
WORK_DIR.mkdir(exist_ok=True)
OUT_DIR.mkdir(exist_ok=True)


def _run(cmd, desc):
    print(f"\n==> {desc}")
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print("STDERR:", res.stderr[-1200:])
        raise RuntimeError(f"Failed: {desc}")
    return res.stdout


def _probe_duration(path: Path) -> float:
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(path),
    ]
    try:
        return float(_run(cmd, f"Probe duration {path.name}").strip())
    except Exception:
        return 10.0


def download_source(url: str, idx: int) -> Path | None:
    for old in WORK_DIR.glob(f"src_{idx}.*"):
        old.unlink(missing_ok=True)
    out_tmpl = str(WORK_DIR / f"src_{idx}.%(ext)s")
    cmd = [
        sys.executable, "-m", "yt_dlp",
        "--no-playlist",
        "-f", "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/b[ext=mp4]/b",
        "--merge-output-format", "mp4",
        "-o", out_tmpl,
        url,
    ]
    try:
        _run(cmd, f"Downloading source #{idx}: {url}")
        found = list(WORK_DIR.glob(f"src_{idx}.*"))
        return found[0] if found else None
    except Exception as e:
        print(f"WARN: Skipping source #{idx} ({url}): {e}")
        return None


def _get_fontfile_opt() -> str:
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
    ]
    for p in candidates:
        if Path(p).exists():
            # Escape drive colon for FFmpeg drawtext filter syntax
            escaped = p.replace(":", "\\:")
            return f"fontfile='{escaped}':"
    return ""


def _esc(text: str) -> str:
    return (
        str(text or "")
        .replace("\\", "\\\\")
        .replace(":", "\\:")
        .replace("'", "")
        .replace("%", "\\%")
    )


def render_multiclip_reel(
    source_urls: list[str],
    out_path: Path,
    product_name: str = "TechEra BD Trending Gadget",
    price_text: str = "",
    clip_len_each: float = 4.0,
    max_clips: int = 3,
) -> dict:
    """Downloads up to max_clips videos, extracts best segment from each, stitches & brands."""
    segments = []
    downloaded_count = 0

    for idx, url in enumerate(source_urls[:max_clips], 1):
        src = download_source(url, idx)
        if not src:
            continue
        downloaded_count += 1
        dur = _probe_duration(src)
        # Skip intro if long enough to jump straight into product action
        start = min(2.0, max(0.0, dur * 0.15)) if dur > (clip_len_each + 2.5) else 0.0
        seg_len = min(clip_len_each, max(2.0, dur - start))
        seg_out = WORK_DIR / f"seg_{idx}.mp4"

        # Normalize each segment to 1080x1920 30fps, blurred backdrop + HD unsharp enhancer + color polish, NO audio
        vf = (
            "[0:v]split=2[bg][fg];"
            "[bg]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=20:5,eq=brightness=-0.12[bgb];"
            "[fg]scale=1080:1500:force_original_aspect_ratio=decrease,unsharp=5:5:0.75:5:5:0.0,eq=contrast=1.05:saturation=1.10[fgs];"
            "[bgb][fgs]overlay=(W-w)/2:(H-h)/2,fps=30,format=yuv420p[vout]"
        )
        cmd = [
            "ffmpeg", "-y",
            "-ss", f"{start:.2f}",
            "-t", f"{seg_len:.2f}",
            "-i", str(src),
            "-filter_complex", vf,
            "-map", "[vout]",
            "-an",
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "23",
            str(seg_out),
        ]
        _run(cmd, f"Normalizing highlight segment #{idx} ({seg_len:.1f}s)")
        segments.append(seg_out)

    if not segments:
        raise RuntimeError("No source videos could be downloaded to render the Reel.")

    # Concat segments if >1
    if len(segments) == 1:
        merged_video = segments[0]
    else:
        concat_list = WORK_DIR / "concat.txt"
        concat_list.write_text("\n".join(f"file '{s.as_posix()}'" for s in segments), encoding="utf-8")
        merged_video = WORK_DIR / "merged_raw.mp4"
        _run(
            ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list), "-c", "copy", str(merged_video)],
            f"Stitching {len(segments)} highlight clips together",
        )

    total_dur = _probe_duration(merged_video)

    # Apply TechEra BD top/bottom branded bars + product & price overlay + copyright-safe silent track
    font_opt = _get_fontfile_opt()
    brand_txt = _esc("TechEra BD")
    prod_txt = _esc(product_name[:38])
    price_txt = _esc(price_text[:22]) if price_text else ""

    overlay_vf = (
        "drawbox=x=0:y=0:w=1080:h=160:color=black@0.58:t=fill,"
        "drawbox=x=0:y=1670:w=1080:h=250:color=black@0.68:t=fill,"
        f"drawtext={font_opt}text='{brand_txt}':fontcolor=white:fontsize=54:x=(w-text_w)/2:y=52,"
        f"drawtext={font_opt}text='{prod_txt}':fontcolor=white:fontsize=42:x=(w-text_w)/2:y=1715"
        + (f",drawtext={font_opt}text='{price_txt}':fontcolor=0x38bdf8:fontsize=52:x=(w-text_w)/2:y=1795" if price_txt else "")
    )

    final_cmd = [
        "ffmpeg", "-y",
        "-i", str(merged_video),
        "-f", "lavfi", "-t", f"{total_dur:.2f}", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
        "-vf", overlay_vf,
        "-map", "0:v",
        "-map", "1:a",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-shortest",
        str(out_path),
    ]
    _run(final_cmd, f"Finalizing branded multi-clip Reel -> {out_path.name}")

    return {
        "clips_stitched": len(segments),
        "downloaded_sources": downloaded_count,
        "duration_seconds": round(total_dur, 1),
        "output_bytes": out_path.stat().st_size,
    }
