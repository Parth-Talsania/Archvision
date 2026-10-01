import { useEffect, useState, useRef, useCallback } from "react";
import { Link } from "react-router-dom";
import { BarChart3, CheckCircle2, XCircle, Home, Upload, ArrowRight, Workflow, Cpu, LayoutDashboard } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
import api from "@/api/client";
import HowItWorks from "@/components/HowItWorks";
import TechStack from "@/components/TechStack";

interface DashboardData {
  total_analyses: number;
  completed_analyses: number;
  failed_analyses: number;
  total_rooms_detected: number;
  recent_analyses: {
    id: number;
    filename: string;
    status: string;
    total_rooms: number | null;
    created_at: string;
  }[];
}

/* ---------------------------------------------------------------- */
/*  NAV TABS — sticky in-page navigation                            */
/* ---------------------------------------------------------------- */
const navTabs = [
  { id: "overview", label: "Overview", icon: LayoutDashboard },
  { id: "how-it-works", label: "How It Works", icon: Workflow },
  { id: "tech-stack", label: "Tech Stack", icon: Cpu },
] as const;

export default function Dashboard() {
  const { user } = useAuth();
  const [stats, setStats] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeSection, setActiveSection] = useState("overview");
  const scrollRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    api.get("/dashboard").then((res) => {
      setStats(res.data);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  /* ---- Intersection Observer for active tab highlighting ---- */
  useEffect(() => {
    const sectionIds = navTabs.map((t) => t.id);
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            setActiveSection(entry.target.id);
          }
        }
      },
      { rootMargin: "-20% 0px -60% 0px", threshold: 0.1 },
    );

    sectionIds.forEach((id) => {
      const el = document.getElementById(id);
      if (el) observer.observe(el);
    });

    return () => observer.disconnect();
  }, [loading]); // re-observe once loading finishes

  /* ---- Smooth scroll to section ---- */
  const scrollTo = useCallback((id: string) => {
    const el = document.getElementById(id);
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, []);

  const statCards = stats
    ? [
        { label: "Total Analyses", value: stats.total_analyses, icon: BarChart3, color: "text-[#0EA5E9]" },
        { label: "Completed", value: stats.completed_analyses, icon: CheckCircle2, color: "text-[#34D399]" },
        { label: "Failed", value: stats.failed_analyses, icon: XCircle, color: "text-[#FCA5A5]" },
        { label: "Rooms Detected", value: stats.total_rooms_detected, icon: Home, color: "text-[#22D3EE]" },
      ]
    : [];

  return (
    <div ref={scrollRef} className="space-y-8">
      {/* ---- Sticky In-Page Navigation Bar ---- */}
      <nav className="sticky top-0 z-20 -mx-6 mb-2 border-b border-[rgba(56,189,248,0.1)] bg-[#020617]/70 px-6 backdrop-blur-xl lg:-mx-8 lg:px-8">
        <div className="flex items-center gap-1 overflow-x-auto py-2 scrollbar-none">
          {navTabs.map(({ id, label, icon: Icon }) => {
            const isActive = activeSection === id;
            return (
              <button
                key={id}
                onClick={() => scrollTo(id)}
                className={`relative flex shrink-0 items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-all duration-300 ${
                  isActive
                    ? "text-[#00F0FF]"
                    : "text-[#94A3B8] hover:bg-[#CBD5E1]/10 hover:text-white"
                }`}
              >
                <Icon className="h-4 w-4" />
                {label}
                {/* Active indicator bar */}
                {isActive && (
                  <span className="absolute bottom-0 left-2 right-2 h-0.5 rounded-full bg-gradient-to-r from-[#0EA5E9] to-[#00F0FF]" />
                )}
              </button>
            );
          })}
        </div>
      </nav>

      {/* ============================================================ */}
      {/*  SECTION: Overview                                            */}
      {/* ============================================================ */}
      <section id="overview" className="space-y-8">
        {/* Header */}
        <div className="flex items-center justify-between">
        <div>
          <h1 className="font-display text-2xl font-bold tracking-tight text-white">
            Welcome back, <span className="text-[#0EA5E9]">{user?.full_name?.split(" ")[0]}</span>
          </h1>
          <p className="mt-1 text-sm text-[#94A3B8]">Here's an overview of your floor plan analyses</p>
        </div>
        <Link
          to="/upload"
          className="btn-shimmer flex items-center gap-2 rounded-lg px-5 py-2.5 text-sm font-semibold text-white transition-all"
        >
          <Upload className="h-4 w-4 text-[#0EA5E9]" />
          New Analysis
        </Link>
      </div>

      {/* Stats cards */}
      {loading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="animate-galaxy-pulse rounded-xl border border-[rgba(56,189,248,0.15)] bg-slate-900/40 backdrop-blur-xl p-6">
              <div className="h-4 w-20 rounded bg-[#1E293B]" />
              <div className="mt-3 h-8 w-12 rounded bg-[#1E293B]" />
            </div>
          ))}
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {statCards.map(({ label, value, icon: Icon, color }) => (
            <div
              key={label}
              className="rounded-xl border border-[rgba(56,189,248,0.15)] bg-slate-900/40 backdrop-blur-xl p-6 transition-all duration-200 hover:border-[rgba(56,189,248,0.4)] hover:shadow-lg hover:shadow-[rgba(14,165,233,0.1)]"
            >
              <div className="flex items-center justify-between">
                <span className="text-sm text-[#94A3B8]">{label}</span>
                <Icon className={`h-5 w-5 ${color}`} />
              </div>
              <p className="mt-2 text-3xl font-bold font-mono tracking-tighter text-white">{value}</p>
            </div>
          ))}
        </div>
      )}

      {/* Recent analyses */}
      <div className="rounded-xl border border-[rgba(56,189,248,0.15)] bg-slate-900/40 backdrop-blur-xl">
        <div className="flex items-center justify-between border-b border-[rgba(56,189,248,0.15)] px-6 py-4">
          <h2 className="font-display text-lg font-semibold text-white">Recent Analyses</h2>
          <Link to="/history" className="flex items-center gap-1 text-sm text-[#0EA5E9] hover:text-[#7DD3FC]">
            View all <ArrowRight className="h-3 w-3" />
          </Link>
        </div>

        {!stats || stats.recent_analyses.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12">
            <BarChart3 className="h-12 w-12 text-[#94A3B8]/30" />
            <p className="mt-3 text-sm text-[#94A3B8]">No analyses yet</p>
            <Link to="/upload" className="mt-2 text-sm text-[#0EA5E9] hover:text-[#7DD3FC]">
              Upload your first floor plan
            </Link>
          </div>
        ) : (
          <div className="divide-y divide-[rgba(56,189,248,0.15)]">
            {stats.recent_analyses.map((a) => (
              <Link
                key={a.id}
                to={`/analysis/${a.id}`}
                className="flex items-center justify-between px-6 py-4 transition-colors hover:bg-[#CBD5E1]/10"
              >
                <div className="flex items-center gap-4">
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-[#0EA5E9]/10">
                    <Home className="h-5 w-5 text-[#0EA5E9]" />
                  </div>
                  <div>
                    <p className="text-sm font-medium text-white">{a.filename}</p>
                    <p className="text-xs text-[#94A3B8]">
                      {new Date(a.created_at).toLocaleDateString()} &middot;{" "}
                      {a.total_rooms != null ? <span className="font-mono">{a.total_rooms} rooms</span> : "---"}
                    </p>
                  </div>
                </div>
                <span
                  className={`inline-flex items-center justify-center rounded-full px-2.5 py-0.5 text-xs font-medium uppercase ${
                    a.status === "completed"
                      ? "bg-[#10B981]/10 text-[#34D399]"
                      : a.status === "failed"
                      ? "bg-[#EF4444]/10 text-[#FCA5A5]"
                      : "bg-[#F59E0B]/10 text-[#FBBF24]"
                  }`}
                >
                  {a.status}
                </span>
              </Link>
            ))}
          </div>
        )}
      </div>
      </section>

      {/* Divider */}
      <div className="h-px bg-gradient-to-r from-transparent via-[rgba(56,189,248,0.2)] to-transparent" />

      {/* How It Works Pipeline */}
      <HowItWorks />

      {/* Divider */}
      <div className="h-px bg-gradient-to-r from-transparent via-[rgba(56,189,248,0.2)] to-transparent" />

      {/* Tech Stack */}
      <TechStack />
    </div>
  );
}
