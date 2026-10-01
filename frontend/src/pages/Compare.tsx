import { useEffect, useState, useMemo } from "react";
import { Link } from "react-router-dom";
import { ArrowLeft, GitCompareArrows, Home, Ruler, Tag, ChevronDown, BarChart3 } from "lucide-react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, Legend,
} from "recharts";
import api from "@/api/client";
import type { ResultJson, Room } from "@/types/analysis";

/* ------------------------------------------------------------------ */
/*  Types                                                               */
/* ------------------------------------------------------------------ */

interface AnalysisSummary {
  id: number;
  filename: string;
  file_type: string;
  status: string;
  total_rooms: number | null;
  rooms_with_labels: number | null;
  rooms_with_dimensions: number | null;
  created_at: string;
}

interface AnalysisDetail extends AnalysisSummary {
  result_json: ResultJson | null;
}

interface RoomSummary {
  label: string;
  area: number;
  dimensions: string | null;
}

/* ------------------------------------------------------------------ */
/*  Helpers                                                             */
/* ------------------------------------------------------------------ */

function extractRooms(detail: AnalysisDetail): RoomSummary[] {
  const pages = detail.result_json?.pages ?? [];
  const allRooms: Room[] = pages.flatMap((p) => p?.rooms ?? []);
  return allRooms.map((r) => ({
    label: r.label ?? r.label_raw ?? "Room",
    area: r.area?.value_sqft ?? r.dimensions_parsed?.area_sqft ?? 0,
    dimensions: r.dimensions ?? null,
  }));
}

function totalArea(rooms: RoomSummary[]): number {
  return rooms.reduce((s, r) => s + r.area, 0);
}

function countByType(rooms: RoomSummary[]): Record<string, { count: number; totalArea: number }> {
  const map: Record<string, { count: number; totalArea: number }> = {};
  for (const r of rooms) {
    const key = r.label;
    if (!map[key]) map[key] = { count: 0, totalArea: 0 };
    map[key].count++;
    map[key].totalArea += r.area;
  }
  return map;
}

function getOverlayUrl(detail: AnalysisDetail): string {
  const overlays = detail.result_json?.overlay_images ?? [];
  if (overlays.length > 0) return overlays[0].url;
  return `/api/files/results/${detail.id}/result_overlay.png`;
}

function bhkLabel(rooms: RoomSummary[]): string {
  const beds = rooms.filter((r) =>
    /bed|master/i.test(r.label)
  ).length;
  const halls = rooms.filter((r) =>
    /hall|living|drawing/i.test(r.label)
  ).length;
  const kitchens = rooms.filter((r) =>
    /kitchen/i.test(r.label)
  ).length;
  if (beds === 0) return "Studio";
  return `${beds}BHK`;
}

const COLORS_A = ["#0EA5E9", "#38BDF8", "#7DD3FC", "#BAE6FD", "#0284C7", "#0369A1"];
const COLORS_B = ["#8B5CF6", "#A78BFA", "#C4B5FD", "#DDD6FE", "#7C3AED", "#6D28D9"];

/* ------------------------------------------------------------------ */
/*  Selector dropdown                                                   */
/* ------------------------------------------------------------------ */

