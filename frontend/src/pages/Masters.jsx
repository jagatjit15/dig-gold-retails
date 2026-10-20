import React, { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  Tabs, TabsList, TabsTrigger, TabsContent,
} from "@/components/ui/tabs";
import { toast } from "sonner";

export default function Masters() {
  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs uppercase tracking-[0.25em]" style={{ color: "var(--text-muted)" }}>
          Settings
        </p>
        <h1 className="text-3xl font-semibold tracking-tight mt-1">Masters & Rates</h1>
      </div>
      <Tabs defaultValue="rates">
        <TabsList>
          <TabsTrigger value="rates" data-testid="tab-rates">Daily Rates</TabsTrigger>
          <TabsTrigger value="branches" data-testid="tab-branches">Branches</TabsTrigger>
          <TabsTrigger value="purities" data-testid="tab-purities">Purities</TabsTrigger>
          <TabsTrigger value="categories" data-testid="tab-categories">Categories</TabsTrigger>
        </TabsList>
        <TabsContent value="rates"><RatesTab /></TabsContent>
        <TabsContent value="branches"><BranchesTab /></TabsContent>
        <TabsContent value="purities"><PuritiesTab /></TabsContent>
        <TabsContent value="categories"><CategoriesTab /></TabsContent>
      </Tabs>
    </div>
  );
}

