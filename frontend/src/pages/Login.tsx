import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Eye, EyeOff, Building2, Brain, ScanEye, Workflow, Frame, Ruler, PencilRuler, LayoutGrid } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
import { apiErrorMessage } from "@/api/client";

const floatingIcons = [
  { Icon: Brain, top: "8%", left: "6%", anim: "float-drift-1", dur: "20s", size: 32, opacity: 0.12 },
  { Icon: ScanEye, top: "18%", left: "75%", anim: "float-drift-2", dur: "25s", size: 36, opacity: 0.1 },
  { Icon: Ruler, top: "55%", left: "85%", anim: "float-drift-3", dur: "18s", size: 28, opacity: 0.1 },
  { Icon: PencilRuler, top: "70%", left: "10%", anim: "float-drift-1", dur: "22s", size: 30, opacity: 0.11, reverse: true },
  { Icon: Workflow, top: "35%", left: "88%", anim: "float-drift-2", dur: "26s", size: 34, opacity: 0.09 },
  { Icon: LayoutGrid, top: "80%", left: "60%", anim: "float-drift-3", dur: "24s", size: 26, opacity: 0.1 },
  { Icon: Frame, top: "12%", left: "40%", anim: "float-drift-1", dur: "28s", size: 30, opacity: 0.08 },
  { Icon: Building2, top: "45%", left: "4%", anim: "float-drift-2", dur: "30s", size: 38, opacity: 0.09 },
];

const NeuralNetwork = () => (
  <svg
    className="absolute top-[25%] left-[15%] w-48 h-48 opacity-[0.07]"
    viewBox="0 0 200 200"
    style={{ animation: "float-drift-1 32s ease-in-out infinite" }}
  >
    {/* Connections */}
    {[
      [40, 60, 100, 40], [40, 60, 100, 100], [40, 60, 100, 160],
      [40, 140, 100, 40], [40, 140, 100, 100], [40, 140, 100, 160],
      [100, 40, 160, 80], [100, 100, 160, 80], [100, 160, 160, 80],
      [100, 40, 160, 140], [100, 100, 160, 140], [100, 160, 160, 140],
    ].map(([x1, y1, x2, y2], i) => (
      <line key={i} x1={x1} y1={y1} x2={x2} y2={y2} stroke="hsl(280 70% 65%)" strokeWidth="0.8" opacity="0.5" />
    ))}
    {/* Nodes */}
    {[
      [40, 60], [40, 140],
      [100, 40], [100, 100], [100, 160],
      [160, 80], [160, 140],
    ].map(([cx, cy], i) => (
      <circle
        key={i}
        cx={cx}
        cy={cy}
        r="6"
        fill="hsl(280 70% 65%)"
        style={{ animation: `node-pulse 3s ease-in-out infinite`, animationDelay: `${i * 0.4}s` }}
      />
    ))}
  </svg>
);

const ScanningRadar = () => (
  <svg
    className="absolute bottom-[15%] left-[8%] w-36 h-36 opacity-[0.06]"
    viewBox="0 0 100 100"
    style={{ animation: "float-drift-3 26s ease-in-out infinite" }}
  >
    <circle cx="50" cy="50" r="40" fill="none" stroke="hsl(190 80% 55%)" strokeWidth="0.6" />
    <circle cx="50" cy="50" r="28" fill="none" stroke="hsl(190 80% 55%)" strokeWidth="0.5" />
    <circle cx="50" cy="50" r="16" fill="none" stroke="hsl(190 80% 55%)" strokeWidth="0.4" />
    <circle cx="50" cy="50" r="3" fill="hsl(190 80% 55%)" opacity="0.6" />
    <line
      x1="50"
      y1="50"
      x2="50"
      y2="10"
      stroke="hsl(190 80% 55%)"
      strokeWidth="1.2"
      style={{ transformOrigin: "50px 50px", animation: "radar-sweep 12s linear infinite" }}
    />
  </svg>
);

const BoundingBox = () => (
  <svg
    className="absolute top-[60%] right-[15%] w-28 h-28 opacity-[0.07]"
    viewBox="0 0 100 100"
    style={{ animation: "float-drift-2 22s ease-in-out infinite reverse" }}
  >
    <g style={{ animation: "bbox-pulse 2s ease-in-out infinite" }}>
      <rect x="15" y="20" width="70" height="55" fill="none" stroke="hsl(190 80% 55%)" strokeWidth="1.5" rx="2" />
      {/* Corner markers */}
      <path d="M15 30 V20 H25" fill="none" stroke="hsl(280 70% 65%)" strokeWidth="2" />
      <path d="M75 20 H85 V30" fill="none" stroke="hsl(280 70% 65%)" strokeWidth="2" />
      <path d="M85 65 V75 H75" fill="none" stroke="hsl(280 70% 65%)" strokeWidth="2" />
      <path d="M25 75 H15 V65" fill="none" stroke="hsl(280 70% 65%)" strokeWidth="2" />
      {/* Label */}
      <text x="50" y="14" textAnchor="middle" fill="hsl(190 80% 55%)" fontSize="7" opacity="0.7">wall_0.94</text>
    </g>
  </svg>
);

