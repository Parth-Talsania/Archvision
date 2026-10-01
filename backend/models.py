"""
SQLAlchemy ORM models for ArchVision.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from .database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    analyses = relationship("AnalysisJob", back_populates="user", cascade="all, delete-orphan")


class AnalysisJob(Base):
    __tablename__ = "analysis_jobs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    filename = Column(String(512), nullable=False)
    file_type = Column(String(10), nullable=False)  # "image" or "pdf"
    status = Column(String(20), nullable=False, default="pending")  # pending/processing/completed/failed
    error_message = Column(Text, nullable=True)
    result_json = Column(Text, nullable=True)  # Full frontend JSON stored as text
    upload_path = Column(String(1024), nullable=True)
    result_image_path = Column(String(1024), nullable=True)

    total_rooms = Column(Integer, nullable=True)
    rooms_with_labels = Column(Integer, nullable=True)
    rooms_with_dimensions = Column(Integer, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="analyses")
