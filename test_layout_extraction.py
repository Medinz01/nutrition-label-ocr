"""
test_layout_extraction.py — Test harness for layout-first OCR pipeline

Usage:
    python test_layout_extraction.py
    python test_layout_extraction.py test_images/t1.jpg
"""

import sys
import json
from pathlib import Path
from PIL import Image

from extractor import preprocess, run_ocr_structured
from layout_engine import (
    build_layout,
    find_nutrition_region,
    reconstruct_table,
    find_ingredients_region,
    reconstruct_paragraph,
)
from semantic_parser import (
    parse_nutrition_table,
    parse_serving_size,
    parse_fssai_from_blocks,
    assess_confidence,
)

TEST_DIR = Path("test_images")
RESULTS_FILE = TEST_DIR / "layout_results.json"


def process_image(path: Path):

    print("\n" + "─" * 70)
    print(f"  {path.name}")
    print("─" * 70)

    img = Image.open(path).convert("RGB")
    img = preprocess(img)

    blocks = run_ocr_structured(img)

    print(f"OCR blocks detected: {len(blocks)}")

    layout = build_layout(blocks)

    print(f"Rows detected: {len(layout)}")

    # ─── Nutrition ─────────────────────────────────────────

    # nutrition_region = find_nutrition_region(layout)
    # table = reconstruct_table(nutrition_region)

    # print("\nDetected Nutrition Table:")
    # for row in table:
    #     print(" | ".join(row))

    nutrition = parse_nutrition_table(blocks)
    serving_size = parse_serving_size(blocks)

    # ─── Ingredients ───────────────────────────────────────

    ingredients_region = find_ingredients_region(layout)
    ingredients = reconstruct_paragraph(ingredients_region)

    # ─── FSSAI ─────────────────────────────────────────────

    fssai = parse_fssai_from_blocks(blocks)

    confidence = assess_confidence(nutrition, serving_size)

    print("\nExtraction Results:")
    print("Confidence:", confidence)
    print("Serving size:", serving_size)
    print("FSSAI:", fssai)
    print("Ingredients:", ingredients[:120] + "..." if ingredients else None)

    print("\nNutrition:")
    for k, v in nutrition.items():
        print(f"  {k} = {v}")

    return {
        "image": path.name,
        "nutrition": nutrition,
        "serving_size": serving_size,
        "ingredients": ingredients,
        "fssai": fssai,
        "confidence": confidence,
    }


def main():
    args = sys.argv[1:]

    if args:
        images = [Path(args[0])]
    else:
        images = sorted(TEST_DIR.glob("*.*"))

    results = []

    for img_path in images:
        if img_path.suffix.lower() not in [".jpg", ".jpeg", ".png", ".webp"]:
            continue
        results.append(process_image(img_path))

    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print("\nResults saved to:", RESULTS_FILE)


if __name__ == "__main__":
    main()