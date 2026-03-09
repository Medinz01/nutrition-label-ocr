"""
main.py — OCR Service API

Endpoints:
    POST /extract/url     — extract FSSAI from image URLs (auto pipeline)
    POST /extract/image   — extract nutrition from base64 image (snippet)
    GET  /health          — liveness check
"""

import base64
import io
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image
from pydantic import BaseModel

from extractor import preprocess, run_ocr_structured, download_full
from layout_engine import build_layout, find_ingredients_region, reconstruct_paragraph
from semantic_parser import (
    parse_nutrition_table,
    parse_serving_size,
    parse_fssai_from_blocks,
    assess_confidence,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s │ %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("[startup] Warming up PaddleOCR...")
    from extractor import _paddle  # noqa — triggers model load
    logger.info("[startup] Ready")
    yield


app = FastAPI(title="NutriLens OCR Service", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Schemas ─────────────────────────────────────────────────────────────────

class UrlRequest(BaseModel):
    urls: list[str]

class ImageRequest(BaseModel):
    image: str
    mime_type: str = "image/jpeg"

class NutritionResult(BaseModel):
    nutrition:    dict
    serving_size: float | None
    ingredients:  str | None
    fssai:        str | None
    confidence:   str
    source:       str


# ─── Core extraction ─────────────────────────────────────────────────────────

def extract_from_pil(img: Image.Image, source: str) -> NutritionResult:
    img    = preprocess(img)
    blocks = run_ocr_structured(img)

    if not blocks:
        raise HTTPException(status_code=422, detail="No text detected in image")

    layout      = build_layout(blocks)
    nutrition   = parse_nutrition_table(blocks)
    serving     = parse_serving_size(blocks)
    fssai       = parse_fssai_from_blocks(blocks)
    ingr_region = find_ingredients_region(layout)
    ingredients = reconstruct_paragraph(ingr_region)
    confidence  = assess_confidence(nutrition, serving)

    return NutritionResult(
        nutrition=nutrition,
        serving_size=serving,
        ingredients=ingredients,
        fssai=fssai,
        confidence=confidence,
        source=source,
    )


# ─── Endpoints ───────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/extract/url", response_model=NutritionResult)
def extract_url(req: UrlRequest):
    """Scan gallery image URLs — used for FSSAI fallback when seller page has none."""
    best = None
    for url in req.urls:
        img = download_full(url)
        if not img:
            continue
        try:
            result = extract_from_pil(img, source="url")
        except HTTPException:
            continue
        if best is None or len(result.nutrition) > len(best.nutrition):
            best = result

    if best is None:
        raise HTTPException(status_code=422, detail="Could not extract from any URL")
    return best


@app.post("/extract/image", response_model=NutritionResult)
def extract_image(req: ImageRequest):
    """Accept base64 image from extension snippet capture."""
    try:
        image_bytes = base64.b64decode(req.image)
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid image: {e}")

    return extract_from_pil(img, source="snippet")