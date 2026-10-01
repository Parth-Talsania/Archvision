import { useNavigate } from "react-router-dom";
import {
  Building2, Brain, ScanEye, Ruler, PencilRuler, Workflow,
  LayoutGrid, Frame, Layers, Cpu, FileJson, Wifi,
  ArrowRight, ChevronRight, Sparkles, Shield, Zap, Eye
} from "lucide-react";

/* ================================================================ */
/*  FLOATING BACKGROUND — Reuses existing animation keyframes        */
/* ================================================================ */
const floatingIcons = [
  { Icon: Brain, top: "6%", left: "5%", anim: "float-drift-1", dur: "20s", size: 34, opacity: 0.10 },
  { Icon: ScanEye, top: "14%", left: "78%", anim: "float-drift-2", dur: "25s", size: 38, opacity: 0.08 },
  { Icon: Ruler, top: "52%", left: "88%", anim: "float-drift-3", dur: "18s", size: 28, opacity: 0.09 },
  { Icon: PencilRuler, top: "72%", left: "8%", anim: "float-drift-1", dur: "22s", size: 30, opacity: 0.09, reverse: true },
  { Icon: Workflow, top: "30%", left: "90%", anim: "float-drift-2", dur: "26s", size: 32, opacity: 0.07 },
  { Icon: LayoutGrid, top: "82%", left: "55%", anim: "float-drift-3", dur: "24s", size: 26, opacity: 0.08 },
  { Icon: Frame, top: "10%", left: "42%", anim: "float-drift-1", dur: "28s", size: 28, opacity: 0.07 },
  { Icon: Building2, top: "44%", left: "3%", anim: "float-drift-2", dur: "30s", size: 36, opacity: 0.08 },
  { Icon: Layers, top: "65%", left: "70%", anim: "float-drift-1", dur: "23s", size: 30, opacity: 0.07 },
  { Icon: Cpu, top: "88%", left: "20%", anim: "float-drift-3", dur: "27s", size: 28, opacity: 0.06 },
];

const NeuralNetworkBg = () => (
  <svg
    className="absolute top-[20%] left-[12%] w-64 h-64 opacity-[0.05]"
    viewBox="0 0 200 200"
    style={{ animation: "float-drift-1 35s ease-in-out infinite" }}
  >
    {[
      [40, 60, 100, 40], [40, 60, 100, 100], [40, 60, 100, 160],
      [40, 140, 100, 40], [40, 140, 100, 100], [40, 140, 100, 160],
      [100, 40, 160, 80], [100, 100, 160, 80], [100, 160, 160, 80],
      [100, 40, 160, 140], [100, 100, 160, 140], [100, 160, 160, 140],
    ].map(([x1, y1, x2, y2], i) => (
      <line key={i} x1={x1} y1={y1} x2={x2} y2={y2} stroke="hsl(190 80% 55%)" strokeWidth="0.7" opacity="0.4" />
    ))}
    {[
      [40, 60], [40, 140], [100, 40], [100, 100], [100, 160], [160, 80], [160, 140],
    ].map(([cx, cy], i) => (
      <circle key={i} cx={cx} cy={cy} r="5" fill="hsl(190 80% 55%)"
        style={{ animation: `node-pulse 3s ease-in-out infinite`, animationDelay: `${i * 0.4}s` }} />
    ))}
  </svg>
);

const BlueprintSvg = () => (
  <svg
    className="absolute bottom-[15%] right-[8%] w-56 h-56 opacity-[0.04]"
    viewBox="0 0 100 100"
    style={{ animation: "float-drift-2 30s ease-in-out infinite" }}
  >
    <path d="M10 10 H60 V40 H40 V90 H10 Z" fill="none" stroke="hsl(190 80% 55%)" strokeWidth="1"
      strokeDasharray="300" style={{ animation: "draw-line 4s ease-in-out infinite alternate" }} />
    <line x1="10" y1="50" x2="40" y2="50" stroke="hsl(190 80% 55%)" strokeWidth="0.5" strokeDasharray="2,2" />
    <line x1="25" y1="10" x2="25" y2="90" stroke="hsl(190 80% 55%)" strokeWidth="0.5" strokeDasharray="2,2" />
    <rect x="55" y="50" width="35" height="40" fill="none" stroke="hsl(280 70% 65%)" strokeWidth="0.8" rx="1" />
    <rect x="65" y="10" width="25" height="30" fill="none" stroke="hsl(280 70% 65%)" strokeWidth="0.8" rx="1" />
  </svg>
);

