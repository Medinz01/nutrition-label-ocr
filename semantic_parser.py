import re

NUTRIENT_ALIASES = {
    "energy_kcal":      ["energy"],
    "protein_g":        ["protein", "orotein", "total protein"],
    "carbohydrates_g":  ["carbohydrate"],
    "sugar_g":          ["total sugars", "cotal sugars", "- total sugars", "sugars (g)"],
    "added_sugar_g":    ["added sugars", "- added sugars"],
    "dietary_fiber_g":  ["dietary fibre", "dietary fiber", "- dietary fibre", "- dietary fiber"],
    "total_fat_g":      ["total fat", "otal fat"],
    "saturated_fat_g":  ["saturated fat", "saturated fatty", "- saturated"],
    "trans_fat_g":      ["trans fat", "trans fats", "- trans"],
    "sodium_mg":        ["sodium"],
    "cholesterol_mg":   ["cholesterol"],
}

# ─── Codex CAC/GL 2-1985 s3.2.1 mandatory nutrients ─────────────────────────
# These 7 must appear on every prepackaged food label.
# Source: GUIDELINES ON NUTRITION LABELLING CAC/GL 2-1985
MANDATORY_NUTRIENTS = [
    "energy_kcal",
    "protein_g",
    "carbohydrates_g",
    "total_fat_g",
    "saturated_fat_g",
    "sodium_mg",
    "sugar_g",
]

def match_nutrient(text):
    t = text.lower()
    for canon, aliases in NUTRIENT_ALIASES.items():
        for a in aliases:
            if a in t:
                return canon
    return None


def extract_number(text):
    cleaned = text.replace("I", "1").replace("O", "0").replace(",", ".")
    m = re.search(r"<?\s*(\d+\.?\d*)", cleaned)
    return float(m.group(1)) if m else None


# ─── Per-100g expected ranges ─────────────────────────────────────────────────

PER_100G_RANGES = {
    "energy_kcal":     (50,    900),
    "protein_g":       (1,     100),
    "carbohydrates_g": (0,     100),
    "sugar_g":         (0,     100),
    "added_sugar_g":   (0,     100),
    "total_fat_g":     (0,     100),
    "saturated_fat_g": (0,     50),
    "trans_fat_g":     (0,     10),
    "dietary_fiber_g": (0,     50),
    "sodium_mg":       (0,    3000),
    "cholesterol_mg":  (0,    500),
}

PER_SERVING_RANGES = {
    "energy_kcal":     (20,   600),
    "protein_g":       (1,    60),
    "carbohydrates_g": (0,    60),
    "sugar_g":         (0,    40),
    "added_sugar_g":   (0,    30),
    "total_fat_g":     (0,    30),
    "saturated_fat_g": (0,    15),
    "trans_fat_g":     (0,     5),
    "dietary_fiber_g": (0,    15),
    "sodium_mg":       (0,   800),
    "cholesterol_mg":  (0,   200),
}

def in_per_100g_range(nutrient, value):
    lo, hi = PER_100G_RANGES.get(nutrient, (0, 1e9))
    return lo <= value <= hi

def in_per_serving_range(nutrient, value):
    lo, hi = PER_SERVING_RANGES.get(nutrient, (0, 1e9))
    return lo <= value <= hi


def parse_nutrition_table(blocks):
    """
    Extract per-100g values from nutrition label blocks.
    Labels typically have: | nutrient | per 100g | per serving | %RDA |
    We want the per-100g column — the larger of the two numeric columns.
    """
    if not blocks:
        return {}

    result = {}

    max_x    = max(b["x2"] for b in blocks)
    x_cap    = max_x * 0.85
    y_thresh = max_x * 0.025

    for b in blocks:
        nutrient = match_nutrient(b["text"])
        if not nutrient:
            continue

        candidates = []
        for other in blocks:
            dx = other["cx"] - b["cx"]
            if dx > 0 and abs(other["cy"] - b["cy"]) < y_thresh and dx < x_cap:
                v = extract_number(other["text"])
                if v is not None:
                    candidates.append((other["cx"], v))

        candidates.sort(key=lambda c: c[0])
        values = [v for _, v in candidates[:3]]

        if not values:
            continue

        if len(values) >= 2:
            per_100g_candidates = [v for v in values if in_per_100g_range(nutrient, v)]
            if per_100g_candidates:
                result[nutrient] = max(per_100g_candidates)
            else:
                result[nutrient] = max(values)
        else:
            v = values[0]
            if in_per_100g_range(nutrient, v):
                result[nutrient] = v

    return result


def parse_serving_size(blocks):
    for b in blocks:
        text = b["text"].lower()
        if any(k in text for k in ["serving size", "scoop", "per 35", "per 30",
                                    "per 36", "per 45", "serving ="]):
            cleaned = re.sub(r'\bI\b', '1', b["text"])
            m = re.search(r'(\d+\.?\d*)\s*g', cleaned)
            if m:
                val = float(m.group(1))
                if 5 <= val <= 500:
                    return val
    return None


def parse_fssai_from_blocks(blocks):
    for b in blocks:
        text = b["text"].replace("I", "1").replace("O", "0")
        m = re.search(r"\b\d{14}\b", text)
        if m:
            num = m.group(0)
            if 10 <= int(num[:2]) <= 35:
                return num
    return None


def validate_mandatory_nutrients(nutrition: dict) -> dict:
    """
    Check extracted nutrition against Codex CAC/GL 2-1985 s3.2.1 mandatory list.

    Returns:
        {
            "complete":          bool   — True if all 7 mandatory nutrients present
            "missing_mandatory": list   — keys missing from extraction
            "present_mandatory": list   — keys successfully extracted
        }

    A label that is incomplete does not necessarily mean the product is non-compliant —
    OCR may have missed a field. The caller should lower confidence accordingly.
    """
    present = [n for n in MANDATORY_NUTRIENTS if nutrition.get(n) is not None]
    missing = [n for n in MANDATORY_NUTRIENTS if nutrition.get(n) is None]
    return {
        "complete":          len(missing) == 0,
        "missing_mandatory": missing,
        "present_mandatory": present,
    }


def assess_confidence(nutrition: dict, serving_size) -> str:
    """
    Assess extraction confidence based on nutrient count and mandatory completeness.

    high   — all 7 mandatory nutrients present + serving size
    medium — core nutrients (protein + energy) present, or ≥3 nutrients total
    low    — fewer than 3 nutrients or missing both core nutrients
    """
    validation = validate_mandatory_nutrients(nutrition)
    count      = len(nutrition)
    has_core   = "protein_g" in nutrition and "energy_kcal" in nutrition

    if validation["complete"] and has_core and serving_size:
        return "high"
    if count >= 3 or has_core:
        return "medium"
    return "low"