"""Build responsive image derivatives from originals.

Reads every image in `alexkaufmanlive/content/static/originals/` and
produces multiple resized/reformatted versions in
`alexkaufmanlive/content/static/images/`, plus a `manifest.json` that
the `photo()` Jinja macro uses to emit <picture>/<img> tags with the
correct dimensions and srcset entries.

Incremental: a derivative is regenerated only when the original is
newer than the existing derivative (or the derivative is missing).
Running this repeatedly after a no-op is fast.

Run manually in dev:
    python scripts/build_images.py

It also runs automatically on deploy via update-site.sh.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

# Enable AVIF support.
try:
    import pillow_avif  # noqa: F401
except ImportError:
    print(
        "WARNING: pillow-avif-plugin not installed. AVIF derivatives will be skipped.",
        file=sys.stderr,
    )

ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = ROOT / "alexkaufmanlive" / "content" / "static"
ORIGINALS_DIR = STATIC_DIR / "originals"
OUTPUT_DIR = STATIC_DIR / "images"
MANIFEST_PATH = OUTPUT_DIR / "manifest.json"

# Display sizes. The <img> fallback uses the largest, so its dimensions
# are what we store in the manifest for width/height attributes (CLS).
DISPLAY_WIDTHS = [400, 1200]
DISPLAY_FORMATS = ["avif", "webp", "jpeg"]

# Encoding quality per format. Tuned for good-enough visual quality at
# aggressive file sizes. Bump if you notice banding or smearing.
QUALITY = {"avif": 55, "webp": 78, "jpeg": 82}


@dataclass
class Derivative:
    """One generated file."""

    path: Path
    width: int
    height: int


def main() -> int:
    if not ORIGINALS_DIR.is_dir():
        print(f"error: {ORIGINALS_DIR} does not exist", file=sys.stderr)
        return 1

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    manifest: dict[str, dict] = {}
    built = 0
    skipped = 0

    for original in sorted(ORIGINALS_DIR.iterdir()):
        if not original.is_file():
            continue
        if original.suffix.lower() not in (".jpg", ".jpeg", ".png", ".webp"):
            continue

        try:
            entry, n_built, n_skipped = process_one(original)
        except Exception as e:
            print(f"failed to process {original.name}: {e}", file=sys.stderr)
            continue

        manifest[original.name] = entry
        built += n_built
        skipped += n_skipped

    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, sort_keys=True))
    print(f"built {built} derivatives, skipped {skipped} up-to-date")
    print(f"wrote manifest: {MANIFEST_PATH.relative_to(ROOT)}")
    return 0


def process_one(original: Path) -> tuple[dict, int, int]:
    """Generate all derivatives for one original. Returns (manifest_entry, built, skipped)."""
    stem = original.stem
    source_mtime = original.stat().st_mtime

    with Image.open(original) as im:
        # Orient according to EXIF, strip EXIF after, convert to RGB for formats
        # that don't do alpha the same way (jpeg). We keep RGBA for PNGs going
        # to webp/avif.
        im = _apply_exif_orientation(im)
        src_w, src_h = im.size

        # Compute what each width actually becomes (never upscale).
        size_dims: dict[int, tuple[int, int]] = {}
        for target_w in DISPLAY_WIDTHS:
            w = min(target_w, src_w)
            h = round(src_h * (w / src_w))
            size_dims[target_w] = (w, h)

        built = 0
        skipped = 0

        for target_w in DISPLAY_WIDTHS:
            w, h = size_dims[target_w]
            resized_cache: Image.Image | None = None

            for fmt in DISPLAY_FORMATS:
                ext = "jpg" if fmt == "jpeg" else fmt
                out_path = OUTPUT_DIR / f"{stem}-{target_w}.{ext}"

                if _is_up_to_date(out_path, source_mtime):
                    skipped += 1
                    continue

                if resized_cache is None:
                    resized_cache = im.resize((w, h), Image.LANCZOS)

                try:
                    _save(resized_cache, out_path, fmt)
                    built += 1
                except Exception as e:
                    print(
                        f"  skipping {out_path.name}: {e}",
                        file=sys.stderr,
                    )

    # Manifest uses the dimensions of the largest display derivative,
    # since that's what goes in <img src> as the fallback.
    largest = max(DISPLAY_WIDTHS)
    w, h = size_dims[largest]
    return {"stem": stem, "w": w, "h": h}, built, skipped


def _apply_exif_orientation(im: Image.Image) -> Image.Image:
    """Honor EXIF orientation so portrait photos aren't sideways."""
    try:
        from PIL import ImageOps

        return ImageOps.exif_transpose(im)
    except Exception:
        return im


def _is_up_to_date(out_path: Path, source_mtime: float) -> bool:
    return out_path.exists() and out_path.stat().st_mtime >= source_mtime


def _save(im: Image.Image, out_path: Path, fmt: str) -> None:
    # JPEG can't hold alpha; flatten onto white.
    if fmt == "jpeg" and im.mode in ("RGBA", "LA", "P"):
        bg = Image.new("RGB", im.size, (255, 255, 255))
        rgba = im.convert("RGBA")
        bg.paste(rgba, mask=rgba.split()[-1])
        im = bg
    elif fmt != "jpeg" and im.mode == "P":
        im = im.convert("RGBA")

    save_kwargs = {"quality": QUALITY[fmt]}
    if fmt == "jpeg":
        save_kwargs["progressive"] = True
        save_kwargs["optimize"] = True
    elif fmt == "webp":
        save_kwargs["method"] = 6  # slower, better compression
    elif fmt == "avif":
        save_kwargs["speed"] = 4  # 0 slowest/best, 10 fastest

    pil_format = {"jpeg": "JPEG", "webp": "WEBP", "avif": "AVIF"}[fmt]
    im.save(out_path, pil_format, **save_kwargs)


if __name__ == "__main__":
    sys.exit(main())
