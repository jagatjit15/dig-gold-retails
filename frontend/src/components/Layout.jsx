import React, { useEffect, useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { api } from "@/lib/api";
import {
  Crown, LayoutDashboard, Package, ScanLine, ClipboardCheck,
  Settings, Printer, ShieldCheck, Sun, Moon, LogOut, Receipt, FolderOpen, MessageCircle, Users, Truck, Sparkles,
} from "lucide-react";
import {
  DropdownMenu, DropdownMenuTrigger, DropdownMenuContent,
  DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator,
} from "@/components/ui/dropdown-menu";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

const NAV = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, end: true, tid: "nav-dashboard" },
  { to: "/billing", label: "Billing", icon: Receipt, tid: "nav-billing" },
  { to: "/inventory", label: "Inventory", icon: Package, tid: "nav-inventory" },
  { to: "/scan", label: "Scan Lookup", icon: ScanLine, tid: "nav-scan" },
  { to: "/audit", label: "Stock Audit", icon: ClipboardCheck, tid: "nav-audit" },
  { to: "/transfers", label: "Transfers", icon: Truck, tid: "nav-transfers" },
  { to: "/labels", label: "Label Print", icon: Printer, tid: "nav-labels" },
  { to: "/documents", label: "Documents", icon: FolderOpen, tid: "nav-documents" },
  { to: "/whatsapp", label: "WhatsApp", icon: MessageCircle, tid: "nav-whatsapp" },
  { to: "/lookbook", label: "Lookbook", icon: Sparkles, tid: "nav-lookbook" },
  { to: "/staff", label: "Staff", icon: Users, tid: "nav-staff", roles: ["admin"] },
  { to: "/masters", label: "Masters & Rates", icon: Settings, tid: "nav-masters" },
  { to: "/audit-log", label: "Audit Log", icon: ShieldCheck, tid: "nav-audit-log" },
];

