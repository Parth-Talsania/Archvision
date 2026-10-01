import { useCallback, useEffect, useRef, useState } from "react";
import { ZoomIn, ZoomOut, Maximize } from "lucide-react";

interface Room {
  id: number;
  label: string | null;
  dimensions: string | null;
  color?: string;
  confidence: { geometry: number; label: number; dimensions: number };
  geometry: {
    centroid: { x: number; y: number };
    bbox: { x1: number; y1: number; x2: number; y2: number };
    polygon: number[][];
    area_pixels: number;
  };
}

interface FloorPlanViewerProps {
  imageUrl: string;
  rooms: Room[];
  selectedRoomId: number | null;
  onSelectRoom: (id: number | null) => void;
}

/* ------------------------------------------------------------------ */
/* Consistent room-label colour map (mirrors backend visualize.py)     */
/* ------------------------------------------------------------------ */
const ROOM_LABEL_COLORS: Record<string, string> = {
  Kitchen:          "#FF0000",
  Bedroom:          "#1E90FF",
  "Master Bedroom": "#1464E6",
  Living:           "#00C800",
  Hall:             "#C8C800",
  Dining:           "#FFA500",
  Toilet:           "#C800C8",
  Bathroom:         "#C800C8",
  Balcony:          "#00C8C8",
  Pooja:            "#C83264",
  Utility:          "#64B464",
  Store:            "#B48250",
  Passage:          "#5082B4",
  Lobby:            "#3C8C8C",
  Staircase:        "#B43C3C",
  Terrace:          "#DCB432",
  Wash:             "#B450B4",
  Dress:            "#DC6482",
};

const FALLBACK_PALETTE = [
  "#6464FF", "#64FF64", "#FF6464",
  "#FFFF64", "#FF64FF", "#64FFFF",
];
let _fallbackIdx = 0;
const _dynamicCache: Record<string, string> = {};

function getRoomColor(label: string, serverColor?: string): string {
  if (serverColor) return serverColor;
  const key = label.trim();
  if (ROOM_LABEL_COLORS[key]) return ROOM_LABEL_COLORS[key];
  // normalised check
  const norm = key.toLowerCase().replace(/\s+/g, "");
  for (const [canon, clr] of Object.entries(ROOM_LABEL_COLORS)) {
    if (canon.toLowerCase().replace(/\s+/g, "") === norm) return clr;
  }
  if (!_dynamicCache[key]) {
    _dynamicCache[key] = FALLBACK_PALETTE[_fallbackIdx % FALLBACK_PALETTE.length];
    _fallbackIdx++;
  }
  return _dynamicCache[key];
}

