import React, { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { Card, CardContent } from "@/components/ui/card";
import { Package, TrendingUp, Scale, Coins } from "lucide-react";

function fmtWt(w) {
  return (Number(w) || 0).toFixed(3);
}
function fmtInr(n) {
  return "₹" + (Number(n) || 0).toLocaleString("en-IN", { maximumFractionDigits: 2 });
}

export default function Dashboard() {
  const { branchId, branches, user } = useAuth();
  const [rates, setRates] = useState([]);
  const [summary, setSummary] = useState(null);

  useEffect(() => {
    api.get("/daily-rates/latest").then((r) => setRates(r.data)).catch(() => {});
  }, []);

  useEffect(() => {
    if (branchId) {
      api.get(`/stock/summary?branch_id=${branchId}`)
        .then((r) => setSummary(r.data))
        .catch(() => setSummary(null));
    }
  }, [branchId]);

  const current = branches.find((b) => b.id === branchId);
  const g24 = rates.find((r) => r.purity_code === "24K");
  const stockValue = summary && g24
    ? summary.total_net_weight * g24.rate_per_gram
    : 0;

  return (
    <div className="space-y-8">
      <div>
        <p className="text-xs uppercase tracking-[0.25em]" style={{ color: "var(--text-muted)" }}>
          {current?.name || "Dashboard"}
        </p>
        <h1 className="text-3xl font-semibold tracking-tight mt-1">
          Good day, {user?.name?.split(" ")[0]}.
        </h1>
      </div>

      {/* Rate Board */}
      <Card data-testid="daily-rate-board-card" className="overflow-hidden"
        style={{ borderColor: "var(--line)", background: "var(--panel)" }}>
        <div className="h-1 shimmer-gold"></div>
        <CardContent className="p-6">
          <div className="flex items-center justify-between mb-5">
            <div>
              <div className="text-xs uppercase tracking-[0.25em]" style={{ color: "var(--text-muted)" }}>
                Daily Rate Board
              </div>
              <h2 className="font-semibold tracking-tight text-2xl mt-0.5">Today's Metal Rates</h2>
            </div>
            <div className="text-xs font-mono" style={{ color: "var(--text-muted)" }}>
              per gram · INR
            </div>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            {rates.map((r) => (
              <div key={r.id} className="rounded-md p-4 border"
                style={{ borderColor: "var(--line)", background: "var(--surface)" }}
                data-testid={`rate-card-${r.purity_code}`}>
                <div className="text-[10px] uppercase tracking-widest font-medium"
                  style={{ color: "var(--text-muted)" }}>
                  {r.metal}
                </div>
                <div className="font-semibold tracking-tight text-xl mt-1">{r.purity_code}</div>
                <div className="font-num text-2xl font-semibold mt-2"
                  style={{ color: "var(--gold-text)" }}>
                  ₹{r.rate_per_gram.toFixed(2)}
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <StatCard
          icon={Package}
          label="Items in stock"
          value={summary?.total_items_in_stock ?? "—"}
          testId="stat-items-count"
        />
        <StatCard
          icon={Scale}
          label="Total net weight"
          value={summary ? `${fmtWt(summary.total_net_weight)} g` : "—"}
          testId="stat-total-weight"
          mono
        />
        <StatCard
          icon={Coins}
          label="Approx. valuation @ 24K"
          value={stockValue ? fmtInr(stockValue) : "—"}
          testId="stat-valuation"
          mono
        />
      </div>
    </div>
  );
}

function StatCard({ icon: Icon, label, value, mono, testId }) {
  return (
    <Card style={{ borderColor: "var(--line)", background: "var(--panel)" }}>
      <CardContent className="p-5">
        <div className="flex items-center gap-2 text-xs uppercase tracking-widest"
          style={{ color: "var(--text-muted)" }}>
          <Icon className="w-3.5 h-3.5" />
          {label}
        </div>
        <div
          className={`mt-3 text-3xl font-semibold ${mono ? "font-num" : "font-semibold tracking-tight"}`}
          data-testid={testId}
        >
          {value}
        </div>
      </CardContent>
    </Card>
  );
}
