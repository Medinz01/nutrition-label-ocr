"""
extractor.py — Pass 2: full extraction on high-scoring images.
Uses PaddleOCR 3.x (predict API) for accurate structured text extraction.
"""

import io
import logging
import numpy as np
import httpx
from PIL import Image, ImageEnhance, ImageOps
import threading
from paddleocr import PaddleOCR

from parser import (
    parse_nutrition_rows,
    parse_serving_size,
    parse_ingredients,
    parse_fssai_number,
    assess_confidence,
)

logger = logging.getLogger(__name__)

# Initialize once — PaddleOCR 3.x uses predict(), no use_angle_cls param
_paddle = PaddleOCR(lang="en")
_paddle_lock = threading.Lock()  # PaddleOCR is not thread-safe


# ─── Download ─────────────────────────────────────────────────────────────────

def download_full(url: str) -> Image.Image | None:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://www.amazon.in/",
        "Accept": "image/*",
    }
    try:
        r = httpx.get(url, headers=headers, timeout=15, follow_redirects=True)
        r.raise_for_status()
        return Image.open(io.BytesIO(r.content)).convert("RGB")
    except Exception as e:
        logger.warning(f"[extractor] Download failed {url[-50:]}: {e}")
        return None


# ─── Preprocessing ────────────────────────────────────────────────────────────

def preprocess(img: Image.Image) -> Image.Image:
    """Preprocessing for nutrition label images. PaddleOCR expects RGB."""
    w, h = img.size
    if w < 1200:
        scale = 1200 / w
        img = img.resize((1200, int(h * scale)), Image.LANCZOS)

    gray = img.convert("L")
    gray = ImageOps.autocontrast(gray, cutoff=1)
    gray = ImageEnhance.Contrast(gray).enhance(2.0)
    return gray.convert("RGB")


# ─── OCR Engine ───────────────────────────────────────────────────────────────

def _parse_results(results) -> list:
    blocks = []
    for res in results:
        texts  = res.get("rec_texts", [])
        scores = res.get("rec_scores", [])
        polys  = res.get("dt_polys", [])
        for text, score, poly in zip(texts, scores, polys):
            if score < 0.3:
                continue
            xs = [float(pt[0]) for pt in poly]
            ys = [float(pt[1]) for pt in poly]
            blocks.append({
                "text":  text.strip(),
                "score": score,
                "x1": min(xs), "x2": max(xs),
                "y1": min(ys), "y2": max(ys),
                "cx": sum(xs) / 4,
                "cy": sum(ys) / 4,
            })
    return blocks


def run_ocr_structured(img: Image.Image) -> list:
    """
    Run PaddleOCR and return blocks with x/y coordinates.
    Auto-reinitializes on crash — PaddleOCR internal state can corrupt.
    """
    global _paddle

    img_array = np.array(img)

    with _paddle_lock:
        # First attempt
        try:
            results = _paddle.predict(img_array)
            return _parse_results(results)
        except Exception as e:
            logger.warning(f"[extractor] PaddleOCR crashed ({e}), reinitializing...")

        # Reinitialize and retry once
        try:
            _paddle = PaddleOCR(lang="en")
            results = _paddle.predict(img_array)
            logger.info("[extractor] PaddleOCR reinitialized successfully")
            return _parse_results(results)
        except Exception as e:
            logger.error(f"[extractor] PaddleOCR failed after reinit: {e}")
            return []


def _run_ocr_engine(img: Image.Image) -> str:
    """
    Run PaddleOCR 3.x predict() on image.
    Returns text reconstructed in reading order (top-to-bottom, left-to-right).
    """
    try:
        img_array = np.array(img)
        with _paddle_lock:
            results   = _paddle.predict(img_array)

        if not results:
            logger.warning("[extractor] PaddleOCR returned empty results")
            return ""

        lines = []
        for res in results:
            texts  = res.get("rec_texts", [])
            scores = res.get("rec_scores", [])
            polys  = res.get("dt_polys", [])

            for text, score, poly in zip(texts, scores, polys):
                if score < 0.3:
                    continue
                top_y  = min(float(pt[1]) for pt in poly)
                left_x = min(float(pt[0]) for pt in poly)
                lines.append((top_y, left_x, text))

        lines.sort(key=lambda x: (round(x[0] / 20) * 20, x[1]))
        reconstructed = "\n".join(t for _, _, t in lines)
        logger.info(f"[extractor] PaddleOCR extracted {len(lines)} text regions")
        return reconstructed

    except Exception as e:
        logger.error(f"[extractor] PaddleOCR failed: {e}")
        return ""


# ─── Full extraction ──────────────────────────────────────────────────────────

def extract_from_image(url: str) -> dict:
    result = {
        "url": url, "nutrition": {}, "serving_size": None,
        "ingredients": None, "fssai": None, "ocr_text_len": 0, "success": False,
    }
    img = download_full(url)
    if not img:
        return result

    processed        = preprocess(img)
    ocr_text         = _run_ocr_engine(processed)
    result["success"]      = bool(ocr_text.strip())
    result["ocr_text_len"] = len(ocr_text)
    result["nutrition"]    = parse_nutrition_rows(ocr_text)
    result["serving_size"] = parse_serving_size(ocr_text)
    result["ingredients"]  = parse_ingredients(ocr_text)
    result["fssai"]        = parse_fssai_number(ocr_text)
    return result


def merge_extractions(extractions: list[dict]) -> dict:
    extractions.sort(key=lambda x: len(x.get("nutrition", {})), reverse=True)
    merged_nutrition = {}
    serving_size = ingredients = fssai = None
    source_images = {}

    for ext in extractions:
        if not ext["success"]:
            continue
        for nutrient, value in ext["nutrition"].items():
            if nutrient not in merged_nutrition:
                merged_nutrition[nutrient] = value
                source_images[nutrient] = ext["url"]
        if "nutrition" not in source_images and ext["nutrition"]:
            source_images["nutrition"] = ext["url"]
        if serving_size is None and ext["serving_size"]:
            serving_size = ext["serving_size"]
        if ingredients is None and ext["ingredients"]:
            ingredients = ext["ingredients"]
            source_images["ingredients"] = ext["url"]
        if fssai is None and ext["fssai"]:
            fssai = ext["fssai"]
            source_images["fssai"] = ext["url"]

    return {
        "nutrition": merged_nutrition, "serving_size": serving_size,
        "ingredients": ingredients, "fssai": fssai,
        "confidence": assess_confidence(merged_nutrition, serving_size),
        "source_images": source_images,
    }