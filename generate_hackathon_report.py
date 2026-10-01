"""
ArchVision — Hackathon Report PDF Generator
Generates a professional, detailed hackathon-style project report.
"""

import os, textwrap
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm, cm, inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable, KeepTogether, ListFlowable, ListItem,
    Flowable,
)
from reportlab.graphics.shapes import Drawing, Rect, String, Line, Circle
from reportlab.graphics import renderPDF
from reportlab.pdfgen import canvas

# ── Colour Palette (Deep Blue Galaxy Theme) ──────────────────────────
NAVY       = colors.HexColor("#0B1120")
DARK_BLUE  = colors.HexColor("#111827")
SLATE      = colors.HexColor("#1E293B")
CYAN       = colors.HexColor("#00F0FF")
CYAN_DIM   = colors.HexColor("#0EA5E9")
WHITE      = colors.HexColor("#F8FAFC")
LIGHT_GRAY = colors.HexColor("#CBD5E1")
MID_GRAY   = colors.HexColor("#94A3B8")
ACCENT_ROSE = colors.HexColor("#F43F5E")
ACCENT_AMBER = colors.HexColor("#F59E0B")
ACCENT_GREEN = colors.HexColor("#22C55E")

OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "ArchVision_Hackathon_Report.pdf")

# ── Custom Flowables ─────────────────────────────────────────────────
class ColorBar(Flowable):
    """A thin horizontal accent bar."""
    def __init__(self, width, height=2, color=CYAN):
        super().__init__()
        self.width = width
        self.height = height
        self._color = color

    def wrap(self, availWidth, availHeight):
        return self.width, self.height + 4

    def draw(self):
        self.canv.setFillColor(self._color)
        self.canv.roundRect(0, 2, self.width, self.height, 1, fill=1, stroke=0)


class SectionBanner(Flowable):
    """Dark banner with section number and title."""
    def __init__(self, number, title, width):
        super().__init__()
        self._number = number
        self._title = title
        self._width = width

    def wrap(self, availWidth, availHeight):
        return self._width, 32

    def draw(self):
        c = self.canv
        c.setFillColor(SLATE)
        c.roundRect(0, 0, self._width, 28, 4, fill=1, stroke=0)
        c.setFillColor(CYAN)
        c.setFont("Helvetica-Bold", 13)
        c.drawString(12, 8, f"{self._number}")
        c.setFillColor(WHITE)
        c.setFont("Helvetica-Bold", 13)
        c.drawString(36, 8, self._title.upper())


# ── Page Templates ───────────────────────────────────────────────────
def _header_footer(canvas_obj, doc):
    canvas_obj.saveState()
    # Footer
    canvas_obj.setFillColor(MID_GRAY)
    canvas_obj.setFont("Helvetica", 7.5)
    canvas_obj.drawString(doc.leftMargin, 12 * mm,
                          "ArchVision — Hybrid AI Floor Plan Analysis Pipeline  |  Hackathon Project Report")
    canvas_obj.drawRightString(A4[0] - doc.rightMargin, 12 * mm,
                               f"Page {doc.page}")
    # Top accent line
    canvas_obj.setStrokeColor(CYAN)
    canvas_obj.setLineWidth(0.5)
    canvas_obj.line(doc.leftMargin, A4[1] - 14 * mm,
                    A4[0] - doc.rightMargin, A4[1] - 14 * mm)
    canvas_obj.restoreState()


def _cover_page(canvas_obj, doc):
    w, h = A4
    # Background
    canvas_obj.setFillColor(NAVY)
    canvas_obj.rect(0, 0, w, h, fill=1, stroke=0)

    # Decorative accent rectangles
    canvas_obj.setFillColor(CYAN)
    canvas_obj.setFillAlpha(0.08)
    canvas_obj.roundRect(30, h - 300, 200, 200, 20, fill=1, stroke=0)
    canvas_obj.roundRect(w - 180, 80, 160, 160, 16, fill=1, stroke=0)
    canvas_obj.setFillAlpha(1.0)

    # Cyan accent bar
    canvas_obj.setFillColor(CYAN)
    canvas_obj.roundRect(w / 2 - 40, h - 240, 80, 3, 1, fill=1, stroke=0)

    # Title
    canvas_obj.setFillColor(CYAN)
    canvas_obj.setFont("Helvetica-Bold", 42)
    canvas_obj.drawCentredString(w / 2, h - 290, "ArchVision")

    # Subtitle
    canvas_obj.setFillColor(WHITE)
    canvas_obj.setFont("Helvetica", 15)
    canvas_obj.drawCentredString(w / 2, h - 320,
                                 "Hybrid AI Floor Plan Analysis Pipeline")

    # Tagline
    canvas_obj.setFillColor(LIGHT_GRAY)
    canvas_obj.setFont("Helvetica-Oblique", 11)
    canvas_obj.drawCentredString(w / 2, h - 350,
                                 '"Converting 2D architectural drawings into structured spatial intelligence"')

    # Info box
    canvas_obj.setFillColor(SLATE)
    canvas_obj.setFillAlpha(0.6)
    canvas_obj.roundRect(w / 2 - 150, h - 520, 300, 130, 8, fill=1, stroke=0)
    canvas_obj.setFillAlpha(1.0)

    y_info = h - 415
    canvas_obj.setFillColor(CYAN)
    canvas_obj.setFont("Helvetica-Bold", 10)
    canvas_obj.drawCentredString(w / 2, y_info, "PROJECT TYPE")
    canvas_obj.setFillColor(WHITE)
    canvas_obj.setFont("Helvetica", 10)
    canvas_obj.drawCentredString(w / 2, y_info - 16, "Full-Stack AI Web Application")

    canvas_obj.setFillColor(CYAN)
    canvas_obj.setFont("Helvetica-Bold", 10)
    canvas_obj.drawCentredString(w / 2, y_info - 42, "DOMAIN")
    canvas_obj.setFillColor(WHITE)
    canvas_obj.setFont("Helvetica", 10)
    canvas_obj.drawCentredString(w / 2, y_info - 58,
                                 "Computer Vision  •  Architecture  •  PropTech")

    canvas_obj.setFillColor(CYAN)
    canvas_obj.setFont("Helvetica-Bold", 10)
    canvas_obj.drawCentredString(w / 2, y_info - 84, "DATE")
    canvas_obj.setFillColor(WHITE)
    canvas_obj.setFont("Helvetica", 10)
    canvas_obj.drawCentredString(w / 2, y_info - 100,
                                 datetime.now().strftime("%B %Y"))

    # Team
    canvas_obj.setFillColor(CYAN)
    canvas_obj.setFont("Helvetica-Bold", 12)
    canvas_obj.drawCentredString(w / 2, h - 580, "TEAM MEMBERS")

    members = [
        "Parth Talsania", "Mohammed Ayaan", "Abhishek Rathod",
        "Harshil Darji", "Heli Darji"
    ]
    canvas_obj.setFillColor(WHITE)
    canvas_obj.setFont("Helvetica", 10)
    for i, name in enumerate(members):
        canvas_obj.drawCentredString(w / 2, h - 602 - i * 17, name)

    # Bottom accent
    canvas_obj.setFillColor(CYAN)
    canvas_obj.roundRect(w / 2 - 60, 50, 120, 2, 1, fill=1, stroke=0)
    canvas_obj.setFillColor(MID_GRAY)
    canvas_obj.setFont("Helvetica", 8)
    canvas_obj.drawCentredString(w / 2, 34, "IAR — 6th Semester Project  •  Confidential")


