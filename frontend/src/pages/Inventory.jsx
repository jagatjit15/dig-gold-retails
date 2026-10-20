import React, { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter,
} from "@/components/ui/dialog";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Plus, Search } from "lucide-react";
import { toast } from "sonner";

const STATUS_COLORS = {
  in_stock: "#1B5E20",
  sold: "#6E6259",
  transferred: "#1565C0",
  in_transit: "#E65100",
  with_karigar: "#7A1C1C",
  scrapped: "#C62828",
};

export default function Inventory() {
  const { branchId } = useAuth();
  const [items, setItems] = useState([]);
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [cats, setCats] = useState([]);
  const [purities, setPurities] = useState([]);
  const [open, setOpen] = useState(false);

  const load = () => {
    const params = new URLSearchParams();
    if (branchId) params.set("branch_id", branchId);
    if (statusFilter !== "all") params.set("status", statusFilter);
    if (query) params.set("q", query);
    api.get(`/items?${params.toString()}`).then((r) => setItems(r.data))
      .catch(() => {});
  };

  useEffect(() => {
    api.get("/categories").then((r) => setCats(r.data)).catch(() => {});
    api.get("/purities").then((r) => setPurities(r.data)).catch(() => {});
  }, []);

  useEffect(() => { if (branchId) load(); }, [branchId, statusFilter]);

  const stats = useMemo(() => {
    const inStock = items.filter((i) => i.status === "in_stock");
    const wt = inStock.reduce((s, i) => s + (i.net_wt || 0), 0);
    return { count: inStock.length, weight: wt };
  }, [items]);

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between">
        <div>
          <p className="text-xs uppercase tracking-[0.25em]" style={{ color: "var(--text-muted)" }}>
            Tagged Inventory
          </p>
          <h1 className="font-serif-brand text-4xl mt-1">Items & Stock Register</h1>
        </div>
        <AddItemDialog
          open={open} setOpen={setOpen}
          cats={cats} purities={purities} branchId={branchId} onDone={load}
        />
      </div>

      <div className="flex flex-wrap gap-3 items-center">
        <div className="relative">
          <Search className="w-4 h-4 absolute left-3 top-2.5" style={{ color: "var(--text-muted)" }} />
          <Input
            placeholder="Search tag, barcode, HUID, RFID…"
            className="pl-9 w-80"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && load()}
            data-testid="inventory-search-input"
          />
        </div>
        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="w-44" data-testid="inventory-status-filter">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All statuses</SelectItem>
            <SelectItem value="in_stock">In stock</SelectItem>
            <SelectItem value="sold">Sold</SelectItem>
            <SelectItem value="transferred">Transferred</SelectItem>
            <SelectItem value="with_karigar">With karigar</SelectItem>
            <SelectItem value="scrapped">Scrapped</SelectItem>
          </SelectContent>
        </Select>
        <Button variant="outline" onClick={load} data-testid="inventory-refresh-button">
          Refresh
        </Button>
        <div className="ml-auto text-sm" style={{ color: "var(--text-2)" }}>
          <span className="font-num font-semibold">{stats.count}</span> in stock ·{" "}
          <span className="font-num font-semibold">{stats.weight.toFixed(3)} g</span> net
        </div>
      </div>

      <Card style={{ borderColor: "var(--border)", background: "var(--card)" }}>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-sm" data-testid="inventory-table">
              <thead
                className="text-left text-[11px] uppercase tracking-widest sticky top-0 backdrop-blur"
                style={{
                  color: "var(--text-muted)",
                  background: "color-mix(in oklab, var(--surface) 85%, transparent)",
                }}>
                <tr>
                  <Th>Tag / HUID</Th>
                  <Th>Barcode</Th>
                  <Th>Category · Purity</Th>
                  <Th num>Gross (g)</Th>
                  <Th num>Stone (g)</Th>
                  <Th num>Net (g)</Th>
                  <Th>Status</Th>
                </tr>
              </thead>
              <tbody>
                {items.length === 0 && (
                  <tr>
                    <td colSpan={7} className="text-center py-16"
                      style={{ color: "var(--text-muted)" }}>
                      No items yet — add your first tagged item.
                    </td>
                  </tr>
                )}
                {items.map((i) => {
                  const cat = cats.find((c) => c.id === i.category_id);
                  const pur = purities.find((p) => p.id === i.purity_id);
                  return (
                    <tr key={i.id} className="border-t"
                      style={{ borderColor: "var(--border)" }}
                      data-testid={`inventory-row-${i.tag_id}`}>
                      <Td>
                        <div className="font-medium">{i.tag_id}</div>
                        <div className="text-xs font-mono" style={{ color: "var(--text-muted)" }}>
                          {i.huid || "—"}
                        </div>
                      </Td>
                      <Td mono>{i.barcode || "—"}</Td>
                      <Td>
                        {cat?.name || "—"} · {pur?.code || "—"}
                      </Td>
                      <Td num>{i.gross_wt?.toFixed(3)}</Td>
                      <Td num>{i.stone_wt?.toFixed(3)}</Td>
                      <Td num bold>{i.net_wt?.toFixed(3)}</Td>
                      <Td>
                        <Badge
                          variant="outline"
                          className="font-mono text-[10px] uppercase"
                          style={{
                            borderColor: STATUS_COLORS[i.status],
                            color: STATUS_COLORS[i.status],
                          }}
                        >
                          {i.status.replace("_", " ")}
                        </Badge>
                      </Td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function Th({ children, num }) {
  return (
    <th className={`px-4 py-3 ${num ? "text-right" : "text-left"}`}>{children}</th>
  );
}
function Td({ children, num, mono, bold }) {
  return (
    <td
      className={`px-4 py-3 align-middle ${num ? "text-right font-num" : ""} ${
        mono ? "font-mono text-xs" : ""
      } ${bold ? "font-semibold" : ""}`}
    >
      {children}
    </td>
  );
}

function AddItemDialog({ open, setOpen, cats, purities, branchId, onDone }) {
  const [form, setForm] = useState({
    tag_id: "", barcode: "", rfid_epc: "", huid: "",
    category_id: "", purity_id: "",
    gross_wt: "", stone_wt: "0",
    making_charge_type: "per_gram", making_charge_value: "",
    description: "",
  });
  const [busy, setBusy] = useState(false);
  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));
  const submit = async (e) => {
    e.preventDefault();
    if (!branchId) {
      toast.error("Select a branch first"); return;
    }
    setBusy(true);
    try {
      await api.post("/items", {
        ...form,
        gross_wt: parseFloat(form.gross_wt),
        stone_wt: parseFloat(form.stone_wt || "0"),
        making_charge_value: parseFloat(form.making_charge_value || "0"),
        branch_id: branchId,
        rfid_epc: form.rfid_epc || null,
        huid: form.huid || null,
        barcode: form.barcode || null,
      });
      toast.success(`Item ${form.tag_id} added`);
      setOpen(false);
      setForm({
        tag_id: "", barcode: "", rfid_epc: "", huid: "",
        category_id: "", purity_id: "",
        gross_wt: "", stone_wt: "0",
        making_charge_type: "per_gram", making_charge_value: "",
        description: "",
      });
      onDone();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Could not add item");
    } finally { setBusy(false); }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button
          data-testid="add-tagged-item-button"
          className="gap-2"
          style={{ background: "var(--gold)", color: "#fff" }}
        >
          <Plus className="w-4 h-4" /> New Tagged Item
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-xl">
        <DialogHeader>
          <DialogTitle className="font-serif-brand text-2xl">New Tagged Item</DialogTitle>
        </DialogHeader>
        <form onSubmit={submit} className="grid grid-cols-2 gap-4">
          <Field label="Tag ID *">
            <Input required value={form.tag_id} onChange={(e) => set("tag_id", e.target.value)}
              data-testid="item-tag-id-input" />
          </Field>
          <Field label="Barcode">
            <Input value={form.barcode} onChange={(e) => set("barcode", e.target.value)}
              data-testid="item-barcode-input" />
          </Field>
          <Field label="HUID">
            <Input value={form.huid} onChange={(e) => set("huid", e.target.value)} />
          </Field>
          <Field label="RFID EPC">
            <Input value={form.rfid_epc} onChange={(e) => set("rfid_epc", e.target.value)} />
          </Field>
          <Field label="Category *">
            <Select value={form.category_id} onValueChange={(v) => set("category_id", v)}>
              <SelectTrigger data-testid="item-category-select"><SelectValue placeholder="Select…" /></SelectTrigger>
              <SelectContent>
                {cats.map((c) => <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>)}
              </SelectContent>
            </Select>
          </Field>
          <Field label="Purity *">
            <Select value={form.purity_id} onValueChange={(v) => set("purity_id", v)}>
              <SelectTrigger data-testid="item-purity-select"><SelectValue placeholder="Select…" /></SelectTrigger>
              <SelectContent>
                {purities.map((p) => <SelectItem key={p.id} value={p.id}>{p.label}</SelectItem>)}
              </SelectContent>
            </Select>
          </Field>
          <Field label="Gross wt (g) *">
            <Input type="number" step="0.001" required value={form.gross_wt}
              onChange={(e) => set("gross_wt", e.target.value)}
              data-testid="item-gross-wt-input" />
          </Field>
          <Field label="Stone wt (g)">
            <Input type="number" step="0.001" value={form.stone_wt}
              onChange={(e) => set("stone_wt", e.target.value)} />
          </Field>
          <Field label="Making charge type">
            <Select value={form.making_charge_type}
              onValueChange={(v) => set("making_charge_type", v)}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="per_gram">Per gram</SelectItem>
                <SelectItem value="percent">Percent</SelectItem>
                <SelectItem value="fixed">Fixed</SelectItem>
              </SelectContent>
            </Select>
          </Field>
          <Field label="Making charge value">
            <Input type="number" step="0.01" value={form.making_charge_value}
              onChange={(e) => set("making_charge_value", e.target.value)} />
          </Field>
          <div className="col-span-2">
            <Field label="Description">
              <Input value={form.description} onChange={(e) => set("description", e.target.value)} />
            </Field>
          </div>
          <DialogFooter className="col-span-2 mt-2">
            <Button type="button" variant="outline" onClick={() => setOpen(false)}>Cancel</Button>
            <Button type="submit" disabled={busy}
              style={{ background: "var(--gold)", color: "#fff" }}
              data-testid="item-submit-button">
              {busy ? "Saving…" : "Add Item"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function Field({ label, children }) {
  return (
    <div className="space-y-1.5">
      <Label className="text-xs uppercase tracking-widest"
        style={{ color: "var(--text-muted)" }}>{label}</Label>
      {children}
    </div>
  );
}
