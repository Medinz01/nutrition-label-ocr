# ==========================================
# Nutrition OCR Service - Scaffold Script
# Run from repo root
# ==========================================

Write-Host "Creating nutrition-ocr-service structure..."

# If you are already inside the cloned repo, do NOT create root folder again.
# Otherwise uncomment below:
# New-Item -ItemType Directory -Name "nutrition-ocr-service" -Force
# Set-Location "nutrition-ocr-service"

# ---------- APP ----------
New-Item -ItemType Directory -Force -Path "app"

New-Item -ItemType File -Force -Path `
"app/__init__.py", `
"app/engine.py", `
"app/parser.py", `
"app/main.py"

# ---------- TESTS ----------
New-Item -ItemType Directory -Force -Path "tests/images"

# ---------- ROOT FILES ----------
New-Item -ItemType File -Force -Path `
"Dockerfile", `
"docker-compose.yml", `
"requirements.txt", `
"README.md"

Write-Host "Structure created successfully."