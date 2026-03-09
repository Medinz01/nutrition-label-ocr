<div align="center">

# nutrition-label-ocr

**Extract structured nutrition facts from Indian food supplement labels using PaddleOCR**

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688.svg)](https://fastapi.tiangolo.com)
[![Docker](https://img.shields.io/badge/Docker-ready-2496ED.svg)](Dockerfile)

A standalone microservice that takes a nutrition label image and returns structured per-100g nutrient data as JSON. Built for Indian supplement packaging — handles rotated labels, multi-column tables, and FSSAI-formatted layouts.

[**Quick Start**](#-quick-start) · [**API**](#-api) · [**Pipeline**](#-pipeline) · [**Accuracy**](#-accuracy)

</div>

---

## What it does

Input: a photo or screenshot of a nutrition facts panel (JPEG/PNG, base64)

Output:
```json
{
  "per_100g": {
    "energy_kcal": 393.9,
    "protein_g": 70.0,
    "carbohydrates_g": 21.2,
    "sugar_g": 0.0,
    "total_fat_g": 3.25,
    "saturated_fat_g": 0.52,
    "trans_fat_g": 0.2,
    "sodium_mg": 357.0,
    "cholesterol_mg": 84.8
  },
  "serving_size_g": 36,
  "confidence": "high",
  "source": "ocr_verified"
}
```

---

## 🚀 Quick Start

### With Docker (recommended)

```bash
git clone https://github.com/manideep/nutrition-label-ocr.git
cd nutrition-label-ocr
docker compose up
```

First run downloads PaddleOCR models (~200MB) into a named volume — cached on subsequent starts.

### Test it

```bash
# Health check
curl http://localhost:8001/health

# Extract from a local image
curl -X POST http://localhost:8001/extract/image \
  -H "Content-Type: application/json" \
  -d "{\"image_b64\": \"$(base64 -i test_images/example.jpg)\"}"
```

### Without Docker

```bash
pip install -r requirements.txt
# PaddleOCR has heavy deps — see requirements-heavy.txt
pip install -r requirements-heavy.txt
uvicorn main:app --port 8001
```

---

## 📡 API

### `POST /extract/image`

Extract nutrition from a base64-encoded image (snippet from a product page).

**Request:**
```json
{
  "image_b64": "<base64 encoded JPEG or PNG>",
  "hint": "per_100g"
}
```

**Response:**
```json
{
  "per_100g": { ... },
  "serving_size_g": 36,
  "raw_text": [...],
  "confidence": "high",
  "source": "ocr_verified"
}
```

### `POST /extract/url`

Download an image from a URL and extract nutrition. Used for FSSAI number extraction from product images.

**Request:**
```json
{
  "urls": ["https://example.com/label.jpg"]
}
```

### `GET /health`

```json
{ "status": "ok", "paddle_loaded": true }
```

---

## 🔬 Pipeline

Extraction runs in two passes to balance speed and accuracy:

```
Input image
     │
     ▼
┌─────────────────────────┐
│  Pass 1: Tesseract      │  Fast, lightweight
│  PSM11 (sparse text)    │  Scores keyword hits:
│                         │  "protein", "energy",
│                         │  "per 100g", "sodium"...
└──────────┬──────────────┘
           │
     score ≥ threshold?
           │
     No ───┴──► Reject (not a nutrition label)
           │
     Yes   ▼
┌─────────────────────────┐
│  Pass 2: PaddleOCR 3.x  │  Full spatial extraction
│  DB-Net + CRNN          │  Returns bounding boxes
│                         │  for every text block
└──────────┬──────────────┘
           │
           ▼
┌─────────────────────────┐
│  Coordinate Parser      │  Groups text spatially
│                         │  Left column = nutrient name
│  x_cap = 0.85×width     │  Right column = value
│  (excludes amino acid   │
│   tables on far right)  │
└──────────┬──────────────┘
           │
           ▼
┌─────────────────────────┐
│  Semantic Normaliser    │  Fuzzy-matches OCR noise:
│                         │  "orotein" → protein_g
│  NUTRIENT_ALIASES dict  │  "cotal sugars" → sugar_g
│                         │  Handles I/1, O/0 swaps
└──────────┬──────────────┘
           │
           ▼
     Per-100g JSON
```

### Why coordinate-based parsing?

Nutrition tables on Indian supplement packaging vary significantly:
- Single column (per 100g only)
- Two columns (per serving + per 100g)
- Three columns (per serving + per 100g + %RDA)
- Rotated or photographed at an angle
- Amino acid profile sub-tables (must be excluded)

Line-by-line OCR fails on multi-column layouts. By grouping detected text blocks by their `x` coordinate, the parser reliably separates nutrient names from values regardless of table width.

### Per-100g as canonical unit

All output is normalised to per-100g — the FSSAI standard and the only fair basis for cross-product comparison when serving sizes differ. If the label only shows per-serving values, the parser detects the serving size and converts.

---

## 📊 Accuracy

Tested on 47 Indian protein supplement labels from Amazon.in, Flipkart, and BigBasket.

| Metric | Result |
|---|---|
| Protein extraction accuracy | 94% |
| All nutrients correct (no errors) | 78% |
| False positives (non-label images accepted) | 2% |
| Per-100g vs per-serving correctly identified | 91% |

Common failure modes:
- Heavily curved labels (plastic tub side panels)
- Very low resolution images (< 300px wide)
- Handwritten or stylised fonts on artisan products

---

## 🗂 Project Structure

```
nutrition-label-ocr/
├── main.py              # FastAPI app — /extract/image, /extract/url, /health
├── extractor.py         # Two-pass pipeline orchestrator
├── scanner.py           # Pass 1: Tesseract PSM11 keyword scoring
├── semantic_parser.py   # Pass 2: PaddleOCR coordinate-based extraction
├── parser.py            # Nutrient name normalisation + alias matching
├── models.py            # Pydantic request/response models
├── requirements.txt     # Light deps (FastAPI, Pillow, Tesseract)
├── requirements-heavy.txt  # PaddleOCR + paddlepaddle (large)
├── Dockerfile
├── docker-compose.yml
└── test_images/         # Add your own .jpg label images here
```

---

## ⚙️ Configuration

| Env variable | Default | Description |
|---|---|---|
| `OCR_SCORE_THRESHOLD` | `3` | Min Tesseract keyword hits to proceed to PaddleOCR |
| `OCR_X_CAP_RATIO` | `0.85` | Fraction of image width beyond which columns are ignored (excludes amino acid tables) |
| `LOG_LEVEL` | `INFO` | Logging verbosity |

---

## 🤝 Contributing

Issues and PRs welcome. Most useful contributions:

- Additional entries in `NUTRIENT_ALIASES` for OCR noise patterns you encounter
- Test images (anonymised label crops) to expand the benchmark set
- Support for non-English labels (Tamil, Hindi nutrient names)

See [CONTRIBUTING.md](CONTRIBUTING.md) for setup and style guide.

---

## Used by

- [NutriLens](https://github.com/manideep/NutriLens) — Chrome extension for nutrition accountability on Indian e-commerce

---

## License

MIT — see [LICENSE](LICENSE).
