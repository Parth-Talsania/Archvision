import { useState, useEffect, useRef, useCallback, useMemo } from "react";
import {
  PieChart, Pie, Cell, Tooltip as ReTooltip, ResponsiveContainer,
  RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
  BarChart, Bar, XAxis, YAxis, CartesianGrid, type TooltipProps,
} from "recharts";
import type { Room } from "@/types/analysis";

/* ================================================================== */
/*  THEME CONSTANTS                                                    */
/* ================================================================== */

const NEON = {
  neonCyan:  "#00F0FF",
  skyBlue:   "#0EA5E9",
  royalBlue: "#2563EB",
  indigo:    "#818CF8",
  deepOcean: "#0284C7",
  electricCyan: "#00D4FF",
  slate:     "#94A3B8",
};

const DOUGHNUT_COLORS = [NEON.neonCyan, NEON.skyBlue, NEON.royalBlue, NEON.indigo];

/* ================================================================== */
/*  UTILITY: Count-Up Hook (pure React, no deps)                       */
/* ================================================================== */

function useCountUp(end: number, duration = 1400, decimals = 0) {
  const [value, setValue] = useState(0);
  const raf = useRef<number>(0);
  const start = useRef(0);

  useEffect(() => {
    if (!end) { setValue(0); return; }
    start.current = performance.now();
    const animate = (now: number) => {
      const elapsed = now - start.current;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3); // ease-out cubic
      setValue(Number((eased * end).toFixed(decimals)));
      if (progress < 1) raf.current = requestAnimationFrame(animate);
    };
    raf.current = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(raf.current);
  }, [end, duration, decimals]);

  return value;
}

/* ================================================================== */
/*  UTILITY: Intersection Observer for animate-on-scroll               */
/* ================================================================== */

function useInView(threshold = 0.2) {
  const ref = useRef<HTMLDivElement>(null);
  const [inView, setInView] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const obs = new IntersectionObserver(([e]) => { if (e.isIntersecting) setInView(true); }, { threshold });
    obs.observe(el);
    return () => obs.disconnect();
  }, [threshold]);
  return { ref, inView };
}

/* ================================================================== */
/*  DATA HELPERS                                                       */
/* ================================================================== */


type Category = "Sleeping" | "Living" | "Utility" | "Outdoor";

function categorize(label: string): Category {
  const l = label.toLowerCase();
  if (/bed|master\s*bed|bunk/i.test(l)) return "Sleeping";
  if (/living|lounge|family|hall|dining|kitchen|drawing|sit/i.test(l)) return "Living";
  if (/balcony|terrace|deck|patio|garden|yard|verandah|porch/i.test(l)) return "Outdoor";
  return "Utility"; // toilet, corridor, passage, store, utility, wash, laundry, etc.
}

function getRoomArea(room: Room): number {
  if (room.area?.value_sqft) return room.area.value_sqft;
  if (room.dimensions_parsed?.area_sqft) return room.dimensions_parsed.area_sqft;
  return 0;
}

function getRoomLabel(room: Room): string {
  return room.label || room.label_raw || `Room ${room.id}`;
}

/* ================================================================== */
/*  SKELETON LOADER                                                    */
/* ================================================================== */

function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`rounded-xl animate-galaxy-pulse ${className}`} />;
}

function DashboardSkeleton() {
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {[...Array(4)].map((_, i) => <Skeleton key={i} className="h-32" />)}
      </div>
      <div className="grid gap-6 lg:grid-cols-2">
        <Skeleton className="h-80" />
        <Skeleton className="h-80" />
      </div>
      <Skeleton className="h-72" />
    </div>
  );
}

/* ================================================================== */
/*  GLASSMORPHISM CUSTOM TOOLTIP                                       */
/* ================================================================== */

function GlassTooltip({ active, payload, label }: TooltipProps<number, string>) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-xl border border-[rgba(56,189,248,0.15)] bg-slate-900/80 px-4 py-3 shadow-2xl backdrop-blur-xl">
      {label && <p className="mb-1 text-xs font-semibold uppercase tracking-wider text-[#94A3B8]">{label}</p>}
      {payload.map((p, i) => (
        <p key={i} className="text-sm font-bold" style={{ color: p.color || p.payload?.fill || NEON.neonCyan }}>
          {p.name}: {typeof p.value === "number" ? p.value.toLocaleString(undefined, { maximumFractionDigits: 1 }) : p.value}
          {p.payload?.unit || " sq ft"}
        </p>
      ))}
    </div>
  );
}