# ── Styles ───────────────────────────────────────────────────────────
def _build_styles():
    ss = getSampleStyleSheet()
    styles = {}

    styles["body"] = ParagraphStyle("body", parent=ss["Normal"],
        fontName="Helvetica", fontSize=10, leading=14.5,
        textColor=DARK_BLUE, alignment=TA_JUSTIFY, spaceAfter=6)

    styles["body_small"] = ParagraphStyle("body_small", parent=styles["body"],
        fontSize=9, leading=13)

    styles["h1"] = ParagraphStyle("h1", parent=ss["Heading1"],
        fontName="Helvetica-Bold", fontSize=22, leading=26,
        textColor=NAVY, spaceAfter=4, spaceBefore=2)

    styles["h2"] = ParagraphStyle("h2", parent=ss["Heading2"],
        fontName="Helvetica-Bold", fontSize=14, leading=18,
        textColor=SLATE, spaceBefore=14, spaceAfter=4)

    styles["h3"] = ParagraphStyle("h3", parent=ss["Heading3"],
        fontName="Helvetica-Bold", fontSize=11, leading=14,
        textColor=colors.HexColor("#334155"), spaceBefore=10, spaceAfter=3)

    styles["bullet"] = ParagraphStyle("bullet", parent=styles["body"],
        leftIndent=14, bulletIndent=4, spaceBefore=1, spaceAfter=1)

    styles["code"] = ParagraphStyle("code",
        fontName="Courier", fontSize=8.5, leading=11,
        textColor=colors.HexColor("#1E293B"),
        backColor=colors.HexColor("#F1F5F9"),
        borderPadding=(4, 6, 4, 6), spaceAfter=8)

    styles["caption"] = ParagraphStyle("caption",
        fontName="Helvetica-Oblique", fontSize=8.5, leading=11,
        textColor=MID_GRAY, alignment=TA_CENTER, spaceAfter=8)

    styles["toc_item"] = ParagraphStyle("toc_item",
        fontName="Helvetica", fontSize=10.5, leading=20,
        textColor=DARK_BLUE, leftIndent=8)

    styles["center"] = ParagraphStyle("center", parent=styles["body"],
        alignment=TA_CENTER)

    return styles


# ── Helpers ──────────────────────────────────────────────────────────
def _hr():
    return HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#E2E8F0"),
                       spaceAfter=6, spaceBefore=6)

def _accent_bar(w):
    return ColorBar(w, 2.5, CYAN)

def _section(num, title, w):
    return SectionBanner(num, title, w)

def _bullet_list(items, style):
    return ListFlowable(
        [ListItem(Paragraph(it, style), bulletColor=CYAN) for it in items],
        bulletType="bullet", start="•", bulletFontSize=10,
        leftIndent=16, bulletOffsetY=-1, spaceAfter=8
    )

def _kv_table(rows, col_widths, style_body):
    """Key-value style table with alternating rows."""
    data = [[Paragraph(f"<b>{r[0]}</b>", style_body),
             Paragraph(r[1], style_body)] for r in rows]
    t = Table(data, colWidths=col_widths, hAlign="LEFT")
    row_styles = [
        ("BACKGROUND", (0, i), (-1, i),
         colors.HexColor("#F8FAFC") if i % 2 == 0 else colors.white)
        for i in range(len(data))
    ]
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#E2E8F0")),
    ] + row_styles))
    return t

def _tech_table(data_rows, col_widths, style_body):
    """Table with header row."""
    header = data_rows[0]
    body = data_rows[1:]
    cells = []
    cells.append([Paragraph(f"<b>{c}</b>", style_body) for c in header])
    for row in body:
        cells.append([Paragraph(c, style_body) for c in row])
    t = Table(cells, colWidths=col_widths, hAlign="LEFT")
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), SLATE),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#E2E8F0")),
    ] + [
        ("BACKGROUND", (0, i + 1), (-1, i + 1),
         colors.HexColor("#F8FAFC") if i % 2 == 0 else colors.white)
        for i in range(len(body))
    ]))
    return t


# ── CONTENT BUILDERS ─────────────────────────────────────────────────

