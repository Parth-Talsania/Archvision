"""
Pydantic request / response schemas for the ArchVision API.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, EmailStr, Field


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

class RegisterRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=255)
    password: str = Field(..., min_length=6, max_length=128)
    full_name: str = Field(..., min_length=1, max_length=255)


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: int
    email: str
    full_name: str
    created_at: datetime

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

class AnalysisJobResponse(BaseModel):
    id: int
    filename: str
    file_type: str
    status: str
    error_message: Optional[str] = None
    total_rooms: Optional[int] = None
    rooms_with_labels: Optional[int] = None
    rooms_with_dimensions: Optional[int] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AnalysisDetailResponse(AnalysisJobResponse):
    result_json: Optional[Dict[str, Any]] = None


class AnalysisListResponse(BaseModel):
    total: int
    page: int
    per_page: int
    analyses: List[AnalysisJobResponse]


class DashboardStats(BaseModel):
    total_analyses: int
    completed_analyses: int
    failed_analyses: int
    total_rooms_detected: int
    recent_analyses: List[AnalysisJobResponse]
