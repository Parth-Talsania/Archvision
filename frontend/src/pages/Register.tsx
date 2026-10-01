import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Eye, EyeOff, Building2 } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
import { apiErrorMessage } from "@/api/client";

const Register = () => {
  const [showPassword, setShowPassword] = useState(false);
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const { register } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    if (password !== confirmPassword) {
      setError("Passwords do not match");
      return;
    }
    if (password.length < 6) {
      setError("Password must be at least 6 characters");
      return;
    }

    setLoading(true);
    try {
      await register(email, password, fullName);
      navigate("/dashboard");
    } catch (err) {
      setError(apiErrorMessage(err, "Registration failed"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden">
      <div className="blueprint-grid absolute inset-0" />
      <div className="absolute inset-0 bg-gradient-to-br from-background via-background/90 to-background/80" />

      <div className="glass-panel relative z-10 mx-4 w-full max-w-md rounded-2xl p-8 shadow-2xl sm:p-10">
        <div className="mb-6 flex flex-col items-center">
          <div className="animate-logo-float mb-3 flex h-14 w-14 items-center justify-center rounded-xl border border-[#0EA5E9]/20 bg-[#0EA5E9]/10">
            <Building2 className="h-7 w-7 text-[#0EA5E9]" />
          </div>
          <h1 className="font-display text-2xl font-bold tracking-tight text-white">
            Create <span className="text-[#0EA5E9]">Account</span>
          </h1>
          <p className="mt-1 text-sm text-[#94A3B8]">Join ArchVision today</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          {error && (
            <div className="rounded-lg border border-[#EF4444]/50 bg-[#EF4444]/10 px-4 py-2 text-sm text-[#EF4444]">
              {error}
            </div>
          )}

          <div className="space-y-1.5">
            <label htmlFor="fullName" className="text-xs font-medium uppercase tracking-wider text-[#94A3B8]">Full Name</label>
            <input
              id="fullName"
              type="text"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              placeholder="John Doe"
              required
              className="input-glow w-full rounded-lg border border-[rgba(56,189,248,0.15)] bg-[#CBD5E1]/10 px-4 py-2.5 text-sm text-white placeholder:text-[#94A3B8]/50 transition-all duration-300 outline-none"
            />
          </div>

          <div className="space-y-1.5">
            <label htmlFor="email" className="text-xs font-medium uppercase tracking-wider text-[#94A3B8]">Email</label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              required
              className="input-glow w-full rounded-lg border border-[rgba(56,189,248,0.15)] bg-[#CBD5E1]/10 px-4 py-2.5 text-sm text-white placeholder:text-[#94A3B8]/50 transition-all duration-300 outline-none"
            />
          </div>

          <div className="space-y-1.5">
            <label htmlFor="password" className="text-xs font-medium uppercase tracking-wider text-[#94A3B8]">Password</label>
            <div className="relative">
              <input
                id="password"
                type={showPassword ? "text" : "password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                required
                className="input-glow w-full rounded-lg border border-[rgba(56,189,248,0.15)] bg-[#CBD5E1]/10 px-4 py-2.5 pr-10 text-sm text-white placeholder:text-[#94A3B8]/50 transition-all duration-300 outline-none"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-[#94A3B8] transition-colors duration-200 hover:text-[#0EA5E9]"
              >
                {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
          </div>

          <div className="space-y-1.5">
            <label htmlFor="confirmPassword" className="text-xs font-medium uppercase tracking-wider text-[#94A3B8]">Confirm Password</label>
            <input
              id="confirmPassword"
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              placeholder="••••••••"
              required
              className="input-glow w-full rounded-lg border border-[rgba(56,189,248,0.15)] bg-[#CBD5E1]/10 px-4 py-2.5 text-sm text-white placeholder:text-[#94A3B8]/50 transition-all duration-300 outline-none"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="btn-shimmer w-full rounded-lg py-2.5 text-sm font-semibold text-white transition-all disabled:opacity-50"
          >
            {loading ? "Creating account..." : "Create Account"}
          </button>
        </form>

        <p className="mt-6 text-center text-sm text-[#94A3B8]">
          Already have an account?{" "}
          <a href="/login" className="link-slide font-medium text-[#0EA5E9] transition-colors hover:text-[#7DD3FC]">
            Sign in
          </a>
        </p>
      </div>
    </div>
  );
};

export default Register;
