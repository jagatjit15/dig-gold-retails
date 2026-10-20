import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent } from "@/components/ui/card";
import { toast } from "sonner";
import { Crown, Lock } from "lucide-react";

export default function Login() {
  const nav = useNavigate();
  const { login } = useAuth();
  const [email, setEmail] = useState("admin@swarnaerp.in");
  const [password, setPassword] = useState("Admin@12345");
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      await login(email, password);
      toast.success("Welcome to SwarnaERP");
      nav("/");
    } catch (err) {
      toast.error(err.response?.data?.detail || "Login failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      className="min-h-screen flex bg-grain"
      style={{ background: "var(--bg)" }}
    >
      <div className="hidden lg:flex flex-1 flex-col justify-between p-16 relative overflow-hidden"
        style={{ background: "linear-gradient(135deg,#1C1613 0%,#2A1F15 60%,#3D2A17 100%)" }}>
        <div className="flex items-center gap-3 text-amber-100">
          <Crown className="w-7 h-7" style={{ color: "#D4AF37" }} />
          <span className="font-serif-brand text-2xl">SwarnaERP</span>
        </div>
        <div className="text-amber-50 space-y-4 max-w-md">
          <p className="uppercase tracking-[0.3em] text-xs text-amber-200/70">
            Multi-branch Jewellery Platform
          </p>
          <h1 className="font-serif-brand text-5xl leading-[1.05]">
            Precision for every <em style={{ color: "#D4AF37" }}>gram</em>,
            trust in every <em style={{ color: "#D4AF37" }}>tag</em>.
          </h1>
          <p className="text-amber-100/70 text-sm leading-relaxed">
            GST-compliant billing, append-only stock ledger, scan-driven audits,
            and branch-scoped RBAC — built for the Indian retail jeweller.
          </p>
        </div>
        <div className="text-xs text-amber-100/40 font-mono">
          Phase 1 · Masters · Inventory · ScanService · Labels
        </div>
      </div>
      <div className="flex-1 flex items-center justify-center p-6">
        <Card className="w-full max-w-md border shadow-sm"
          style={{ borderColor: "var(--border)", background: "var(--card)" }}>
          <CardContent className="p-10 space-y-6">
            <div className="space-y-1">
              <div className="flex items-center gap-2 text-amber-700">
                <Lock className="w-4 h-4" />
                <span className="text-xs uppercase tracking-widest">Sign In</span>
              </div>
              <h2 className="font-serif-brand text-3xl">Welcome back</h2>
              <p className="text-sm" style={{ color: "var(--text-2)" }}>
                Sign in with your branch-scoped credentials.
              </p>
            </div>
            <form onSubmit={submit} className="space-y-4">
              <div className="space-y-1.5">
                <Label htmlFor="email">Email</Label>
                <Input
                  id="email"
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  data-testid="login-email-input"
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="password">Password</Label>
                <Input
                  id="password"
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  data-testid="login-password-input"
                />
              </div>
              <Button
                type="submit"
                disabled={busy}
                className="w-full h-11 font-medium"
                style={{ background: "var(--gold)", color: "#fff" }}
                data-testid="login-submit-button"
              >
                {busy ? "Signing in…" : "Sign in"}
              </Button>
              <div className="text-xs text-center font-mono"
                style={{ color: "var(--text-muted)" }}>
                admin@swarnaerp.in · Admin@12345
              </div>
            </form>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