def _build_toc(S, W):
    """Table of Contents."""
    elements = []
    elements.append(Paragraph("Table of Contents", S["h1"]))
    elements.append(_accent_bar(120))
    elements.append(Spacer(1, 6))
    toc_entries = [
        ("01", "Executive Summary"),
        ("02", "Problem Statement"),
        ("03", "Our Solution — ArchVision"),
        ("04", "System Architecture"),
        ("05", "Two-Step AI Pipeline — Deep Dive"),
        ("06", "Technology Stack"),
        ("07", "Backend Architecture"),
        ("08", "Frontend Architecture"),
        ("09", "Core Data Structures & Schema"),
        ("10", "Key Features Showcase"),
        ("11", "Wi-Fi Deadzone Mapper — Downstream Application"),
        ("12", "Security & Authentication"),
        ("13", "Development Workflow"),
        ("14", "Challenges & Learnings"),
        ("15", "Future Roadmap"),
        ("16", "Team"),
    ]
    for num, title in toc_entries:
        elements.append(Paragraph(
            f'<font color="{CYAN.hexval()}">{num}</font>&nbsp;&nbsp;&nbsp;{title}',
            S["toc_item"]))
    elements.append(PageBreak())
    return elements


def _build_executive_summary(S, W):
    elements = []
    elements.append(_section("01", "Executive Summary", W))
    elements.append(Spacer(1, 10))
    elements.append(Paragraph(
        "<b>ArchVision</b> is a hybrid AI-powered web application that transforms 2D architectural "
        "floor plan images and PDFs into rich, structured JSON data — complete with room geometries, "
        "semantic labels, parsed dimensions, area calculations, and confidence scores.", S["body"]))
    elements.append(Paragraph(
        "The system combines <b>YOLOv8 instance segmentation</b> for room detection with <b>dual-path "
        "OCR</b> (EasyOCR + PaddleOCR) for text extraction, wrapped in a modern <b>React + FastAPI</b> "
        "full-stack application featuring interactive SVG viewers, analytics dashboards, printable "
        "spatial reports, and a Wi-Fi signal simulation proof-of-concept.", S["body"]))
    elements.append(Spacer(1, 4))

    highlights = [
        "<b>Smart PDF Extraction</b> — YOLO-validated pipeline filters only real 2D floor plans from multi-page brochure PDFs.",
        "<b>Per-Room OCR</b> — Targeted text extraction within each detected room's bounding box for superior accuracy.",
        "<b>Interactive Viewer</b> — SVG overlay with zoom, pan, colour-coded polygons, and room selection.",
        "<b>Analytics Suite</b> — KPIs, doughnut charts, radar profiles, and ranked bar charts via Recharts.",
        "<b>Spatial Report</b> — Printable audit document with HVAC and LED estimates.",
        "<b>Wi-Fi Mapper</b> — Downstream application using Euclidean distance for signal simulation.",
        "<b>OAuth2 Social Login</b> — Google and GitHub authentication alongside JWT email/password.",
    ]
    elements.append(_bullet_list(highlights, S["bullet"]))
    elements.append(PageBreak())
    return elements


def _build_problem_statement(S, W):
    elements = []
    elements.append(_section("02", "Problem Statement", W))
    elements.append(Spacer(1, 10))
    elements.append(Paragraph(
        "Architectural floor plans remain one of the most information-dense documents in the "
        "construction and real estate industries. Yet extracting structured, machine-readable data "
        "from these drawings is still a largely <b>manual, error-prone, and time-consuming</b> process.", S["body"]))
    elements.append(Spacer(1, 4))
    elements.append(Paragraph("The Theoretical Gap", S["h2"]))
    problems = [
        "<b>No automated room segmentation</b> — Existing tools cannot reliably detect individual room boundaries from 2D plans.",
        "<b>OCR fails on architectural text</b> — Standard OCR struggles with rotated dimension text, overlapping labels, and mixed fonts common in floor plans.",
        "<b>PDF brochures contain noise</b> — Real estate PDFs mix floor plans with photographs, logos, amenity renders, and marketing pages — naive extraction captures everything.",
        "<b>No structured output</b> — Even when rooms are identified, converting visual data into a standardized, queryable JSON schema is an unsolved integration challenge.",
        "<b>Downstream applications blocked</b> — Without structured spatial data, applications like smart building analytics, HVAC estimation, and signal simulation cannot be automated.",
    ]
    elements.append(_bullet_list(problems, S["bullet"]))
    elements.append(PageBreak())
    return elements


def _build_solution(S, W):
    elements = []
    elements.append(_section("03", "Our Solution — ArchVision", W))
    elements.append(Spacer(1, 10))
    elements.append(Paragraph(
        "ArchVision addresses every gap identified above through a <b>modular, two-step AI pipeline</b> "
        "wrapped in a production-grade full-stack web application.", S["body"]))
    elements.append(Spacer(1, 4))

    rows = [
        ("Input Formats", "PDF brochures, PNG, JPG, BMP, TIFF"),
        ("AI Models", "YOLOv8-Seg (segmentation) + EasyOCR + PaddleOCR (dual-path OCR)"),
        ("Output", "Frontend Schema v1.0.0 JSON — rooms with geometry, labels, dimensions, area, confidence"),
        ("Web Stack", "React 18 + TypeScript + Tailwind (frontend) — FastAPI + SQLite (backend)"),
        ("Auth", "JWT email/password + OAuth2 (Google, GitHub)"),
        ("Deployment", "Monorepo — Vite dev server proxying to FastAPI"),
    ]
    elements.append(_kv_table(rows, [110, W - 120], S["body_small"]))
    elements.append(PageBreak())
    return elements


