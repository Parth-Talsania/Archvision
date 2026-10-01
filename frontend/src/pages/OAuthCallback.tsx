import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { Building2 } from "lucide-react";

/**
 * Handles the redirect from the FastAPI OAuth callback.
 * Reads `?token=...` or `?error=...` from the URL,
 * stores the JWT via AuthContext, and navigates to /dashboard.
 */
const OAuthCallback = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { loginWithToken } = useAuth();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const token = searchParams.get("token");
    const oauthError = searchParams.get("error");

    if (oauthError) {
      setError(oauthError);
      // Redirect to login after showing error briefly
      setTimeout(() => navigate("/login", { state: { oauthError } }), 3000);
      return;
    }

    if (token) {
      loginWithToken(token)
        .then(() => navigate("/dashboard", { replace: true }))
        .catch(() => {
          setError("Failed to authenticate. Please try again.");
          setTimeout(() => navigate("/login"), 3000);
        });
    } else {
      setError("No authentication token received.");
      setTimeout(() => navigate("/login"), 3000);
    }
  }, [searchParams, loginWithToken, navigate]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-background">
      <div className="flex flex-col items-center gap-4">
        <div className="flex h-14 w-14 items-center justify-center rounded-xl border border-[#0EA5E9]/20 bg-[#0EA5E9]/10">
          <Building2 className="h-7 w-7 text-[#0EA5E9]" />
        </div>
        {error ? (
          <div className="text-center">
            <p className="text-red-400 font-sans text-sm mt-2">{error}</p>
            <p className="text-[#94A3B8] text-xs mt-2">Redirecting to login...</p>
          </div>
        ) : (
          <div className="text-center">
            <div className="h-8 w-8 mx-auto animate-spin rounded-full border-2 border-[#0EA5E9] border-t-transparent" />
            <p className="text-[#94A3B8] text-sm mt-3">Completing sign in...</p>
          </div>
        )}
      </div>
    </div>
  );
};

export default OAuthCallback;
