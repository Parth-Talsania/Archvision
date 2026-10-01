import { Hexagon, ScanText, X } from "lucide-react";
import { useState, useCallback } from "react";

/* ================================================================ */
/*  GLOWING POLYGON ICON (Step 1)                                    */
/* ================================================================ */
function GlowingPolygonIcon() {
  return (
    <div className="flex h-12 w-12 items-center justify-center rounded-xl border border-[#0EA5E9]/30 bg-[#0EA5E9]/10 shadow-[0_0_20px_rgba(14,165,233,0.25)]">
      <Hexagon className="h-6 w-6 text-[#00F0FF]" style={{ filter: "drop-shadow(0 0 6px rgba(0,240,255,0.5))" }} />
    </div>
  );
}

/* ================================================================ */
/*  GLOWING TEXT SCANNER ICON (Step 2)                               */
/* ================================================================ */
function GlowingTextIcon() {
  return (
    <div className="flex h-12 w-12 items-center justify-center rounded-xl border border-[#0EA5E9]/30 bg-[#0EA5E9]/10 shadow-[0_0_20px_rgba(14,165,233,0.25)]">
      <ScanText className="h-6 w-6 text-[#00F0FF]" style={{ filter: "drop-shadow(0 0 6px rgba(0,240,255,0.5))" }} />
    </div>
  );
}

/* ================================================================ */
/*  LIGHTBOX MODAL                                                    */
/* ================================================================ */
function Lightbox({ src, alt, onClose }: { src: string; alt: string; onClose: () => void }) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-md"
      onClick={onClose}
    >
      {/* Close button */}
      <button
        onClick={onClose}
        className="absolute right-4 top-4 z-50 flex h-10 w-10 items-center justify-center rounded-full border border-white/20 bg-slate-900/80 text-white/80 transition-colors hover:bg-slate-800 hover:text-white"
      >
        <X className="h-5 w-5" />
      </button>
      {/* Image */}
      <img
        src={src}
        alt={alt}
        className="max-h-[90vh] max-w-[90vw] rounded-xl object-contain shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      />
    </div>
  );
}

/* ================================================================ */
/*  IMAGE CONTAINER (Glass-framed)                                   */
/* ================================================================ */
function ImageFrame({ src, alt, caption }: { src: string; alt: string; caption: string }) {
  const [lightboxOpen, setLightboxOpen] = useState(false);
  const [imgLoaded, setImgLoaded] = useState(true);

  const openLightbox = useCallback(() => {
    if (imgLoaded) setLightboxOpen(true);
  }, [imgLoaded]);

  return (
    <>
      <div className="flex flex-col gap-3">
        <div
          className={`group relative overflow-hidden rounded-xl border border-[rgba(56,189,248,0.2)] bg-slate-900/50 backdrop-blur-sm transition-all duration-500 hover:border-[rgba(56,189,248,0.4)] hover:shadow-[0_0_30px_rgba(14,165,233,0.12)] ${
            imgLoaded ? "cursor-pointer" : ""
          }`}
          onClick={openLightbox}
        >
          <div className="relative aspect-[4/3] w-full overflow-hidden bg-slate-950/80">
            {/* Scan line animation overlay */}
            <div className="pointer-events-none absolute inset-0 z-10 opacity-0 transition-opacity duration-500 group-hover:opacity-100">
              <div
                className="absolute left-0 h-px w-full bg-gradient-to-r from-transparent via-[#00F0FF]/60 to-transparent"
                style={{ animation: "scan-line 2.5s ease-in-out infinite" }}
              />
            </div>
            {/* Click hint */}
            {imgLoaded && (
              <div className="pointer-events-none absolute bottom-2 right-2 z-20 flex items-center gap-1 rounded-md bg-black/50 px-2 py-1 text-[10px] text-white/60 opacity-0 transition-opacity duration-300 group-hover:opacity-100">
                <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0zM10 7v3m0 0v3m0-3h3m-3 0H7" />
                </svg>
                Click to enlarge
              </div>
            )}
            <img
              src={src}
              alt={alt}
              className="h-full w-full object-contain transition-transform duration-700 group-hover:scale-105"
              onError={(e) => {
                setImgLoaded(false);
                const el = e.currentTarget;
                el.style.display = "none";
                el.parentElement!.classList.add("flex", "items-center", "justify-center");
                const placeholder = document.createElement("div");
                placeholder.className = "flex flex-col items-center gap-2 p-8";
                placeholder.innerHTML = `
                  <svg class="h-16 w-16 text-[#0EA5E9]/30" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M2.25 15.75l5.159-5.159a2.25 2.25 0 013.182 0l5.159 5.159m-1.5-1.5l1.409-1.409a2.25 2.25 0 013.182 0l2.909 2.909M3.75 21h16.5A2.25 2.25 0 0022.5 18.75V5.25A2.25 2.25 0 0020.25 3H3.75A2.25 2.25 0 001.5 5.25v13.5A2.25 2.25 0 003.75 21z" />
                  </svg>
                  <span class="text-xs text-[#94A3B8]/60">Image placeholder</span>
                `;
                el.parentElement!.appendChild(placeholder);
              }}
            />
          </div>
        </div>
        <p className="text-center text-xs font-medium tracking-wide text-[#94A3B8]">{caption}</p>
      </div>
      {lightboxOpen && <Lightbox src={src} alt={alt} onClose={() => setLightboxOpen(false)} />}
    </>
  );
}

