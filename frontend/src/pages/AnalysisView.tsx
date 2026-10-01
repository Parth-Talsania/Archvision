import { useEffect, useState, useRef, useCallback } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import { ArrowLeft, Download, Home, Tag, Ruler, Loader2, Image as ImageIcon, Layers, BarChart3, Eye, FileText, Wifi } from "lucide-react";
import api from "@/api/client";
import FloorPlanViewer from "@/components/FloorPlanViewer";
import RoomDetailPanel from "@/components/RoomDetailPanel";
import AnalyticsDashboard from "@/components/AnalyticsDashboard";
import CostEstimator from "@/components/CostEstimator";
import PropertySummary from "@/components/PropertySummary";
import SpatialReport from "@/components/SpatialReport";
import type { PageImage, ResultJson, ResultPage, Room } from "@/types/analysis";

/* ------------------------------------------------------------------ */
/* Types                                                               */
/* ------------------------------------------------------------------ */

interface AnalysisData {
  id: number;
  filename: string;
  file_type: string;
  status: string;
  error_message: string | null;
  result_json: ResultJson | null;
  total_rooms: number | null;
  rooms_with_labels: number | null;
  rooms_with_dimensions: number | null;
  created_at: string;
}

interface LegendItem {
  label: string;
  color: string;
}

/* ------------------------------------------------------------------ */
/* Colour Legend                                                        */
/* ------------------------------------------------------------------ */