function PlanSelector({
  analyses,
  selectedId,
  onSelect,
  label,
}: {
  analyses: AnalysisSummary[];
  selectedId: number | null;
  onSelect: (id: number) => void;
  label: string;
}) {
  const [open, setOpen] = useState(false);
  const completed = analyses.filter((a) => a.status === "completed");
  const selected = completed.find((a) => a.id === selectedId);

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="flex w-full items-center justify-between gap-2 rounded-lg border border-[rgba(56,189,248,0.15)] bg-[#0F172A]/60 px-4 py-3 text-left transition-colors hover:bg-[#CBD5E1]/10"
      >
        <div>
          <p className="text-[10px] uppercase tracking-wider text-[#94A3B8]">{label}</p>
          <p className="mt-0.5 text-sm font-medium text-white truncate">
            {selected ? selected.filename : "Select a floor plan..."}
          </p>
        </div>
        <ChevronDown className={`h-4 w-4 text-[#94A3B8] transition-transform ${open ? "rotate-180" : ""}`} />
      </button>
      {open && (
        <div className="absolute z-20 mt-1 max-h-60 w-full overflow-auto rounded-lg border border-[rgba(56,189,248,0.15)] bg-[#0F172A] shadow-xl backdrop-blur-xl">
          {completed.length === 0 && (
            <p className="px-4 py-3 text-xs text-[#94A3B8]">No completed analyses</p>
          )}
          {completed.map((a) => (
            <button
              key={a.id}
              onClick={() => { onSelect(a.id); setOpen(false); }}
              className={`flex w-full items-center justify-between px-4 py-2.5 text-left transition-colors hover:bg-[#CBD5E1]/10 ${
                a.id === selectedId ? "bg-[#0EA5E9]/10 text-[#0EA5E9]" : "text-white"
              }`}
            >
              <span className="truncate text-sm">{a.filename}</span>
              <span className="ml-2 shrink-0 text-xs text-[#94A3B8]">{a.total_rooms ?? 0} rooms</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Stat comparison card                                                */
/* ------------------------------------------------------------------ */

function StatCompare({
  label,
  icon,
  valueA,
  valueB,
  suffix,
}: {
  label: string;
  icon: React.ReactNode;
  valueA: number;
  valueB: number;
  suffix?: string;
}) {
  const diff = valueA === 0 && valueB === 0 ? 0 : ((valueB - valueA) / Math.max(valueA, 1)) * 100;
  return (
    <div className="rounded-lg border border-[rgba(56,189,248,0.15)] bg-[#0F172A]/60 backdrop-blur-xl p-4">
      <div className="flex items-center gap-2 mb-3">
        {icon}
        <span className="text-xs uppercase tracking-wider text-[#94A3B8]">{label}</span>
      </div>
      <div className="grid grid-cols-[1fr_auto_1fr] items-end gap-3">
        <div>
          <p className="font-mono text-2xl font-bold text-[#0EA5E9]">{Math.round(valueA)}</p>
          <p className="text-[10px] text-[#94A3B8]">{suffix ?? ""} Plan A</p>
        </div>
        <span className="text-xs text-[#94A3B8] pb-1">vs</span>
        <div className="text-right">
          <p className="font-mono text-2xl font-bold text-[#A78BFA]">{Math.round(valueB)}</p>
          <p className="text-[10px] text-[#94A3B8]">{suffix ?? ""} Plan B</p>
        </div>
      </div>
      {diff !== 0 && (
        <p className={`mt-2 text-xs font-medium ${diff > 0 ? "text-[#34D399]" : "text-[#FBBF24]"}`}>
          Plan B is {Math.abs(Math.round(diff))}% {diff > 0 ? "more" : "less"}
        </p>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Main Page                                                           */
/* ------------------------------------------------------------------ */

export default function ComparePage() {
  const [analyses, setAnalyses] = useState<AnalysisSummary[]>([]);
  const [idA, setIdA] = useState<number | null>(null);
  const [idB, setIdB] = useState<number | null>(null);
  const [detailA, setDetailA] = useState<AnalysisDetail | null>(null);
  const [detailB, setDetailB] = useState<AnalysisDetail | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api.get("/analyses?page=1&per_page=100").then((res) => {
      setAnalyses(res.data.analyses ?? []);
    });
  }, []);

  useEffect(() => {
    if (!idA) { setDetailA(null); return; }
    setLoading(true);
    api.get(`/analyses/${idA}`).then((res) => { setDetailA(res.data); setLoading(false); }).catch(() => setLoading(false));
  }, [idA]);

  useEffect(() => {
    if (!idB) { setDetailB(null); return; }
    setLoading(true);
    api.get(`/analyses/${idB}`).then((res) => { setDetailB(res.data); setLoading(false); }).catch(() => setLoading(false));
  }, [idB]);

  const roomsA = useMemo(() => detailA ? extractRooms(detailA) : [], [detailA]);
  const roomsB = useMemo(() => detailB ? extractRooms(detailB) : [], [detailB]);
  const typesA = useMemo(() => countByType(roomsA), [roomsA]);
  const typesB = useMemo(() => countByType(roomsB), [roomsB]);

  const allTypes = useMemo(() => {
    const s = new Set([...Object.keys(typesA), ...Object.keys(typesB)]);
    return Array.from(s).sort();
  }, [typesA, typesB]);

  const chartData = useMemo(() =>
    allTypes.map((t) => ({
      name: t,
      "Plan A": Math.round(typesA[t]?.totalArea ?? 0),
      "Plan B": Math.round(typesB[t]?.totalArea ?? 0),
    })),
    [allTypes, typesA, typesB]
  );

  const ready = detailA && detailB;

  const insights = useMemo(() => {
    if (!ready) return [];
    const msgs: string[] = [];
    const areaA = totalArea(roomsA);
    const areaB = totalArea(roomsB);
    if (areaA && areaB) {
      const bigger = areaA > areaB ? "Plan A" : "Plan B";
      const pct = Math.abs(Math.round(((areaA - areaB) / Math.max(areaA, areaB)) * 100));
      if (pct > 3) msgs.push(`${bigger} is ${pct}% larger in total area.`);
    }
    for (const t of allTypes) {
      const cA = typesA[t]?.count ?? 0;
      const cB = typesB[t]?.count ?? 0;
      if (cA !== cB) {
        msgs.push(`${t}: Plan A has ${cA}, Plan B has ${cB}.`);
      } else if (cA > 0) {
        const avgA = Math.round((typesA[t]?.totalArea ?? 0) / cA);
        const avgB = Math.round((typesB[t]?.totalArea ?? 0) / cB);
        if (avgA && avgB && Math.abs(avgA - avgB) > 10) {
          const bigger = avgA > avgB ? "Plan A" : "Plan B";
          msgs.push(`${t}: Both have ${cA}, but ${bigger} averages ${Math.max(avgA, avgB)} sqft vs ${Math.min(avgA, avgB)} sqft.`);
        }
      }
    }
    const typesOnlyA = allTypes.filter((t) => (typesA[t]?.count ?? 0) > 0 && !(typesB[t]?.count));
    const typesOnlyB = allTypes.filter((t) => (typesB[t]?.count ?? 0) > 0 && !(typesA[t]?.count));
    if (typesOnlyA.length) msgs.push(`Only in Plan A: ${typesOnlyA.join(", ")}.`);
    if (typesOnlyB.length) msgs.push(`Only in Plan B: ${typesOnlyB.join(", ")}.`);
    return msgs;
  }, [ready, roomsA, roomsB, allTypes, typesA, typesB]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Link to="/history" className="rounded-lg p-1.5 text-[#94A3B8] hover:bg-[#CBD5E1]/20 hover:text-white">
          <ArrowLeft className="h-4 w-4" />
        </Link>
        <div>
          <h1 className="font-display text-2xl font-bold tracking-tight text-white flex items-center gap-2">
            <GitCompareArrows className="h-6 w-6 text-[#0EA5E9]" />
            Compare Floor Plans
          </h1>
          <p className="mt-1 text-sm text-[#94A3B8]">Select two completed analyses to compare side by side</p>
        </div>
      </div>

      {/* Selectors */}
      <div className="grid grid-cols-2 gap-4">
        <PlanSelector analyses={analyses} selectedId={idA} onSelect={setIdA} label="Plan A" />
        <PlanSelector analyses={analyses} selectedId={idB} onSelect={setIdB} label="Plan B" />
      </div>

      {!ready && (
        <div className="flex flex-col items-center justify-center py-20">
          <GitCompareArrows className="h-12 w-12 text-[#94A3B8]/20" />
          <p className="mt-4 text-sm text-[#94A3B8]">Select two floor plans above to begin comparison</p>
        </div>
      )}

      {ready && (
        <>
          {/* Side-by-side overlays */}
          <div className="grid grid-cols-2 gap-4">
            {[detailA, detailB].map((d, i) => (
              <div key={d!.id} className="overflow-hidden rounded-xl border border-[rgba(56,189,248,0.15)] bg-[#0F172A]/60 backdrop-blur-xl">
                <img
                  src={getOverlayUrl(d!)}
                  alt={d!.filename}
                  className="w-full object-contain max-h-[400px] bg-slate-950"
                />
                <div className="flex items-center justify-between border-t border-[rgba(56,189,248,0.15)] px-4 py-2">
                  <span className={`text-xs font-bold ${i === 0 ? "text-[#0EA5E9]" : "text-[#A78BFA]"}`}>
                    Plan {i === 0 ? "A" : "B"}
                  </span>
                  <span className="text-xs text-[#94A3B8] truncate ml-2">{d!.filename}</span>
                  <span className="ml-auto text-xs font-mono text-white">{bhkLabel(i === 0 ? roomsA : roomsB)}</span>
                </div>
              </div>
            ))}
          </div>

          {/* Stats comparison */}
          <div className="grid grid-cols-3 gap-4">
            <StatCompare
              label="Total Rooms"
              icon={<Home className="h-4 w-4 text-[#0EA5E9]" />}
              valueA={roomsA.length}
              valueB={roomsB.length}
            />
            <StatCompare
              label="Total Area"
              icon={<Ruler className="h-4 w-4 text-[#22D3EE]" />}
              valueA={totalArea(roomsA)}
              valueB={totalArea(roomsB)}
              suffix="sqft"
            />
            <StatCompare
              label="Labelled Rooms"
              icon={<Tag className="h-4 w-4 text-[#34D399]" />}
              valueA={roomsA.filter((r) => r.label !== "Room").length}
              valueB={roomsB.filter((r) => r.label !== "Room").length}
            />
          </div>

          {/* Room type comparison table */}
          <div className="rounded-xl border border-[rgba(56,189,248,0.15)] bg-[#0F172A]/60 backdrop-blur-xl overflow-hidden">
            <div className="border-b border-[rgba(56,189,248,0.15)] bg-[#CBD5E1]/10 px-4 py-3">
              <h2 className="text-sm font-semibold text-white flex items-center gap-2">
                <BarChart3 className="h-4 w-4 text-[#0EA5E9]" /> Room-by-Room Breakdown
              </h2>
            </div>
            <div className="grid grid-cols-[1fr_100px_100px_100px_100px] gap-2 px-4 py-2 text-[10px] uppercase tracking-wider text-[#94A3B8] border-b border-[rgba(56,189,248,0.08)]">
              <span>Room Type</span>
              <span className="text-center">Count A</span>
              <span className="text-center">Count B</span>
              <span className="text-center">Area A (sqft)</span>
              <span className="text-center">Area B (sqft)</span>
            </div>
            {allTypes.map((t) => (
              <div key={t} className="grid grid-cols-[1fr_100px_100px_100px_100px] gap-2 px-4 py-2.5 text-sm border-b border-[rgba(56,189,248,0.05)] hover:bg-[#CBD5E1]/5">
                <span className="text-white font-medium">{t}</span>
                <span className="text-center font-mono text-[#0EA5E9]">{typesA[t]?.count ?? 0}</span>
                <span className="text-center font-mono text-[#A78BFA]">{typesB[t]?.count ?? 0}</span>
                <span className="text-center font-mono text-[#0EA5E9]">{Math.round(typesA[t]?.totalArea ?? 0)}</span>
                <span className="text-center font-mono text-[#A78BFA]">{Math.round(typesB[t]?.totalArea ?? 0)}</span>
              </div>
            ))}
          </div>

          {/* Bar chart */}
          {chartData.length > 0 && (
            <div className="rounded-xl border border-[rgba(56,189,248,0.15)] bg-[#0F172A]/60 backdrop-blur-xl p-6">
              <h2 className="mb-4 text-sm font-semibold text-white">Area Distribution by Room Type (sqft)</h2>
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={chartData} barGap={4}>
                  <XAxis dataKey="name" tick={{ fill: "#94A3B8", fontSize: 11 }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fill: "#94A3B8", fontSize: 11 }} axisLine={false} tickLine={false} />
                  <Tooltip
                    contentStyle={{ background: "#0F172A", border: "1px solid rgba(56,189,248,0.3)", borderRadius: 8, color: "#fff" }}
                  />
                  <Legend />
                  <Bar dataKey="Plan A" fill="#0EA5E9" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="Plan B" fill="#8B5CF6" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* AI Insights */}
          {insights.length > 0 && (
            <div className="rounded-xl border border-[rgba(56,189,248,0.15)] bg-[#0F172A]/60 backdrop-blur-xl p-6">
              <h2 className="mb-3 text-sm font-semibold text-white">Key Differences</h2>
              <ul className="space-y-2">
                {insights.map((msg, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-[#94A3B8]">
                    <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-[#0EA5E9]" />
                    {msg}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}
    </div>
  );
}
