import { useMemo, useState } from "react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
  PieChart, Pie,
} from "recharts";
import { IndianRupee, Sliders, Building2, Paintbrush } from "lucide-react";

/* ------------------------------------------------------------------ */
/*  Types                                                               */
/* ------------------------------------------------------------------ */

interface Room {
  id: number;
  label?: string | null;
  label_raw?: string | null;
  dimensions?: string | null;
  dimensions_parsed?: {
    width_ft?: number;
    width_in?: number;
    height_ft?: number;
    height_in?: number;
    area_sqft?: number;
  } | null;
  area?: {
    value_sqft?: number | null;
  } | null;
}

interface CostEstimatorProps {
  rooms: Room[];
  filename: string;
}

/* ------------------------------------------------------------------ */
/*  Cost model                                                          */
/* ------------------------------------------------------------------ */

const ROOM_MULTIPLIERS: Record<string, { construction: number; interior: number; label: string }> = {
  kitchen:          { construction: 1.30, interior: 1.80, label: "Kitchen (plumbing + counters)" },
  toilet:           { construction: 1.50, interior: 1.60, label: "Toilet/Bath (tiling + fixtures)" },
  bathroom:         { construction: 1.50, interior: 1.60, label: "Bathroom (tiling + fixtures)" },
  wash:             { construction: 1.40, interior: 1.20, label: "Wash Area" },
  balcony:          { construction: 0.60, interior: 0.30, label: "Balcony (open area)" },
  terrace:          { construction: 0.50, interior: 0.20, label: "Terrace (open area)" },
  "sit-out":        { construction: 0.60, interior: 0.30, label: "Sit-Out (open area)" },
  passage:          { construction: 0.90, interior: 0.50, label: "Passage / Corridor" },
  lobby:            { construction: 0.90, interior: 0.60, label: "Lobby" },
  staircase:        { construction: 1.20, interior: 0.40, label: "Staircase" },
  pooja:            { construction: 1.00, interior: 1.50, label: "Pooja Room (woodwork)" },
  store:            { construction: 0.90, interior: 0.50, label: "Store Room" },
  utility:          { construction: 1.10, interior: 0.60, label: "Utility Room" },
};

const DEFAULT_MULTIPLIER = { construction: 1.00, interior: 1.00, label: "Standard Room" };

function getMultiplier(label: string) {
  const lower = (label || "").toLowerCase();
  for (const [key, val] of Object.entries(ROOM_MULTIPLIERS)) {
    if (lower.includes(key)) return val;
  }
  return DEFAULT_MULTIPLIER;
}

function getRoomArea(r: Room): number {
  return r.area?.value_sqft ?? r.dimensions_parsed?.area_sqft ?? 0;
}

function getRoomLabel(r: Room): string {
  return r.label || r.label_raw || `Room ${r.id}`;
}

function formatINR(n: number): string {
  if (n >= 10000000) return `${(n / 10000000).toFixed(2)} Cr`;
  if (n >= 100000) return `${(n / 100000).toFixed(2)} L`;
  return n.toLocaleString("en-IN");
}

const PIE_COLORS = ["#0EA5E9", "#8B5CF6", "#F59E0B", "#10B981", "#EF4444", "#EC4899", "#14B8A6", "#F97316"];

/* ------------------------------------------------------------------ */
/*  Component                                                           */
/* ------------------------------------------------------------------ */

