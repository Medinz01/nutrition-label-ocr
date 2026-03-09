# layout_engine.py

import re
from collections import defaultdict


# ─── Row Clustering ──────────────────────────────────────────────────────────

# layout_engine.py

import statistics


def build_layout(blocks, y_threshold=18):
    """
    Step 1: split blocks into vertical zones
    Step 2: cluster rows within each zone
    """

    if not blocks:
        return []

    # ─── Vertical Zoning (left vs right panel) ─────────────

    xs = [b["cx"] for b in blocks]
    median_x = statistics.median(xs)

    left_blocks  = [b for b in blocks if b["cx"] < median_x]
    right_blocks = [b for b in blocks if b["cx"] >= median_x]

    zones = [left_blocks, right_blocks]

    all_rows = []

    for zone in zones:
        zone = sorted(zone, key=lambda b: b["cy"])

        rows = []
        current = []

        for b in zone:
            if not current:
                current.append(b)
                continue

            if abs(b["cy"] - current[-1]["cy"]) < y_threshold:
                current.append(b)
            else:
                rows.append(sorted(current, key=lambda x: x["cx"]))
                current = [b]

        if current:
            rows.append(sorted(current, key=lambda x: x["cx"]))

        all_rows.extend(rows)

    return all_rows


# ─── Region Detection ────────────────────────────────────────────────────────

def find_nutrition_region(layout):
    """
    Detect region with highest numeric density per row.
    Nutrition table rows contain multiple numeric values.
    Amino acid rows contain only one.
    """

    def count_numeric(row):
        import re
        count = 0
        for cell in row:
            if re.search(r"\d", cell["text"]):
                count += 1
        return count

    # score rows by numeric density
    scored = [(i, count_numeric(row)) for i, row in enumerate(layout)]

    # keep rows with >=2 numeric cells (nutrition rows)
    nutrition_rows = [layout[i] for i, score in scored if score >= 2]

    return nutrition_rows

def find_ingredients_region(layout):
    region = []
    capture = False

    for row in layout:
        row_text = " ".join([b["text"].lower() for b in row])

        if "ingredient" in row_text:
            capture = True
            continue

        if capture:
            if any(k in row_text for k in ["allergen", "nutrition", "storage"]):
                break
            region.append(row)

    return region


# ─── Reconstruction ──────────────────────────────────────────────────────────

def reconstruct_table(region):

    # Flatten blocks
    blocks = [b for row in region for b in row]

    if not blocks:
        return []

    # ─── Step 1: cluster columns by X ─────────────

    blocks_sorted_x = sorted(blocks, key=lambda b: b["cx"])

    columns = []
    col_threshold = 40

    for b in blocks_sorted_x:
        placed = False

        for col in columns:
            if abs(b["cx"] - col["center"]) < col_threshold:
                col["blocks"].append(b)
                col["center"] = sum(x["cx"] for x in col["blocks"]) / len(col["blocks"])
                placed = True
                break

        if not placed:
            columns.append({
                "center": b["cx"],
                "blocks": [b]
            })

    # Sort columns left to right
    columns.sort(key=lambda c: c["center"])

    # ─── Step 2: cluster rows by Y across columns ─────────

    rows_dict = {}

    row_threshold = 18

    for col_idx, col in enumerate(columns):
        for b in col["blocks"]:
            y_key = round(b["cy"] / row_threshold)

            if y_key not in rows_dict:
                rows_dict[y_key] = {}

            rows_dict[y_key][col_idx] = b["text"]

    # ─── Step 3: reconstruct ordered table ─────────

    table = []

    for y in sorted(rows_dict.keys()):
        row = []
        max_col = max(rows_dict[y].keys())

        for col_idx in range(max_col + 1):
            row.append(rows_dict[y].get(col_idx, ""))

        table.append(row)

    return table


def reconstruct_paragraph(region):
    lines = []
    for row in region:
        line = " ".join([cell["text"] for cell in row])
        lines.append(line)

    paragraph = " ".join(lines)
    paragraph = re.sub(r"\s+", " ", paragraph).strip()

    return paragraph if len(paragraph) > 10 else None