"""
File serving routes: uploaded images and result overlays.

NOTE: These endpoints are intentionally public (no JWT required).
Security is provided by UUID-prefixed filenames (effectively unguessable)
and path-traversal protection.  Browser <img> and <a> tags cannot send
the Authorization header stored in localStorage, so requiring JWT here
would break image display and file downloads in the frontend.
"""
from __future__ import annotations

import mimetypes
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from ..config import RESULTS_DIR, UPLOAD_DIR

router = APIRouter(prefix="/api/files", tags=["files"])


def _guess_media_type(file_path: Path) -> str | None:
    """Return a MIME type so the browser renders images inline."""
    mt, _ = mimetypes.guess_type(str(file_path))
    return mt


@router.get("/uploads/{filename}")
def serve_upload(filename: str):
    """Serve an uploaded file (public — protected by UUID filename)."""
    file_path = UPLOAD_DIR / filename
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    # Security: ensure the path doesn't escape the uploads directory
    if not file_path.resolve().is_relative_to(UPLOAD_DIR.resolve()):
        raise HTTPException(status_code=403, detail="Forbidden")
    return FileResponse(str(file_path), media_type=_guess_media_type(file_path))


@router.get("/results/{job_id}/{filename}")
def serve_result(job_id: int, filename: str):
    """Serve a result file (public — protected by job ID + UUID path)."""
    file_path = RESULTS_DIR / str(job_id) / filename
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    if not file_path.resolve().is_relative_to(RESULTS_DIR.resolve()):
        raise HTTPException(status_code=403, detail="Forbidden")
    return FileResponse(str(file_path), media_type=_guess_media_type(file_path))
