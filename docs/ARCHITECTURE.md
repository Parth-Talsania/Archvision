# ArchVision — Architecture & Technical Reference

## 1. PROJECT OVERVIEW

**Project Name:** ArchVision - Hybrid AI Floor Plan Analysis Pipeline  
**Type:** Full-stack web application with AI-powered floor plan analysis  
**Purpose:** Convert 2D architectural floor plan images (PDF or PNG/JPG) into structured JSON with room geometry, labels, dimensions, and confidence scores  
**Architecture:** Modular Python backend + React frontend with FastAPI backend  
**Current Status:** End-to-end pipeline operational — login/signup (email + OAuth), image/PDF upload, YOLO+OCR analysis, result viewing with interactive SVG overlays, analytics dashboard with Recharts, printable spatial report, Wi-Fi Deadzone Mapper mini-project, and authenticated JSON downloads all working. PDF extraction uses smart `PDFFloorPlanExtractor` with YOLO validation to filter only real 2D floor plans from brochure PDFs. Backend service flow mirrors Kaggle notebook exactly (Cell 4 for images, Cell 8 for PDFs).

## 2. TECHNICAL STACK

### Backend (Python)
- **Framework:** FastAPI 0.110+
- **Database:** SQLite (SQLAlchemy ORM)
- **Authentication:** JWT (python-jose) + bcrypt (direct, not passlib) + OAuth2 (Google & GitHub)
- **AI/ML Models:**
  - YOLOv8-Seg (Ultralytics) for room instance segmentation
  - EasyOCR (primary OCR engine) for text extraction
  - PaddleOCR (fallback OCR engine) for robustness
- **PDF Processing:** PyMuPDF (fitz) for PDF text extraction and image rendering
- **Image Processing:** OpenCV (opencv-python-headless), Pillow, NumPy
- **Geometry:** Shapely for polygon operations and spatial analysis
- **Other Libraries:** PyTorch (ML backend, CPU build), python-multipart (file uploads), python-dotenv, httpx (OAuth HTTP calls)

### Frontend (TypeScript)
- **Framework:** React 18 + Vite 5
- **Language:** TypeScript
- **Styling:** Tailwind CSS 3 + shadcn/ui components
- **UI Library:** Radix UI primitives
- **State Management:** React Context API
- **Routing:** React Router v6
- **HTTP Client:** Axios with JWT interceptors
- **Data Fetching:** TanStack Query (React Query)
- **Animation:** Framer Motion (Wi-Fi heatmap pulsing)
- **Charts:** Recharts (analytics dashboard + Wi-Fi signal bars)
- **Icons:** Lucide React
- **Toasts:** sonner + shadcn toaster