def _build_architecture(S, W):
    elements = []
    elements.append(_section("04", "System Architecture", W))
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("High-Level Architecture", S["h2"]))
    elements.append(Paragraph(
        "The system follows a clean three-tier architecture with a decoupled frontend, API layer, "
        "and AI pipeline backend.", S["body"]))
    elements.append(Spacer(1, 6))

    arch_data = [
        ["Layer", "Technology", "Responsibility"],
        ["Presentation", "React + Vite + Tailwind", "Interactive UI, SVG viewer, analytics dashboards"],
        ["API Gateway", "FastAPI + SQLAlchemy", "REST endpoints, JWT/OAuth auth, job management"],
        ["AI Pipeline", "YOLOv8 + OCR Engines", "Room detection, text extraction, semantic parsing"],
        ["PDF Extraction", "PyMuPDF + YOLO Validator", "Smart floor plan crop extraction from PDFs"],
        ["Storage", "SQLite + File System", "User data, analysis jobs, uploads, results"],
    ]
    elements.append(_tech_table(arch_data, [80, 130, W - 220], S["body_small"]))
    elements.append(Spacer(1, 8))

    elements.append(Paragraph("Data Flow", S["h2"]))
    flow_text = (
        "Input (PDF/Image) → <b>[PDF?]</b> Smart Extraction (120 DPI scoring → 450 DPI YOLO validation → "
        "region detection → crop validation) → <b>YOLOv8-Seg</b> room instance detection → "
        "<b>Per-Room OCR</b> text extraction → <b>Semantic Parser</b> label/dimension structuring → "
        "<b>Frontend Schema Builder</b> JSON output → <b>Visualization</b> overlay + interactive viewer"
    )
    elements.append(Paragraph(flow_text, S["body"]))
    elements.append(PageBreak())
    return elements


def _build_pipeline_deep_dive(S, W):
    elements = []
    elements.append(_section("05", "Two-Step AI Pipeline — Deep Dive", W))
    elements.append(Spacer(1, 10))

    # Step 1
    elements.append(Paragraph("Step 1: Smart PDF Floor Plan Extraction", S["h2"]))
    elements.append(Paragraph(
        "The <b>PDFFloorPlanExtractor</b> is a multi-stage filtering pipeline that ensures only genuine "
        "2D floor plan crops are extracted from brochure PDFs. This is critical because real estate PDFs "
        "contain photographs, logos, amenity renders, and marketing content.", S["body"]))
    elements.append(Spacer(1, 4))

    stages = [
        "<b>Page Scoring (120 DPI thumbnails)</b> — Each page is rendered as a low-res thumbnail and scored using text analysis (room keywords like 'bedroom', 'kitchen' vs negative keywords like 'luxury', 'spa') combined with image features (edge ratio, line count, orthogonal line ratio, colourfulness). Minimum score: 0.55.",
        "<b>YOLO Page Validation (450 DPI)</b> — Qualifying pages are rendered at full resolution and validated with the YOLO model to confirm room presence.",
        "<b>Region Detection</b> — Edge detection + morphological operations + connected components identify up to 4 candidate floor plan regions per page.",
        "<b>YOLO Crop Validation</b> — Each candidate crop is validated independently; only crops with ≥3 detected rooms pass through.",
    ]
    elements.append(_bullet_list(stages, S["bullet"]))

    config_rows = [
        ("DPI (full render)", "450"),
        ("Thumbnail DPI", "120"),
        ("Min page score", "0.55"),
        ("Min crop score", "0.60"),
        ("Validator", "YOLO"),
        ("Min rooms per crop", "3"),
        ("Target long side", "4096 px"),
        ("Scan all pages", "True"),
    ]
    elements.append(Paragraph("Extraction Configuration", S["h3"]))
    elements.append(_kv_table(config_rows, [120, 100], S["body_small"]))
    elements.append(Spacer(1, 8))

    # Step 2
    elements.append(Paragraph("Step 2: Floor Plan Analysis", S["h2"]))
    analysis_stages = [
        "<b>Room Instance Segmentation</b> — YOLOv8-Seg model (conf=0.35, IoU=0.5, img_size=640) detects rooms with pixel-level segmentation masks. Overlapping detections filtered at IoU > 0.85.",
        "<b>Per-Room OCR</b> — Each room's bounding box (padded by 20px) is cropped and passed to EasyOCR (primary) or PaddleOCR (fallback). Text tokens include confidence and bounding box data.",
        "<b>Semantic Parsing</b> — Extracted text is parsed to identify room labels (e.g., 'Bedroom'), dimension strings (e.g., 12'6\" × 10'), and area text (e.g., '125 SQFT'). Dimensions are decomposed into feet + inches with computed area.",
        "<b>Geometry Processing</b> — Raw segmentation masks are converted to Shapely polygons, simplified (tolerance=2.0), and enriched with centroids, bounding boxes, and pixel areas.",
        "<b>Schema Generation</b> — All data is assembled into Frontend Schema v1.0.0 JSON for consumption by the web application.",
    ]
    elements.append(_bullet_list(analysis_stages, S["bullet"]))
    elements.append(PageBreak())
    return elements