const FloatingBackground = () => (
  <div className="absolute inset-0 overflow-hidden pointer-events-none">
    {floatingIcons.map(({ Icon, top, left, anim, dur, size, opacity, reverse }, i) => (
      <div key={i} className="absolute text-[#0EA5E9]"
        style={{ top, left, opacity, animation: `${anim} ${dur} ease-in-out infinite${reverse ? " reverse" : ""}` }}>
        <Icon size={size} strokeWidth={1.2} />
      </div>
    ))}
    <NeuralNetworkBg />
    <BlueprintSvg />
    {Array.from({ length: 16 }).map((_, i) => (
      <div key={i} className="absolute w-1 h-1 rounded-full bg-[#0EA5E9]/30"
        style={{
          top: `${8 + (i * 6) % 84}%`, left: `${4 + (i * 9) % 88}%`,
          animation: `particle-drift ${7 + (i % 5) * 3}s linear infinite`,
          animationDelay: `${i * 0.6}s`,
        }} />
    ))}
  </div>
);

/* ================================================================ */
/*  FEATURES DATA                                                     */
/* ================================================================ */
const features = [
  {
    Icon: Eye,
    title: "YOLO Instance Segmentation",
    desc: "Precision room detection powered by YOLOv8-Seg with per-instance segmentation masks and confidence scoring.",
    color: "from-[#0EA5E9] to-[#06B6D4]",
  },
  {
    Icon: FileJson,
    title: "Structured JSON Output",
    desc: "Auto-generates standardized spatial JSON with room geometry, parsed dimensions, labels, and area computations.",
    color: "from-[#818CF8] to-[#A855F7]",
  },
  {
    Icon: Brain,
    title: "Dual-Path OCR Engine",
    desc: "EasyOCR primary + PaddleOCR fallback ensures robust text extraction across diverse blueprint styles.",
    color: "from-[#34D399] to-[#06B6D4]",
  },
  {
    Icon: Layers,
    title: "Smart PDF Extraction",
    desc: "AI-validated PDF pipeline with page scoring, YOLO crop validation, and automatic floor plan isolation.",
    color: "from-[#F59E0B] to-[#EF4444]",
  },
  {
    Icon: Sparkles,
    title: "Interactive Analytics",
    desc: "Rich Recharts dashboards with KPIs, space allocation doughnuts, radar profiles, and room hierarchies.",
    color: "from-[#EC4899] to-[#8B5CF6]",
  },
  {
    Icon: Wifi,
    title: "Wi-Fi Signal Simulation",
    desc: "Downstream proof-of-concept using pipeline centroids for Euclidean Wi-Fi dead zone mapping.",
    color: "from-[#06B6D4] to-[#3B82F6]",
  },
];

// Measured values: mask mAP@50 from training/runs/floor_plan_rooms/results.csv,
// per-image time on CPU, PDF render DPI from the extractor config.
const stats = [
  { value: "0.98", label: "Mask mAP@50" },
  { value: "7", label: "Room Classes" },
  { value: "< 30s", label: "Per Image (CPU)" },
  { value: "450", label: "PDF Render DPI" },
];

/* ================================================================ */
/*  PIPELINE STEPS                                                    */
/* ================================================================ */
const pipelineSteps = [
  { step: "01", label: "Upload", desc: "PDF or Image", Icon: Frame },
  { step: "02", label: "Segment", desc: "YOLO Detection", Icon: ScanEye },
  { step: "03", label: "Recognize", desc: "OCR Extraction", Icon: Brain },
  { step: "04", label: "Output", desc: "Structured JSON", Icon: FileJson },
];

