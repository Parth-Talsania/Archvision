import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { Building2, LayoutDashboard, Upload, History, LogOut, User, Info, Users, GitCompareArrows } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
import TelemetryBar from "@/components/TelemetryBar";

const navItems = [
  { to: "/introduction", label: "Introduction", icon: Info },
  { to: "/founders", label: "Founders", icon: Users },
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { to: "/upload", label: "Upload", icon: Upload },
  { to: "/history", label: "History", icon: History },
  { to: "/compare", label: "Compare", icon: GitCompareArrows },
];

export default function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  return (
    <div className="flex min-h-screen flex-col">
      {/* Telemetry Bar — fixed top edge */}
      <TelemetryBar />

      <div className="flex flex-1 pt-8">
      {/* Sidebar */}
      <aside className="fixed inset-y-0 left-0 z-30 flex w-64 flex-col border-r border-[rgba(56,189,248,0.15)] bg-slate-900/40 backdrop-blur-xl pt-8">
        {/* Logo */}
        <div className="flex h-16 items-center gap-3 border-b border-[rgba(56,189,248,0.15)] px-6">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg border border-[#0EA5E9]/20 bg-[#0EA5E9]/10">
            <Building2 className="h-5 w-5 text-[#0EA5E9]" />
          </div>
          <span className="font-display text-lg font-bold tracking-tight text-white">
            Arch<span className="text-[#0EA5E9]">Vision</span>
          </span>
        </div>

        {/* Navigation */}
        <nav className="flex-1 space-y-1 p-4">
          {navItems.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-all duration-200 ${
                  isActive
                    ? "bg-[#0EA5E9]/15 text-[#0EA5E9] shadow-sm"
                    : "text-[#94A3B8] hover:bg-[#CBD5E1]/10 hover:text-white"
                }`
              }
            >
              <Icon className="h-4 w-4" />
              {label}
            </NavLink>
          ))}
        </nav>

        {/* User section */}
        <div className="border-t border-[rgba(56,189,248,0.15)] p-4">
          <div className="flex items-center gap-3">
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-[#0EA5E9]/10">
              <User className="h-4 w-4 text-[#0EA5E9]" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="truncate text-sm font-medium text-white">{user?.full_name}</p>
              <p className="truncate text-xs text-[#94A3B8]">{user?.email}</p>
            </div>
            <button
              onClick={handleLogout}
              className="rounded-lg p-1.5 text-[#94A3B8] transition-colors hover:bg-[#EF4444]/10 hover:text-[#EF4444]"
              title="Logout"
            >
              <LogOut className="h-4 w-4" />
            </button>
          </div>
        </div>
      </aside>

      {/* Main content */}
      <main className="ml-64 flex-1 overflow-auto">
        <div className="mx-auto max-w-7xl p-6 lg:p-8">
          <Outlet />
        </div>
      </main>
      </div>
    </div>
  );
}