def _build_tech_stack(S, W):
    elements = []
    elements.append(_section("06", "Technology Stack", W))
    elements.append(Spacer(1, 10))

    elements.append(Paragraph("AI & Backend", S["h2"]))
    be_data = [
        ["Technology", "Version / Variant", "Purpose"],
        ["Python", "3.10+", "Core backend language"],
        ["FastAPI", "0.110+", "Async REST API framework"],
        ["YOLOv8-Seg", "Ultralytics", "Room instance segmentation with masks"],
        ["EasyOCR", "Latest", "Primary OCR engine for text extraction"],
        ["PaddleOCR", "Latest", "Fallback OCR engine for robustness"],
        ["PyMuPDF (fitz)", "Latest", "PDF text extraction and image rendering"],
        ["OpenCV", "Headless", "Image processing, edge detection, morphology"],
        ["Shapely", "Latest", "Polygon operations and spatial analysis"],
        ["SQLAlchemy", "Latest", "ORM for SQLite database access"],
        ["PyTorch", "CPU build", "ML backend for YOLO inference"],
        ["NumPy / Pillow", "Latest", "Array operations and image I/O"],
    ]
    elements.append(_tech_table(be_data, [90, 90, W - 190], S["body_small"]))
    elements.append(Spacer(1, 10))

    elements.append(Paragraph("Frontend & Visualization", S["h2"]))
    fe_data = [
        ["Technology", "Version", "Purpose"],
        ["React", "18", "Component-based UI framework"],
        ["TypeScript", "5+", "Type-safe frontend development"],
        ["Vite", "5", "Fast dev server and build tool"],
        ["Tailwind CSS", "3", "Utility-first styling"],
        ["shadcn/ui + Radix", "Latest", "Accessible UI component primitives"],
        ["Recharts", "Latest", "Charts: doughnut, radar, bar, pie"],
        ["Framer Motion", "Latest", "Animations: heatmap pulse, transitions"],
        ["TanStack Query", "Latest", "Server-state data fetching and caching"],
        ["Axios", "Latest", "HTTP client with JWT interceptors"],
        ["React Router", "v6", "Client-side routing"],
    ]
    elements.append(_tech_table(fe_data, [100, 60, W - 170], S["body_small"]))
    elements.append(PageBreak())
    return elements


def _build_backend_arch(S, W):
    elements = []
    elements.append(_section("07", "Backend Architecture", W))
    elements.append(Spacer(1, 10))

    elements.append(Paragraph("Directory Structure", S["h3"]))
    dir_items = [
        "<b>main.py</b> — FastAPI app entry point with lifespan, CORS, 4 routers, /api/health",
        "<b>config.py</b> — Paths, secrets, OAuth creds, file limits",
        "<b>database.py</b> — SQLAlchemy engine + SessionLocal + get_db dependency",
        "<b>models.py</b> — ORM: User (email, hashed_password, full_name) and AnalysisJob (status, result_json, metrics)",
        "<b>auth.py</b> — JWT creation + bcrypt hashing + get_current_user dependency",
        "<b>routes/auth_routes.py</b> — POST register, POST login, GET me",
        "<b>routes/oauth_routes.py</b> — Google & GitHub OAuth flows with CSRF state cookies",
        "<b>routes/analysis_routes.py</b> — POST analyze, GET list, GET detail, GET download, DELETE, GET dashboard",
        "<b>routes/files_routes.py</b> — Public file serving (UUID filename security)",
        "<b>services/pipeline_service.py</b> — Singleton AI pipeline wrapper (mirrors Kaggle notebook)",
    ]
    elements.append(_bullet_list(dir_items, S["bullet"]))

    elements.append(Paragraph("API Endpoints Summary", S["h2"]))
    api_data = [
        ["Endpoint", "Method", "Auth", "Description"],
        ["/api/auth/register", "POST", "No", "Create account → JWT"],
        ["/api/auth/login", "POST", "No", "Authenticate → JWT"],
        ["/api/auth/me", "GET", "JWT", "Current user profile"],
        ["/api/auth/google", "GET", "No", "Redirect to Google OAuth"],
        ["/api/auth/github", "GET", "No", "Redirect to GitHub OAuth"],
        ["/api/analyze", "POST", "JWT", "Upload + analyze file"],
        ["/api/analyses", "GET", "JWT", "Paginated job list"],
        ["/api/analyses/{id}", "GET", "JWT", "Job detail with JSON"],
        ["/api/analyses/{id}/download", "GET", "JWT", "Download result JSON"],
        ["/api/dashboard", "GET", "JWT", "Aggregated statistics"],
        ["/api/files/uploads/{name}", "GET", "No", "Serve uploaded file"],
        ["/api/files/results/{id}/{name}", "GET", "No", "Serve result file"],
        ["/api/health", "GET", "No", "Health check"],
    ]
    elements.append(_tech_table(api_data, [130, 40, 30, W - 210], S["body_small"]))
    elements.append(PageBreak())
    return elements


def _build_frontend_arch(S, W):
    elements = []
    elements.append(_section("08", "Frontend Architecture", W))
    elements.append(Spacer(1, 10))

    elements.append(Paragraph(
        "The frontend is a single-page React application with a <b>\"Deep Blue Galaxy\"</b> design system — "
        "dark glassmorphism with cyan accents, Space Grotesk typography, and rich CSS animations.", S["body"]))
    elements.append(Spacer(1, 4))

    elements.append(Paragraph("Page Routing", S["h2"]))
    routes = [
        ["Route", "Component", "Access", "Description"],
        ["/login", "Login", "Public", "Glassmorphic login + OAuth buttons"],
        ["/register", "Register", "Public", "Registration form"],
        ["/auth/callback", "OAuthCallback", "Public", "OAuth redirect handler"],
        ["/dashboard", "Dashboard", "Protected", "Overview + How It Works + Tech Stack"],
        ["/upload", "Upload", "Protected", "Drag-and-drop + PipelineOverlay animation"],
        ["/analysis/:id", "AnalysisView", "Protected", "Viewer + Analytics + Report + Wi-Fi"],
        ["/history", "History", "Protected", "Paginated analysis table"],
        ["/introduction", "ProjectIntro", "Protected", "Intelligence for Spatial Design"],
        ["/founders", "Founders", "Protected", "Team bio cards"],
        ["/wifi-mapper", "WifiMapper", "Protected", "Wi-Fi signal simulation"],
    ]
    elements.append(_tech_table(routes, [85, 80, 52, W - 227], S["body_small"]))
    elements.append(Spacer(1, 8))

    elements.append(Paragraph("Key UI Components", S["h2"]))
    components = [
        "<b>TelemetryBar</b> — Fixed top bar with LIVE system status marquee (OpenCV, EasyOCR telemetry).",
        "<b>PipelineOverlay</b> — Full-screen 4-step animated stepper (INGEST → SEGMENT → RECOGNIZE → FUSE) shown during analysis.",
        "<b>FloorPlanViewer</b> — Interactive SVG overlay with zoom (scroll/buttons), pan (Ctrl+click), colour-coded room polygons, hover tooltips, and centroid labels.",
        "<b>RoomDetailPanel</b> — Selected room details: parsed dimensions, area, confidence bars, geometry info.",
        "<b>AnalyticsDashboard</b> — Full Recharts suite: 4 KPI hero cards, doughnut (space allocation), radar (architectural balance), horizontal bar (room hierarchy).",
        "<b>SpatialReport</b> — Portal-rendered printable audit: segmented blueprint, spatial data matrix, HVAC/LED estimates.",
        "<b>HowItWorks</b> — Two-step pipeline explainer with lightbox images and animated data-stream connectors.",
        "<b>TechStack</b> — Custom SVG logo grid with brand-colour hover glows.",
    ]
    elements.append(_bullet_list(components, S["bullet"]))
    elements.append(PageBreak())
    return elements


