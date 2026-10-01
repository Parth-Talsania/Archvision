const MARQUEE_TEXT =
  "ARCHVISION CORE v1.0.4 /// OpenCV KERNEL: ACTIVE /// EasyOCR: PyTorch Backend /// TOPOLOGICAL NOISE REJECTION: ON /// MODEL CONFIDENCE: HIGH /// LATENCY: 42ms /// WAITING FOR BLUEPRINT UPLOAD...";

export default function TelemetryBar() {
  return (
    <div className="telemetry-bar fixed top-0 left-0 right-0 z-50 flex h-8 items-center gap-4 border-b border-cyan-500/20 bg-slate-950/80 backdrop-blur-md px-4 overflow-hidden font-mono">
      {/* LIVE Indicator Pill */}
      <div className="live-pill flex-shrink-0 flex items-center gap-1.5 rounded-full border border-[#00F0FF]/30 bg-[#00F0FF]/10 px-3 py-0.5">
        <span className="live-dot relative flex h-2 w-2">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[#00F0FF] opacity-60" />
          <span className="relative inline-flex h-2 w-2 rounded-full bg-[#00F0FF]" />
        </span>
        <span
          className="text-[10px] font-medium tracking-widest text-[#00F0FF] uppercase"
        >
          System: Online
        </span>
      </div>

      {/* Marquee */}
      <div className="marquee-container flex-1 overflow-hidden">
        <div className="marquee-track">
          <span className="marquee-content">{MARQUEE_TEXT}</span>
          <span className="marquee-content" aria-hidden="true">
            {MARQUEE_TEXT}
          </span>
        </div>
      </div>
    </div>
  );
}
