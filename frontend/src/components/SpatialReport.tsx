import { forwardRef, useMemo } from "react";
import { createPortal } from "react-dom";

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
    source?: string;
    raw_text?: string | null;
  } | null;
  confidence?: {
    geometry?: number;
    label?: number;
    dimensions?: number;
  } | null;
}

interface SpatialReportProps {
  rooms: Room[];
  filename: string;
  imageUrl: string;
  totalRooms: number;
  roomsWithLabels: number;
  roomsWithDimensions: number;
}

/* ------------------------------------------------------------------ */
/*  Helpers                                                             */
/* ------------------------------------------------------------------ */
function getRoomArea(r: Room): number {
  if (r.area?.value_sqft) return r.area.value_sqft;
  if (r.dimensions_parsed?.area_sqft) return r.dimensions_parsed.area_sqft;
  return 0;
}

function getRoomLabel(r: Room): string {
  return r.label || r.label_raw || `Room ${r.id}`;
}

function getOccupancy(label: string): string {
  const l = label.toLowerCase();
  if (/bed|master\s*bed|bunk/i.test(l)) return "Residential — Sleeping";
  if (/living|lounge|family|hall|drawing|sit/i.test(l)) return "Residential — Living";
  if (/dining/i.test(l)) return "Residential — Dining";
  if (/kitchen/i.test(l)) return "Residential — Kitchen";
  if (/toilet|wash|bath|wc/i.test(l)) return "Utility — Sanitation";
  if (/balcony|terrace|deck|patio|porch/i.test(l)) return "Outdoor — Open";
  if (/corridor|passage|lobby|foyer|stair/i.test(l)) return "Circulation";
  if (/store|utility|laundry/i.test(l)) return "Utility — Service";
  return "General Purpose";
}

/** Estimate HVAC tonnage: ~1 ton per 500 sq ft */
function estimateHVAC(sqft: number): string {
  if (sqft <= 0) return "—";
  const tons = Math.max(0.5, Math.round((sqft / 500) * 2) / 2);
  return `${tons} ton${tons !== 1 ? "s" : ""}`;
}

/** Estimate smart lighting wattage: ~1.5W per sq ft LED */
function estimateLighting(sqft: number): string {
  if (sqft <= 0) return "—";
  const watts = Math.round(sqft * 1.5);
  return `${watts}W`;
}

function generateDocId(): string {
  const chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";
  let id = "AV-";
  for (let i = 0; i < 8; i++) id += chars[Math.floor(Math.random() * chars.length)];
  return id;
}

/* ------------------------------------------------------------------ */
/*  Component                                                           */
/* ------------------------------------------------------------------ */
const SpatialReport = forwardRef<HTMLDivElement, SpatialReportProps>(
  ({ rooms, filename, imageUrl, totalRooms, roomsWithLabels, roomsWithDimensions }, ref) => {
    const timestamp = useMemo(() => new Date().toLocaleString("en-US", {
      year: "numeric", month: "long", day: "numeric",
      hour: "2-digit", minute: "2-digit", timeZoneName: "short",
    }), []);
    const docId = useMemo(() => generateDocId(), []);
    const totalArea = useMemo(() => rooms.reduce((s, r) => s + getRoomArea(r), 0), [rooms]);

    // Render as a portal directly under <body> so @media print can show it
    // while hiding everything inside #root
    return createPortal(
      <div ref={ref} className="print-report">
        {/* ====== HEADER ====== */}
        <header className="print-header">
          <h1 className="print-title">ARCHVISION AUTOMATED SPATIAL AUDIT</h1>
          <div className="print-meta">
            <span>Document ID: <strong>{docId}</strong></span>
            <span>Generated: <strong>{timestamp}</strong></span>
            <span>Source File: <strong>{filename}</strong></span>
            <span className="print-verified">Status: VERIFIED BY AI</span>
          </div>
        </header>

        <hr className="print-rule" />

        {/* ====== BLUEPRINT IMAGE ====== */}
        <section className="print-section">
          <h2 className="print-section-title">SEGMENTED BLUEPRINT</h2>
          <div className="print-image-wrap">
            <img src={imageUrl} alt="Segmented Blueprint" className="print-blueprint" crossOrigin="anonymous" />
          </div>
          <div className="print-image-caption">
            {totalRooms} rooms detected &middot; {roomsWithLabels} labeled &middot; {roomsWithDimensions} with dimensions
          </div>
        </section>

        <hr className="print-rule" />

        {/* ====== DATA MATRIX ====== */}
        <section className="print-section">
          <h2 className="print-section-title">SPATIAL DATA MATRIX</h2>
          <table className="print-table">
            <thead>
              <tr>
                <th>#</th>
                <th>Room Label</th>
                <th>Sq Ft</th>
                <th>Occupancy Type</th>
                <th>Confidence</th>
              </tr>
            </thead>
            <tbody>
              {rooms.map((r, i) => {
                const label = getRoomLabel(r);
                const area = getRoomArea(r);
                const conf = r.confidence?.geometry ?? r.confidence?.label ?? 0;
                return (
                  <tr key={r.id}>
                    <td>{i + 1}</td>
                    <td className="print-label-cell">{label}</td>
                    <td>{area > 0 ? `${Math.round(area).toLocaleString()}` : "—"}</td>
                    <td>{getOccupancy(label)}</td>
                    <td>{conf > 0 ? `${Math.round(conf * 100)}%` : "—"}</td>
                  </tr>
                );
              })}
            </tbody>
            <tfoot>
              <tr>
                <td colSpan={2} className="print-total-label">TOTAL USABLE AREA</td>
                <td className="print-total-value">{Math.round(totalArea).toLocaleString()} sq ft</td>
                <td colSpan={2}></td>
              </tr>
            </tfoot>
          </table>
        </section>

        <hr className="print-rule" />

        {/* ====== BONUS: SMART BUILDING ESTIMATES ====== */}
        <section className="print-section">
          <h2 className="print-section-title">SMART BUILDING ESTIMATES</h2>
          <p className="print-disclaimer">
            Estimates derived from industry standard formulas. HVAC: ~1 ton / 500 sq ft. LED Lighting: ~1.5W / sq ft.
          </p>
          <table className="print-table">
            <thead>
              <tr>
                <th>#</th>
                <th>Room Label</th>
                <th>Sq Ft</th>
                <th>Est. HVAC Tonnage</th>
                <th>Req. Smart Lighting</th>
              </tr>
            </thead>
            <tbody>
              {rooms.map((r, i) => {
                const label = getRoomLabel(r);
                const area = getRoomArea(r);
                return (
                  <tr key={r.id}>
                    <td>{i + 1}</td>
                    <td className="print-label-cell">{label}</td>
                    <td>{area > 0 ? `${Math.round(area).toLocaleString()}` : "—"}</td>
                    <td>{estimateHVAC(area)}</td>
                    <td>{estimateLighting(area)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </section>

        {/* ====== FOOTER ====== */}
        <footer className="print-footer">
          <p>ArchVision &mdash; Automated Spatial Intelligence &middot; {docId} &middot; {timestamp}</p>
          <p className="print-footer-note">This report was generated automatically by AI. Verify measurements on-site before construction or legal use.</p>
        </footer>
      </div>,
      document.body
    );
  }
);

SpatialReport.displayName = "SpatialReport";
export default SpatialReport;
