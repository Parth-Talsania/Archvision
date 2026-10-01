import React, { useState, useEffect, useRef, useCallback } from "react";
import { motion } from "framer-motion";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";

// ── Mock data representing ArchVision CV pipeline JSON output ──────────────
const mockRooms: Room[] = [
  { id: "r1", label: "Living Room", x: 300, y: 400, area: 350, width_ft: 15, width_in: 0, height_ft: 12, height_in: 0, bbox: null },
  { id: "r2", label: "Master Bed", x: 600, y: 200, area: 250, width_ft: 12, width_in: 6, height_ft: 10, height_in: 0, bbox: null },
  { id: "r3", label: "Kitchen", x: 200, y: 150, area: 200, width_ft: 10, width_in: 0, height_ft: 8, height_in: 0, bbox: null },
  { id: "r4", label: "Guest Bed", x: 700, y: 500, area: 180, width_ft: 10, width_in: 0, height_ft: 9, height_in: 0, bbox: null },
];

// ── Types ──────────────────────────────────────────────────────────────────
interface Room {
  id: string;
  label: string;
  x: number;
  y: number;
  area: number;
  width_ft?: number;
  width_in?: number;
  height_ft?: number;
  height_in?: number;
  bbox?: { x1: number; y1: number; x2: number; y2: number } | null;
}

interface WifiMeta {
  image_width: number;
  image_height: number;
}

interface SignalEntry {
  id: string;
  label: string;
  signal: number;
}

// ── Custom glassmorphic tooltip for Recharts ──────────────────────────────
const SignalTooltip = ({ active, payload }: any) => {
  if (!active || !payload || payload.length === 0) return null;
  const entry = payload[0].payload as SignalEntry;
  const color =
    entry.signal >= 80 ? "#00F0FF" : entry.signal >= 40 ? "#FBBF24" : "#E11D48";
  const tier =
    entry.signal >= 80 ? "Excellent" : entry.signal >= 40 ? "Moderate" : "Deadzone";
  return (
    <div className="bg-slate-900/90 backdrop-blur-md border border-cyan-500/30 p-3 rounded-lg text-white font-mono">
      <p className="text-xs text-slate-400 mb-1">{entry.label}</p>
      <p className="text-lg font-bold" style={{ color }}>
        {entry.signal}%
      </p>
      <p className="text-[10px] uppercase tracking-widest" style={{ color }}>
        {tier}
      </p>
    </div>
  );
};

// ── Component ──────────────────────────────────────────────────────────────
// Wi-Fi 2.4 GHz typical indoor range ~30 feet through walls
const WIFI_MAX_RANGE_FT = 50;
// Free-space path loss at 2.4 GHz, simplified: signal degrades with distance^2
// We use a log-distance model: signal = 100 - 10 * n * log10(d / d0)
// n = path loss exponent (2.5 for indoor residential), d0 = 1 ft reference
const PATH_LOSS_EXPONENT = 2.5;

function signalAtDistance(distanceFt: number, wallCount: number): number {
  if (distanceFt < 1) return 100;
  // Log-distance signal model
  const pathLoss = 10 * PATH_LOSS_EXPONENT * Math.log10(distanceFt);
  // Each wall attenuates ~6 dB which we model as ~8% signal loss
  const wallLoss = wallCount * 8;
  const signal = Math.max(0, Math.min(100, 100 - pathLoss - wallLoss));
  return Math.round(signal);
}

