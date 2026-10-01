import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Eye, Download, Trash2, Home, ChevronLeft, ChevronRight } from "lucide-react";
import api from "@/api/client";

interface Analysis {
  id: number;
  filename: string;
  file_type: string;
  status: string;
  total_rooms: number | null;
  rooms_with_labels: number | null;
  rooms_with_dimensions: number | null;
  created_at: string;
}

export default function HistoryPage() {
  const [analyses, setAnalyses] = useState<Analysis[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const perPage = 15;

  const fetchPage = (p: number) => {
    setLoading(true);
    api
      .get(`/analyses?page=${p}&per_page=${perPage}`)
      .then((res) => {
        setAnalyses(res.data.analyses);
        setTotal(res.data.total);
        setPage(p);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  };

  useEffect(() => {
    fetchPage(1);
  }, []);

  const totalPages = Math.ceil(total / perPage);

  const handleDelete = async (id: number) => {
    if (!confirm("Delete this analysis?")) return;
    try {
      await api.delete(`/analyses/${id}`);
      fetchPage(page);
    } catch {
      // ignore
    }
  };

  const handleDownload = async (a: Analysis) => {
    try {
      const res = await api.get(`/analyses/${a.id}/download`, { responseType: "blob" });
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const link = document.createElement("a");
      link.href = url;
      link.download = `${a.filename.replace(/\.[^.]+$/, "")}_result.json`;
      link.click();
      window.URL.revokeObjectURL(url);
    } catch {
      // ignore
    }
  };

  const statusBadge = (status: string) => {
    const styles: Record<string, string> = {
      completed: "bg-[#10B981]/10 text-[#34D399]",
      failed: "bg-[#EF4444]/10 text-[#FCA5A5]",
      processing: "bg-[#F59E0B]/10 text-[#FBBF24]",
      pending: "bg-[#60A5FA]/10 text-[#93C5FD]",
    };
    return (
      <span className={`inline-flex items-center justify-center rounded-full px-2.5 py-0.5 text-xs font-medium uppercase ${styles[status] || styles.pending}`}>
        {status}
      </span>
    );
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-2xl font-bold tracking-tight text-white">Analysis History</h1>
        <p className="mt-1 text-sm text-[#94A3B8]">
          {total} total {total === 1 ? "analysis" : "analyses"}
        </p>
      </div>

      <div className="rounded-xl border border-[rgba(56,189,248,0.15)] bg-[#0F172A]/60 backdrop-blur-xl overflow-hidden">
        {/* Table header */}
        <div className="grid grid-cols-[1fr_100px_90px_90px_90px_120px] gap-2 border-b border-[rgba(56,189,248,0.15)] bg-[#CBD5E1]/10 px-4 py-3 text-xs font-medium uppercase tracking-wider text-[#94A3B8]">
          <span>File</span>
          <span>Type</span>
          <span>Status</span>
          <span>Rooms</span>
          <span>Date</span>
          <span className="text-right">Actions</span>
        </div>

        {/* Rows */}
        {loading ? (
          <div className="space-y-0 divide-y divide-[rgba(56,189,248,0.15)]">
            {[1, 2, 3, 4, 5].map((i) => (
              <div key={i} className="animate-galaxy-pulse grid grid-cols-[1fr_100px_90px_90px_90px_120px] gap-2 px-4 py-4">
                <div className="h-4 w-40 rounded bg-[#1E293B]" />
                <div className="h-4 w-12 rounded bg-[#1E293B]" />
                <div className="h-4 w-16 rounded bg-[#1E293B]" />
                <div className="h-4 w-8 rounded bg-[#1E293B]" />
                <div className="h-4 w-16 rounded bg-[#1E293B]" />
                <div className="h-4 w-20 rounded bg-[#1E293B] ml-auto" />
              </div>
            ))}
          </div>
        ) : analyses.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16">
            <Home className="h-10 w-10 text-[#94A3B8]/30" />
            <p className="mt-3 text-sm text-[#94A3B8]">No analyses found</p>
            <Link to="/upload" className="mt-2 text-sm text-[#0EA5E9] hover:text-[#7DD3FC]">
              Upload a floor plan
            </Link>
          </div>
        ) : (
          <div className="divide-y divide-[rgba(56,189,248,0.15)]">
            {analyses.map((a) => (
              <div
                key={a.id}
                className="grid grid-cols-[1fr_100px_90px_90px_90px_120px] items-center gap-2 px-4 py-3 transition-colors hover:bg-[#CBD5E1]/10"
              >
                <span className="truncate text-sm text-white">{a.filename}</span>
                <span className="text-xs text-[#94A3B8] uppercase">{a.file_type}</span>
                {statusBadge(a.status)}
                <span className="font-mono text-sm text-white">{a.total_rooms ?? "---"}</span>
                <span className="text-xs text-[#94A3B8]">
                  {new Date(a.created_at).toLocaleDateString()}
                </span>
                <div className="flex items-center justify-end gap-1">
                  <Link
                    to={`/analysis/${a.id}`}
                    className="rounded p-1.5 text-[#94A3B8] hover:bg-[#0EA5E9]/10 hover:text-[#0EA5E9]"
                    title="View"
                  >
                    <Eye className="h-4 w-4" />
                  </Link>
                  {a.status === "completed" && (
                    <button
                      onClick={() => handleDownload(a)}
                      className="rounded p-1.5 text-[#94A3B8] hover:bg-[#22D3EE]/10 hover:text-[#22D3EE]"
                      title="Download JSON"
                    >
                      <Download className="h-4 w-4" />
                    </button>
                  )}
                  <button
                    onClick={() => handleDelete(a.id)}
                    className="rounded p-1.5 text-[#94A3B8] hover:bg-[#EF4444]/10 hover:text-[#EF4444]"
                    title="Delete"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between border-t border-[rgba(56,189,248,0.15)] px-4 py-3">
            <span className="text-xs text-[#94A3B8]">
              Page {page} of {totalPages}
            </span>
            <div className="flex items-center gap-1">
              <button
                onClick={() => fetchPage(page - 1)}
                disabled={page <= 1}
                className="rounded p-1.5 text-[#94A3B8] hover:bg-[#CBD5E1]/20 disabled:opacity-30"
              >
                <ChevronLeft className="h-4 w-4" />
              </button>
              <button
                onClick={() => fetchPage(page + 1)}
                disabled={page >= totalPages}
                className="rounded p-1.5 text-[#94A3B8] hover:bg-[#CBD5E1]/20 disabled:opacity-30"
              >
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