/* ================================================================ */
/*  LANDING PAGE                                                      */
/* ================================================================ */
export default function Landing() {
  const navigate = useNavigate();

  return (
    <div className="relative min-h-screen overflow-hidden">
      {/* Background layers */}
      <div className="blueprint-grid absolute inset-0" />
      <div className="absolute inset-0 bg-gradient-to-br from-background via-background/90 to-background/80" />
      <FloatingBackground />

      {/* ---- NAVBAR ---- */}
      <nav className="relative z-20 flex items-center justify-between px-6 py-5 sm:px-10 lg:px-16">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-[#0EA5E9]/20 bg-[#0EA5E9]/10">
            <Building2 className="h-5 w-5 text-[#0EA5E9]" />
          </div>
          <span className="font-display text-xl font-bold tracking-tight text-white">
            Arch<span className="text-[#0EA5E9]">Vision</span>
          </span>
        </div>
        <div className="flex items-center gap-3">
          <button onClick={() => navigate("/login")}
            className="rounded-lg border border-[rgba(56,189,248,0.2)] bg-transparent px-5 py-2 text-sm font-medium text-[#94A3B8] transition-all duration-300 hover:border-[#0EA5E9]/50 hover:text-white hover:shadow-[0_0_20px_rgba(14,165,233,0.15)]">
            Sign In
          </button>
          <button onClick={() => navigate("/register")}
            className="btn-shimmer rounded-lg px-5 py-2 text-sm font-semibold text-white transition-all">
            Get Started
          </button>
        </div>
      </nav>

      {/* ---- HERO SECTION ---- */}
      <section className="relative z-10 mx-auto max-w-6xl px-6 pt-16 pb-20 text-center sm:pt-24 sm:pb-28 lg:pt-32">
        {/* Pill badge */}
        <div className="landing-fade-up mb-8 inline-flex items-center gap-2 rounded-full border border-[#0EA5E9]/20 bg-[#0EA5E9]/5 px-4 py-1.5">
          <Zap className="h-3.5 w-3.5 text-[#0EA5E9]" />
          <span className="text-xs font-medium tracking-wider text-[#0EA5E9] uppercase">Hybrid AI Floor Plan Analysis</span>
        </div>

        <h1 className="landing-fade-up font-display text-4xl font-extrabold leading-[1.1] tracking-tight sm:text-5xl lg:text-7xl"
          style={{ animationDelay: "0.1s" }}>
          <span className="text-white">Transform Blueprints into</span>
          <br />
          <span className="text-gradient-cyan-purple">Computable Spatial Data</span>
        </h1>

        <p className="landing-fade-up mx-auto mt-6 max-w-2xl text-base leading-relaxed text-[#94A3B8] sm:text-lg"
          style={{ animationDelay: "0.2s" }}>
          ArchVision converts 2D architectural floor plans into structured JSON with room geometry,
          dimensions, labels, and confidence scores — powered by YOLOv8 segmentation and dual-path OCR.
        </p>

        {/* CTA Buttons */}
        <div className="landing-fade-up mt-10 flex flex-col items-center justify-center gap-4 sm:flex-row"
          style={{ animationDelay: "0.3s" }}>
          <button onClick={() => navigate("/register")}
            className="btn-shimmer group flex items-center gap-2 rounded-xl px-8 py-3.5 text-base font-semibold text-white transition-all">
            Start Analyzing
            <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
          </button>
          <button onClick={() => navigate("/login")}
            className="flex items-center gap-2 rounded-xl border border-[rgba(56,189,248,0.2)] bg-[rgba(15,23,42,0.5)] px-8 py-3.5 text-base font-medium text-white backdrop-blur-sm transition-all duration-300 hover:border-[#0EA5E9]/40 hover:bg-[rgba(15,23,42,0.7)] hover:shadow-[0_0_30px_rgba(14,165,233,0.12)]">
            <Shield className="h-4 w-4 text-[#0EA5E9]" />
            Sign In
          </button>
        </div>

        {/* Stats strip */}
        <div className="landing-fade-up mx-auto mt-16 grid max-w-3xl grid-cols-2 gap-4 sm:grid-cols-4"
          style={{ animationDelay: "0.45s" }}>
          {stats.map(({ value, label }) => (
            <div key={label} className="rounded-xl border border-[rgba(56,189,248,0.1)] bg-[rgba(15,23,42,0.4)] px-4 py-4 backdrop-blur-sm transition-all duration-300 hover:border-[rgba(56,189,248,0.3)]">
              <p className="font-mono text-2xl font-bold text-white">{value}</p>
              <p className="mt-1 text-xs font-medium tracking-wider text-[#94A3B8] uppercase">{label}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ---- DIVIDER ---- */}
      <div className="relative z-10 mx-auto max-w-4xl">
        <div className="h-px bg-gradient-to-r from-transparent via-[#0EA5E9]/25 to-transparent" />
      </div>

      {/* ---- PIPELINE SECTION ---- */}
      <section className="relative z-10 mx-auto max-w-5xl px-6 py-20 sm:py-28">
        <div className="text-center mb-14">
          <h2 className="font-display text-2xl font-bold tracking-tight text-white sm:text-3xl">
            How the <span className="text-[#0EA5E9]">Pipeline</span> Works
          </h2>
          <p className="mt-3 text-sm text-[#94A3B8]">From upload to structured output in four intelligent steps</p>
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {pipelineSteps.map(({ step, label, desc, Icon }, i) => (
            <div key={step} className="landing-fade-up group relative flex flex-col items-center rounded-2xl border border-[rgba(56,189,248,0.1)] bg-[rgba(15,23,42,0.4)] p-6 backdrop-blur-sm transition-all duration-300 hover:border-[rgba(56,189,248,0.35)] hover:shadow-[0_0_30px_rgba(14,165,233,0.08)]"
              style={{ animationDelay: `${0.1 * i}s` }}>
              {/* Step number */}
              <span className="mb-3 font-mono text-xs font-bold tracking-widest text-[#0EA5E9]/50">{step}</span>
              {/* Icon */}
              <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-xl border border-[#0EA5E9]/20 bg-[#0EA5E9]/10 transition-all duration-300 group-hover:border-[#0EA5E9]/40 group-hover:bg-[#0EA5E9]/20 group-hover:shadow-[0_0_20px_rgba(14,165,233,0.2)]">
                <Icon className="h-6 w-6 text-[#0EA5E9]" />
              </div>
              <h3 className="font-display text-base font-bold text-white">{label}</h3>
              <p className="mt-1 text-xs text-[#94A3B8]">{desc}</p>

              {/* Connector arrow (not on last) */}
              {i < pipelineSteps.length - 1 && (
                <ChevronRight className="absolute -right-3 top-1/2 hidden h-5 w-5 -translate-y-1/2 text-[#0EA5E9]/30 lg:block" />
              )}
            </div>
          ))}
        </div>
      </section>

      {/* ---- DIVIDER ---- */}
      <div className="relative z-10 mx-auto max-w-4xl">
        <div className="h-px bg-gradient-to-r from-transparent via-[#818CF8]/20 to-transparent" />
      </div>

      {/* ---- FEATURES SECTION ---- */}
      <section className="relative z-10 mx-auto max-w-6xl px-6 py-20 sm:py-28">
        <div className="text-center mb-14">
          <h2 className="font-display text-2xl font-bold tracking-tight text-white sm:text-3xl">
            Powerful <span className="text-gradient-cyan-purple">Capabilities</span>
          </h2>
          <p className="mt-3 text-sm text-[#94A3B8]">Enterprise-grade AI pipeline built for architectural intelligence</p>
        </div>

        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {features.map(({ Icon, title, desc, color }, i) => (
            <div key={title}
              className="landing-fade-up pillar-card glass-panel group relative flex flex-col rounded-2xl p-7 transition-all duration-300 hover:scale-[1.02]"
              style={{ animationDelay: `${0.08 * i}s` }}>
              <div className={`mb-5 flex h-12 w-12 items-center justify-center rounded-xl bg-gradient-to-br ${color} shadow-lg transition-transform duration-300 group-hover:scale-110`}>
                <Icon className="h-5 w-5 text-white" />
              </div>
              <h3 className="mb-2 font-display text-base font-bold tracking-tight text-white">{title}</h3>
              <p className="flex-1 text-sm leading-relaxed text-[#94A3B8]">{desc}</p>
              <div className="mt-5 h-px w-full bg-gradient-to-r from-transparent via-[#0EA5E9]/20 to-transparent" />
            </div>
          ))}
        </div>
      </section>

      {/* ---- DIVIDER ---- */}
      <div className="relative z-10 mx-auto max-w-4xl">
        <div className="h-px bg-gradient-to-r from-transparent via-[#0EA5E9]/25 to-transparent" />
      </div>

      {/* ---- FINAL CTA SECTION ---- */}
      <section className="relative z-10 mx-auto max-w-4xl px-6 py-20 text-center sm:py-28">
        <div className="landing-fade-up rounded-3xl border border-[rgba(56,189,248,0.15)] bg-[rgba(15,23,42,0.5)] px-8 py-14 backdrop-blur-md sm:px-14">
          <h2 className="font-display text-2xl font-bold tracking-tight text-white sm:text-3xl">
            Ready to <span className="text-[#0EA5E9]">Analyze</span> Your Floor Plans?
          </h2>
          <p className="mx-auto mt-4 max-w-xl text-sm leading-relaxed text-[#94A3B8]">
            Upload a PDF brochure or floor plan image and get structured spatial data in seconds.
            No complex setup required.
          </p>
          <div className="mt-8 flex flex-col items-center justify-center gap-4 sm:flex-row">
            <button onClick={() => navigate("/register")}
              className="btn-shimmer group flex items-center gap-2 rounded-xl px-8 py-3.5 text-base font-semibold text-white transition-all">
              Create Free Account
              <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
            </button>
            <button onClick={() => navigate("/login")}
              className="text-sm font-medium text-[#0EA5E9] transition-colors hover:text-[#7DD3FC]">
              Already have an account? Sign in &rarr;
            </button>
          </div>
        </div>
      </section>

      {/* ---- FOOTER ---- */}
      <footer className="relative z-10 border-t border-[rgba(56,189,248,0.08)] py-8">
        <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-4 px-6 sm:flex-row">
          <div className="flex items-center gap-2">
            <Building2 className="h-4 w-4 text-[#0EA5E9]" />
            <span className="font-display text-sm font-semibold text-[#94A3B8]">
              Arch<span className="text-[#0EA5E9]/70">Vision</span>
            </span>
          </div>
          <p className="text-xs text-[#475569]">
            &copy; {new Date().getFullYear()} ArchVision &middot; Hybrid AI Floor Plan Analysis Pipeline
          </p>
        </div>
      </footer>
    </div>
  );
}