const FloatingShapes = () => (
  <div className="absolute inset-0 overflow-hidden pointer-events-none">
    {floatingIcons.map(({ Icon, top, left, anim, dur, size, opacity, reverse }, i) => (
      <div
        key={i}
        className="absolute text-[#0EA5E9]"
        style={{
          top,
          left,
          opacity,
          animation: `${anim} ${dur} ease-in-out infinite${reverse ? " reverse" : ""}`,
        }}
      >
        <Icon size={size} strokeWidth={1.2} />
      </div>
    ))}

    {/* Neural Network */}
    <NeuralNetwork />

    {/* Scanning Radar */}
    <ScanningRadar />

    {/* Bounding Box Detection */}
    <BoundingBox />

    {/* Blueprint unfold with draw animation */}
    <svg
      className="absolute top-[15%] right-[12%] w-40 h-40 opacity-[0.06]"
      viewBox="0 0 100 100"
      style={{ animation: "float-drift-2 28s ease-in-out infinite" }}
    >
      <path
        d="M10 10 H60 V40 H40 V90 H10 Z"
        fill="none"
        stroke="hsl(280 70% 65%)"
        strokeWidth="1"
        strokeDasharray="300"
        style={{ animation: "draw-line 4s ease-in-out infinite alternate" }}
      />
      <line x1="10" y1="50" x2="40" y2="50" stroke="hsl(280 70% 65%)" strokeWidth="0.5" strokeDasharray="2,2" />
      <line x1="25" y1="10" x2="25" y2="90" stroke="hsl(280 70% 65%)" strokeWidth="0.5" strokeDasharray="2,2" />
    </svg>

    {/* Room layout fragment */}
    <svg
      className="absolute bottom-[30%] right-[30%] w-32 h-32 opacity-[0.05]"
      viewBox="0 0 100 100"
      style={{ animation: "float-drift-3 24s ease-in-out infinite" }}
    >
      <rect x="10" y="10" width="35" height="35" fill="none" stroke="hsl(190 80% 55%)" strokeWidth="1" />
      <rect x="55" y="10" width="35" height="80" fill="none" stroke="hsl(190 80% 55%)" strokeWidth="1" />
      <rect x="10" y="55" width="35" height="35" fill="none" stroke="hsl(190 80% 55%)" strokeWidth="1" />
    </svg>

    {/* Particle dots */}
    {Array.from({ length: 12 }).map((_, i) => (
      <div
        key={i}
        className="absolute w-1 h-1 rounded-full bg-accent/40"
        style={{
          top: `${10 + (i * 7) % 80}%`,
          left: `${5 + (i * 11) % 85}%`,
          animation: `particle-drift ${8 + (i % 5) * 3}s linear infinite`,
          animationDelay: `${i * 0.8}s`,
        }}
      />
    ))}
  </div>
);