export default function CostEstimator({ rooms, filename }: CostEstimatorProps) {
  const [baseRate, setBaseRate] = useState(1800);
  const [interiorRate, setInteriorRate] = useState(800);

  const breakdown = useMemo(() => {
    return rooms.map((r) => {
      const label = getRoomLabel(r);
      const area = getRoomArea(r);
      const mult = getMultiplier(label);
      return {
        id: r.id,
        label,
        area,
        constructionMult: mult.construction,
        interiorMult: mult.interior,
        multLabel: mult.label,
        constructionCost: Math.round(area * baseRate * mult.construction),
        interiorCost: Math.round(area * interiorRate * mult.interior),
      };
    }).filter((r) => r.area > 0);
  }, [rooms, baseRate, interiorRate]);

  const totalArea = breakdown.reduce((s, r) => s + r.area, 0);
  const totalConstruction = breakdown.reduce((s, r) => s + r.constructionCost, 0);
  const totalInterior = breakdown.reduce((s, r) => s + r.interiorCost, 0);
  const totalCost = totalConstruction + totalInterior;

  const barData = breakdown.map((r) => ({
    name: r.label,
    Construction: r.constructionCost,
    Interior: r.interiorCost,
  }));

  const pieData = breakdown.map((r) => ({
    name: r.label,
    value: r.constructionCost + r.interiorCost,
  }));

  return (
    <div className="space-y-6">
      {/* Rate controls */}
      <div className="rounded-xl border border-[rgba(56,189,248,0.15)] bg-[#0F172A]/60 backdrop-blur-xl p-6">
        <div className="flex items-center gap-2 mb-4">
          <Sliders className="h-4 w-4 text-[#0EA5E9]" />
          <h2 className="text-sm font-semibold text-white">Cost Parameters</h2>
          <span className="ml-auto text-xs text-[#94A3B8]">Adjust rates per your city / quality tier</span>
        </div>
        <div className="grid grid-cols-2 gap-6">
          <div>
            <label className="flex items-center justify-between text-xs text-[#94A3B8] mb-2">
              <span className="flex items-center gap-1"><Building2 className="h-3 w-3" /> Construction Rate</span>
              <span className="font-mono text-white">Rs {baseRate}/sqft</span>
            </label>
            <input
              type="range" min={800} max={4000} step={100} value={baseRate}
              onChange={(e) => setBaseRate(Number(e.target.value))}
              className="w-full accent-[#0EA5E9]"
            />
            <div className="flex justify-between text-[10px] text-[#94A3B8] mt-1">
              <span>Rs 800</span><span>Rs 4,000</span>
            </div>
          </div>
          <div>
            <label className="flex items-center justify-between text-xs text-[#94A3B8] mb-2">
              <span className="flex items-center gap-1"><Paintbrush className="h-3 w-3" /> Interior Rate</span>
              <span className="font-mono text-white">Rs {interiorRate}/sqft</span>
            </label>
            <input
              type="range" min={300} max={2500} step={100} value={interiorRate}
              onChange={(e) => setInteriorRate(Number(e.target.value))}
              className="w-full accent-[#8B5CF6]"
            />
            <div className="flex justify-between text-[10px] text-[#94A3B8] mt-1">
              <span>Rs 300</span><span>Rs 2,500</span>
            </div>
          </div>
        </div>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-4 gap-4">
        {[
          { label: "Total Carpet Area", value: `${Math.round(totalArea)} sqft`, color: "text-white" },
          { label: "Construction Cost", value: `Rs ${formatINR(totalConstruction)}`, color: "text-[#0EA5E9]" },
          { label: "Interior Cost", value: `Rs ${formatINR(totalInterior)}`, color: "text-[#8B5CF6]" },
          { label: "Total Estimated Cost", value: `Rs ${formatINR(totalCost)}`, color: "text-[#34D399]" },
        ].map((card) => (
          <div key={card.label} className="rounded-xl border border-[rgba(56,189,248,0.15)] bg-[#0F172A]/60 backdrop-blur-xl p-4 text-center">
            <p className="text-[10px] uppercase tracking-wider text-[#94A3B8]">{card.label}</p>
            <p className={`mt-2 font-mono text-xl font-bold ${card.color}`}>{card.value}</p>
          </div>
        ))}
      </div>

      {/* Charts side by side */}
      <div className="grid grid-cols-[1fr_320px] gap-4">
        {/* Bar chart */}
        <div className="rounded-xl border border-[rgba(56,189,248,0.15)] bg-[#0F172A]/60 backdrop-blur-xl p-6">
          <h2 className="mb-4 text-sm font-semibold text-white">Cost Breakdown by Room</h2>
          <ResponsiveContainer width="100%" height={Math.max(250, breakdown.length * 40)}>
            <BarChart data={barData} layout="vertical" barGap={2}>
              <XAxis type="number" tick={{ fill: "#94A3B8", fontSize: 10 }} axisLine={false} tickLine={false}
                tickFormatter={(v) => `Rs ${formatINR(v)}`} />
              <YAxis type="category" dataKey="name" tick={{ fill: "#94A3B8", fontSize: 11 }} axisLine={false} tickLine={false} width={120} />
              <Tooltip
                contentStyle={{ background: "#0F172A", border: "1px solid rgba(56,189,248,0.3)", borderRadius: 8, color: "#fff" }}
                formatter={(v: number) => `Rs ${formatINR(v)}`}
              />
              <Bar dataKey="Construction" fill="#0EA5E9" radius={[0, 4, 4, 0]} stackId="cost" />
              <Bar dataKey="Interior" fill="#8B5CF6" radius={[0, 4, 4, 0]} stackId="cost" />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Pie chart */}
        <div className="rounded-xl border border-[rgba(56,189,248,0.15)] bg-[#0F172A]/60 backdrop-blur-xl p-6">
          <h2 className="mb-4 text-sm font-semibold text-white">Cost Share</h2>
          <ResponsiveContainer width="100%" height={250}>
            <PieChart>
              <Pie data={pieData} dataKey="value" nameKey="name" cx="50%" cy="50%" innerRadius={50} outerRadius={90}
                paddingAngle={2} strokeWidth={0}>
                {pieData.map((_, i) => <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />)}
              </Pie>
              <Tooltip
                contentStyle={{ background: "#0F172A", border: "1px solid rgba(56,189,248,0.3)", borderRadius: 8, color: "#fff" }}
                formatter={(v: number) => `Rs ${formatINR(v)}`}
              />
            </PieChart>
          </ResponsiveContainer>
          <div className="mt-2 space-y-1">
            {pieData.map((d, i) => (
              <div key={d.name} className="flex items-center gap-2 text-xs">
                <span className="h-2 w-2 rounded-full shrink-0" style={{ background: PIE_COLORS[i % PIE_COLORS.length] }} />
                <span className="text-[#94A3B8] truncate">{d.name}</span>
                <span className="ml-auto font-mono text-white">Rs {formatINR(d.value)}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Detailed table */}
      <div className="rounded-xl border border-[rgba(56,189,248,0.15)] bg-[#0F172A]/60 backdrop-blur-xl overflow-hidden">
        <div className="border-b border-[rgba(56,189,248,0.15)] bg-[#CBD5E1]/10 px-4 py-3">
          <h2 className="text-sm font-semibold text-white flex items-center gap-2">
            <IndianRupee className="h-4 w-4 text-[#0EA5E9]" /> Room-wise Cost Detail
          </h2>
        </div>
        <div className="grid grid-cols-[1fr_80px_70px_70px_110px_110px_110px] gap-2 px-4 py-2 text-[10px] uppercase tracking-wider text-[#94A3B8] border-b border-[rgba(56,189,248,0.08)]">
          <span>Room</span>
          <span className="text-right">Area</span>
          <span className="text-right">Const.x</span>
          <span className="text-right">Int.x</span>
          <span className="text-right">Construction</span>
          <span className="text-right">Interior</span>
          <span className="text-right">Total</span>
        </div>
        {breakdown.map((r) => (
          <div key={r.id} className="grid grid-cols-[1fr_80px_70px_70px_110px_110px_110px] gap-2 px-4 py-2.5 text-sm border-b border-[rgba(56,189,248,0.05)] hover:bg-[#CBD5E1]/5">
            <span className="text-white font-medium truncate">{r.label}</span>
            <span className="text-right font-mono text-[#94A3B8]">{Math.round(r.area)}</span>
            <span className="text-right font-mono text-[#94A3B8]">{r.constructionMult}x</span>
            <span className="text-right font-mono text-[#94A3B8]">{r.interiorMult}x</span>
            <span className="text-right font-mono text-[#0EA5E9]">Rs {formatINR(r.constructionCost)}</span>
            <span className="text-right font-mono text-[#8B5CF6]">Rs {formatINR(r.interiorCost)}</span>
            <span className="text-right font-mono text-white font-semibold">Rs {formatINR(r.constructionCost + r.interiorCost)}</span>
          </div>
        ))}
        <div className="grid grid-cols-[1fr_80px_70px_70px_110px_110px_110px] gap-2 px-4 py-3 text-sm bg-[#CBD5E1]/10 font-semibold">
          <span className="text-white">TOTAL</span>
          <span className="text-right font-mono text-white">{Math.round(totalArea)}</span>
          <span />
          <span />
          <span className="text-right font-mono text-[#0EA5E9]">Rs {formatINR(totalConstruction)}</span>
          <span className="text-right font-mono text-[#8B5CF6]">Rs {formatINR(totalInterior)}</span>
          <span className="text-right font-mono text-[#34D399]">Rs {formatINR(totalCost)}</span>
        </div>
      </div>
    </div>
  );
}
