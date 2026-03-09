"""
scanner.py — Pass 1: fast keyword scan on all images.

Uses Tesseract PSM 11 (sparse text) at reduced resolution.
Goal: score each image by content type, not extract values.
Fast: ~0.3-0.8s per image vs 3-5s for full extraction.
"""

import re
import io
import logging
import httpx
from PIL import Image
import pytesseract

from models import ImageScore

logger = logging.getLogger(__name__)

# ─── Tesseract config ────────────────────────────────────────────────────────
# PSM 11: sparse text — finds text anywhere without assuming layout
# Much faster than PSM 6 for keyword detection
TESS_FAST = "--psm 11 --oem 3 -c tessedit_do_invert=0"

# ─── Keyword sets ─────────────────────────────────────────────────────────────

NUTRITION_KEYWORDS = [
    "protein", "energy", "calorie", "carbohydrate", "carbs",
    "fat", "sodium", "sugar", "fibre", "fiber", "calcium",
    "iron", "serving", "per 100", "nutrition", "nutritional",
    "supplement facts", "typical values", "kcal", "kj",
    "trans fat", "saturated", "cholesterol",
]

INGREDIENT_KEYWORDS = [
    "ingredients", "ingredient", "contains", "allergen",
    "allergy", "made from", "whey", "casein", "soy",
    "artificial", "preservative", "emulsifier", "ins ",
    "e numbers", "flavour", "flavor",
]

FSSAI_KEYWORDS = [
    "fssai", "fpo", "agmark", "lic", "licence", "license",
    "food safety", "food business",
]

SKIP_KEYWORDS = [
    "scan to", "qr code", "barcode",
]

# Loose FSSAI pattern for scanning (14 digits)
FSSAI_SCAN_PATTERN = re.compile(r'\b\d{14}\b')


# ─── Image download (reduced res for Pass 1) ─────────────────────────────────

def download_thumbnail(url: str, max_width: int = 500) -> Image.Image | None:
    """
    Download image at reduced resolution for fast scanning.
    Converts high-res Amazon URLs to smaller versions where possible.
    """
    # Downgrade Amazon URL to smaller version for Pass 1
    thumb_url = (url
        .replace("_SL1500_", "_SL500_")
        .replace("_SL1200_", "_SL500_")
        .replace("_AC_SL1500_", "_AC_SL500_")
    )

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://www.amazon.in/",
        "Accept": "image/*",
    }

    for attempt_url in [thumb_url, url]:  # fall back to full-res if thumb fails
        try:
            r = httpx.get(attempt_url, headers=headers, timeout=8, follow_redirects=True)
            if r.status_code == 200:
                img = Image.open(io.BytesIO(r.content)).convert("RGB")
                # Resize to max_width for fast processing
                w, h = img.size
                if w > max_width:
                    ratio = max_width / w
                    img = img.resize((max_width, int(h * ratio)), Image.LANCZOS)
                return img
        except Exception as e:
            logger.debug(f"[scanner] Download attempt failed: {e}")
            continue

    logger.warning(f"[scanner] Failed to download: {url[-60:]}")
    return None


# ─── Keyword scoring ──────────────────────────────────────────────────────────

def score_text(text: str) -> tuple[int, int, int]:
    """
    Returns (nutrition_score, ingredient_score, fssai_score).
    Counts keyword hits in OCR text.
    """
    text_lower = text.lower()

    nutrition_score  = sum(1 for kw in NUTRITION_KEYWORDS  if kw in text_lower)
    ingredient_score = sum(1 for kw in INGREDIENT_KEYWORDS if kw in text_lower)
    fssai_score      = sum(1 for kw in FSSAI_KEYWORDS      if kw in text_lower)

    # FSSAI number pattern detection
    if FSSAI_SCAN_PATTERN.search(text):
        fssai_score += 3  # Strong signal

    # Penalize if it looks like a skip image
    if any(kw in text_lower for kw in SKIP_KEYWORDS):
        nutrition_score  = max(0, nutrition_score - 2)
        ingredient_score = max(0, ingredient_score - 2)

    return nutrition_score, ingredient_score, fssai_score


def should_run_full_extract(n_score: int, i_score: int, f_score: int) -> bool:
    """Decide if Pass 2 should run on this image."""
    return n_score >= 2 or i_score >= 2 or f_score >= 3


# ─── Main scanner ─────────────────────────────────────────────────────────────

def scan_image(url: str) -> ImageScore:
    """
    Pass 1: download thumbnail, run fast OCR, score by keywords.
    Returns ImageScore with decision on whether to run full extraction.
    """
    img = download_thumbnail(url)

    if not img:
        return ImageScore(
            url=url,
            nutrition_score=0,
            ingredient_score=0,
            fssai_score=0,
            total_score=0,
            run_full_extract=False,
        )

    try:
        # Convert to grayscale — faster OCR
        gray = img.convert("L")
        text = pytesseract.image_to_string(gray, config=TESS_FAST)
    except Exception as e:
        logger.warning(f"[scanner] Tesseract failed on {url[-40:]}: {e}")
        text = ""

    n_score, i_score, f_score = score_text(text)
    total = n_score + i_score + f_score

    score = ImageScore(
        url=url,
        nutrition_score=n_score,
        ingredient_score=i_score,
        fssai_score=f_score,
        total_score=total,
        run_full_extract=should_run_full_extract(n_score, i_score, f_score),
    )

    logger.info(
        f"[scanner] {url[-50:]} → "
        f"nutrition={n_score} ingredients={i_score} fssai={f_score} "
        f"→ extract={score.run_full_extract}"
    )

    return score


def scan_all_images(urls: list[str], max_workers: int = 4) -> list[ImageScore]:
    """
    Run Pass 1 on all image URLs in parallel.
    Returns sorted list with highest-scoring images first.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    scores = []
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(scan_image, url): url for url in urls}
        for future in as_completed(futures):
            try:
                scores.append(future.result())
            except Exception as e:
                logger.error(f"[scanner] Unexpected error: {e}")

    # Sort by total score descending
    scores.sort(key=lambda s: s.total_score, reverse=True)
    return scores