function RatesTab() {
  const today = new Date().toISOString().slice(0, 10);
  const [rates, setRates] = useState([]);
  const [purities, setPurities] = useState([]);
  const [metal, setMetal] = useState("gold");
  const [purityCode, setPurityCode] = useState("");
  const [price, setPrice] = useState("");

  const load = () =>
    api.get("/daily-rates/latest").then((r) => setRates(r.data));

  useEffect(() => {
    load();
    api.get("/purities").then((r) => setPurities(r.data));
  }, []);

  const submit = async (e) => {
    e.preventDefault();
    try {
      await api.post("/daily-rates", {
        rate_date: today,
        metal, purity_code: purityCode,
        rate_per_gram: parseFloat(price),
      });
      toast.success("Rate updated");
      setPrice("");
      load();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed");
    }
  };

  return (
    <Card className="mt-4" style={{ borderColor: "var(--border)", background: "var(--card)" }}>
      <CardContent className="p-6 grid md:grid-cols-[1fr,320px] gap-6">
        <div>
          <h3 className="font-semibold tracking-tight text-lg mb-3">Latest rates</h3>
          <div className="space-y-2">
            {rates.map((r) => (
              <div key={r.id}
                className="flex items-center justify-between p-3 rounded-md border"
                style={{ borderColor: "var(--border)" }}
                data-testid={`rate-row-${r.purity_code}`}>
                <div>
                  <div className="font-medium">{r.purity_code}</div>
                  <div className="text-xs" style={{ color: "var(--text-muted)" }}>
                    {r.metal} · {r.rate_date}
                  </div>
                </div>
                <div className="font-num text-xl" style={{ color: "var(--gold-text)" }}>
                  ₹{r.rate_per_gram.toFixed(2)}/g
                </div>
              </div>
            ))}
          </div>
        </div>
        <form onSubmit={submit} className="space-y-3">
          <h3 className="font-semibold tracking-tight text-lg">Update rate</h3>
          <div>
            <Label>Metal</Label>
            <Select value={metal} onValueChange={setMetal}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="gold">Gold</SelectItem>
                <SelectItem value="silver">Silver</SelectItem>
                <SelectItem value="platinum">Platinum</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label>Purity</Label>
            <Select value={purityCode} onValueChange={setPurityCode}>
              <SelectTrigger><SelectValue placeholder="Select…" /></SelectTrigger>
              <SelectContent>
                {purities.filter((p) => p.metal === metal).map((p) => (
                  <SelectItem key={p.id} value={p.code}>{p.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label>Rate per gram (INR)</Label>
            <Input type="number" step="0.01" required value={price}
              onChange={(e) => setPrice(e.target.value)}
              data-testid="rate-input" />
          </div>
          <Button type="submit" style={{ background: "var(--primary)", color: "var(--primary-fg)" }}
            className="w-full" data-testid="rate-update-button">
            Save new rate
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}

function BranchesTab() {
  const [branches, setBranches] = useState([]);
  const [form, setForm] = useState({ code: "", name: "", address: "", gstin: "", state_code: "" });
  const load = () => api.get("/branches").then((r) => setBranches(r.data));
  useEffect(() => { load(); }, []);
  const submit = async (e) => {
    e.preventDefault();
    try {
      await api.post("/branches", form);
      toast.success("Branch added");
      setForm({ code: "", name: "", address: "", gstin: "", state_code: "" });
      load();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed");
    }
  };
  return (
    <Card className="mt-4" style={{ borderColor: "var(--border)", background: "var(--card)" }}>
      <CardContent className="p-6 grid md:grid-cols-[1fr,320px] gap-6">
        <div>
          <h3 className="font-semibold tracking-tight text-lg mb-3">Branches</h3>
          <div className="space-y-2">
            {branches.map((b) => (
              <div key={b.id} className="p-3 rounded-md border flex items-start justify-between"
                style={{ borderColor: "var(--border)" }}>
                <div>
                  <div className="font-medium">{b.name}</div>
                  <div className="text-xs font-mono" style={{ color: "var(--text-muted)" }}>
                    {b.code} · {b.gstin || "No GSTIN"}
                  </div>
                  <div className="text-xs mt-1" style={{ color: "var(--text-2)" }}>
                    {b.address}
                  </div>
                </div>
                <Badge variant="outline">{b.state_code || "—"}</Badge>
              </div>
            ))}
          </div>
        </div>
        <form onSubmit={submit} className="space-y-3">
          <h3 className="font-semibold tracking-tight text-lg">Add branch</h3>
          {[
            ["code", "Code *"], ["name", "Name *"], ["address", "Address"],
            ["gstin", "GSTIN"], ["state_code", "State Code"],
          ].map(([k, l]) => (
            <div key={k}>
              <Label>{l}</Label>
              <Input value={form[k]} required={l.includes("*")}
                onChange={(e) => setForm({ ...form, [k]: e.target.value })}
                data-testid={`branch-${k}-input`} />
            </div>
          ))}
          <Button type="submit" style={{ background: "var(--primary)", color: "var(--primary-fg)" }}
            className="w-full" data-testid="branch-submit-button">
            Create branch
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}

function PuritiesTab() {
  const [list, setList] = useState([]);
  useEffect(() => { api.get("/purities").then((r) => setList(r.data)); }, []);
  return (
    <Card className="mt-4" style={{ borderColor: "var(--border)", background: "var(--card)" }}>
      <CardContent className="p-6 space-y-2">
        {list.map((p) => (
          <div key={p.id} className="flex items-center justify-between p-3 rounded-md border"
            style={{ borderColor: "var(--border)" }}>
            <div>
              <div className="font-medium">{p.label}</div>
              <div className="text-xs font-mono" style={{ color: "var(--text-muted)" }}>
                {p.code} · {p.metal}
              </div>
            </div>
            <div className="font-num">{(p.fineness * 100).toFixed(1)}%</div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

function CategoriesTab() {
  const [list, setList] = useState([]);
  useEffect(() => { api.get("/categories").then((r) => setList(r.data)); }, []);
  return (
    <Card className="mt-4" style={{ borderColor: "var(--border)", background: "var(--card)" }}>
      <CardContent className="p-6 space-y-2">
        {list.map((c) => (
          <div key={c.id} className="flex items-center justify-between p-3 rounded-md border"
            style={{ borderColor: "var(--border)" }}>
            <div>
              <div className="font-medium">{c.name}</div>
              <div className="text-xs font-mono" style={{ color: "var(--text-muted)" }}>
                HSN {c.hsn_code || "—"}
              </div>
            </div>
            <Badge variant="outline">{c.gst_rate ? `${c.gst_rate}% GST` : "—"}</Badge>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
