import { useEffect, useState } from "react";
import { Sparkles, Home, Bath, BedDouble, Trees, Loader2, AlertCircle } from "lucide-react";
import api from "@/api/client";

interface SummaryData {
  summary: string;
  highlights: string[];
  bhk: string;
  total_area_sqft: number | null;
  room_count: number;
  bedroom_count: number;
  bathroom_count: number;
  outdoor_count: number;
}

interface PropertySummaryProps {
  jobId: number;
  pageCount?: number;
}

function SummaryCard({ data, title }: { data: SummaryData; title?: string }) {
  return (
    <div className="rounded-xl border border-[rgba(56,189,248,0.15)] bg-[#0F172A]/60 backdrop-blur-xl overflow-hidden">
      <div className="border-b border-[rgba(56,189,248,0.15)] bg-gradient-to-r from-[#0EA5E9]/10 to-transparent px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-[#0EA5E9]" />
            <h2 className="text-sm font-semibold text-white">{title || "Property Summary"}</h2>
          </div>
          <div className="flex items-center gap-3">
            <span className="rounded-full bg-[#0EA5E9]/15 px-3 py-1 text-xs font-bold text-[#0EA5E9]">
              {data.bhk}
            </span>
            {data.total_area_sqft && (
              <span className="text-xs font-mono text-[#94A3B8]">{data.total_area_sqft} sqft</span>
            )}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-4 gap-px bg-[rgba(56,189,248,0.08)]">
        {[
          { icon: Home, label: "Rooms", value: data.room_count, color: "text-[#0EA5E9]" },
          { icon: BedDouble, label: "Bedrooms", value: data.bedroom_count, color: "text-[#8B5CF6]" },
          { icon: Bath, label: "Bathrooms", value: data.bathroom_count, color: "text-[#F59E0B]" },
          { icon: Trees, label: "Outdoor", value: data.outdoor_count, color: "text-[#10B981]" },
        ].map((s) => (
          <div key={s.label} className="bg-[#0F172A]/80 px-4 py-3 text-center">
            <s.icon className={`mx-auto h-4 w-4 ${s.color}`} />
            <p className="mt-1 font-mono text-lg font-bold text-white">{s.value}</p>
            <p className="text-[10px] uppercase tracking-wider text-[#94A3B8]">{s.label}</p>
          </div>
        ))}
      </div>

      <div className="px-6 py-5">
        <p className="text-sm leading-relaxed text-[#CBD5E1]">{data.summary}</p>
      </div>

      {data.highlights.length > 0 && (
        <div className="border-t border-[rgba(56,189,248,0.08)] px-6 py-4">
          <p className="text-[10px] uppercase tracking-wider text-[#94A3B8] mb-3">Key Highlights</p>
          <div className="flex flex-wrap gap-2">
            {data.highlights.map((h, i) => (
              <span
                key={i}
                className="inline-flex items-center rounded-full border border-[rgba(56,189,248,0.2)] bg-[#0EA5E9]/5 px-3 py-1 text-xs text-[#7DD3FC]"
              >
                {h}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default function PropertySummary({ jobId, pageCount = 0 }: PropertySummaryProps) {
  const [summaries, setSummaries] = useState<SummaryData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);

    if (pageCount > 1) {
      const fetches = Array.from({ length: pageCount }, (_, i) =>
        api.get(`/analyses/${jobId}/summary?page=${i}`).then((r) => r.data as SummaryData)
      );
      Promise.all(fetches)
        .then((results) => { setSummaries(results.filter((r) => r.room_count > 0)); setLoading(false); })
        .catch((err) => { setError(err.response?.data?.detail || "Failed to generate summary"); setLoading(false); });
    } else {
      api.get(`/analyses/${jobId}/summary`)
        .then((res) => { setSummaries([res.data]); setLoading(false); })
        .catch((err) => { setError(err.response?.data?.detail || "Failed to generate summary"); setLoading(false); });
    }
  }, [jobId, pageCount]);

  if (loading) {
    return (
      <div className="rounded-xl border border-[rgba(56,189,248,0.15)] bg-[#0F172A]/60 backdrop-blur-xl p-6">
        <div className="flex items-center gap-2">
          <Loader2 className="h-4 w-4 animate-spin text-[#0EA5E9]" />
          <span className="text-sm text-[#94A3B8]">Generating property summaries...</span>
        </div>
      </div>
    );
  }

  if (error || summaries.length === 0) {
    return (
      <div className="rounded-xl border border-[rgba(56,189,248,0.15)] bg-[#0F172A]/60 backdrop-blur-xl p-6">
        <div className="flex items-center gap-2 text-[#94A3B8]">
          <AlertCircle className="h-4 w-4" />
          <span className="text-sm">{error || "No summary available"}</span>
        </div>
      </div>
    );
  }

  if (summaries.length === 1) {
    return <SummaryCard data={summaries[0]} />;
  }

  return (
    <div className="space-y-4">
      {summaries.map((s, i) => (
        <SummaryCard key={i} data={s} title={`AI Property Summary — Floor Plan ${i + 1}`} />
      ))}
    </div>
  );
}
