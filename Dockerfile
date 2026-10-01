# ArchVision backend: FastAPI + YOLOv8 + OCR pipeline (CPU)
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# OpenCV (pulled in by Ultralytics) needs these system libraries
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# CPU-only PyTorch keeps the image far smaller than the default CUDA build
RUN pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
COPY backend/requirements.txt backend/requirements.txt
RUN pip install -r backend/requirements.txt

COPY backend backend
COPY pipeline pipeline
COPY pdf_extract pdf_extract
COPY models models

# Database lives on a volume; uploads, results and the EasyOCR model cache
# (downloaded on first analysis) are mounted as volumes by docker-compose.yml
ENV ARCHVISION_DATABASE_URL=sqlite:////app/data/archvision.db
RUN mkdir -p /app/data /app/backend/uploads /app/backend/results /app/results/easyocr_cache

EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