def _build_data_schema(S, W):
    elements = []
    elements.append(_section("09", "Core Data Structures & Schema", W))
    elements.append(Spacer(1, 10))

    elements.append(Paragraph("Frontend Schema v1.0.0 — Output Format", S["h2"]))
    elements.append(Paragraph(
        "Every analysis produces a JSON document following this standardised schema, enabling "
        "consistent consumption by the frontend viewer, analytics, and downstream applications.", S["body"]))
    elements.append(Spacer(1, 4))

    schema_rows = [
        ["Field", "Type", "Description"],
        ["schema_version", "string", "Always '1.0.0'"],
        ["generated_at", "ISO datetime", "Timestamp of analysis"],
        ["source.type", "pdf | image", "Input file type"],
        ["pages[].rooms[].id", "integer", "Unique room identifier"],
        ["rooms[].label", "string", "Semantic room label (Bedroom, Kitchen, etc.)"],
        ["rooms[].dimensions", "string", "Raw dimension text (12'6\" x 10')"],
        ["rooms[].dimensions_parsed", "object", "Decomposed: width_ft, width_in, height_ft, height_in, area_sqft"],
        ["rooms[].area.value_sqft", "float", "Area in square feet"],
        ["rooms[].area.source", "string", "computed_from_dimensions | ocr_text | none"],
        ["rooms[].confidence", "object", "geometry, label, dimensions scores (0-1)"],
        ["rooms[].geometry.polygon", "int[][]", "Simplified polygon coordinates"],
        ["rooms[].geometry.centroid", "object", "{ x, y } centre point"],
        ["rooms[].geometry.bbox", "object", "{ x1, y1, x2, y2 } bounding box"],
    ]
    elements.append(_tech_table(schema_rows, [120, 70, W - 200], S["body_small"]))
    elements.append(Spacer(1, 8))

    elements.append(Paragraph("Internal Data Classes", S["h2"]))
    internal = [
        "<b>OCRToken</b> — text, conf, box (polygon coords), box_poly (Shapely), source ('ocr' | 'pdf_text'), meta dict.",
        "<b>RoomInstance</b> — id, yolo_conf, mask (ndarray), polygon, polygon_simplified, bbox, centroid, area_px2, label, label_confidence, dimensions_text, dimension_parsed, area_text, area_ft2, ocr_tokens, ocr_lines, ocr_merged_text.",
        "<b>PipelineConfig</b> — model_path, yolo_img_size (640), yolo_conf (0.35), yolo_iou (0.5), polygon_simplify_tol (2.0), room_crop_pad (20), ocr_mode ('per_room'), device ('auto'), text_source ('auto').",
    ]
    elements.append(_bullet_list(internal, S["bullet"]))
    elements.append(PageBreak())
    return elements


def _build_features(S, W):
    elements = []
    elements.append(_section("10", "Key Features Showcase", W))
    elements.append(Spacer(1, 10))

    features = [
        ("Smart PDF Extraction",
         "YOLO-validated multi-stage pipeline filters real 2D floor plans from noisy brochure PDFs. "
         "Combines text scoring, image feature analysis, and neural network validation to achieve "
         "near-zero false positive extraction."),
        ("Interactive Floor Plan Viewer",
         "SVG overlay on the original image with colour-coded room polygons, zoom/pan controls, "
         "room selection, hover tooltips with dimensions, and centroid labels. Keyboard shortcut "
         "(Escape) to deselect."),
        ("Dual-Path OCR Engine",
         "EasyOCR as primary engine with PaddleOCR fallback. Per-room cropping with configurable "
         "padding ensures text extraction is contextually targeted rather than full-image."),
        ("Analytics Dashboard",
         "Four animated KPI cards (total area, room count, largest space, efficiency gauge), "
         "doughnut chart for space allocation, radar chart for architectural balance, and "
         "horizontal bar chart ranking rooms by area."),
        ("Printable Spatial Report",
         "One-click export generates a professional audit document with document ID, segmented "
         "blueprint, spatial data matrix, occupancy types, and smart building estimates (HVAC "
         "tonnage, LED wattage). Rendered via React Portal for clean print styling."),
        ("Animated Pipeline Overlay",
         "Full-screen 4-step stepper animation (INGEST → SEGMENT → RECOGNIZE → FUSE) with "
         "spinning dashed rings, scan-line thumbnail preview, and timed step transitions."),
        ("OAuth2 Social Login",
         "Google and GitHub authentication with CSRF state cookies, find-or-create user pattern, "
         "and seamless JWT token handoff to the SPA via redirect callback."),
    ]
    for title, desc in features:
        elements.append(Paragraph(title, S["h2"]))
        elements.append(Paragraph(desc, S["body"]))
    elements.append(PageBreak())
    return elements


