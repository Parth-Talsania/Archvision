import { useEffect, useState } from "react";
import api from "@/api/client";

const MARQUEE_TEXT =
  "ARCHVISION /// SEGMENTATION: YOLOv8s-seg, 7 room classes, mask mAP@50 0.98 /// TEXT: PDF text layer first, EasyOCR / PaddleOCR fallback /// PDF RENDER: 450 DPI /// DIMENSIONS: feet-inch parsing to sq ft /// READY FOR BLUEPRINT UPLOAD...";

const HEALTH_POLL_MS = 30_000;

type BackendStatus = "checking" | "online" | "offline";

const STATUS_STYLE: Record<BackendStatus, { color: string; label: string }> = {
  checking: { color: "#94A3B8", label: "System: Checking" },
  online: { color: "#00F0FF", label: "System: Online" },
  offline: { color: "#F43F5E", label: "System: Offline" },
};

export default function TelemetryBar() {
  const [status, setStatus] = useState<BackendStatus>("checking");

  useEffect(() => {
    let cancelled = false;
    const check = () =>
      api
        .get("/health", { timeout: 5000 })
        .then(() => !cancelled && setStatus("online"))
        .catch(() => !cancelled && setStatus("offline"));
    check();
    const id = window.setInterval(check, HEALTH_POLL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, []);

  const { color, label } = STATUS_STYLE[status];

  return (
    <div className="telemetry-bar fixed top-0 left-0 right-0 z-50 flex h-8 items-center gap-4 border-b border-cyan-500/20 bg-slate-950/80 backdrop-blur-md px-4 overflow-hidden font-mono">
      {/* Backend status pill, from GET /api/health */}
      <div
        className="live-pill flex-shrink-0 flex items-center gap-1.5 rounded-full border px-3 py-0.5"
        style={{ borderColor: `${color}4D`, backgroundColor: `${color}1A` }}
        title="Backend health check (GET /api/health)"
      >
        <span className="live-dot relative flex h-2 w-2">
          {status === "online" && (
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full opacity-60" style={{ backgroundColor: color }} />
          )}
          <span className="relative inline-flex h-2 w-2 rounded-full" style={{ backgroundColor: color }} />
        </span>
        <span className="text-[10px] font-medium tracking-widest uppercase" style={{ color }}>
          {label}
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
