"""
test_extraction.py — Test harness for iterative OCR tuning.

Usage:
    python test_extraction.py                     # all images in test_images/
    python test_extraction.py test_images/t4.jpg  # single image
"""

import json
import sys
import logging
from pathlib import Path
from PIL import Image

logging.basicConfig(level=logging.WARNING, format="%(levelname)s │ %(message)s")

TEST_DIR     = Path("test_images")
RESULTS_FILE = TEST_DIR / "results.json"
OCR_TEXT_DIR = TEST_DIR / "ocr_text"   # raw OCR text saved here per image

from extractor import preprocess, _run_ocr_engine
from parser import (
    parse_nutrition_rows,
    parse_serving_size,
    parse_ingredients,
    parse_fssai_number,
    assess_confidence,
    clean_ocr_text,
)

EXPECTED_NUTRIENTS = [
    ("energy_kcal",     "Energy",      "kcal"),
    ("protein_g",       "Protein",     "g"),
    ("carbohydrates_g", "Carbs",       "g"),
    ("sugar_g",         "Sugar",       "g"),
    ("total_fat_g",     "Total fat",   "g"),
    ("saturated_fat_g", "Sat fat",     "g"),
    ("trans_fat_g",     "Trans fat",   "g"),
    ("dietary_fiber_g", "Fiber",       "g"),
    ("sodium_mg",       "Sodium",      "mg"),
    ("cholesterol_mg",  "Cholesterol", "mg"),
]


def process_local_image(path: Path) -> dict:
    print(f"\n{'─'*70}")
    print(f"  {path.name}")
    print(f"{'─'*70}")

    try:
        img = Image.open(path).convert("RGB")
    except Exception as e:
        print(f"  ✗ Cannot open: {e}")
        return {"image": path.name, "error": str(e)}

    processed = preprocess(img)
    ocr_text  = _run_ocr_engine(processed)

    # ── Always save raw OCR text ──────────────────────────────────────────────
    OCR_TEXT_DIR.mkdir(exist_ok=True)
    ocr_file = OCR_TEXT_DIR / (path.stem + "_ocr.txt")
    ocr_file.write_text(ocr_text, encoding="utf-8")

    cleaned = clean_ocr_text(ocr_text)

    print(f"\n  ── RAW OCR TEXT (first 1500 chars) ──")
    print(ocr_text[:1500])
    print(f"\n  ── CLEANED TEXT (first 1500 chars) ──")
    print(cleaned[:1500])
    print(f"  [Full text saved → {ocr_file}]")
    print(f"  OCR chars: {len(ocr_text)}")

    # ── Parse ─────────────────────────────────────────────────────────────────
    nutrition    = parse_nutrition_rows(ocr_text)
    serving_size = parse_serving_size(ocr_text)
    ingredients  = parse_ingredients(ocr_text)
    fssai        = parse_fssai_number(ocr_text)
    confidence   = assess_confidence(nutrition, serving_size)

    # ── Report ────────────────────────────────────────────────────────────────
    print(f"\n  ── EXTRACTION RESULTS ──")
    print(f"  Confidence   : {confidence.upper()}")
    print(f"  Serving size : {serving_size}g" if serving_size else "  Serving size : ✗")
    print(f"  FSSAI        : {fssai}" if fssai else "  FSSAI        : ✗")
    print(f"  Ingredients  : {'✓ ' + (ingredients[:80] + '...') if ingredients else '✗'}")

    print(f"\n  ── NUTRITION ({len(nutrition)} found) ──")
    for key, label, unit in EXPECTED_NUTRIENTS:
        if key in nutrition:
            print(f"  ✓  {label:<14} {nutrition[key]:>8} {unit}")
        else:
            print(f"  ✗  {label}")

    return {
        "image":           path.name,
        "confidence":      confidence,
        "nutrients_found": len(nutrition),
        "serving_size":    serving_size,
        "fssai":           fssai,
        "has_ingredients": bool(ingredients),
        "nutrition":       nutrition,
        "ingredients":     ingredients,
        "ocr_text_len":    len(ocr_text),
        "ocr_text_file":   str(ocr_file),
    }


def print_summary(results: list[dict]):
    print(f"\n{'═'*70}")
    print(f"  SUMMARY — {len(results)} images")
    print(f"{'═'*70}")
    for r in results:
        if "error" in r:
            print(f"  ✗  {r['image']:<20} ERROR")
            continue
        icon = {"high": "🟢", "medium": "🟡", "low": "🔴"}.get(r.get("confidence"), "⚪")
        print(
            f"  {icon}  {r['image']:<20} "
            f"{r.get('nutrients_found',0):>2} nutrients  "
            f"serving={'✓' if r.get('serving_size') else '✗'}  "
            f"fssai={'✓' if r.get('fssai') else '✗'}  "
            f"ingr={'✓' if r.get('has_ingredients') else '✗'}"
        )

    print(f"\n  OCR text files saved in: {OCR_TEXT_DIR}/")
    print(f"  Inspect failing images: cat test_images/ocr_text/tX_ocr.txt")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]

    if args:
        image_paths = [Path(args[0])]
    else:
        if not TEST_DIR.exists():
            print("✗ test_images/ not found"); return
        image_paths = sorted([
            p for p in TEST_DIR.iterdir()
            if p.suffix.lower() in [".jpg", ".jpeg", ".png", ".webp"]
        ])
        if not image_paths:
            print("✗ No images in test_images/"); return

    print(f"\n{'═'*70}")
    print(f"  NutriLens OCR Test Harness — {len(image_paths)} image(s)")
    print(f"{'═'*70}")

    results = []
    for path in image_paths:
        results.append(process_local_image(path))

    print_summary(results)

    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\n  Results → {RESULTS_FILE}")


if __name__ == "__main__":
    main()