const Login = () => {
  const [showPassword, setShowPassword] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [rememberMe, setRememberMe] = useState(false);
  const [error, setError] = useState("");
  const [oauthError, setOauthError] = useState("");
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  // Pick up OAuth error passed via router state (from OAuthCallback redirect)
  useEffect(() => {
    const state = window.history.state?.usr as { oauthError?: string } | undefined;
    if (state?.oauthError) {
      setOauthError(state.oauthError);
    }
  }, []);

  const handleGoogleLogin = () => {
    window.location.href = "/api/auth/google";
  };

  const handleGitHubLogin = () => {
    window.location.href = "/api/auth/github";
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login(email, password);
      navigate("/dashboard");
    } catch (err) {
      setError(apiErrorMessage(err, "Invalid email or password"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden">
      <div className="blueprint-grid absolute inset-0" />
      <div className="absolute inset-0 bg-gradient-to-br from-background via-background/90 to-background/80" />
      <FloatingShapes />

      <div className="glass-panel relative z-10 mx-4 w-full max-w-md rounded-2xl p-8 shadow-2xl sm:p-10">
        <div className="mb-6 flex flex-col items-center">
          <div className="animate-logo-float mb-3 flex h-14 w-14 items-center justify-center rounded-xl border border-[#0EA5E9]/20 bg-[#0EA5E9]/10">
            <Building2 className="h-7 w-7 text-[#0EA5E9]" />
          </div>
          <h1 className="font-display text-2xl font-bold tracking-tight text-white">
            Arch<span className="text-[#0EA5E9]">Vision</span>
          </h1>
          <p className="mt-1 text-sm text-[#94A3B8]">Intelligent Floor Plan Analysis</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-5">
          {error && (
            <div className="rounded-lg border border-[#EF4444]/50 bg-[#EF4444]/10 px-4 py-2 text-sm text-[#EF4444]">
              {error}
            </div>
          )}
          {oauthError && (
            <p className="text-red-400 font-sans text-sm mt-2">{oauthError}</p>
          )}
          <div className="space-y-1.5">
            <label htmlFor="email" className="text-xs font-medium uppercase tracking-wider text-[#94A3B8]">Email</label>
            <input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" className="input-glow w-full rounded-lg border border-[rgba(56,189,248,0.15)] bg-[#CBD5E1]/10 px-4 py-2.5 text-sm text-white placeholder:text-[#94A3B8]/50 transition-all duration-300 outline-none" />
          </div>

          <div className="space-y-1.5">
            <label htmlFor="password" className="text-xs font-medium uppercase tracking-wider text-[#94A3B8]">Password</label>
            <div className="relative">
              <input id="password" type={showPassword ? "text" : "password"} value={password} onChange={(e) => setPassword(e.target.value)} placeholder="••••••••" className="input-glow w-full rounded-lg border border-[rgba(56,189,248,0.15)] bg-[#CBD5E1]/10 px-4 py-2.5 pr-10 text-sm text-white placeholder:text-[#94A3B8]/50 transition-all duration-300 outline-none" />
              <button type="button" onClick={() => setShowPassword(!showPassword)} className="absolute right-3 top-1/2 -translate-y-1/2 text-[#94A3B8] transition-colors duration-200 hover:text-[#0EA5E9]">
                {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
          </div>

          <div className="flex items-center justify-between">
            <label className="flex cursor-pointer items-center gap-2 text-sm text-[#94A3B8]">
              <div className="relative">
                <input type="checkbox" checked={rememberMe} onChange={(e) => setRememberMe(e.target.checked)} className="peer sr-only" />
                <div className="h-4 w-4 rounded border border-[rgba(56,189,248,0.15)] bg-[#CBD5E1]/10 transition-all duration-200 peer-checked:border-[#0EA5E9] peer-checked:bg-[#0EA5E9]" />
                <svg className="absolute left-0.5 top-0.5 h-3 w-3 text-white opacity-0 transition-opacity duration-200 peer-checked:opacity-100" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M2 6l3 3 5-5" /></svg>
              </div>
              Remember me
            </label>
            <a href="#" className="link-slide text-sm text-[#0EA5E9] transition-colors hover:text-[#7DD3FC]">Forgot password?</a>
          </div>

          <button type="submit" disabled={loading} className="btn-shimmer w-full rounded-lg py-2.5 text-sm font-semibold text-white transition-all disabled:opacity-50">
            {loading ? "Signing in..." : "Sign In"}
          </button>
        </form>

        <div className="my-6 flex items-center gap-3">
          <div className="h-px flex-1 bg-[rgba(56,189,248,0.15)]" />
          <span className="text-xs text-[#94A3B8]">or continue with</span>
          <div className="h-px flex-1 bg-[rgba(56,189,248,0.15)]" />
        </div>

        <div className="grid grid-cols-2 gap-3">
          <button onClick={handleGoogleLogin} type="button" className="social-btn flex items-center justify-center gap-2 rounded-lg border border-[rgba(56,189,248,0.15)] bg-[#CBD5E1]/10 py-2.5 text-sm font-medium text-white">
            <svg className="h-4 w-4" viewBox="0 0 24 24"><path fill="currentColor" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" /><path fill="currentColor" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" /><path fill="currentColor" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" /><path fill="currentColor" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" /></svg>
            Google
          </button>
          <button onClick={handleGitHubLogin} type="button" className="social-btn flex items-center justify-center gap-2 rounded-lg border border-[rgba(56,189,248,0.15)] bg-[#CBD5E1]/10 py-2.5 text-sm font-medium text-white">
            <svg className="h-4 w-4" fill="currentColor" viewBox="0 0 24 24"><path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z" /></svg>
            GitHub
          </button>
        </div>

        <p className="mt-6 text-center text-sm text-[#94A3B8]">
          Don't have an account?{" "}
          <a href="/register" className="link-slide font-medium text-[#0EA5E9] transition-colors hover:text-[#7DD3FC]">Sign up</a>
        </p>
      </div>
    </div>
  );
};

export default Login;