def _build_wifi_mapper(S, W):
    elements = []
    elements.append(_section("11", "Wi-Fi Deadzone Mapper — Downstream Application", W))
    elements.append(Spacer(1, 10))

    elements.append(Paragraph(
        "The Wi-Fi Deadzone Mapper is a <b>proof-of-concept downstream application</b> demonstrating "
        "that ArchVision's structured output enables real-world spatial analytics beyond simple "
        "visualization.", S["body"]))
    elements.append(Spacer(1, 4))

    elements.append(Paragraph("How It Works", S["h2"]))
    wifi_steps = [
        "<b>Data Handoff</b> — AnalysisView maps pipeline rooms to {id, label, x, y, area} using centroids and saves to localStorage alongside the blueprint image URL.",
        "<b>Coordinate Transformation</b> — Pipeline centroids (original image pixel space) are mapped to the scaled container using CSS object-contain math: scale = min(cW/nW, cH/nH), with letterbox offset.",
        "<b>Signal Calculation</b> — MAX_RANGE = container diagonal × 0.85. Raw signal = max(0, 100 − (distance / MAX_RANGE) × 100). Wall penalty: −15% per non-router room crossed.",
        "<b>Heatmap Visualization</b> — Framer Motion pulsing radial gradient (1400px, 3s infinite easeInOut) at router position. Node colours: Cyan (≥80%), Amber (40–79%), Rose (&lt;40%).",
        "<b>Analytics Panel</b> — Average signal metric, Recharts vertical BarChart with conditional cell colours, and signal tier legend.",
    ]
    elements.append(_bullet_list(wifi_steps, S["bullet"]))
    elements.append(PageBreak())
    return elements


def _build_security(S, W):
    elements = []
    elements.append(_section("12", "Security & Authentication", W))
    elements.append(Spacer(1, 10))

    sec_rows = [
        ("JWT Tokens", "24-hour expiration, HS256 algorithm, stored in localStorage"),
        ("Password Hashing", "bcrypt (direct, not passlib) for all user passwords"),
        ("OAuth2 CSRF", "State parameter in signed cookie, verified on callback"),
        ("File Upload Validation", "Type whitelist (PNG, JPG, PDF, BMP, TIFF), 50 MB max"),
        ("Path Traversal Protection", "Filename sanitisation on file-serving endpoints"),
        ("CORS Policy", "Configured for specific origins (localhost:8080, 5173)"),
        ("File Serving Security", "Public endpoints secured via UUID-prefixed filenames"),
        ("OAuth User Creation", "Random bcrypt hash for OAuth-created users (no reusable password)"),
        ("API Authorization", "Bearer token required on all /api/analyze, /api/analyses, /api/dashboard"),
    ]
    elements.append(_kv_table(sec_rows, [130, W - 140], S["body_small"]))
    elements.append(PageBreak())
    return elements


def _build_dev_workflow(S, W):
    elements = []
    elements.append(_section("13", "Development Workflow", W))
    elements.append(Spacer(1, 10))

    elements.append(Paragraph("Running the Backend", S["h2"]))
    elements.append(Paragraph(
        "<font face='Courier' size='9'>python -m uvicorn backend.main:app --reload --port 8000</font>", S["code"]))
    elements.append(Paragraph(
        "API documentation available at <b>http://127.0.0.1:8000/docs</b> (Swagger UI).", S["body"]))

    elements.append(Paragraph("Running the Frontend", S["h2"]))
    elements.append(Paragraph(
        "<font face='Courier' size='9'>cd archvision-login-glow-main &amp;&amp; npm run dev</font>", S["code"]))
    elements.append(Paragraph(
        "Dev server at <b>http://localhost:8080</b> with Vite proxy forwarding /api → backend.", S["body"]))

    elements.append(Paragraph("Environment Variables", S["h2"]))
    env_rows = [
        ("ARCHVISION_SECRET_KEY", "JWT signing secret"),
        ("ARCHVISION_MODEL_PATH", "Path to YOLOv8 best.pt weights"),
        ("GOOGLE_CLIENT_ID / SECRET", "Google OAuth credentials"),
        ("GITHUB_CLIENT_ID / SECRET", "GitHub OAuth credentials"),
        ("ARCHVISION_FRONTEND_URL", "http://localhost:8080"),
        ("ARCHVISION_BACKEND_URL", "http://localhost:8000"),
    ]
    elements.append(_kv_table(env_rows, [150, W - 160], S["body_small"]))
    elements.append(PageBreak())
    return elements


def _build_challenges(S, W):
    elements = []
    elements.append(_section("14", "Challenges & Learnings", W))
    elements.append(Spacer(1, 10))

    challenges = [
        ("<b>PDF Noise Filtering</b>", "Real estate brochure PDFs contain photographs, amenity renders, logos, and marketing pages alongside actual floor plans. Naive extraction produced 80%+ false positives. Solution: multi-stage scoring (text + image features) combined with YOLO validation at both page and crop levels reduced false positives to near zero."),
        ("<b>OCR Accuracy on Architectural Text</b>", "Dimension strings (12'6\" × 10') use special characters and mixed fonts that confuse standard OCR. Solution: per-room cropping with padding isolates text context, and dual-engine fallback (EasyOCR → PaddleOCR) maximises extraction recall."),
        ("<b>Coordinate Space Mapping</b>", "Pipeline outputs centroids in original image pixel coordinates, but the frontend renders images with CSS object-contain scaling. Misaligned coordinates caused Wi-Fi mapper nodes to appear in wrong positions. Solution: compute scale + letterbox offset to transform coordinates."),
        ("<b>Large PDF Processing Time</b>", "Multi-page PDFs at 450 DPI with YOLO inference per page/crop created long processing times. Solution: 120 DPI thumbnail pre-screening eliminates non-candidate pages before expensive full-resolution rendering, and a 10-minute timeout with animated PipelineOverlay keeps users informed."),
        ("<b>OAuth Integration Complexity</b>", "Handling CSRF state, cookie signing, token exchange, and find-or-create user patterns across Google and GitHub required careful async HTTP flows. Solution: httpx.AsyncClient with state cookies and unified JWT handoff via redirect callback."),
    ]
    for title, desc in challenges:
        elements.append(Paragraph(title, S["h2"]))
        elements.append(Paragraph(desc, S["body"]))
    elements.append(PageBreak())
    return elements


