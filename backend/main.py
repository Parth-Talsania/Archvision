"""
ArchVision Backend — FastAPI application entry point.

Start with:
    cd pipeline
    uvicorn backend.main:app --reload --port 8000
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import Base, engine
from .routes.analysis_routes import router as analysis_router
from .routes.auth_routes import router as auth_router
from .routes.files_routes import router as files_router
from .routes.oauth_routes import router as oauth_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create database tables on startup."""
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="ArchVision API",
    description="Hybrid AI Floor Plan Analysis Backend",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow the Vite dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8080",
        "http://localhost:5173",
        "http://127.0.0.1:8080",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(auth_router)
app.include_router(oauth_router)
app.include_router(analysis_router)
app.include_router(files_router)


@app.get("/api/health")
def health_check():
    return {"status": "ok", "service": "archvision-api"}
