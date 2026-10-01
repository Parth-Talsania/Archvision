import { X, Ruler, Tag, Target, BarChart3 } from "lucide-react";
import type { Room } from "@/types/analysis";


interface RoomDetailPanelProps {
  room: Room | null;
  onClose: () => void;
}

function ConfidenceBar({ label, value }: { label: string; value: number }) {
  const pct = Math.round(value * 100);
  const color =
    pct >= 80 ? "bg-green-500" : pct >= 50 ? "bg-yellow-500" : "bg-red-500";

  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between">
        <span className="text-xs text-[#94A3B8]">{label}</span>
        <span className="font-mono text-xs font-medium text-white">{pct}%</span>
      </div>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-secondary">
        <div className={`h-full rounded-full ${color} transition-all duration-500`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

export default function RoomDetailPanel({ room, onClose }: RoomDetailPanelProps) {
  if (!room) {
    return (
      <div className="flex h-full flex-col items-center justify-center rounded-xl border border-[rgba(56,189,248,0.15)] bg-slate-900/40 backdrop-blur-xl p-6">
        <Target className="h-10 w-10 text-[#94A3B8]/30" />
        <p className="mt-3 text-sm text-[#94A3B8]">Click a room to see details</p>
      </div>
    );
  }

  const dim = room.dimensions_parsed;
  const area = room.area?.value_sqft ?? (dim ? dim.area_sqft : null);
  const confidence = room.confidence ?? { geometry: 0, label: 0, dimensions: 0 };
  const geometry = room.geometry ?? { centroid: { x: 0, y: 0 }, bbox: { x1: 0, y1: 0, x2: 0, y2: 0 }, polygon: [], area_pixels: 0 };

  return (
    <div className="rounded-xl border border-[rgba(56,189,248,0.15)] bg-slate-900/40 backdrop-blur-xl overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-[rgba(56,189,248,0.15)] px-4 py-3">
        <h3 className="font-display text-sm font-semibold text-white">{room.label || `Room ${room.id}`}</h3>
        <button onClick={onClose} className="rounded p-1 text-[#94A3B8] hover:bg-[#CBD5E1]/20 hover:text-white">
          <X className="h-4 w-4 text-[#94A3B8]" />
        </button>
      </div>

      <div className="space-y-5 p-4">
        {/* Dimensions */}
        <div className="space-y-2">
          <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-wider text-[#94A3B8]">
            <Ruler className="h-3 w-3" />
            Dimensions
          </div>
          {room.dimensions ? (
            <div className="rounded-lg bg-secondary/30 px-3 py-2">
              <p className="font-mono text-lg font-semibold text-[#0EA5E9]">{room.dimensions}</p>
              {dim && (
                <div className="mt-1 grid grid-cols-2 gap-2 font-mono text-xs text-[#94A3B8]">
                  <span>Width: {dim.width_ft}'{dim.width_in}"</span>
                  <span>Height: {dim.height_ft}'{dim.height_in}"</span>
                </div>
              )}
            </div>
          ) : (
            <p className="text-xs italic text-[#94A3B8]">No dimensions detected</p>
          )}
        </div>

        {/* Area */}
        {area != null && (
          <div className="space-y-2">
            <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-wider text-[#94A3B8]">
              <BarChart3 className="h-3 w-3" />
              Area
            </div>
            <p className="font-mono text-lg font-semibold text-white">{area.toFixed(1)} sqft</p>
          </div>
        )}

        {/* Label info */}
        <div className="space-y-2">
          <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-wider text-[#94A3B8]">
            <Tag className="h-3 w-3" />
            Label
          </div>
          <p className="text-sm text-white">{room.label || "Unknown"}</p>
        </div>

        {/* Confidence scores */}
        <div className="space-y-3">
          <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-wider text-[#94A3B8]">
            <Target className="h-3 w-3" />
            Confidence
          </div>
          <ConfidenceBar label="Geometry" value={confidence.geometry} />
          <ConfidenceBar label="Label" value={confidence.label} />
        </div>

        {/* Geometry info */}
        <div className="space-y-1 font-mono text-xs text-[#94A3B8]">
          <p>Centroid: ({Math.round(geometry.centroid.x)}, {Math.round(geometry.centroid.y)})</p>
          <p>Area: {Math.round(geometry.area_pixels).toLocaleString()} px</p>
          <p>Polygon: {geometry.polygon.length} vertices</p>
        </div>
      </div>
    </div>
  );
}