const WifiMapper: React.FC = () => {
  const [rooms, setRooms] = useState<Room[]>(mockRooms);
  const [wifiMeta, setWifiMeta] = useState<WifiMeta | null>(null);
  const [blueprint, setBlueprint] = useState<string | null>(null);
  const [activeRouter, setActiveRouter] = useState<string | null>(null);
  const [signalData, setSignalData] = useState<SignalEntry[]>([]);
  const [pixelsPerFoot, setPixelsPerFoot] = useState<number | null>(null);

  // ── Image-to-container coordinate mapping ──────────────────────────────
  const containerRef = useRef<HTMLDivElement>(null);
  const [imgNatural, setImgNatural] = useState<{ w: number; h: number } | null>(null);

  // Compute the object-contain transform: scale + offset
  const getTransform = useCallback(() => {
    if (!containerRef.current || !imgNatural) return null;
    const cw = containerRef.current.clientWidth;
    const ch = containerRef.current.clientHeight;
    const nw = imgNatural.w;
    const nh = imgNatural.h;
    if (nw === 0 || nh === 0) return null;

    const scale = Math.min(cw / nw, ch / nh);
    const renderedW = nw * scale;
    const renderedH = nh * scale;
    const offsetX = (cw - renderedW) / 2;
    const offsetY = (ch - renderedH) / 2;
    return { scale, offsetX, offsetY };
  }, [imgNatural]);

  // Map a raw image-space coordinate to container-space
  const toContainer = useCallback(
    (px: number, py: number): { cx: number; cy: number } => {
      const t = getTransform();
      if (!t) return { cx: px, cy: py }; // fallback: pass-through (mock data)
      return {
        cx: t.offsetX + px * t.scale,
        cy: t.offsetY + py * t.scale,
      };
    },
    [getTransform]
  );

  const handleImageLoad = (e: React.SyntheticEvent<HTMLImageElement>) => {
    const img = e.currentTarget;
    setImgNatural({ w: img.naturalWidth, h: img.naturalHeight });
  };

  // Recalculate on window resize
  useEffect(() => {
    const onResize = () => {
      // Force a re-render by toggling a trivial state
      setImgNatural((prev) => (prev ? { ...prev } : prev));
    };
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  // ── Load dynamic data from localStorage on mount ─────────────────────
  useEffect(() => {
    const storedRooms = localStorage.getItem("archvision_wifi_data");
    const storedImage = localStorage.getItem("archvision_blueprint");
    const storedMeta = localStorage.getItem("archvision_wifi_meta");

    let loadedRooms: Room[] | null = null;
    if (storedRooms) {
      try {
        const parsed = JSON.parse(storedRooms) as Room[];
        if (Array.isArray(parsed) && parsed.length > 0) {
          loadedRooms = parsed;
          setRooms(parsed);
        }
      } catch { /* Fall back to mock */ }
    }

    if (storedMeta) {
      try { setWifiMeta(JSON.parse(storedMeta)); } catch { /* ignore */ }
    }

    if (storedImage) {
      setBlueprint(storedImage);
    }

    // Compute pixels-per-foot from rooms that have both bbox and dimensions
    const rms = loadedRooms ?? mockRooms;
    const samples: number[] = [];
    for (const r of rms) {
      if (!r.bbox || !r.width_ft) continue;
      const bboxW = Math.abs(r.bbox.x2 - r.bbox.x1);
      const roomFt = (r.width_ft ?? 0) + (r.width_in ?? 0) / 12;
      if (bboxW > 10 && roomFt > 1) {
        samples.push(bboxW / roomFt);
      }
      const bboxH = Math.abs(r.bbox.y2 - r.bbox.y1);
      const roomHFt = (r.height_ft ?? 0) + (r.height_in ?? 0) / 12;
      if (bboxH > 10 && roomHFt > 1) {
        samples.push(bboxH / roomHFt);
      }
    }
    if (samples.length > 0) {
      samples.sort((a, b) => a - b);
      const median = samples[Math.floor(samples.length / 2)];
      setPixelsPerFoot(median);
    }
  }, []);

  // Estimate how many walls are between two rooms based on distance
  // Simple heuristic: every ~12 feet of separation ~ 1 wall
  const estimateWalls = (distanceFt: number): number => {
    if (distanceFt < 5) return 0;
    return Math.floor(distanceFt / 12);
  };

  const calculateSignal = (routerId: string) => {
    const router = rooms.find((r) => r.id === routerId);
    if (!router) return;

    const ppf = pixelsPerFoot;

    const newSignalData: SignalEntry[] = rooms.map((room) => {
      if (room.id === routerId) {
        return { id: room.id, label: room.label, signal: 100 };
      }

      const dxPx = room.x - router.x;
      const dyPx = room.y - router.y;
      const distPx = Math.sqrt(dxPx * dxPx + dyPx * dyPx);

      let distanceFt: number;
      if (ppf && ppf > 0) {
        distanceFt = distPx / ppf;
      } else {
        // Fallback: estimate from room areas (avg room ~10ft side)
        distanceFt = distPx * 0.04;
      }

      const walls = estimateWalls(distanceFt);
      const signal = signalAtDistance(distanceFt, walls);

      return { id: room.id, label: room.label, signal };
    });

    setActiveRouter(routerId);
    setSignalData(newSignalData);
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 min-h-screen p-6 bg-transparent text-white">
      {/* ── Left Column: Floor Plan Canvas ─────────────────────────────── */}
      <div className="col-span-12 lg:col-span-8 bg-slate-900/40 backdrop-blur-md border border-cyan-500/30 rounded-2xl p-4 relative overflow-hidden">
        <h2 className="font-display text-lg tracking-wide text-cyan-300/80 mb-2">
          Floor Plan — Signal Canvas
        </h2>
        <p className="font-sans text-sm text-slate-400">
          Click a room centroid to place the virtual router.
        </p>
        <p className="font-mono text-xs text-slate-500 mt-1">
          Model: Log-distance path loss (n={PATH_LOSS_EXPONENT}, 2.4 GHz)
          {pixelsPerFoot
            ? ` | Scale: ${pixelsPerFoot.toFixed(1)} px/ft (from dimensions)`
            : " | Scale: estimated (no dimension data)"}
          {" | Wall attenuation: ~8%/wall"}
        </p>

        {/* ── Blueprint Map Container ──────────────────────────────── */}
        <div
          ref={containerRef}
          className="mt-4 w-full h-[600px] bg-slate-800/30 rounded-xl relative border border-slate-700 overflow-hidden"
        >
          {/* Blueprint image layer */}
          {blueprint && (
            <img
              src={blueprint}
              alt="Segmented Floor Plan"
              className="absolute inset-0 w-full h-full object-contain opacity-80 z-0"
              onLoad={handleImageLoad}
            />
          )}

          {/* ── Pulsing Wi-Fi heatmap gradient (z-10) ── */}
          {activeRouter && (() => {
            const routerRoom = rooms.find((r) => r.id === activeRouter);
            if (!routerRoom) return null;
            const { cx, cy } = toContainer(routerRoom.x, routerRoom.y);
            return (
              <motion.div
                key={activeRouter}
                className="absolute w-[1400px] h-[1400px] rounded-full pointer-events-none"
                style={{
                  left: cx,
                  top: cy,
                  transform: "translate(-50%, -50%)",
                  zIndex: 10,
                  background:
                    "radial-gradient(circle, rgba(0,240,255,0.35) 0%, rgba(14,165,233,0.15) 30%, rgba(0,0,0,0) 65%)",
                }}
                initial={{ scale: 0.8, opacity: 0 }}
                animate={{ scale: [1, 1.05, 1], opacity: 1 }}
                transition={{ duration: 3, repeat: Infinity, ease: "easeInOut" }}
              />
            );
          })()}

          {/* ── Room centroid nodes (z-20 to sit above heatmap) ──────── */}
          {rooms.map((room) => {
            const { cx, cy } = toContainer(room.x, room.y);
            const isRouter = activeRouter === room.id;
            const roomSignal = signalData.find((s) => s.id === room.id);

            // Dynamic node colour based on signal strength
            let nodeColor = "bg-slate-400 hover:bg-slate-300";
            if (roomSignal) {
              if (roomSignal.signal >= 80) {
                nodeColor = "bg-cyan-400 shadow-[0_0_15px_rgba(0,240,255,0.8)]";
              } else if (roomSignal.signal >= 40) {
                nodeColor = "bg-amber-400 shadow-[0_0_15px_rgba(251,191,36,0.8)]";
              } else {
                nodeColor = "bg-rose-500 shadow-[0_0_15px_rgba(225,29,72,0.8)]";
              }
            }

            return (
              <button
                key={room.id}
                onClick={() => calculateSignal(room.id)}
                className={`absolute w-5 h-5 rounded-full transform -translate-x-1/2 -translate-y-1/2 cursor-pointer hover:scale-150 transition-all duration-300 z-20 ${nodeColor}`}
                style={{ left: cx, top: cy }}
              >
                {/* Label above the node */}
                <span className="absolute -top-6 left-1/2 -translate-x-1/2 whitespace-nowrap font-sans text-xs text-slate-300 pointer-events-none">
                  {room.label}
                </span>

                {/* Signal badge below the node */}
                {roomSignal && (
                  <span className={`absolute top-6 left-1/2 -translate-x-1/2 whitespace-nowrap font-mono text-[10px] pointer-events-none ${
                    roomSignal.signal >= 80
                      ? "text-cyan-400"
                      : roomSignal.signal >= 40
                        ? "text-amber-400"
                        : "text-rose-400"
                  }`}>
                    {roomSignal.signal}%
                  </span>
                )}
              </button>
            );
          })}
        </div>
      </div>

      {/* ── Right Column: Network Health Simulator ────────────────────── */}
      <div className="col-span-12 lg:col-span-4 bg-slate-900/40 backdrop-blur-md border border-cyan-500/30 rounded-2xl p-4 relative overflow-hidden">
        <h2 className="font-display font-bold text-2xl tracking-tight text-white mb-2">
          Network Health Simulator
        </h2>
        <p className="text-xs text-slate-500">
          Signal computed using log-distance path loss model with wall attenuation
          {pixelsPerFoot ? ", calibrated from actual room dimensions." : "."}
        </p>

        {signalData.length === 0 ? (
          <div className="mt-6 flex flex-col items-center justify-center h-80">
            <div className="w-16 h-16 rounded-full border-2 border-dashed border-cyan-500/30 flex items-center justify-center mb-4">
              <span className="font-mono text-2xl text-cyan-500/40">{"\u2192"}</span>
            </div>
            <p className="font-sans text-sm text-slate-400 text-center">
              Click a room centroid on the map to place a virtual router and see the signal analysis.
            </p>
          </div>
        ) : (
          <div className="mt-4 space-y-6">
            {/* ── Average Signal Metric ── */}
            <div className="text-center">
              <p className="font-sans text-xs uppercase tracking-widest text-slate-400 mb-1">
                Average Network Strength
              </p>
              <p className="font-mono text-cyan-400 text-5xl font-bold">
                {Math.round(
                  signalData.reduce((sum, s) => sum + s.signal, 0) /
                    signalData.length
                )}
                <span className="text-lg text-cyan-400/60 ml-1">%</span>
              </p>
            </div>

            {/* ── Horizontal Bar Chart ── */}
            <div>
              <p className="font-sans text-xs uppercase tracking-widest text-slate-400 mb-3">
                Per-Room Signal Strength
              </p>
              <ResponsiveContainer width="100%" height={350}>
                <BarChart
                  data={signalData}
                  layout="vertical"
                  margin={{ left: 20, right: 12, top: 0, bottom: 0 }}
                >
                  <YAxis
                    type="category"
                    dataKey="label"
                    stroke="#94A3B8"
                    fontSize={13}
                    tickLine={false}
                    axisLine={false}
                    width={100}
                  />
                  <XAxis type="number" domain={[0, 100]} hide />
                  <Tooltip
                    content={<SignalTooltip />}
                    cursor={{ fill: "rgba(0,240,255,0.05)" }}
                  />
                  <Bar dataKey="signal" radius={[0, 4, 4, 0]} barSize={22}>
                    {signalData.map((entry) => (
                      <Cell
                        key={entry.id}
                        fill={
                          entry.signal >= 80
                            ? "#00F0FF"
                            : entry.signal >= 40
                              ? "#FBBF24"
                              : "#E11D48"
                        }
                      />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>

            {/* ── Signal Legend ── */}
            <div className="flex items-center justify-center gap-5">
              {[
                { color: "#00F0FF", label: "Excellent", range: "\u2265 80%" },
                { color: "#FBBF24", label: "Moderate", range: "40\u201379%" },
                { color: "#E11D48", label: "Deadzone", range: "< 40%" },
              ].map((tier) => (
                <div key={tier.label} className="flex items-center gap-1.5">
                  <span
                    className="inline-block w-2.5 h-2.5 rounded-full"
                    style={{ backgroundColor: tier.color }}
                  />
                  <span className="font-mono text-[10px] text-slate-400">
                    {tier.label} {tier.range}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default WifiMapper;