function TopBar() {
  const { user, logout, branchId, setBranchId, branches } = useAuth();
  const [theme, setTheme] = useState(
    () => localStorage.getItem("swarna_theme") || "light"
  );
  const [rates, setRates] = useState([]);
  const nav = useNavigate();

  useEffect(() => {
    api.get("/daily-rates/latest").then((r) => setRates(r.data)).catch(() => {});
  }, []);

  const toggleTheme = () => {
    const next = theme === "light" ? "dark" : "light";
    document.documentElement.classList.toggle("dark", next === "dark");
    localStorage.setItem("swarna_theme", next);
    setTheme(next);
  };

  const current = branches.find((b) => b.id === branchId);
  const findRate = (metal, code) =>
    rates.find((r) => r.metal === metal && r.purity_code === code);

  return (
    <header
      className="h-16 flex items-center justify-between px-6 border-b sticky top-0 z-30 backdrop-blur"
      style={{
        borderColor: "var(--border)",
        background: "color-mix(in oklab, var(--bg) 92%, transparent)",
      }}
    >
      <div className="flex items-center gap-6">
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              variant="outline"
              className="h-9 gap-2"
              data-testid="branch-switcher-dropdown"
              style={{ borderColor: "var(--border)" }}
            >
              <span className="text-xs uppercase tracking-widest" style={{ color: "var(--text-muted)" }}>
                Branch
              </span>
              <span className="font-medium">{current?.name || "—"}</span>
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start" className="w-64">
            <DropdownMenuLabel>Switch branch</DropdownMenuLabel>
            <DropdownMenuSeparator />
            {branches.map((b) => (
              <DropdownMenuItem
                key={b.id}
                onClick={() => setBranchId(b.id)}
                data-testid={`branch-option-${b.code}`}
              >
                <span className="font-medium">{b.name}</span>
                <span className="ml-auto font-mono text-xs" style={{ color: "var(--text-muted)" }}>
                  {b.code}
                </span>
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>

        <div className="hidden md:flex items-center gap-4 pl-6 border-l"
          style={{ borderColor: "var(--border)" }} data-testid="rate-ticker">
          {[
            { label: "24K", key: findRate("gold", "24K"), tid: "gold-rate-24k-val" },
            { label: "22K", key: findRate("gold", "22K916"), tid: "gold-rate-22k-val" },
            { label: "Ag", key: findRate("silver", "925"), tid: "silver-rate-val" },
          ].map((r) => (
            <div key={r.label} className="flex items-baseline gap-2">
              <span className="text-xs uppercase tracking-widest"
                style={{ color: "var(--text-muted)" }}>{r.label}</span>
              <span className="font-num text-sm font-semibold"
                style={{ color: "var(--gold-text)" }}
                data-testid={r.tid}>
                ₹{r.key ? r.key.rate_per_gram.toFixed(2) : "—"}
              </span>
            </div>
          ))}
        </div>
      </div>

      <div className="flex items-center gap-3">
        <Button variant="ghost" size="icon" onClick={toggleTheme}
          data-testid="theme-toggle-button">
          {theme === "light" ? <Moon className="w-4 h-4" /> : <Sun className="w-4 h-4" />}
        </Button>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" className="gap-2 h-9" data-testid="user-menu-trigger">
              <div className="w-8 h-8 rounded-full flex items-center justify-center font-serif-brand text-sm"
                style={{ background: "var(--gold-soft)", color: "var(--gold-text)" }}>
                {user?.name?.[0]?.toUpperCase() || "U"}
              </div>
              <div className="text-left hidden sm:block">
                <div className="text-sm font-medium leading-none">{user?.name}</div>
                <div className="text-[11px] uppercase tracking-widest"
                  style={{ color: "var(--text-muted)" }}>
                  {user?.role}
                </div>
              </div>
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-56">
            <DropdownMenuLabel>{user?.email}</DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={() => { logout(); nav("/login"); }}
              data-testid="logout-menu-item">
              <LogOut className="w-4 h-4 mr-2" /> Sign out
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
}

function Sidebar() {
  const { user } = useAuth();
  return (
    <aside
      className="w-64 shrink-0 border-r flex flex-col"
      style={{ borderColor: "var(--border)", background: "var(--surface)" }}
    >
      <div className="h-16 flex items-center gap-3 px-6 border-b"
        style={{ borderColor: "var(--border)" }}>
        <div className="w-9 h-9 rounded-md flex items-center justify-center"
          style={{ background: "var(--gold)" }}>
          <Crown className="w-5 h-5 text-white" />
        </div>
        <div>
          <div className="font-serif-brand text-xl leading-none">SwarnaERP</div>
          <div className="text-[10px] uppercase tracking-[0.12em] whitespace-nowrap"
            style={{ color: "var(--text-muted)" }}>
            Jewellery Platform
          </div>
        </div>
      </div>
      <nav className="flex-1 p-3 space-y-1">
        {NAV.filter((n) => !n.roles || n.roles.includes(user?.role)).map((n) => (
          <NavLink
            key={n.to}
            to={n.to}
            end={n.end}
            data-testid={n.tid}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-md text-sm transition-colors ${
                isActive ? "font-semibold" : "hover:bg-black/5 dark:hover:bg-white/5"
              }`
            }
            style={({ isActive }) => isActive ? {
              borderLeft: "3px solid var(--primary)", color: "var(--primary)",
              background: "color-mix(in oklab, var(--primary) 10%, transparent)",
            } : { color: "var(--text-2)" }}
          >
            <n.icon className="w-4 h-4" />
            <span>{n.label}</span>
          </NavLink>
        ))}
      </nav>
      <div className="p-4 border-t text-[11px] font-mono"
        style={{ borderColor: "var(--border)", color: "var(--text-muted)" }}>
        <Badge variant="outline" className="font-mono text-[10px]"
          style={{ borderColor: "var(--border)" }}>
          {user?.role?.toUpperCase()}
        </Badge>
        <div className="mt-2">v0.2</div>
      </div>
    </aside>
  );
}

export default function Layout() {
  return (
    <div className="min-h-screen flex" style={{ background: "var(--bg)" }}>
      <Sidebar />
      <div className="flex-1 flex flex-col">
        <TopBar />
        <main className="flex-1 p-8 overflow-x-hidden">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
