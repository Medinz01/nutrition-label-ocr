"""
models.py — Shared schemas for the OCR service.
Product-agnostic: works for any packaged food product.
"""

from pydantic import BaseModel
from typing import Optional


class NutritionFacts(BaseModel):
    """All values normalized to per-100g."""
    energy_kcal:      Optional[float] = None
    protein_g:        Optional[float] = None
    carbohydrates_g:  Optional[float] = None
    sugar_g:          Optional[float] = None
    added_sugar_g:    Optional[float] = None
    total_fat_g:      Optional[float] = None
    saturated_fat_g:  Optional[float] = None
    trans_fat_g:      Optional[float] = None
    dietary_fiber_g:  Optional[float] = None
    sodium_mg:        Optional[float] = None
    cholesterol_mg:   Optional[float] = None
    calcium_mg:       Optional[float] = None
    iron_mg:          Optional[float] = None
    potassium_mg:     Optional[float] = None


class ImageScore(BaseModel):
    """Pass 1 result for a single image."""
    url:                str
    nutrition_score:    int   # keyword hit count
    ingredient_score:   int
    fssai_score:        int
    total_score:        int
    run_full_extract:   bool  # whether Pass 2 should run on this image


class OCRResult(BaseModel):
    """Final structured result returned by the OCR service."""
    # Core data
    nutrition:          Optional[NutritionFacts] = None
    serving_size_g:     Optional[float] = None
    ingredients:        Optional[str]   = None
    fssai_number:       Optional[str]   = None

    # Quality signals
    confidence:         str = "low"   # high | medium | low
    nutrients_found:    int = 0
    extraction_method:  str = "none"  # tesseract | paddleocr | none

    # Audit trail — which image each piece came from
    source_images: dict = {}   # e.g. {"nutrition": "url", "fssai": "url"}

    # Debug info (stripped in production responses)
    image_scores:  list[ImageScore] = []
    warnings:      list[str]        = []