/* ================================================================== */
/*  KPI HERO CARD                                                      */
/* ================================================================== */

function KPICard({ icon, title, value, suffix, decimals = 0, sub, delay = 0 }: {
  icon: string; title: string; value: number; suffix?: string; decimals?: number; sub?: string; delay?: number;
}) {
  const animated = useCountUp(value, 1600, decimals);
  const { ref, inView } = useInView();

  return (
    <div
      ref={ref}
      className="group relative overflow-hidden rounded-2xl border border-[rgba(56,189,248,0.15)] bg-slate-900/40 p-5 backdrop-blur-xl transition-all duration-500 hover:border-[rgba(56,189,248,0.4)] hover:bg-[#0F172A]/70 hover:shadow-[0_0_15px_rgba(56,189,248,0.1)]"
      style={{
        opacity: inView ? 1 : 0,
        transform: inView ? "translateY(0)" : "translateY(24px)",
        transition: `all 0.7s cubic-bezier(0.16, 1, 0.3, 1) ${delay}ms`,
      }}
    >
      {/* Glow orb */}
      <div className="pointer-events-none absolute -right-6 -top-6 h-24 w-24 rounded-full bg-[#0EA5E9]/10 blur-2xl transition-all duration-500 group-hover:bg-[#0EA5E9]/20" />
      <div className="pointer-events-none absolute -bottom-4 -left-4 h-16 w-16 rounded-full bg-[#00F0FF]/8 blur-2xl transition-all duration-500 group-hover:bg-[#00F0FF]/12" />

      <div className="relative z-10">
        <span className="text-2xl">{icon}</span>
        <p className="mt-2 text-[11px] font-semibold uppercase tracking-widest text-[#94A3B8]">{title}</p>
        <p className="mt-1 font-mono text-3xl font-black tracking-tighter text-[#FFFFFF]">
          {inView ? animated.toLocaleString(undefined, { maximumFractionDigits: decimals }) : "0"}
          {suffix && <span className="ml-1 text-base font-medium text-[#CBD5E1]">{suffix}</span>}
        </p>
        {sub && <p className="mt-1 text-xs text-[#64748B]">{sub}</p>}
      </div>
    </div>
  );
}

/* ================================================================== */
/*  CIRCULAR GAUGE (Space Efficiency)                                  */
/* ================================================================== */

function CircularGauge({ value, delay = 0 }: { value: number; delay?: number }) {
  const animated = useCountUp(value, 1800, 0);
  const { ref, inView } = useInView();
  const radius = 42;
  const circumference = 2 * Math.PI * radius;
  const dashOffset = circumference - (circumference * (inView ? animated : 0)) / 100;

  return (
    <div
      ref={ref}
      className="group relative overflow-hidden rounded-2xl border border-[rgba(56,189,248,0.15)] bg-slate-900/40 p-5 backdrop-blur-xl transition-all duration-500 hover:border-[rgba(56,189,248,0.4)] hover:bg-[#0F172A]/70 hover:shadow-[0_0_15px_rgba(56,189,248,0.1)]"
      style={{
        opacity: inView ? 1 : 0,
        transform: inView ? "translateY(0)" : "translateY(24px)",
        transition: `all 0.7s cubic-bezier(0.16, 1, 0.3, 1) ${delay}ms`,
      }}
    >
      <div className="pointer-events-none absolute -right-6 -top-6 h-24 w-24 rounded-full bg-[#38BDF8]/10 blur-2xl" />
      <div className="relative z-10 flex items-center gap-4">
        <svg width="96" height="96" viewBox="0 0 96 96" className="shrink-0">
          <circle cx="48" cy="48" r={radius} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="7" />
          <circle
            cx="48" cy="48" r={radius} fill="none"
            stroke="url(#gaugeGrad)" strokeWidth="7" strokeLinecap="round"
            strokeDasharray={circumference} strokeDashoffset={dashOffset}
            transform="rotate(-90 48 48)"
            style={{ transition: "stroke-dashoffset 1.8s cubic-bezier(0.16, 1, 0.3, 1)" }}
          />
          <defs>
            <linearGradient id="gaugeGrad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor={NEON.deepOcean} />
              <stop offset="100%" stopColor={NEON.electricCyan} />
            </linearGradient>
          </defs>
          <text x="48" y="48" textAnchor="middle" dominantBaseline="central"
            className="fill-white text-xl font-black" style={{ fontFamily: '"JetBrains Mono", monospace' }}>{inView ? animated : 0}%</text>
        </svg>
        <div>
          <span className="text-2xl">⚡</span>
          <p className="mt-1 text-[11px] font-semibold uppercase tracking-widest text-[#94A3B8]">Space Efficiency</p>
          <p className="mt-0.5 text-xs text-[#64748B]">Usable vs Utility ratio</p>
        </div>
      </div>
    </div>
  );
}

