/* ================================================================ */
/*  TECH STACK GRID — "Powered By Best-in-Class Open Source"         */
/* ================================================================ */

interface TechItem {
  name: string;
  role: string;
  logo: JSX.Element;
  glow: string; // brand color for hover glow
}

/* ---- Inline SVG Logos ---- */

const YOLOLogo = () => (
  <svg viewBox="0 0 48 48" className="h-10 w-10" fill="none">
    <rect x="3" y="3" width="42" height="42" rx="6" stroke="#A855F7" strokeWidth="2" />
    <rect x="10" y="10" width="12" height="12" rx="2" stroke="#A855F7" strokeWidth="1.5" fill="#A855F7" fillOpacity="0.15" />
    <rect x="26" y="10" width="12" height="12" rx="2" stroke="#A855F7" strokeWidth="1.5" fill="#A855F7" fillOpacity="0.15" />
    <rect x="10" y="26" width="12" height="12" rx="2" stroke="#A855F7" strokeWidth="1.5" fill="#A855F7" fillOpacity="0.15" />
    <rect x="26" y="26" width="12" height="12" rx="2" stroke="#A855F7" strokeWidth="1.5" fill="#A855F7" fillOpacity="0.15" />
    <circle cx="16" cy="16" r="3" fill="#A855F7" opacity="0.8" />
    <circle cx="32" cy="32" r="3" fill="#A855F7" opacity="0.8" />
    <path d="M16 16l16 16" stroke="#A855F7" strokeWidth="1" strokeDasharray="2 2" opacity="0.5" />
  </svg>
);

const PythonLogo = () => (
  <svg viewBox="0 0 256 255" className="h-10 w-10">
    <defs>
      <linearGradient id="pyA" x1="12.96%" y1="12.07%" x2="79.68%" y2="78.21%">
        <stop offset="0%" stopColor="#387EB8" />
        <stop offset="100%" stopColor="#366994" />
      </linearGradient>
      <linearGradient id="pyB" x1="19.13%" y1="20.58%" x2="90.43%" y2="88.01%">
        <stop offset="0%" stopColor="#FFE052" />
        <stop offset="100%" stopColor="#FFC331" />
      </linearGradient>
    </defs>
    <path d="M126.916.072c-64.832 0-60.784 28.115-60.784 28.115l.072 29.128h61.868v8.745H41.631S.145 61.355.145 126.77c0 65.417 36.21 63.097 36.21 63.097h21.61v-30.356s-1.165-36.21 35.632-36.21h61.362s34.475.557 34.475-33.319V33.97S194.67.072 126.916.072zM92.802 19.66a11.12 11.12 0 110 22.24 11.12 11.12 0 010-22.24z" fill="url(#pyA)" />
    <path d="M128.757 254.126c64.832 0 60.784-28.115 60.784-28.115l-.072-29.127H127.6v-8.745h86.441s41.486 4.705 41.486-60.712c0-65.416-36.21-63.096-36.21-63.096h-21.61v30.355s1.165 36.21-35.632 36.21h-61.362s-34.475-.557-34.475 33.32v56.013s-5.235 33.897 62.52 33.897zm34.114-19.586a11.12 11.12 0 110-22.24 11.12 11.12 0 010 22.24z" fill="url(#pyB)" />
  </svg>
);

const FastAPILogo = () => (
  <svg viewBox="0 0 48 48" className="h-10 w-10" fill="none">
    <rect x="4" y="4" width="40" height="40" rx="8" fill="#009688" fillOpacity="0.15" stroke="#009688" strokeWidth="2" />
    <path d="M24 12v12l8-4" stroke="#009688" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
    <path d="M24 24l-8 4v8l8-4 8-4v-8" stroke="#009688" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    <circle cx="24" cy="24" r="2.5" fill="#009688" />
  </svg>
);

const OpenCVLogo = () => (
  <svg viewBox="0 0 200 200" className="h-10 w-10">
    <circle cx="65" cy="55" r="40" fill="#FF0000" opacity="0.9" />
    <circle cx="135" cy="55" r="40" fill="#00AA00" opacity="0.9" />
    <circle cx="100" cy="130" r="40" fill="#0000FF" opacity="0.9" />
    <text x="100" y="190" textAnchor="middle" fill="#94A3B8" fontSize="22" fontWeight="bold">OpenCV</text>
  </svg>
);

const EasyOCRLogo = () => (
  <svg viewBox="0 0 48 48" className="h-10 w-10" fill="none">
    <rect x="4" y="8" width="40" height="32" rx="4" stroke="#EE4C2C" strokeWidth="2.5" />
    <path d="M12 18h10M12 24h16M12 30h8" stroke="#EE4C2C" strokeWidth="2" strokeLinecap="round" />
    <rect x="30" y="16" width="8" height="8" rx="1" stroke="#00F0FF" strokeWidth="1.5" />
    <path d="M32 28l4 4" stroke="#00F0FF" strokeWidth="1.5" strokeLinecap="round" />
  </svg>
);

