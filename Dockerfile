FROM python:3.11-slim

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-eng \
    libtesseract-dev \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    && rm -rf /var/lib/apt/lists/*

# ── Layer 1: Heavy deps (PaddlePaddle ~2GB) ──────────────────────────────────
# Copied and installed FIRST so Docker caches this layer separately.
# Only reinstalls if requirements-heavy.txt changes.
COPY requirements-heavy.txt .
RUN pip install --no-cache-dir -r requirements-heavy.txt

# ── Layer 2: Light deps (fast, changes more often) ───────────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Source code (changes most often — last layer) ────────────────────────────
COPY . .

CMD ["python", "test_extraction.py"]