/* ================================================================== */
/*  DOUGHNUT CHART — Space Allocation                                  */
/* ================================================================== */

function DoughnutChart({ data }: { data: { name: string; value: number }[] }) {
  const { ref, inView } = useInView();
  const [activeIdx, setActiveIdx] = useState<number | null>(null);
  const total = data.reduce((s, d) => s + d.value, 0);

  const CustomTooltip = useCallback(({ active, payload }: TooltipProps<number, string>) => {
    if (!active || !payload?.length) return null;
    const d = payload[0];
    const pct = total ? ((d.value / total) * 100).toFixed(1) : "0";
    return (
      <div className="rounded-xl border border-[rgba(56,189,248,0.15)] bg-slate-900/80 px-4 py-3 shadow-2xl backdrop-blur-xl">
        <p className="text-xs font-semibold uppercase tracking-wider" style={{ color: d.payload?.fill }}>{d.name}</p>
        <p className="font-mono text-lg font-black text-[#FFFFFF]">{d.value.toLocaleString()} sq ft</p>
        <p className="font-mono text-xs text-[#CBD5E1]">{pct}% of total</p>
      </div>
    );
  }, [total]);

  return (
    <div
      ref={ref}
      className="relative overflow-hidden rounded-2xl border border-[rgba(56,189,248,0.15)] bg-slate-900/40 p-6 backdrop-blur-xl transition-all duration-700"
      style={{ opacity: inView ? 1 : 0, transform: inView ? "translateY(0)" : "translateY(30px)", transition: "all 0.8s cubic-bezier(0.16,1,0.3,1)" }}
    >
      <div className="pointer-events-none absolute -right-10 -top-10 h-40 w-40 rounded-full bg-[#0EA5E9]/5 blur-3xl" />
      <h3 className="mb-1 font-display text-xs font-bold uppercase tracking-widest text-[#94A3B8]">Space Allocation</h3>
      <p className="mb-4 text-[11px] text-[#64748B]">Area breakdown by category</p>

      <ResponsiveContainer width="100%" height={280}>
        <PieChart>
          <Pie
            data={data} dataKey="value" nameKey="name"
            cx="50%" cy="50%" innerRadius="55%" outerRadius="80%"
            paddingAngle={3} strokeWidth={0}
            onMouseEnter={(_, idx) => setActiveIdx(idx)}
            onMouseLeave={() => setActiveIdx(null)}
          >
            {data.map((_, idx) => (
              <Cell
                key={idx}
                fill={DOUGHNUT_COLORS[idx % DOUGHNUT_COLORS.length]}
                opacity={activeIdx !== null && activeIdx !== idx ? 0.35 : 1}
                style={{ transition: "all 0.3s ease", filter: activeIdx === idx ? `drop-shadow(0 0 12px ${DOUGHNUT_COLORS[idx % DOUGHNUT_COLORS.length]}80)` : "none" }}
              />
            ))}
          </Pie>
          <ReTooltip content={<CustomTooltip />} />
        </PieChart>
      </ResponsiveContainer>

      {/* Legend */}
      <div className="mt-3 flex flex-wrap justify-center gap-3">
        {data.map((d, i) => (
          <div key={d.name} className="flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: DOUGHNUT_COLORS[i % DOUGHNUT_COLORS.length] }} />
            <span className="text-[11px] text-[#CBD5E1]">{d.name}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ================================================================== */
/*  RADAR CHART — Architectural Balance                                */
/* ================================================================== */

function ArchRadarChart({ scores }: { scores: { subject: string; value: number; fullMark: number }[] }) {
  const { ref, inView } = useInView();

  return (
    <div
      ref={ref}
      className="relative overflow-hidden rounded-2xl border border-[rgba(56,189,248,0.15)] bg-slate-900/40 p-6 backdrop-blur-xl transition-all duration-700"
      style={{ opacity: inView ? 1 : 0, transform: inView ? "translateY(0)" : "translateY(30px)", transition: "all 0.8s cubic-bezier(0.16,1,0.3,1) 100ms" }}
    >
      <div className="pointer-events-none absolute -left-10 -bottom-10 h-40 w-40 rounded-full bg-[#2563EB]/5 blur-3xl" />
      <h3 className="mb-1 font-display text-xs font-bold uppercase tracking-widest text-[#94A3B8]">Architectural Balance</h3>
      <p className="mb-4 text-[11px] text-[#64748B]">Functional profile of the floor plan</p>

      <ResponsiveContainer width="100%" height={280}>
        <RadarChart data={scores} cx="50%" cy="50%" outerRadius="70%">
          <PolarGrid stroke="rgba(255,255,255,0.06)" />
          <PolarAngleAxis dataKey="subject" tick={{ fill: "rgba(255,255,255,0.45)", fontSize: 11, fontWeight: 600 }} />
          <PolarRadiusAxis domain={[0, 100]} tick={false} axisLine={false} />
          <defs>
            <linearGradient id="radarFill" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#00F0FF" stopOpacity={0.2} />
              <stop offset="100%" stopColor="#0EA5E9" stopOpacity={0.08} />
            </linearGradient>
          </defs>
          <Radar name="Score" dataKey="value" stroke="#00F0FF" fill="url(#radarFill)" strokeWidth={2}
            dot={{ fill: NEON.neonCyan, r: 4, strokeWidth: 0 }} />
          <ReTooltip content={<GlassTooltip />}
            formatter={(v: number) => [`${v}`, "Score"]}
            labelFormatter={(l: string) => l} />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
}

/* ================================================================== */
/*  HORIZONTAL BAR CHART — Room Size Hierarchy                         */
/* ================================================================== */

function RoomBarsChart({ data }: { data: { name: string; area: number; fill: string }[] }) {
  const { ref, inView } = useInView(0.15);

  const BarTooltip = useCallback(({ active, payload }: TooltipProps<number, string>) => {
    if (!active || !payload?.length) return null;
    const d = payload[0];
    return (
      <div className="rounded-xl border border-[rgba(56,189,248,0.15)] bg-slate-900/80 px-4 py-3 shadow-2xl backdrop-blur-xl">
        <p className="text-xs font-semibold text-[#FFFFFF]">{d.payload?.name}</p>
        <p className="font-mono text-lg font-black" style={{ color: d.payload?.fill }}>{d.value.toLocaleString()} sq ft</p>
      </div>
    );
  }, []);

  return (
    <div
      ref={ref}
      className="relative overflow-hidden rounded-2xl border border-[rgba(56,189,248,0.15)] bg-slate-900/40 p-6 backdrop-blur-xl transition-all duration-700"
      style={{ opacity: inView ? 1 : 0, transform: inView ? "translateY(0)" : "translateY(30px)", transition: "all 0.8s cubic-bezier(0.16,1,0.3,1) 200ms" }}
    >
      <div className="pointer-events-none absolute -right-10 -bottom-10 h-40 w-40 rounded-full bg-[#00F0FF]/5 blur-3xl" />
      <h3 className="mb-1 font-display text-xs font-bold uppercase tracking-widest text-[#94A3B8]">Room Size Hierarchy</h3>
      <p className="mb-4 text-[11px] text-[#64748B]">Individual rooms ranked by area</p>

      <ResponsiveContainer width="100%" height={Math.max(220, data.length * 44)}>
        <BarChart data={data} layout="vertical" margin={{ left: 10, right: 20, top: 0, bottom: 0 }}>
          <CartesianGrid horizontal={false} vertical={false} />
          <XAxis type="number" hide />
          <YAxis type="category" dataKey="name" width={120}
            tick={{ fill: "rgba(255,255,255,0.5)", fontSize: 11, fontWeight: 500 }}
            axisLine={false} tickLine={false} />
          <Bar dataKey="area" radius={[0, 10, 10, 0]} barSize={22}
            animationBegin={300} animationDuration={1200} animationEasing="ease-out"
          >
            {data.map((d, i) => (
              <Cell key={i} fill={d.fill} className="transition-all duration-300 hover:brightness-125"
                style={{ filter: "drop-shadow(0 0 6px " + d.fill + "40)" }} />
            ))}
          </Bar>
          <ReTooltip content={<BarTooltip />} cursor={{ fill: "rgba(255,255,255,0.03)" }} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

/* ================================================================== */
/*  EXPORT BUTTON                                                      */
/* ================================================================== */

function ExportButton({ rooms, filename }: { rooms: Room[]; filename: string }) {
  const [state, setState] = useState<"idle" | "exporting" | "done">("idle");

  const handleExport = () => {
    setState("exporting");
    // Build a simple text report and download
    setTimeout(() => {
      const lines: string[] = [
        "╔══════════════════════════════════════════╗",
        "║   ARCHVISION — FLOOR PLAN ANALYTICS      ║",
        "╚══════════════════════════════════════════╝",
        "",
        `File: ${filename}`,
        `Generated: ${new Date().toLocaleString()}`,
        `Total Rooms: ${rooms.length}`,
        "",
        "─── Room Details ───",
        "",
      ];
      rooms.forEach((r) => {
        const area = getRoomArea(r);
        lines.push(`  ${getRoomLabel(r)}${area ? ` — ${area.toLocaleString()} sq ft` : ""}`);
      });
      lines.push("");
      lines.push("─── Category Breakdown ───");
      const cats: Record<string, number> = {};
      rooms.forEach((r) => {
        const cat = categorize(getRoomLabel(r));
        cats[cat] = (cats[cat] || 0) + getRoomArea(r);
      });
      Object.entries(cats).forEach(([k, v]) => lines.push(`  ${k}: ${v.toLocaleString()} sq ft`));

      const blob = new Blob([lines.join("\n")], { type: "text/plain" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${filename.replace(/\.[^.]+$/, "")}_analytics_report.txt`;
      a.click();
      URL.revokeObjectURL(url);
      setState("done");
      setTimeout(() => setState("idle"), 2200);
    }, 800);
  };

  return (
    <button
      onClick={handleExport}
      disabled={state !== "idle"}
      className="relative inline-flex items-center gap-2 overflow-hidden rounded-xl border border-[rgba(56,189,248,0.15)] bg-quantum-blue px-5 py-2.5 text-sm font-bold text-[#FFFFFF] shadow-lg transition-all duration-300 hover:shadow-[0_0_30px_rgba(0,240,255,0.3)] active:scale-95 disabled:opacity-60"
    >
      {/* shimmer sweep */}
      <span className="pointer-events-none absolute inset-0 bg-gradient-to-r from-transparent via-[#FFFFFF]/10 to-transparent opacity-0 transition-opacity duration-300 group-hover:opacity-100"
        style={{ backgroundSize: "200% 100%", animation: state === "idle" ? "none" : "none" }} />

      {state === "idle" && (
        <>
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="#FFFFFF" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          Download Report
        </>
      )}
      {state === "exporting" && (
        <>
          <svg className="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="#FFFFFF" strokeWidth="4" />
            <path className="opacity-75" fill="#FFFFFF" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          Generating...
        </>
      )}
      {state === "done" && (
        <>
          <svg className="h-5 w-5 text-[#34D399]" fill="none" viewBox="0 0 24 24" stroke="#FFFFFF" strokeWidth={3}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
          </svg>
          <span className="text-[#6EE7B7]">Downloaded!</span>
        </>
      )}
    </button>
  );
}

/* ================================================================== */
/*  MAIN DASHBOARD COMPONENT                                           */
/* ================================================================== */

export default function AnalyticsDashboard({ rooms, filename }: { rooms: Room[]; filename: string }) {
  const [ready, setReady] = useState(false);
  useEffect(() => { const t = setTimeout(() => setReady(true), 350); return () => clearTimeout(t); }, []);

  /* ---- Derived data ---- */
  const totalArea = useMemo(() => rooms.reduce((s, r) => s + getRoomArea(r), 0), [rooms]);
  const roomCount = rooms.length;

  const largest = useMemo(() => {
    let best: Room | null = null;
    let bestArea = 0;
    rooms.forEach((r) => { const a = getRoomArea(r); if (a > bestArea) { bestArea = a; best = r; } });
    return best ? { label: getRoomLabel(best), area: bestArea } : { label: "—", area: 0 };
  }, [rooms]);

  const efficiency = useMemo(() => {
    let usable = 0, total = 0;
    rooms.forEach((r) => {
      const a = getRoomArea(r);
      total += a;
      const cat = categorize(getRoomLabel(r));
      if (cat === "Sleeping" || cat === "Living" || cat === "Outdoor") usable += a;
    });
    return total > 0 ? Math.round((usable / total) * 100) : 0;
  }, [rooms]);

  // Doughnut data
  const doughnutData = useMemo(() => {
    const cats: Record<Category, number> = { Sleeping: 0, Living: 0, Utility: 0, Outdoor: 0 };
    rooms.forEach((r) => { cats[categorize(getRoomLabel(r))] += getRoomArea(r); });
    return Object.entries(cats).filter(([, v]) => v > 0).map(([k, v]) => ({ name: k, value: Math.round(v) }));
  }, [rooms]);

  // Radar scores (0-100 scale)
  const radarScores = useMemo(() => {
    const counts: Record<string, number> = { Living: 0, Privacy: 0, Utility: 0, Circulation: 0, Outdoors: 0 };
    rooms.forEach((r) => {
      const l = getRoomLabel(r).toLowerCase();
      if (/living|hall|dining|kitchen|drawing|family|sit/i.test(l)) counts.Living++;
      if (/bed|master/i.test(l)) counts.Privacy++;
      if (/toilet|wash|bath|store|utility|laundry/i.test(l)) counts.Utility++;
      if (/corridor|passage|lobby|foyer|stair/i.test(l)) counts.Circulation++;
      if (/balcony|terrace|deck|patio|garden|verandah|porch/i.test(l)) counts.Outdoors++;
    });
    const maxC = Math.max(...Object.values(counts), 1);
    return Object.entries(counts).map(([k, v]) => ({
      subject: k,
      value: Math.round(Math.min((v / maxC) * 100, 100)),
      fullMark: 100,
    }));
  }, [rooms]);

  // Bar chart data
  const barData = useMemo(() => {
    return rooms
      .map((r, i) => ({
        name: getRoomLabel(r),
        area: Math.round(getRoomArea(r)),
        fill: DOUGHNUT_COLORS[i % DOUGHNUT_COLORS.length],
      }))
      .filter((d) => d.area > 0)
      .sort((a, b) => b.area - a.area);
  }, [rooms]);

  if (!ready) return <DashboardSkeleton />;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-quantum-blue font-display text-lg font-bold tracking-tight">Insights & Analytics</h2>
          <p className="text-xs text-[#94A3B8]">AI-generated floor plan intelligence</p>
        </div>
        <ExportButton rooms={rooms} filename={filename} />
      </div>

      {/* KPI Hero Cards */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <KPICard icon="📏" title="Total Usable Area" value={Math.round(totalArea)} suffix="sq ft" delay={0} />
        <KPICard icon="🏠" title="Room Count" value={roomCount} delay={100} />
        <KPICard icon="👑" title="Largest Space" value={Math.round(largest.area)} suffix="sq ft" delay={200}
          sub={largest.label} />
        <CircularGauge value={efficiency} delay={300} />
      </div>

      {/* Charts Row */}
      <div className="grid gap-6 lg:grid-cols-2">
        <DoughnutChart data={doughnutData} />
        <ArchRadarChart scores={radarScores} />
      </div>

      {/* Horizontal Bar */}
      {barData.length > 0 && <RoomBarsChart data={barData} />}
    </div>
  );
}