function ColorLegend({ items }: { items: LegendItem[] }) {
  if (!items || items.length === 0) return null;
  return (
    <div className="flex flex-wrap gap-3 rounded-lg border border-[rgba(56,189,248,0.15)] bg-[#0F172A]/60 backdrop-blur-xl px-4 py-3">
      <span className="text-xs font-semibold uppercase tracking-wider text-[#94A3B8]">Legend</span>
      {items.map((item) => (
        <div key={item.label} className="flex items-center gap-1.5">
          <span
            className="inline-block h-3 w-3 rounded-sm border border-white/20"
            style={{ backgroundColor: item.color }}
          />
          <span className="text-xs text-white">{item.label}</span>
        </div>
      ))}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Image Gallery (for extracted / segmented images)                    */
/* ------------------------------------------------------------------ */

function ImageGallery({ title, icon, images }: { title: string; icon: React.ReactNode; images: { page: number; url: string }[] }) {
  if (!images || images.length === 0) return null;
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        {icon}
        <h2 className="text-sm font-semibold text-white">{title}</h2>
        <span className="rounded-full bg-secondary px-2 py-0.5 text-xs text-[#94A3B8]">{images.length}</span>
      </div>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {images.map((img) => (
          <div key={img.url} className="overflow-hidden rounded-lg border border-[rgba(56,189,248,0.15)] bg-[#0F172A]/60 backdrop-blur-xl">
            <img
              src={img.url}
              alt={`Page ${img.page}`}
              className="w-full object-contain"
              loading="lazy"
            />
            <div className="border-t border-[rgba(56,189,248,0.15)] px-3 py-1.5 text-xs text-[#94A3B8]">
              Page {img.page}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Main Component                                                      */
/* ------------------------------------------------------------------ */

export default function AnalysisView() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [data, setData] = useState<AnalysisData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedRoomId, setSelectedRoomId] = useState<number | null>(null);
  const [activePageIdx, setActivePageIdx] = useState(0);
  const [activeTab, setActiveTab] = useState<"viewer" | "analytics" | "cost">("viewer");
  const [showReport, setShowReport] = useState(false);
  const reportRef = useRef<HTMLDivElement>(null);

  const handlePrintReport = useCallback(() => {
    setShowReport(true);
    // Give React a tick to render the hidden report DOM, then print
    setTimeout(() => {
      window.print();
    }, 350);
  }, []);

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    setError(null);
    api
      .get(`/analyses/${id}`)
      .then((res) => {
        setData(res.data);
        setLoading(false);
      })
      .catch((err) => {
        const msg = err.response?.data?.detail || err.message || "Failed to load analysis";
        setError(msg);
        setLoading(false);
      });
  }, [id]);

  if (loading) {
    return (
      <div className="flex h-96 items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-[#0EA5E9]" />
      </div>
    );
  }

  if (!data) {
    return (
      <div className="flex h-96 flex-col items-center justify-center">
        <p className="text-[#94A3B8]">{error || "Analysis not found"}</p>
        <Link to="/history" className="mt-2 text-sm text-[#0EA5E9] hover:text-[#0EA5E9]/80">
          Back to History
        </Link>
      </div>
    );
  }

  if (data.status === "processing") {
    return (
      <div className="flex h-96 flex-col items-center justify-center">
        <Loader2 className="h-10 w-10 animate-spin text-[#0EA5E9]" />
        <p className="mt-4 text-sm text-[#94A3B8]">Analysis still processing...</p>
      </div>
    );
  }

  if (data.status === "failed") {
    return (
      <div className="space-y-4">
        <Link to="/history" className="flex items-center gap-1 text-sm text-[#0EA5E9] hover:text-[#0EA5E9]/80">
          <ArrowLeft className="h-3 w-3" /> Back to History
        </Link>
        <div className="rounded-xl border border-destructive/30 bg-destructive/5 p-6">
          <p className="text-sm font-medium text-destructive">Analysis Failed</p>
          <p className="mt-1 text-xs text-[#94A3B8]">{data.error_message}</p>
        </div>
      </div>
    );
  }

  /* ---- Extract data from result_json ---- */
  const resultJson = data.result_json;
  const isPdf = data.file_type === "pdf";
  const pages: ResultPage[] = resultJson?.pages ?? [];
  const activePage = pages[activePageIdx] ?? pages[0] ?? null;
  const rooms: Room[] = activePage?.rooms ?? resultJson?.rooms ?? [];

  // Colour legend (from backend or build client-side)
  const colorLegend: LegendItem[] = resultJson?.color_legend ?? [];

  // Extracted images & overlay images (PDF only)
  const extractedImages: PageImage[] = resultJson?.extracted_images ?? [];
  const overlayImages: PageImage[] = resultJson?.overlay_images ?? [];

  // Image URL for the interactive viewer
  let imageUrl = "";
  if (activePage) {
    const imgPath = activePage.image_path;
    if (imgPath) {
      imageUrl = imgPath.startsWith("/api/") ? imgPath : `/api/files/uploads/${imgPath.split("/").pop() || ""}`;
    }
  }
  if (!imageUrl) {
    imageUrl = `/api/files/results/${data.id}/result_overlay.png`;
  }

  // Overlay (segmented) image URL for the print report
  // PDF: each page has overlay_path; single image: result_overlay.png
  let overlayUrl = `/api/files/results/${data.id}/result_overlay.png`;
  if (activePage?.overlay_path) {
    overlayUrl = activePage.overlay_path;
  } else if (overlayImages.length > 0) {
    overlayUrl = overlayImages[0].url;
  }

  const selectedRoom = rooms.find((r) => r.id === selectedRoomId) || null;

  const handleDownload = async () => {
    try {
      const res = await api.get(`/analyses/${id}/download`, { responseType: "blob" });
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const a = document.createElement("a");
      a.href = url;
      a.download = `${data.filename.replace(/\.[^.]+$/, "")}_result.json`;
      a.click();
      window.URL.revokeObjectURL(url);
    } catch {
      window.open(`/api/analyses/${id}/download`, "_blank");
    }
  };

  // Collect all rooms across all pages for analytics
  const allRooms: Room[] = pages.flatMap((p) => p?.rooms ?? []);
  if (allRooms.length === 0 && rooms.length > 0) {
    allRooms.push(...rooms);
  }

  return (
    <div className="space-y-4">
      {/* Top bar */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link to="/history" className="rounded-lg p-1.5 text-[#94A3B8] hover:bg-[#CBD5E1]/20 hover:text-white">
            <ArrowLeft className="h-4 w-4" />
          </Link>
          <div>
            <h1 className="font-display text-lg font-bold tracking-tight text-white">{data.filename}</h1>
            <p className="text-xs text-[#94A3B8]">
              {new Date(data.created_at).toLocaleString()}
              {isPdf && <span className="ml-2 rounded bg-[#3B82F6]/20 px-1.5 py-0.5 text-[10px] font-medium text-[#93C5FD]">PDF</span>}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={handlePrintReport}
            className="btn-export-spatial flex items-center gap-2 rounded-lg border border-[#00F0FF]/30 bg-transparent px-4 py-2 text-sm font-semibold text-[#00F0FF] transition-all hover:bg-[#00F0FF]/10"
          >
            <FileText className="h-4 w-4" />
            Export Spatial Report
          </button>
          <button
            onClick={handleDownload}
            className="flex items-center gap-2 rounded-lg border border-[rgba(56,189,248,0.15)] bg-[#CBD5E1]/10 px-4 py-2 text-sm text-white transition-colors hover:bg-[#CBD5E1]/20"
          >
            <Download className="h-4 w-4" />
            Download JSON
          </button>
          <button
            onClick={() => {
              // Map rooms to Wi-Fi Mapper format with real dimensions
              const imgDims = activePage?.image_dimensions;
              const wifiRooms = rooms.map((r, idx) => ({
                id: `r${r.id ?? idx}`,
                label: r.label ?? r.label_raw ?? `Room ${idx + 1}`,
                x: r.geometry?.centroid?.x ?? 0,
                y: r.geometry?.centroid?.y ?? 0,
                area: r.area?.value_sqft ?? r.dimensions_parsed?.area_sqft ?? r.geometry?.area_pixels ?? 0,
                width_ft: r.dimensions_parsed?.width_ft ?? 0,
                width_in: r.dimensions_parsed?.width_in ?? 0,
                height_ft: r.dimensions_parsed?.height_ft ?? 0,
                height_in: r.dimensions_parsed?.height_in ?? 0,
                bbox: r.geometry?.bbox ?? null,
              }));
              const wifiMeta = {
                image_width: imgDims?.width ?? 0,
                image_height: imgDims?.height ?? 0,
              };
              localStorage.setItem("archvision_wifi_data", JSON.stringify(wifiRooms));
              localStorage.setItem("archvision_wifi_meta", JSON.stringify(wifiMeta));
              localStorage.setItem("archvision_blueprint", overlayUrl || imageUrl);
              navigate("/wifi-mapper");
            }}
            className="flex items-center gap-2 rounded-lg border border-cyan-400 bg-cyan-500/20 px-4 py-2 text-sm font-bold font-display text-cyan-400 transition-all hover:bg-cyan-400 hover:text-slate-900"
          >
            <Wifi className="h-4 w-4" />
            Launch Wi-Fi Simulator
          </button>
        </div>
      </div>

      {/* AI Property Summary */}
      <PropertySummary jobId={Number(id)} pageCount={pages.length} />

      {/* Tab switcher */}
      <div className="flex items-center gap-1 rounded-xl border border-[rgba(56,189,248,0.15)] bg-[#0F172A]/30 backdrop-blur-xl p-1">
        <button
          onClick={() => setActiveTab("viewer")}
          className={`flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-all duration-200 ${
            activeTab === "viewer"
              ? "bg-[#0EA5E9]/15 text-[#0EA5E9] shadow-sm"
              : "text-[#94A3B8] hover:bg-[#CBD5E1]/20 hover:text-white"
          }`}
        >
          <Eye className="h-4 w-4" />
          Viewer
        </button>
        <button
          onClick={() => setActiveTab("analytics")}
          className={`flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-all duration-200 ${
            activeTab === "analytics"
              ? "bg-[#0EA5E9]/15 text-[#0EA5E9] shadow-sm"
              : "text-[#94A3B8] hover:bg-[#CBD5E1]/20 hover:text-white"
          }`}
        >
          <BarChart3 className="h-4 w-4" />
          Insights & Analytics
        </button>
        <button
          onClick={() => setActiveTab("cost")}
          className={`flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-all duration-200 ${
            activeTab === "cost"
              ? "bg-[#0EA5E9]/15 text-[#0EA5E9] shadow-sm"
              : "text-[#94A3B8] hover:bg-[#CBD5E1]/20 hover:text-white"
          }`}
        >
          <Ruler className="h-4 w-4" />
          Cost Estimate
        </button>
      </div>

      {/* Analytics Tab */}
      {activeTab === "analytics" && (
        <AnalyticsDashboard rooms={allRooms} filename={data.filename} />
      )}

      {/* Cost Estimate Tab */}
      {activeTab === "cost" && (
        <CostEstimator rooms={allRooms} filename={data.filename} />
      )}

      {/* Viewer Tab */}
      {activeTab === "viewer" && (
        <>
      {/* Summary bar */}
      <div className="grid grid-cols-3 gap-3">
        <div className="flex items-center gap-3 rounded-lg border border-[rgba(56,189,248,0.15)] bg-[#0F172A]/60 backdrop-blur-xl px-4 py-3">
          <Home className="h-5 w-5 text-[#0EA5E9]" />
          <div>
            <p className="text-lg font-bold font-mono tracking-tighter text-white">{data.total_rooms ?? 0}</p>
            <p className="text-xs text-[#94A3B8]">Rooms</p>
          </div>
        </div>
        <div className="flex items-center gap-3 rounded-lg border border-[rgba(56,189,248,0.15)] bg-[#0F172A]/60 backdrop-blur-xl px-4 py-3">
          <Tag className="h-5 w-5 text-[#34D399]" />
          <div>
            <p className="text-lg font-bold font-mono tracking-tighter text-white">{data.rooms_with_labels ?? 0}</p>
            <p className="text-xs text-[#94A3B8]">Labels</p>
          </div>
        </div>
        <div className="flex items-center gap-3 rounded-lg border border-[rgba(56,189,248,0.15)] bg-[#0F172A]/60 backdrop-blur-xl px-4 py-3">
          <Ruler className="h-5 w-5 text-[#22D3EE]" />
          <div>
            <p className="text-lg font-bold font-mono tracking-tighter text-white">{data.rooms_with_dimensions ?? 0}</p>
            <p className="text-xs text-[#94A3B8]">Dimensions</p>
          </div>
        </div>
      </div>

      {/* Colour legend data is available in colorLegend but hidden from header.
         Colours are still applied on segmented images and SVG polygons. */}

      {/* PDF: Extracted Images section */}
      {isPdf && extractedImages.length > 0 && (
        <ImageGallery
          title="Extracted Images"
          icon={<ImageIcon className="h-4 w-4 text-[#93C5FD]" />}
          images={extractedImages}
        />
      )}

      {/* PDF: Segmented Images section */}
      {isPdf && overlayImages.length > 0 && (
        <ImageGallery
          title="Segmented Images"
          icon={<Layers className="h-4 w-4 text-[#34D399]" />}
          images={overlayImages}
        />
      )}

      {/* Page selector (PDF with multiple pages) */}
      {isPdf && pages.length > 1 && (
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium text-[#94A3B8]">Interactive View:</span>
          {pages.map((_, idx) => (
            <button
              key={idx}
              onClick={() => { setActivePageIdx(idx); setSelectedRoomId(null); }}
              className={`rounded-md px-3 py-1 text-xs font-medium transition-colors ${
                idx === activePageIdx
                  ? "bg-[#0EA5E9] text-white"
                  : "bg-[#CBD5E1]/20 text-[#94A3B8] hover:bg-[#CBD5E1]/30"
              }`}
            >
              Page {idx + 1}
            </button>
          ))}
        </div>
      )}

      {/* Main viewer + detail panel */}
      <div>
        {!isPdf && (
          <div className="mb-3 flex items-center gap-2">
            <Layers className="h-4 w-4 text-[#34D399]" />
            <h2 className="text-sm font-semibold text-white">Segmented Image</h2>
          </div>
        )}
        {isPdf && pages.length > 0 && (
          <div className="mb-3 flex items-center gap-2">
            <Layers className="h-4 w-4 text-[#0EA5E9]" />
            <h2 className="text-sm font-semibold text-white">
              Interactive Viewer {pages.length > 1 ? `— Page ${activePageIdx + 1}` : ""}
            </h2>
          </div>
        )}
        <div className="grid gap-4 lg:grid-cols-[1fr_320px]">
          <FloorPlanViewer
            imageUrl={imageUrl}
            rooms={rooms}
            selectedRoomId={selectedRoomId}
            onSelectRoom={setSelectedRoomId}
          />
          <RoomDetailPanel room={selectedRoom} onClose={() => setSelectedRoomId(null)} />
        </div>
      </div>
      </>
      )}

      {/* Hidden Spatial Report — rendered into DOM for @media print */}
      {showReport && (
        <SpatialReport
          ref={reportRef}
          rooms={allRooms}
          filename={data.filename}
          imageUrl={overlayUrl}
          totalRooms={data.total_rooms ?? 0}
          roomsWithLabels={data.rooms_with_labels ?? 0}
          roomsWithDimensions={data.rooms_with_dimensions ?? 0}
        />
      )}
    </div>
  );
}