/* ================================================================ */
/*  ANIMATED CONNECTOR LINE                                          */
/* ================================================================ */
function DataStreamConnector() {
  return (
    <div className="relative flex justify-center py-4">
      {/* Glowing vertical line */}
      <div className="relative h-20 w-px">
        <div className="absolute inset-0 bg-gradient-to-b from-[#0EA5E9]/60 via-[#00F0FF]/40 to-[#0EA5E9]/60" />
        {/* Animated pulse traveling down */}
        <div
          className="absolute left-1/2 h-8 w-px -translate-x-1/2"
          style={{
            background: "linear-gradient(to bottom, transparent, #00F0FF, transparent)",
            animation: "stream-pulse 2s ease-in-out infinite",
          }}
        />
        {/* Glow halo */}
        <div className="absolute left-1/2 top-1/2 h-4 w-4 -translate-x-1/2 -translate-y-1/2 rounded-full bg-[#00F0FF]/20 blur-md" />
      </div>
      {/* Downward arrow */}
      <div className="absolute bottom-2 left-1/2 -translate-x-1/2">
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none" className="text-[#00F0FF]" style={{ filter: "drop-shadow(0 0 4px rgba(0,240,255,0.6))" }}>
          <path d="M8 2v10M4 9l4 4 4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </div>
    </div>
  );
}

/* ================================================================ */
/*  MAIN: HOW IT WORKS                                               */
/* ================================================================ */
export default function HowItWorks() {
  return (
    <section id="how-it-works" className="space-y-4">
      {/* Section header */}
      <div className="mb-8">
        <h2 className="text-quantum-blue font-display text-lg font-bold tracking-tight">How It Works</h2>
        <p className="text-xs text-[#94A3B8]">Our two-step AI pipeline, from pixels to structured data</p>
      </div>

      {/* ---- Step 1: Geometric Core Segmentation (Text Left, Image Right) ---- */}
      <div className="rounded-2xl border border-[rgba(56,189,248,0.15)] bg-slate-900/60 p-6 backdrop-blur-xl transition-all duration-500 hover:border-[rgba(56,189,248,0.3)] hover:shadow-[0_0_40px_rgba(14,165,233,0.08)] md:p-8">
        <div className="grid gap-8 md:grid-cols-2 md:items-center">
          {/* Text Column */}
          <div className="space-y-4">
            <GlowingPolygonIcon />
            <h3 className="font-display text-xl font-bold tracking-tight text-white">
              <span className="mr-2 text-[#00F0FF]">1.</span>Geometric Core Segmentation
            </h3>
            <p className="text-sm leading-relaxed text-[#94A3B8]">
              Our Computer Vision engine first analyzes the raw blueprint. Using advanced OpenCV
              morphological operations, it distinguishes between structural walls (thick lines) and
              architectural details like furniture or cars (thin sketches). It then generates clean,
              closed geometric polygons for every potential room, ignoring noise.
            </p>
            {/* Feature pills */}
            <div className="flex flex-wrap gap-2 pt-1">
              {["Wall Detection", "Polygon Extraction", "Noise Rejection"].map((tag) => (
                <span
                  key={tag}
                  className="rounded-full border border-[#0EA5E9]/20 bg-[#0EA5E9]/5 px-3 py-1 text-[10px] font-semibold uppercase tracking-widest text-[#0EA5E9]"
                >
                  {tag}
                </span>
              ))}
            </div>
          </div>

          {/* Image Column */}
          <ImageFrame
            src="/assets/images/how-it-works-step1-segmentation.jpg"
            alt="Structural polygon extraction from a floor plan"
            caption="Fig 1: Structural Polygon Extraction"
          />
        </div>
      </div>

      {/* ---- Animated Data Stream Connector ---- */}
      <DataStreamConnector />

      {/* ---- Step 2: Semantic Text Recognition & Fusion (Image Left, Text Right) ---- */}
      <div className="rounded-2xl border border-[rgba(56,189,248,0.15)] bg-slate-900/60 p-6 backdrop-blur-xl transition-all duration-500 hover:border-[rgba(56,189,248,0.3)] hover:shadow-[0_0_40px_rgba(14,165,233,0.08)] md:p-8">
        <div className="grid gap-8 md:grid-cols-2 md:items-center">
          {/* Image Column (left on desktop) */}
          <div className="order-2 md:order-1">
            <ImageFrame
              src="/assets/images/how-it-works-step2-fusion.jpg"
              alt="OCR data fusion with room labels overlaid"
              caption="Fig 2: OCR Data Fusion &amp; Labeling"
            />
          </div>

          {/* Text Column (right on desktop) */}
          <div className="order-1 space-y-4 md:order-2">
            <GlowingTextIcon />
            <h3 className="font-display text-xl font-bold tracking-tight text-white">
              <span className="mr-2 text-[#00F0FF]">2.</span>Semantic Recognition (OCR) &amp; Data Fusion
            </h3>
            <p className="text-sm leading-relaxed text-[#94A3B8]">
              In parallel, a deep learning OCR model (EasyOCR) scans the plan for text. The final
              step is the &lsquo;Intelligent Merger,&rsquo; where spatial geometry is married with
              semantic labels. Unlabeled zones are flagged, and labelled zones calculate their
              precise square footage automatically.
            </p>
            {/* Feature pills */}
            <div className="flex flex-wrap gap-2 pt-1">
              {["Deep Learning OCR", "Label Fusion", "Area Calculation"].map((tag) => (
                <span
                  key={tag}
                  className="rounded-full border border-[#0EA5E9]/20 bg-[#0EA5E9]/5 px-3 py-1 text-[10px] font-semibold uppercase tracking-widest text-[#0EA5E9]"
                >
                  {tag}
                </span>
              ))}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