function hexToRgba(hex: string, alpha: number): string {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r},${g},${b},${alpha})`;
}

export default function FloorPlanViewer({ imageUrl, rooms, selectedRoomId, onSelectRoom }: FloorPlanViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [imgSize, setImgSize] = useState({ width: 0, height: 0 });
  const [scale, setScale] = useState(1);
  const [offset, setOffset] = useState({ x: 0, y: 0 });
  const [isPanning, setIsPanning] = useState(false);
  const [panStart, setPanStart] = useState({ x: 0, y: 0 });
  const [hoveredRoom, setHoveredRoom] = useState<number | null>(null);
  const [imageLoading, setImageLoading] = useState(true);
  const [imageError, setImageError] = useState(false);

  // Reset image state when URL changes
  useEffect(() => {
    setImageLoading(true);
    setImageError(false);
    setImgSize({ width: 0, height: 0 });
  }, [imageUrl]);

  const handleImageLoad = useCallback((e: React.SyntheticEvent<HTMLImageElement>) => {
    const img = e.currentTarget;
    setImgSize({ width: img.naturalWidth, height: img.naturalHeight });
    setImageLoading(false);
    setImageError(false);
  }, []);

  const handleImageError = useCallback(() => {
    setImageLoading(false);
    setImageError(true);
  }, []);

  const zoomIn = () => setScale((s) => Math.min(s * 1.3, 5));
  const zoomOut = () => setScale((s) => Math.max(s / 1.3, 0.3));
  const resetView = () => {
    setScale(1);
    setOffset({ x: 0, y: 0 });
  };

  const handleWheel = useCallback((e: React.WheelEvent) => {
    e.preventDefault();
    const delta = e.deltaY > 0 ? 0.9 : 1.1;
    setScale((s) => Math.min(Math.max(s * delta, 0.3), 5));
  }, []);

  const handleMouseDown = (e: React.MouseEvent) => {
    if (e.button === 1 || e.ctrlKey) {
      setIsPanning(true);
      setPanStart({ x: e.clientX - offset.x, y: e.clientY - offset.y });
      e.preventDefault();
    }
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (isPanning) {
      setOffset({ x: e.clientX - panStart.x, y: e.clientY - panStart.y });
    }
  };

  const handleMouseUp = () => setIsPanning(false);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onSelectRoom(null);
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onSelectRoom]);

  const polygonToSvgPoints = (polygon: number[][]) =>
    polygon.map((p) => `${p[0]},${p[1]}`).join(" ");

  return (
    <div className="relative flex flex-col rounded-xl border border-[rgba(56,189,248,0.15)] bg-slate-900/40 backdrop-blur-xl overflow-hidden">
      {/* Toolbar */}
      <div className="flex items-center gap-1 border-b border-[rgba(56,189,248,0.15)] bg-slate-900/40 backdrop-blur-xl px-3 py-2">
        <button onClick={zoomIn} className="rounded p-1.5 text-[#94A3B8] hover:bg-[#CBD5E1]/20 hover:text-white" title="Zoom In">
          <ZoomIn className="h-4 w-4" />
        </button>
        <button onClick={zoomOut} className="rounded p-1.5 text-[#94A3B8] hover:bg-[#CBD5E1]/20 hover:text-white" title="Zoom Out">
          <ZoomOut className="h-4 w-4" />
        </button>
        <button onClick={resetView} className="rounded p-1.5 text-[#94A3B8] hover:bg-[#CBD5E1]/20 hover:text-white" title="Reset View">
          <Maximize className="h-4 w-4" />
        </button>
        <span className="ml-2 font-mono text-xs text-[#94A3B8]">{Math.round(scale * 100)}%</span>
        <span className="ml-auto text-xs text-[#94A3B8]">
          Ctrl+click to pan &middot; Scroll to zoom &middot; Click room to select
        </span>
      </div>

      {/* Canvas area */}
      <div
        ref={containerRef}
        className="relative h-[600px] overflow-hidden bg-[#020617]/50"
        onWheel={handleWheel}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
        style={{ cursor: isPanning ? "grabbing" : "default" }}
      >
        <div
          style={{
            transform: `translate(${offset.x}px, ${offset.y}px) scale(${scale})`,
            transformOrigin: "center center",
            transition: isPanning ? "none" : "transform 0.15s ease-out",
          }}
          className="flex h-full w-full items-center justify-center"
        >
          <div className="relative inline-block">
            {imageLoading && (
              <div className="flex h-[400px] w-[600px] items-center justify-center">
                <div className="h-8 w-8 animate-spin rounded-full border-2 border-[#0EA5E9] border-t-transparent" />
              </div>
            )}

            {imageError && (
              <div className="flex h-[400px] w-[600px] flex-col items-center justify-center rounded-lg bg-[#CBD5E1]/10">
                <p className="text-sm font-medium text-[#EF4444]">Failed to load floor plan image</p>
                <p className="mt-1 text-xs text-[#94A3B8]">The image may be missing or inaccessible</p>
              </div>
            )}

            <img
              src={imageUrl}
              alt="Floor plan"
              onLoad={handleImageLoad}
              onError={handleImageError}
              className={`max-h-[580px] w-auto ${imageLoading || imageError ? "hidden" : ""}`}
              draggable={false}
            />

            {/* SVG overlay for room polygons */}
            {imgSize.width > 0 && (
              <svg
                viewBox={`0 0 ${imgSize.width} ${imgSize.height}`}
                className="absolute inset-0 h-full w-full"
                style={{ pointerEvents: "none" }}
              >
                {rooms.map((room) => {
                  const isSelected = room.id === selectedRoomId;
                  const isHovered = room.id === hoveredRoom;
                  const conf = room.confidence?.geometry ?? 0;
                  const polygon = room.geometry?.polygon;
                  const centroid = room.geometry?.centroid;

                  if (!polygon || polygon.length === 0) return null;

                  return (
                    <g key={room.id} style={{ pointerEvents: "all" }}>
                      <polygon
                        points={polygonToSvgPoints(polygon)}
                        fill={isSelected ? "rgba(168, 85, 247, 0.35)" : isHovered ? "rgba(168, 85, 247, 0.2)" : hexToRgba(getRoomColor(room.label || "room", room.color), 0.35)}
                        stroke={isSelected ? "rgba(168, 85, 247, 1)" : isHovered ? "rgba(168, 85, 247, 0.8)" : hexToRgba(getRoomColor(room.label || "room", room.color), 0.9)}
                        strokeWidth={isSelected ? 3 : isHovered ? 2.5 : 2}
                        className="cursor-pointer transition-all duration-150"
                        onClick={(e) => {
                          e.stopPropagation();
                          onSelectRoom(room.id === selectedRoomId ? null : room.id);
                        }}
                        onMouseEnter={() => setHoveredRoom(room.id)}
                        onMouseLeave={() => setHoveredRoom(null)}
                      />
                      {/* Label at centroid */}
                      {room.label && centroid && (
                        <text
                          x={centroid.x}
                          y={centroid.y}
                          textAnchor="middle"
                          dominantBaseline="central"
                          fill="white"
                          fontSize={Math.max(12, Math.min(16, imgSize.width / 60))}
                          fontWeight="600"
                          paintOrder="stroke"
                          stroke="rgba(0,0,0,0.7)"
                          strokeWidth="3"
                          className="pointer-events-none select-none"
                        >
                          {room.label}
                        </text>
                      )}
                    </g>
                  );
                })}
              </svg>
            )}
          </div>
        </div>

        {/* Tooltip for hovered room */}
        {hoveredRoom !== null && (() => {
          const room = rooms.find((r) => r.id === hoveredRoom);
          if (!room) return null;
          return (
            <div className="absolute bottom-3 left-3 z-10 rounded-lg border border-[rgba(56,189,248,0.15)] bg-slate-900/80 backdrop-blur px-3 py-2 shadow-lg">
              <p className="text-sm font-medium text-white">{room.label || `Room ${room.id}`}</p>
              {room.dimensions && <p className="text-xs text-[#94A3B8]">{room.dimensions}</p>}
            </div>
          );
        })()}
      </div>
    </div>
  );
}
