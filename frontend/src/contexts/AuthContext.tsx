import { createContext, useContext, useState, useEffect, useCallback, ReactNode, useMemo } from "react";
import api from "@/api/client";

interface User {
  id: number;
  email: string;
  full_name: string;
  created_at: string;
}

interface AuthContextType {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  loginWithToken: (token: string) => Promise<void>;
  register: (email: string, password: string, fullName: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(
    () => localStorage.getItem("archvision_token")
  );
  const [isLoading, setIsLoading] = useState(true);

  const fetchUser = useCallback(async () => {
    if (!token) {
      setIsLoading(false);
      return;
    }
    try {
      const res = await api.get("/auth/me");
      setUser(res.data);
    } catch {
      localStorage.removeItem("archvision_token");
      setToken(null);
      setUser(null);
    } finally {
      setIsLoading(false);
    }
  }, [token]);

  useEffect(() => {
    fetchUser();
  }, [fetchUser]);

  const login = async (email: string, password: string) => {
    const res = await api.post("/auth/login", { email, password });
    const accessToken = res.data.access_token;
    localStorage.setItem("archvision_token", accessToken);
    setToken(accessToken);
    // Fetch user profile
    const userRes = await api.get("/auth/me", {
      headers: { Authorization: `Bearer ${accessToken}` },
    });
    setUser(userRes.data);
  };

  const register = async (email: string, password: string, fullName: string) => {
    const res = await api.post("/auth/register", {
      email,
      password,
      full_name: fullName,
    });
    const accessToken = res.data.access_token;
    localStorage.setItem("archvision_token", accessToken);
    setToken(accessToken);
    const userRes = await api.get("/auth/me", {
      headers: { Authorization: `Bearer ${accessToken}` },
    });
    setUser(userRes.data);
  };

  const logout = () => {
    localStorage.removeItem("archvision_token");
    setToken(null);
    setUser(null);
  };

  const loginWithToken = useCallback(async (jwt: string) => {
    localStorage.setItem("archvision_token", jwt);
    setToken(jwt);
    const userRes = await api.get("/auth/me", {
      headers: { Authorization: `Bearer ${jwt}` },
    });
    setUser(userRes.data);
  }, []);

  const value = useMemo(() => ({
    user,
    token,
    isAuthenticated: !!user,
    isLoading,
    login,
    loginWithToken,
    register,
    logout,
  }), [user, token, isLoading, loginWithToken]);

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