const PaddleOCRLogo = () => (
  <svg viewBox="0 0 48 48" className="h-10 w-10" fill="none">
    <circle cx="24" cy="24" r="18" stroke="#2563EB" strokeWidth="2" />
    <path d="M16 20c0-4.4 3.6-8 8-8s8 3.6 8 8" stroke="#2563EB" strokeWidth="2" strokeLinecap="round" />
    <path d="M18 28h12" stroke="#2563EB" strokeWidth="2" strokeLinecap="round" />
    <path d="M20 32h8" stroke="#2563EB" strokeWidth="1.5" strokeLinecap="round" />
    <text x="24" y="26" textAnchor="middle" fill="#2563EB" fontSize="8" fontWeight="bold">P</text>
  </svg>
);

const ShapelyLogo = () => (
  <svg viewBox="0 0 48 48" className="h-10 w-10" fill="none">
    <polygon points="24,6 42,18 42,34 24,42 6,34 6,18" stroke="#10B981" strokeWidth="2" fill="#10B981" fillOpacity="0.1" />
    <polygon points="24,14 34,20 34,30 24,36 14,30 14,20" stroke="#10B981" strokeWidth="1.5" fill="#10B981" fillOpacity="0.15" />
    <circle cx="24" cy="24" r="3" fill="#10B981" opacity="0.8" />
  </svg>
);

const PyMuPDFLogo = () => (
  <svg viewBox="0 0 48 48" className="h-10 w-10" fill="none">
    <path d="M14 6h14l10 10v26a2 2 0 01-2 2H14a2 2 0 01-2-2V8a2 2 0 012-2z" stroke="#EF4444" strokeWidth="2" />
    <path d="M28 6v10h10" stroke="#EF4444" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    <text x="24" y="30" textAnchor="middle" fill="#EF4444" fontSize="8" fontWeight="bold">PDF</text>
    <path d="M18 36h12" stroke="#EF4444" strokeWidth="1.5" strokeLinecap="round" />
  </svg>
);

const NumPyLogo = () => (
  <svg viewBox="0 0 128 128" className="h-10 w-10">
    <path d="M63.4 0L2.3 31.4v64.3l22.1 11.5V43.5L63 12l38.7 31.5v63.7l22.1-11.5V31.4z" fill="#4DABCF" />
    <path d="M63 12l38.7 31.5v40.7L63 115.8 24.4 84.2V43.5z" fill="#4D77CF" opacity="0.7" />
    <path d="M63 45l18 14.7v25L63 99.4 45 84.7v-25z" fill="#FFFFFF" opacity="0.4" />
  </svg>
);

const ReactLogo = () => (
  <svg viewBox="-11.5 -10.232 23 20.463" className="h-10 w-10">
    <circle r="2.05" fill="#61DAFB" />
    <g stroke="#61DAFB" strokeWidth="1" fill="none">
      <ellipse rx="11" ry="4.2" />
      <ellipse rx="11" ry="4.2" transform="rotate(60)" />
      <ellipse rx="11" ry="4.2" transform="rotate(120)" />
    </g>
  </svg>
);

const TailwindLogo = () => (
  <svg viewBox="0 0 54 33" className="h-10 w-10">
    <path
      fillRule="evenodd"
      clipRule="evenodd"
      d="M27 0c-7.2 0-11.7 3.6-13.5 10.8 2.7-3.6 5.85-4.95 9.45-4.05 2.054.514 3.522 2.004 5.147 3.653C30.744 13.09 33.808 16.2 40.5 16.2c7.2 0 11.7-3.6 13.5-10.8-2.7 3.6-5.85 4.95-9.45 4.05-2.054-.514-3.522-2.004-5.147-3.653C36.756 3.11 33.692 0 27 0zM13.5 16.2C6.3 16.2 1.8 19.8 0 27c2.7-3.6 5.85-4.95 9.45-4.05 2.054.514 3.522 2.004 5.147 3.653C17.244 29.29 20.308 32.4 27 32.4c7.2 0 11.7-3.6 13.5-10.8-2.7 3.6-5.85 4.95-9.45 4.05-2.054-.514-3.522-2.004-5.147-3.653C23.256 19.31 20.192 16.2 13.5 16.2z"
      fill="#38BDF8"
    />
  </svg>
);

const RechartsLogo = () => (
  <svg viewBox="0 0 48 48" className="h-10 w-10" fill="none">
    <rect x="6" y="28" width="8" height="14" rx="2" fill="#8884d8" />
    <rect x="20" y="18" width="8" height="24" rx="2" fill="#82ca9d" />
    <rect x="34" y="8" width="8" height="34" rx="2" fill="#ffc658" />
    <path d="M10 12l14-4 14 8" stroke="#00F0FF" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    <circle cx="10" cy="12" r="2.5" fill="#00F0FF" />
    <circle cx="24" cy="8" r="2.5" fill="#00F0FF" />
    <circle cx="38" cy="16" r="2.5" fill="#00F0FF" />
  </svg>
);