def _build_roadmap(S, W):
    elements = []
    elements.append(_section("15", "Future Roadmap", W))
    elements.append(Spacer(1, 10))

    roadmap = [
        "<b>3D Model Generation</b> — Extrude detected room polygons into 3D meshes for virtual walkthroughs using Three.js or Blender integration.",
        "<b>Multi-Model Ensemble</b> — Combine YOLOv8 with Mask R-CNN and SAM (Segment Anything Model) for improved segmentation on complex plans.",
        "<b>Dimension Line Detection</b> — Train a dedicated model to detect dimension line annotations (arrows, tick marks) for more accurate measurement extraction.",
        "<b>Real-Time Collaboration</b> — WebSocket-based multi-user editing of floor plan annotations with conflict resolution.",
        "<b>Cloud Deployment</b> — Dockerised deployment on AWS/GCP with GPU-accelerated inference, S3 storage, and PostgreSQL.",
        "<b>Mobile Application</b> — React Native companion app for on-site floor plan capture and instant analysis.",
        "<b>Custom YOLO Training UI</b> — In-app interface for users to annotate and fine-tune the YOLO model on their specific floor plan styles.",
        "<b>HVAC & Electrical Layout</b> — Extend the pipeline to detect and place HVAC ducts, electrical outlets, and plumbing fixtures.",
    ]
    elements.append(_bullet_list(roadmap, S["bullet"]))
    elements.append(PageBreak())
    return elements


def _build_team(S, W):
    elements = []
    elements.append(_section("16", "Team", W))
    elements.append(Spacer(1, 10))

    elements.append(Paragraph(
        "ArchVision was built by a team of five students from the <b>Institute of Advanced Research (IAR)</b> "
        "as part of their 6th semester project.", S["body"]))
    elements.append(Spacer(1, 6))

    team_data = [
        ["Name", "Role", "Contribution"],
        ["Parth Talsania", "Project Lead / Full-Stack", "Architecture design, AI pipeline, backend API, frontend UI, integration"],
        ["Mohammed Ayaan", "AI / ML Engineer", "YOLO model training, segmentation pipeline, OCR integration"],
        ["Abhishek Rathod", "Backend Developer", "FastAPI endpoints, database models, authentication system"],
        ["Harshil Darji", "Frontend Developer", "React components, interactive viewer, analytics dashboard"],
        ["Heli Darji", "UI/UX & Testing", "Design system, user experience, quality assurance"],
    ]
    elements.append(_tech_table(team_data, [100, 100, W - 210], S["body_small"]))
    elements.append(Spacer(1, 20))

    # Closing
    elements.append(_hr())
    elements.append(Spacer(1, 10))
    elements.append(Paragraph(
        "<i>Thank you for reviewing the ArchVision project report. This document provides a "
        "comprehensive technical overview of our hybrid AI floor plan analysis pipeline and "
        "its full-stack web application.</i>", S["center"]))
    elements.append(Spacer(1, 8))
    elements.append(Paragraph(
        "<b>Prepared:</b> February 24, 2026 at 19:29", S["center"]))
    return elements


# ── MAIN ─────────────────────────────────────────────────────────────
def generate_report():
    doc = SimpleDocTemplate(
        OUTPUT_PATH,
        pagesize=A4,
        leftMargin=22 * mm,
        rightMargin=22 * mm,
        topMargin=22 * mm,
        bottomMargin=22 * mm,
        title="ArchVision — Hackathon Project Report",
        author="Team ArchVision",
        subject="Hybrid AI Floor Plan Analysis Pipeline",
    )

    usable_width = A4[0] - 44 * mm
    S = _build_styles()
    elements = []

    # Cover page placeholder (drawn by _cover_page callback on first page)
    # Just need an empty spacer + page break; cover art is drawn on canvas
    elements.append(Spacer(1, 1))
    elements.append(PageBreak())

    # Table of Contents
    elements.extend(_build_toc(S, usable_width))

    # Sections
    elements.extend(_build_executive_summary(S, usable_width))
    elements.extend(_build_problem_statement(S, usable_width))
    elements.extend(_build_solution(S, usable_width))
    elements.extend(_build_architecture(S, usable_width))
    elements.extend(_build_pipeline_deep_dive(S, usable_width))
    elements.extend(_build_tech_stack(S, usable_width))
    elements.extend(_build_backend_arch(S, usable_width))
    elements.extend(_build_frontend_arch(S, usable_width))
    elements.extend(_build_data_schema(S, usable_width))
    elements.extend(_build_features(S, usable_width))
    elements.extend(_build_wifi_mapper(S, usable_width))
    elements.extend(_build_security(S, usable_width))
    elements.extend(_build_dev_workflow(S, usable_width))
    elements.extend(_build_challenges(S, usable_width))
    elements.extend(_build_roadmap(S, usable_width))
    elements.extend(_build_team(S, usable_width))

    doc.build(
        elements,
        onFirstPage=_cover_page,
        onLaterPages=_header_footer,
    )
    print(f"\n✅  Report generated: {OUTPUT_PATH}")
    print(f"    Pages: ~18  |  Sections: 16  |  Format: A4 PDF")


if __name__ == "__main__":
    generate_report()
