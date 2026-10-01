"""
Analysis routes: upload, list, detail, download, dashboard stats, SSE progress.
"""
from __future__ import annotations

import asyncio
import json
import queue
import threading
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..auth import get_current_user, get_current_user_sse
from ..config import ALLOWED_EXTENSIONS, ALLOWED_IMAGE_EXTENSIONS, ALLOWED_PDF_EXTENSIONS, MAX_UPLOAD_SIZE_MB, UPLOAD_DIR
from ..database import get_db
from ..models import AnalysisJob, User
from ..schemas import AnalysisDetailResponse, AnalysisJobResponse, AnalysisListResponse, DashboardStats

router = APIRouter(prefix="/api", tags=["analysis"])


@router.post("/analyze", response_model=AnalysisJobResponse, status_code=status.HTTP_201_CREATED)
async def upload_and_analyze(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Upload a floor plan image or PDF and run the analysis pipeline."""
    filename = file.filename or "upload"
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type '{ext}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    file_type = "pdf" if ext in ALLOWED_PDF_EXTENSIONS else "image"

    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE_MB * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Maximum size: {MAX_UPLOAD_SIZE_MB} MB",
        )

    unique_name = f"{uuid.uuid4().hex}_{filename}"
    upload_path = UPLOAD_DIR / unique_name
    upload_path.write_bytes(content)

    job = AnalysisJob(
        user_id=current_user.id,
        filename=filename,
        file_type=file_type,
        status="processing",
        upload_path=str(upload_path),
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    if file_type == "pdf":
        # PDF: launch in background thread, return immediately
        from ..services.pipeline_service import run_pdf_background
        t = threading.Thread(
            target=run_pdf_background,
            args=(str(upload_path), job.id),
            daemon=True,
        )
        t.start()
        return job

    # Image: run synchronously (fast, < 30s)
    try:
        from ..services.pipeline_service import analyze_image
        result = analyze_image(str(upload_path), job.id)

        job.status = "completed"
        job.result_json = json.dumps(result["result_json"], ensure_ascii=False)
        job.result_image_path = result.get("result_image_path")
        job.total_rooms = result.get("total_rooms", 0)
        job.rooms_with_labels = result.get("rooms_with_labels", 0)
        job.rooms_with_dimensions = result.get("rooms_with_dimensions", 0)
        job.completed_at = datetime.now(timezone.utc)
    except Exception as e:
        traceback.print_exc()
        job.status = "failed"
        job.error_message = str(e)[:2000]
        job.completed_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(job)
    return job


@router.get("/analyses/{job_id}/progress")
async def stream_progress(
    job_id: int,
    current_user: User = Depends(get_current_user_sse),
    db: Session = Depends(get_db),
):
    """SSE endpoint streaming real-time progress for a PDF analysis job."""
    job = (
        db.query(AnalysisJob)
        .filter(AnalysisJob.id == job_id, AnalysisJob.user_id == current_user.id)
        .first()
    )
    if not job:
        raise HTTPException(status_code=404, detail="Analysis not found")

    if job.status in ("completed", "failed"):
        async def _done():
            data = json.dumps({"step": job.status, "page": 0, "total": 0, "message": job.status})
            yield f"data: {data}\n\n"
        return StreamingResponse(_done(), media_type="text/event-stream")

    from ..services.pipeline_service import get_progress_queue, remove_progress_queue
    q = get_progress_queue(job_id)

    async def _stream():
        try:
            while True:
                try:
                    evt = q.get_nowait()
                except queue.Empty:
                    await asyncio.sleep(0.5)
                    continue
                data = json.dumps(evt)
                yield f"data: {data}\n\n"
                if evt.get("step") in ("done", "completed", "failed"):
                    break
        finally:
            remove_progress_queue(job_id)

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@router.get("/analyses", response_model=AnalysisListResponse)
def list_analyses(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List the current user's analyses with pagination."""
    query = db.query(AnalysisJob).filter(AnalysisJob.user_id == current_user.id)
    total = query.count()
    analyses = (
        query.order_by(AnalysisJob.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return AnalysisListResponse(
        total=total,
        page=page,
        per_page=per_page,
        analyses=analyses,
    )


@router.get("/analyses/{job_id}", response_model=AnalysisDetailResponse)
def get_analysis(
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get full analysis details including result JSON."""
    job = (
        db.query(AnalysisJob)
        .filter(AnalysisJob.id == job_id, AnalysisJob.user_id == current_user.id)
        .first()
    )
    if not job:
        raise HTTPException(status_code=404, detail="Analysis not found")

    # Build response manually — result_json is stored as TEXT in DB but needs
    # to be a parsed dict in the response.
    parsed_json = None
    if job.result_json:
        try:
            parsed_json = json.loads(job.result_json)
        except (json.JSONDecodeError, TypeError):
            parsed_json = None

    return AnalysisDetailResponse(
        id=job.id,
        filename=job.filename,
        file_type=job.file_type,
        status=job.status,
        error_message=job.error_message,
        total_rooms=job.total_rooms,
        rooms_with_labels=job.rooms_with_labels,
        rooms_with_dimensions=job.rooms_with_dimensions,
        created_at=job.created_at,
        completed_at=job.completed_at,
        result_json=parsed_json,
    )


@router.get("/analyses/{job_id}/download")
def download_analysis(
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Download analysis result as JSON file."""
    from fastapi.responses import JSONResponse

    job = (
        db.query(AnalysisJob)
        .filter(AnalysisJob.id == job_id, AnalysisJob.user_id == current_user.id)
        .first()
    )
    if not job:
        raise HTTPException(status_code=404, detail="Analysis not found")
    if not job.result_json:
        raise HTTPException(status_code=404, detail="No results available")

    result = json.loads(job.result_json)
    return JSONResponse(
        content=result,
        headers={
            "Content-Disposition": f'attachment; filename="{Path(job.filename).stem}_result.json"',
        },
    )


@router.delete("/analyses/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_analysis(
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete an analysis job."""
    job = (
        db.query(AnalysisJob)
        .filter(AnalysisJob.id == job_id, AnalysisJob.user_id == current_user.id)
        .first()
    )
    if not job:
        raise HTTPException(status_code=404, detail="Analysis not found")

    db.delete(job)
    db.commit()


@router.get("/dashboard", response_model=DashboardStats)
def get_dashboard_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get dashboard statistics for the current user."""
    base_query = db.query(AnalysisJob).filter(AnalysisJob.user_id == current_user.id)

    total = base_query.count()
    completed = base_query.filter(AnalysisJob.status == "completed").count()
    failed = base_query.filter(AnalysisJob.status == "failed").count()
    total_rooms = (
        db.query(func.coalesce(func.sum(AnalysisJob.total_rooms), 0))
        .filter(AnalysisJob.user_id == current_user.id, AnalysisJob.status == "completed")
        .scalar()
    )

    recent = (
        base_query.order_by(AnalysisJob.created_at.desc())
        .limit(5)
        .all()
    )

    return DashboardStats(
        total_analyses=total,
        completed_analyses=completed,
        failed_analyses=failed,
        total_rooms_detected=total_rooms or 0,
        recent_analyses=recent,
    )


@router.get("/analyses/{job_id}/summary")
def get_summary(
    job_id: int,
    page: Optional[int] = Query(None, description="0-based page index for per-page summary (PDF)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate AI-powered property summary. Pass ?page=0 for per-page PDF summaries."""
    job = (
        db.query(AnalysisJob)
        .filter(AnalysisJob.id == job_id, AnalysisJob.user_id == current_user.id)
        .first()
    )
    if not job:
        raise HTTPException(status_code=404, detail="Analysis not found")
    if not job.result_json:
        raise HTTPException(status_code=404, detail="No results available")

    from ..services.summary_generator import generate_summary
    result = json.loads(job.result_json)
    return generate_summary(result, page_index=page)