const FramerLogo = () => (
  <svg viewBox="0 0 14 21" className="h-10 w-10">
    <path d="M0 0h14v7H7zm0 7h7l7 7H7v7l-7-7z" fill="#0055FF" />
  </svg>
);

/* ---- Tech Data — grouped into two wings ---- */

interface TechGroup {
  title: string;
  items: TechItem[];
}

const techGroups: TechGroup[] = [
  {
    title: "AI & Backend",
    items: [
      { name: "YOLOv8-Seg", role: "Room Segmentation", logo: <YOLOLogo />, glow: "rgba(168,85,247,0.35)" },
      { name: "Python", role: "Core Logic", logo: <PythonLogo />, glow: "rgba(55,118,171,0.35)" },
      { name: "FastAPI", role: "API Framework", logo: <FastAPILogo />, glow: "rgba(0,150,136,0.35)" },
      { name: "OpenCV", role: "Computer Vision", logo: <OpenCVLogo />, glow: "rgba(0,170,0,0.3)" },
      { name: "EasyOCR", role: "Primary OCR", logo: <EasyOCRLogo />, glow: "rgba(238,76,44,0.3)" },
      { name: "PaddleOCR", role: "Fallback OCR", logo: <PaddleOCRLogo />, glow: "rgba(37,99,235,0.35)" },
      { name: "Shapely", role: "Geometry Engine", logo: <ShapelyLogo />, glow: "rgba(16,185,129,0.3)" },
      { name: "PyMuPDF", role: "PDF Processing", logo: <PyMuPDFLogo />, glow: "rgba(239,68,68,0.3)" },
      { name: "NumPy", role: "Matrix Math", logo: <NumPyLogo />, glow: "rgba(77,171,207,0.35)" },
    ],
  },
  {
    title: "Frontend & Visualization",
    items: [
      { name: "React", role: "UI Framework", logo: <ReactLogo />, glow: "rgba(97,218,251,0.3)" },
      { name: "Tailwind CSS", role: "Styling Engine", logo: <TailwindLogo />, glow: "rgba(56,189,248,0.3)" },
      { name: "Recharts", role: "Analytics Charts", logo: <RechartsLogo />, glow: "rgba(136,132,216,0.3)" },
      { name: "Framer Motion", role: "Animation Physics", logo: <FramerLogo />, glow: "rgba(0,85,255,0.3)" },
    ],
  },
];

/* ---- Tech Card ---- */

function TechCard({ item }: { item: TechItem }) {
  return (
    <div
      className="group relative flex flex-col items-center justify-center gap-3 rounded-2xl border border-[rgba(56,189,248,0.12)] bg-slate-900/60 p-6 backdrop-blur-xl transition-all duration-500 hover:border-[rgba(56,189,248,0.35)]"
      onMouseEnter={(e) => {
        (e.currentTarget as HTMLDivElement).style.boxShadow = `inset 0 0 40px ${item.glow}, 0 0 20px ${item.glow}`;
      }}
      onMouseLeave={(e) => {
        (e.currentTarget as HTMLDivElement).style.boxShadow = "none";
      }}
    >
      {/* Logo with glow */}
      <div className="relative transition-transform duration-500 group-hover:scale-110">
        <div
          className="absolute inset-0 rounded-full opacity-0 blur-xl transition-opacity duration-500 group-hover:opacity-60"
          style={{ backgroundColor: item.glow }}
        />
        <div className="relative">{item.logo}</div>
      </div>

      {/* Name */}
      <span className="text-sm font-bold text-white">{item.name}</span>

      {/* Role sub-label */}
      <span className="text-[10px] font-semibold uppercase tracking-widest text-[#0EA5E9]">{item.role}</span>
    </div>
  );
}

/* ================================================================ */
/*  MAIN: TECH STACK                                                 */
/* ================================================================ */

export default function TechStack() {
  return (
    <section id="tech-stack" className="space-y-8">
      {/* Section header */}
      <div>
        <h2 className="text-quantum-blue font-display text-lg font-bold tracking-tight">
          Powered By Best-in-Class Open Source
        </h2>
        <p className="text-xs text-[#94A3B8]">The engine under the hood</p>
      </div>

      {/* Grouped grids */}
      {techGroups.map((group) => (
        <div key={group.title} className="space-y-4">
          {/* Wing sub-header */}
          <div className="flex items-center gap-3">
            <div className="h-px flex-1 bg-gradient-to-r from-[rgba(56,189,248,0.2)] to-transparent" />
            <span className="text-[11px] font-bold uppercase tracking-[0.2em] text-[#94A3B8]">{group.title}</span>
            <div className="h-px flex-1 bg-gradient-to-l from-[rgba(56,189,248,0.2)] to-transparent" />
          </div>

          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            {group.items.map((item) => (
              <TechCard key={item.name} item={item} />
            ))}
          </div>
        </div>
      ))}
    </section>
  );
}