### Design System — "Deep Blue Galaxy"
- **Theme:** Dark mode glassmorphism
- **Primary Accent:** Cyan (#00F0FF / #0EA5E9)
- **Glass Panels:** `bg-slate-900/40 backdrop-blur-md border border-cyan-500/30`
- **Fonts:** Space Grotesk (display), Plus Jakarta Sans (sans), JetBrains Mono (mono)
- **Animations:** CSS keyframes for floating icons, scanning radars, blueprint draws, particle drifts, pipeline step pulses

### Infrastructure
- **Development:** Vite dev server (port 8080) with proxy to FastAPI backend (port 8000)
- **Production:** Build output served via any static file server
- **Deployment:** Monorepo structure (frontend and backend in same workspace)

## 3. CORE ARCHITECTURE

### 3.1 Pipeline Architecture (Two-Step Process)

**Step 1: PDF Floor Plan Extraction (`PDFFloorPlanExtractor` — Smart YOLO-Validated Extraction)**
- **Page Scoring:** Renders each page as a thumbnail (120 DPI), scores using:
  - Text analysis: counts room keywords ("bedroom", "kitchen", etc.) + plan context keywords ("floor plan", "sq ft") minus negative keywords ("luxury", "spa", "hotel")
  - Image features: edge ratio, line count, orthogonal line ratio, colorfulness metric
  - Combined page score (min 0.55 to proceed)
- **YOLO Page Validation:** Renders qualifying pages at full 450 DPI, runs YOLO to verify room presence
- **Region Detection:** Edge detection + morphological operations + connected components to find candidate floor plan regions within each page (up to 4 per page)
- **YOLO Crop Validation:** Each candidate crop is validated with YOLO; only crops with >= 3 detected rooms are accepted
- **Result:** Only actual 2D floor plan crops are extracted — photos, logos, amenity renders, and marketing pages are filtered out
- **Module:** `pdf_extract/` package with `PDFFloorPlanExtractor` + `ExtractConfig`
- **Config:** `dpi=450, thumb_dpi=120, min_page_score=0.55, min_crop_score=0.60, validator="yolo", min_rooms=3, target_long_side=4096, scan_all_pages=True`

**Step 2: Floor Plan Analysis**
- **Room Detection:** YOLOv8-Seg model detects room instances with segmentation masks
- **Text Extraction:** Per-room OCR using EasyOCR (primary) or PaddleOCR (fallback)
- **Semantic Parsing:** Extract room labels, dimensions, and area information
- **Geometry Processing:** Polygon simplification, centroid calculation, area computation
- **Output Generation:** Structured JSON following Frontend Schema v1.0.0

### 3.2 Data Flow

```
Input (PDF/Image) 
    ↓
[If PDF] PDFFloorPlanExtractor:
    ├── Render thumbnail (120 DPI) → Text + image scoring per page
    ├── Render full-res (450 DPI) → YOLO validation on full page
    ├── Edge/morphology region detection → candidate crops
    └── YOLO validation per crop → only keep crops with ≥3 rooms
    ↓
[Only real 2D floor plan crops pass through]
    ↓
YOLOv8-Seg → Room Instance Detection (masks, polygons, confidence)
    ↓
Per-Room OCR → Text Tokens (labels, dimensions, area)
    ↓
Semantic Parser → Structured Data (parsed dimensions, labels)
    ↓
Frontend Schema Builder → JSON Output
    ↓
Visualization → Overlay Image + JSON
```

## 4. CORE DATA STRUCTURES

### 4.1 OCRToken (pipeline/types.py)
```python
@dataclass
class OCRToken:
    text: str                    # Extracted text
    conf: float                  # OCR confidence (0.0-1.0)
    box: List[Tuple[float, float]]  # Bounding box coordinates
    box_poly: Polygon            # Shapely polygon of bounding box
    box_bbox: Tuple[float, float, float, float]  # (x1, y1, x2, y2)
    source: str = "ocr"          # "ocr" or "pdf_text"
    meta: Dict[str, Any]         # Metadata (block_no, line_no, etc.)
```

### 4.2 RoomInstance (pipeline/types.py)
```python
@dataclass
class RoomInstance:
    id: int                      # Unique room identifier
    yolo_conf: float             # YOLO detection confidence
    mask: np.ndarray             # Segmentation mask
    polygon: Polygon             # Full-resolution polygon
    polygon_simplified: Polygon  # Simplified polygon for output
    bbox: Tuple[int, int, int, int]  # Bounding box
    centroid: Tuple[float, float]    # Room center point
    area_px2: float              # Area in pixels
    class_name: str = "room"     # Default class name
    label: Optional[str] = None  # Room label (e.g., "Bedroom")
    label_confidence: float = 0.0 # Label extraction confidence
    dimensions_text: Optional[str] = None  # Raw dimension text
    dimension_parsed: Optional[DimensionParseResult] = None
    area_text: Optional[str] = None       # Raw area text
    area_ft2: Optional[float] = None      # Area in square feet
    ocr_tokens: List[OCRToken] = field(default_factory=list)
    ocr_lines: List[str] = field(default_factory=list)
    ocr_merged_text: str = ""    # All OCR text merged
    meta: Dict[str, str] = field(default_factory=dict)
```

### 4.3 Frontend Schema (pipeline/frontend_schema.py)
**Schema Version:** 1.0.0

**Structure:**
```json
{
  "schema_version": "1.0.0",
  "generated_at": "2026-02-22T10:30:00Z",
  "source": { "type": "pdf|image", "file": "filename.pdf", "dpi": 300, "total_pages": 1 },
  "pages": [
    {
      "page_index": 0,
      "plan_id": "optional_plan_id",
      "image_path": "/path/to/image.png",
      "image_dimensions": {"width": 1000, "height": 800},
      "summary": { "total_rooms": 5, "rooms_with_labels": 4, "rooms_with_dimensions": 5, "rooms_with_area": 3, "text_strategy": "pdf_text|easyocr|paddleocr", "warnings": [] },
      "rooms": [
        {
          "id": 1,
          "label": "Bedroom",
          "label_raw": "Bedroom",
          "dimensions": "12'6\" x 10'",
          "dimensions_parsed": { "width_ft": 12, "width_in": 6.0, "height_ft": 10, "height_in": 0.0, "area_sqft": 125.0 },
          "area": { "value_sqft": 125.0, "source": "computed_from_dimensions|ocr_text|none", "raw_text": "125 SQFT" },
          "confidence": { "geometry": 0.95, "label": 0.87, "dimensions": 0.92 },
          "geometry": { "centroid": {"x": 250.5, "y": 180.2}, "bbox": {"x1": 200, "y1": 150, "x2": 300, "y2": 210}, "polygon": [[200,150],[300,150],[300,210],[200,210]], "area_pixels": 6000.0 }
        }
      ]
    }
  ]
}
```

## 5. PIPELINE CONFIGURATION

### 5.1 PipelineConfig (pipeline/config.py)
```python
@dataclass
class PipelineConfig:
    model_path: str              # Path to YOLOv8 model
    yolo_img_size: int = 640     # YOLO input image size
    yolo_conf: float = 0.35      # YOLO confidence threshold
    yolo_iou: float = 0.5        # YOLO IoU threshold
    polygon_simplify_tol: float = 2.0
    room_crop_pad: int = 20      # Padding around room crops for OCR
    overlap_iou_drop_threshold: float = 0.85
    ocr_mode: str = "per_room"   # "per_room" or "full_image"
    device: str = "auto"         # "cpu", "cuda", "auto"
    text_source: str = "auto"    # "auto", "pdf", "ocr"
    pipeline_version: str = "v2.0.0"
    ocr: OCRConfig = field(default_factory=OCRConfig)
    parse: ParseConfig = field(default_factory=ParseConfig)
```

## 6. BACKEND ARCHITECTURE (FastAPI)

### 6.1 Directory Structure
```
backend/
├── __init__.py
├── config.py              # Configuration: paths, security, OAuth creds, file limits
├── database.py            # SQLAlchemy setup (engine + SessionLocal + get_db)
├── models.py              # ORM models (User, AnalysisJob)
├── schemas.py             # Pydantic models
├── auth.py                # JWT + bcrypt password utilities + get_current_user dependency
├── main.py                # FastAPI app entry point (lifespan, CORS, 4 routers, /api/health)
├── routes/
│   ├── __init__.py
│   ├── auth_routes.py     # /api/auth/* endpoints (register, login, me)
│   ├── oauth_routes.py    # /api/auth/google, /api/auth/github, callbacks
│   ├── analysis_routes.py # /api/analyze, /api/analyses/*, /api/dashboard
│   └── files_routes.py    # /api/files/* endpoints (public file serving)
├── services/
│   ├── __init__.py
│   ├── pipeline_service.py # Pipeline wrapper service (singleton pattern)
│   └── summary_generator.py # Template-based natural-language property summary
├── uploads/               # Uploaded files storage (UUID-prefixed)
├── results/               # Analysis results storage (per job_id)
└── archvision.db         # SQLite database
```

### 6.2 Configuration (backend/config.py)
```python
# Paths
BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent

# Security
SECRET_KEY: str = os.getenv("ARCHVISION_SECRET_KEY", _DEFAULT_SECRET)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 1440  # 24h

# Database
DATABASE_URL = f"sqlite:///{BACKEND_DIR / 'archvision.db'}"

# File storage
UPLOAD_DIR = BACKEND_DIR / "uploads"
RESULTS_DIR = BACKEND_DIR / "results"

# Pipeline
MODEL_PATH = str(PROJECT_ROOT / "models" / "best.pt")

# OAuth
GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET  # from .env
GITHUB_CLIENT_ID / GITHUB_CLIENT_SECRET  # from .env
FRONTEND_URL = "http://localhost:8080"
BACKEND_URL = "http://localhost:8000"
```

### 6.3 ORM Models (backend/models.py)

**User Model:**
```python
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    analyses = relationship("AnalysisJob", back_populates="user", cascade="all, delete-orphan")
```

**AnalysisJob Model:**
```python
class AnalysisJob(Base):
    __tablename__ = "analysis_jobs"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    filename, file_type, status, error_message, result_json
    upload_path, result_image_path
    total_rooms, rooms_with_labels, rooms_with_dimensions
    created_at, completed_at
```

### 6.4 API Endpoints

**Authentication Routes (/api/auth):**
- `POST /api/auth/register` → `{access_token, token_type}`
- `POST /api/auth/login` → `{access_token, token_type}`
- `GET /api/auth/me` → `{id, email, full_name, created_at}` (protected)

**OAuth Routes (/api/auth):**
- `GET /api/auth/google` → Redirects to Google OAuth consent screen (sets CSRF state cookie)
- `GET /api/auth/google/callback` → Exchanges code for tokens, find-or-create user, redirects to `FRONTEND_URL/auth/callback?token=JWT`
- `GET /api/auth/github` → Redirects to GitHub OAuth authorize page (sets CSRF state cookie)
- `GET /api/auth/github/callback` → Exchanges code for tokens, find-or-create user, redirects to `FRONTEND_URL/auth/callback?token=JWT`
- **OAuth flow details:** Uses `httpx.AsyncClient` for token exchange and profile fetching. CSRF state stored in signed cookie. Find-or-create pattern: if user email exists, returns existing user's JWT; otherwise creates new user with random password hash.

**Analysis Routes (/api):**
- `POST /api/analyze` → Upload + analyze (protected, multipart form)
- `GET /api/analyses` → Paginated list (protected, `?page=&per_page=`)
- `GET /api/analyses/{id}` → Detail with full result_json (protected)
- `GET /api/analyses/{id}/download` → Download JSON (protected)
- `DELETE /api/analyses/{id}` → Delete (protected)
- `GET /api/dashboard` → Stats (protected, total/completed/failed/rooms/recent)
- `GET /api/analyses/{id}/progress` → Server-Sent Events stream of PDF processing progress (protected)
- `GET /api/analyses/{id}/summary` → Generated natural-language property summary (protected)

**File Routes (/api/files):**
- `GET /api/files/uploads/{filename}` → Serve uploaded files (**public** — UUID filename security)
- `GET /api/files/results/{job_id}/{filename}` → Serve result files (**public**)

**Health:**
- `GET /api/health` → `{status: "ok", service: "archvision-api"}`

### 6.5 Pipeline Service (backend/services/pipeline_service.py)

**Singleton Pattern:**
- `_pipeline_instance`: Global singleton loaded on first use
- Config: `yolo_img_size=640, yolo_conf=0.35, room_crop_pad=20, ocr_mode="per_room", engine="paddle", upscale=3`

**Functions:**
- `analyze_image(image_path, job_id)` — Mirrors Kaggle Cell 4
- `analyze_pdf(pdf_path, job_id)` — Mirrors Kaggle Cell 8 / `scripts/run_pdf_pipeline.py` (PDFFloorPlanExtractor with YOLO validation)

## 7. FRONTEND ARCHITECTURE (React)

### 7.1 Directory Structure
```
frontend/
├── src/
│   ├── api/
│   │   └── client.ts              # Axios instance with JWT interceptors
│   ├── components/
│   │   ├── ProtectedRoute.tsx     # Authentication guard
│   │   ├── Layout.tsx             # Sidebar layout + TelemetryBar
│   │   ├── NavLink.tsx            # NavLink wrapper with active/pending className support
│   │   ├── TelemetryBar.tsx       # Fixed top-edge LIVE system telemetry marquee
│   │   ├── UploadZone.tsx         # Drag-and-drop upload component
│   │   ├── PipelineOverlay.tsx    # Animated pipeline processing stepper overlay
│   │   ├── FloorPlanViewer.tsx    # Interactive SVG room polygon viewer with zoom/pan
│   │   ├── RoomDetailPanel.tsx    # Room details sidebar
│   │   ├── AnalyticsDashboard.tsx # Full analytics suite: KPIs, doughnut, radar, bars
│   │   ├── SpatialReport.tsx      # Printable spatial audit report (portal into body)
│   │   ├── HowItWorks.tsx         # Two-step pipeline explanation with lightbox images
│   │   ├── TechStack.tsx          # Tech stack grid with SVG logos and hover glows
│   │   ├── WifiMapper.tsx         # Wi-Fi Deadzone Mapper mini-project
│   │   ├── CostEstimator.tsx      # Per-room construction cost estimate with breakdown charts
│   │   ├── PropertySummary.tsx    # Natural-language property summary card
│   │   └── ui/                    # shadcn/ui primitives (button, card, dialog, etc.)
│   ├── contexts/
│   │   └── AuthContext.tsx        # Auth state: login, register, loginWithToken, logout
│   ├── hooks/
│   │   └── use-mobile.tsx         # Mobile breakpoint hook
│   ├── lib/
│   │   └── utils.ts               # cn() class merge utility
│   ├── pages/
│   │   ├── Landing.tsx            # Public landing page (features, pipeline overview)
│   │   ├── Compare.tsx            # Side-by-side comparison of two analyses
│   │   ├── Login.tsx              # Login with floating SVG background animations + OAuth buttons
│   │   ├── Register.tsx           # Registration page
│   │   ├── OAuthCallback.tsx      # OAuth redirect handler (?token=... → loginWithToken)
│   │   ├── Dashboard.tsx          # Dashboard with sticky nav tabs (Overview, How It Works, Tech Stack)
│   │   ├── Upload.tsx             # File upload page with PipelineOverlay animation
│   │   ├── AnalysisView.tsx       # Analysis results: viewer tab, analytics tab, spatial report, Wi-Fi button
│   │   ├── History.tsx            # Paginated analysis history table
│   │   ├── ProjectIntro.tsx       # "Intelligence for Spatial Design" intro page
│   │   ├── Founders.tsx           # Team bio cards with GitHub/LinkedIn links
│   │   ├── NotFound.tsx           # 404 page
│   │   └── Index.tsx              # Redirect helper
│   ├── App.tsx                    # Main app routing (public + protected routes)
│   └── main.tsx                   # Entry point
├── public/
│   └── assets/images/             # Static images for HowItWorks section
├── index.html
├── tailwind.config.ts
└── vite.config.ts
```

### 7.2 API Client (src/api/client.ts)
- Axios instance with `baseURL: "/api"` (proxied to backend)
- Request interceptor: adds `Authorization: Bearer <token>` from `localStorage("archvision_token")`
- Response interceptor: on 401, removes token and redirects to `/login` (skips if already on login/register)

### 7.3 Authentication Context (src/contexts/AuthContext.tsx)
```typescript
interface AuthContextType {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email, password) => Promise<void>;
  loginWithToken: (token: string) => Promise<void>;  // used by the OAuth callback
  register: (email, password, fullName) => Promise<void>;
  logout: () => void;
}
```
- Token stored in `localStorage` as `"archvision_token"`
- `loginWithToken()`: Sets token directly (used by OAuthCallback page), then fetches `/auth/me`
- Auto-fetches user profile on mount if token exists

### 7.4 Main App Routing (src/App.tsx)
```tsx
<Routes>
  {/* Public routes */}
  <Route path="/" element={<Navigate to="/landing" />} />
  <Route path="/landing" element={<Landing />} />
  <Route path="/login" element={<Login />} />
  <Route path="/register" element={<Register />} />
  <Route path="/auth/callback" element={<OAuthCallback />} />

  {/* Protected routes with sidebar layout */}
  <Route element={<ProtectedRoute><Layout /></ProtectedRoute>}>
    <Route path="/introduction" element={<ProjectIntro />} />
    <Route path="/founders" element={<Founders />} />
    <Route path="/dashboard" element={<Dashboard />} />
    <Route path="/upload" element={<UploadPage />} />
    <Route path="/analysis/:id" element={<AnalysisView />} />
    <Route path="/history" element={<HistoryPage />} />
    <Route path="/compare" element={<Compare />} />
    <Route path="/wifi-mapper" element={<WifiMapper />} />
  </Route>

  <Route path="*" element={<NotFound />} />
</Routes>
```

### 7.5 Key Components

**TelemetryBar (src/components/TelemetryBar.tsx):**
- Fixed top-edge bar (h-8, z-50) with `bg-slate-950/80 backdrop-blur-md`
- "System: Online" LIVE indicator pill with pinging dot animation
- Scrolling marquee displaying system telemetry text (OpenCV, EasyOCR status, latency)
- Layout adds `pt-8` to main content to accommodate

**Layout Component (src/components/Layout.tsx):**
- Renders `<TelemetryBar />` at top
- Fixed 264px sidebar with navigation
- Nav items: Introduction, Founders, Dashboard, Upload, History
- User profile section with logout button
- Main content area using `<Outlet />`

**Login Page (src/pages/Login.tsx):**
- Full-screen glassmorphic login form
- FloatingShapes background: 8 animated Lucide icons, NeuralNetwork SVG, ScanningRadar SVG, BoundingBox SVG, blueprint unfold SVG, room layout fragment, particle dots
- Email/password form with remember me
- Google & GitHub OAuth buttons → redirect to `/api/auth/google` / `/api/auth/github`
- Picks up OAuth error from router state (from OAuthCallback redirect)

**Register Page (src/pages/Register.tsx):**
- Full-screen glassmorphic registration form
- Fields: full name, email, password, confirm password
- Client-side validation: password match, min 6 chars

**OAuthCallback Page (src/pages/OAuthCallback.tsx):**
- Reads `?token=...` or `?error=...` from URL search params
- On token: calls `loginWithToken(token)` → navigates to `/dashboard`
- On error: shows error message, redirects to `/login` after 3s with error state

**Dashboard Page (src/pages/Dashboard.tsx):**
- Sticky in-page navigation bar with IntersectionObserver-powered active tab highlighting
- Three sections: Overview, How It Works, Tech Stack
- Overview: welcome header, 4 stat cards (total/completed/failed/rooms), recent analyses list
- Embeds `<HowItWorks />` and `<TechStack />` components below

**HowItWorks Component (src/components/HowItWorks.tsx):**
- Two-step pipeline explanation (Geometric Core Segmentation + Semantic Recognition)
- Glass-framed image containers with lightbox modal on click, scan-line hover animation
- Animated DataStreamConnector between steps (glowing vertical line with pulse + arrow)
- Feature pills for each step

**TechStack Component (src/components/TechStack.tsx):**
- Two grouped grids: "AI & Backend" (9 items) and "Frontend & Visualization" (4 items)
- Custom inline SVG logos for each tech: YOLOv8, Python, FastAPI, OpenCV, EasyOCR, PaddleOCR, Shapely, PyMuPDF, NumPy, React, Tailwind, Recharts, Framer Motion
- Hover glow effects using brand colors per technology

**Upload Page (src/pages/Upload.tsx):**
- UploadZone drag-and-drop component (accepts PNG, JPG, PDF, BMP, TIFF)
- On analyze: shows `<PipelineOverlay />` with animated stepper while backend processes
- 10-minute timeout for large PDFs
- After pipeline completes + animation finishes → navigates to `/analysis/{id}`

**PipelineOverlay Component (src/components/PipelineOverlay.tsx):**
- Full-screen modal overlay shown during analysis processing
- 4-step stepper: INGEST → SEGMENT → RECOGNIZE → FUSE
- Steps 0-2 advance on timed intervals (2.5s, 4s, 5s); step 3 stays active until real pipeline finishes
- Each step has: circle icon (pending/active/complete states), spinning dashed ring for active, vertical connector line
- Thumbnail preview (image preview or PDF icon) with scan line animation
- After all steps complete + 800ms delay → calls `onAnimationDone` so parent can navigate

**AnalysisView Page (src/pages/AnalysisView.tsx):**
- Top bar: back link, filename, date, PDF badge
- Action buttons: "Export Spatial Report" (print), "Download JSON", "Launch Wi-Fi Simulator"
- Tab switcher: Viewer | Insights & Analytics
- **Viewer tab:** Summary stats, FloorPlanViewer + RoomDetailPanel, PDF image galleries, page selector
- **Analytics tab:** Renders `<AnalyticsDashboard />` with all rooms
- **Spatial Report:** Renders `<SpatialReport />` (hidden portal) and triggers `window.print()`
- **Wi-Fi Simulator button:** Maps rooms to `{id, label, x, y, area}` using centroids, saves to `localStorage("archvision_wifi_data")` + `localStorage("archvision_blueprint")`, navigates to `/wifi-mapper`

**AnalyticsDashboard Component (src/components/AnalyticsDashboard.tsx):**
- Props: `rooms: Room[], filename: string`
- **KPI Hero Cards** (4): Total Usable Area, Room Count, Largest Space, Space Efficiency (circular gauge)
- **Doughnut Chart:** Space allocation by category (Sleeping, Living, Utility, Outdoor) using Recharts PieChart
- **Radar Chart:** Architectural balance profile (Living, Privacy, Utility, Circulation, Outdoors)
- **Horizontal Bar Chart:** Room size hierarchy, ranked by area, with custom per-room colors
- **Export Button:** Downloads plain-text analytics report
- All cards use `useCountUp` hook for animated number display, `useInView` hook for animate-on-scroll

**SpatialReport Component (src/components/SpatialReport.tsx):**
- Renders via `createPortal` into `document.body` (for `@media print`)
- Sections: header (doc ID, timestamp, filename), segmented blueprint image, spatial data matrix table (room label, sqft, occupancy type, confidence), smart building estimates (HVAC tonnage, LED wattage)
- Auto-generated random document ID (AV-XXXXXXXX)

**FloorPlanViewer Component (src/components/FloorPlanViewer.tsx):**
- Interactive SVG overlay on floor plan image
- Room polygons colour-coded using consistent `ROOM_LABEL_COLORS` map (Kitchen=red, Bedroom=blue, etc.)
- Features: zoom (scroll/buttons), pan (Ctrl+click/middle mouse), room selection, hover tooltips, room labels at centroids
- Keyboard: Escape to deselect

**RoomDetailPanel Component (src/components/RoomDetailPanel.tsx):**
- Selected room details: dimensions (parsed feet/inches), area (sqft), label, confidence bars (geometry, label), geometry info (centroid, area pixels, polygon vertices)
- Defensive: `room.confidence ?? { geometry: 0, label: 0, dimensions: 0 }`

**History Page (src/pages/History.tsx):**
- Paginated table (15/page) with columns: file, type, status badge, rooms, date, actions
- Actions: view (link), download (authenticated axios blob), delete (with confirm)

**ProjectIntro Page (src/pages/ProjectIntro.tsx):**
- Hero header: "ArchVision: Intelligence for Spatial Design"
- Three pillar cards: The Theoretical Gap, The Technical Stack, Real-World Utility

**Founders Page (src/pages/Founders.tsx):**
- Story panel: "How ArchVision Started" (IAR 6th semester project narrative)
- 5 founder cards with initials avatar, name, role, bio, GitHub/LinkedIn links
- Team: Mohammed Ayaan, Parth Talsania, Abhishek Rathod, Harshil Darji, Heli Darji

### 7.6 Wi-Fi Deadzone Mapper (src/components/WifiMapper.tsx)

**Purpose:** Proof-of-concept downstream application built on ArchVision's structured JSON output. Uses X/Y centroids from the pipeline to simulate Wi-Fi signal drop-off using Euclidean distance math.

**Architecture:**
- Two-column glassmorphic layout (12-col grid: 8 map + 4 analytics)
- Left: Floor plan signal canvas with centroid nodes and heatmap
- Right: Network Health Simulator with bar chart and signal legend

**Data Flow:**
1. `AnalysisView` → "Launch Wi-Fi Simulator" button maps pipeline rooms to `{id, label, x, y, area}` format
2. Data saved to `localStorage("archvision_wifi_data")` + `localStorage("archvision_blueprint")`
3. `WifiMapper` reads from localStorage on mount, falls back to mock data

**Coordinate Transformation (object-contain mapping):**
```typescript
const getTransform = () => {
  // Compute CSS object-contain equivalent: scale + letterbox offset
  const scale = Math.min(containerWidth / naturalWidth, containerHeight / naturalHeight);
  const offsetX = (containerWidth - naturalWidth * scale) / 2;
  const offsetY = (containerHeight - naturalHeight * scale) / 2;
  return { scale, offsetX, offsetY };
};

const toContainer = (px, py) => ({
  cx: offsetX + px * scale,
  cy: offsetY + py * scale,
});
```
- Solves the problem of pipeline centroids in original image pixel space needing to be placed on a scaled-down container

**Signal Calculation:**
- `MAX_RANGE_PX` = container diagonal × 0.85 (dynamic)
- `rawSignal = max(0, 100 - (distance / MAX_RANGE) * 100)`
- Wall penalty: -15% for every non-router room
- Result: per-room `SignalEntry { id, label, signal }`

**Visualization:**
- **Heatmap:** Framer Motion pulsing radial gradient (`motion.div`) at router position, 1400px circle, 3s infinite easeInOut
- **Node Colors:** Cyan (≥80%), Amber (40-79%), Rose (<40%) with glow shadows
- **Analytics:** Average signal metric (large mono text), Recharts vertical BarChart with conditional Cell colors, signal legend (Excellent/Moderate/Deadzone)

**Custom Glassmorphic Tooltip:**
- `bg-slate-900/90 backdrop-blur-md border-cyan-500/30` with signal tier label

## 8. DEVELOPMENT WORKFLOW

### 8.1 Backend
```bash
python -m venv .venv
# Windows: .venv\Scripts\activate    Linux/macOS: source .venv/bin/activate
pip install -r backend/requirements.txt
python -m uvicorn backend.main:app --reload --port 8000
# API docs: http://127.0.0.1:8000/docs
```

### 8.2 Frontend
```bash
cd frontend
npm install
npm run dev
# http://localhost:8080 (proxies /api → http://127.0.0.1:8000)
```

### 8.3 Tests
```bash
python -m pytest tests
cd frontend && npm test
```

## 9. ENVIRONMENT VARIABLES

```bash
# Backend (.env at project root)
ARCHVISION_SECRET_KEY=your_secret_key_here
ARCHVISION_DATABASE_URL=sqlite:///backend/archvision.db
ARCHVISION_MODEL_PATH=/path/to/best.pt
ARCHVISION_TOKEN_EXPIRE=1440
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
GITHUB_CLIENT_ID=...
GITHUB_CLIENT_SECRET=...
ARCHVISION_FRONTEND_URL=http://localhost:8080
ARCHVISION_BACKEND_URL=http://localhost:8000
```

## 10. SECURITY

- JWT tokens with 24-hour expiration
- Password hashing with bcrypt (direct, NOT passlib)
- OAuth2 CSRF state cookie verification
- File upload validation (type, size: 50MB max)
- Path traversal protection for file serving
- CORS configured for specific origins (localhost:8080, 5173)
- File-serving endpoints public; security via UUID filenames
- OAuth find-or-create: random password hash for OAuth-created users

## 11. TROUBLESHOOTING

### 11.1 Common Issues

**ModuleNotFoundError:** Activate the venv and run `pip install -r backend/requirements.txt`

**Floor plan images 401 errors:** File-serving endpoints are public (no JWT on <img> tags). Security via UUID filenames.

**room.confidence undefined crash:** Use optional chaining: `room.confidence?.geometry ?? 0`

**Download buttons 401:** Use authenticated axios blob download, not plain `<a>` tags

**PDF extracts useless images:** Use `PDFFloorPlanExtractor` with YOLO validation, not `PDFImageExtractor`

**Wi-Fi centroids misplaced:** Pipeline outputs centroids in original image pixel space. Use `getTransform()` + `toContainer()` to map through object-contain scale + letterbox offset.


## 12. PROJECT HISTORY & EVOLUTION

### 12.1 Key Milestones
1. Initial Pipeline: Basic YOLO + OCR implementation
2. PDF Integration: PyMuPDF for native text extraction
3. Quality Improvements: Extract-First, Render-Fallback strategy
4. Frontend Development: React dashboard with interactive viewer
5. Full Stack Integration: FastAPI backend with JWT authentication
6. Smart PDF Extraction: PDFFloorPlanExtractor with YOLO crop validation
7. Kaggle Alignment: Backend mirrors exact Kaggle notebook flows
8. OAuth2 Social Login: Google + GitHub with find-or-create user pattern
9. TelemetryBar + PipelineOverlay: Live system marquee + animated processing stepper
10. ProjectIntro + Founders pages: Team and project narrative
11. HowItWorks + TechStack: Interactive pipeline documentation on Dashboard
12. AnalyticsDashboard: Full Recharts analytics suite with KPIs, doughnut, radar, bars
13. SpatialReport: Printable audit report with smart building estimates
14. **Wi-Fi Deadzone Mapper:** Proof-of-concept downstream application using pipeline centroids for Euclidean Wi-Fi signal simulation with Framer Motion heatmap
15. Landing page, Compare view, Cost Estimator and generated property summaries

---

*This document provides a complete overview of the ArchVision project architecture, all frontend components, backend endpoints, the Wi-Fi Mapper mini-project, OAuth integration, analytics dashboard, and development workflow. It serves as a comprehensive reference for understanding the system's full current state.*
