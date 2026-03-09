# Contributing to nutrition-label-ocr

## Setup

```bash
git clone https://github.com/manideep/nutrition-label-ocr.git
cd nutrition-label-ocr
docker compose up
```

First run downloads PaddleOCR models (~200MB). Subsequent starts are instant.

## Testing a change

Add your label image to `test_images/`, then:

```bash
docker compose exec ocr python test_extraction.py test_images/your_image.jpg
```

This prints detected bounding boxes, the intermediate column grouping, and final per-100g output — useful for debugging parser changes.

## What needs work

- **`NUTRIENT_ALIASES` in `semantic_parser.py`** — add any OCR noise patterns you encounter (common: `"orotein"`, `"cotal sugars"`, Roman numeral confusion)
- **`PER_100G_RANGES` bounds** — if a product has a legitimately high/low value that gets rejected, widen the range
- **Multi-language support** — Hindi/Tamil nutrient names on regional products
- **Test image set** — anonymised label crops (no brand name visible) to expand coverage

## Commit style

```
fix(parser): handle "Ener gy" split across two bounding boxes
feat(aliases): add Tamil nutrient name variants
test: add label image for three-column FSSAI table
```

## Code style

- PEP 8, type hints on all functions
- No `print()` — use `logging.getLogger(__name__)`
