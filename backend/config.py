"""
ArchVision Backend Configuration
"""
from __future__ import annotations

import os
import secrets
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root (parent of backend/)
_BACKEND_DIR = Path(__file__).resolve().parent
load_dotenv(_BACKEND_DIR.parent / ".env")

# Paths
BACKEND_DIR = _BACKEND_DIR
PROJECT_ROOT = BACKEND_DIR.parent  # pipeline/ workspace root

# Security
_DEFAULT_SECRET = "archvision-dev-secret-key-change-in-production"
SECRET_KEY: str = os.getenv("ARCHVISION_SECRET_KEY", _DEFAULT_SECRET)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ARCHVISION_TOKEN_EXPIRE", "1440"))  # 24h

# Database
DATABASE_URL: str = os.getenv(
    "ARCHVISION_DATABASE_URL",
    f"sqlite:///{BACKEND_DIR / 'archvision.db'}",
)

# File storage
UPLOAD_DIR: Path = BACKEND_DIR / "uploads"
RESULTS_DIR: Path = BACKEND_DIR / "results"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

# Pipeline
MODEL_PATH: str = os.getenv(
    "ARCHVISION_MODEL_PATH",
    str(PROJECT_ROOT / "results" / "runs" / "segment" / "runs" / "segment" / "floor_plan_rooms" / "weights" / "best.pt"),
)

# Allowed upload extensions
ALLOWED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif"}
ALLOWED_PDF_EXTENSIONS = {".pdf"}
ALLOWED_EXTENSIONS = ALLOWED_IMAGE_EXTENSIONS | ALLOWED_PDF_EXTENSIONS

# Max upload size (50 MB)
MAX_UPLOAD_SIZE_MB: int = 50

# OAuth — Google
GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET: str = os.getenv("GOOGLE_CLIENT_SECRET", "")

# OAuth — GitHub
GITHUB_CLIENT_ID: str = os.getenv("GITHUB_CLIENT_ID", "")
GITHUB_CLIENT_SECRET: str = os.getenv("GITHUB_CLIENT_SECRET", "")

# Frontend URL (for OAuth callback redirects)
FRONTEND_URL: str = os.getenv("ARCHVISION_FRONTEND_URL", "http://localhost:8080")

# Backend public URL (used to build OAuth callback URIs — must match what you
# registered in the Google / GitHub developer console)
BACKEND_URL: str = os.getenv("ARCHVISION_BACKEND_URL", "http://localhost:8000")
