import React, { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Plus, X } from "lucide-react";

const inr = (n) => (Number(n) < 0 ? "-" : "") + "₹" + Math.abs(Number(n || 0)).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const EMPTY = { description: "Old gold", metal: "gold", fineness: "0.916", gross_wt: "", stone_wt: "0", deduction_pct: "2" };

export function OldGoldCard({ entries, setEntries, priced }) {
  const [purities, setPurities] = useState([]);
  const [f, setF] = useState(EMPTY);
  useEffect(() => { api.get("/purities").then((r) => setPurities(r.data)).catch(() => {}); }, []);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });

  const add = (e) => {
    e.preventDefault();
    setEntries([...entries, {
      description: f.description || "Old gold", metal: f.metal, fineness: Number(f.fineness),
      gross_wt: Number(f.gross_wt), stone_wt: Number(f.stone_wt || 0), deduction_pct: Number(f.deduction_pct || 0),
    }]);
    setF({ ...EMPTY, metal: f.metal, fineness: f.fineness, deduction_pct: f.deduction_pct });
  };

  return (
    <Card style={{ borderColor: "var(--line)", background: "var(--panel)" }} data-testid="old-gold-voucher-entry-form">
      <CardContent className="p-6 space-y-3">
        <div>
          <h3 className="font-semibold">Old gold exchange</h3>
          <p className="text-xs" style={{ color: "var(--text-muted)" }}>Valued at net weight × tested purity × today's fine rate, less deduction. Deducted after GST.</p>
        </div>
        <form onSubmit={add} className="grid grid-cols-2 md:grid-cols-6 gap-2 items-end">
          <div className="col-span-2"><label className="text-xs">Description</label>
            <Input className="h-11" value={f.description} onChange={set("description")} data-testid="old-gold-description-input" /></div>
          <div className="col-span-2"><label className="text-xs">Purity (tested)</label>
            <Select value={`${f.metal}|${f.fineness}`} onValueChange={(v) => { const [m, fi] = v.split("|"); setF({ ...f, metal: m, fineness: fi }); }}>
              <SelectTrigger className="h-11" data-testid="old-gold-purity-select"><SelectValue /></SelectTrigger>
              <SelectContent>
                {purities.map((p) => <SelectItem key={p.id} value={`${p.metal}|${p.fineness}`}>{p.label}</SelectItem>)}
                {!purities.some((p) => `${p.metal}|${p.fineness}` === `${f.metal}|${f.fineness}`) &&
                  <SelectItem value={`${f.metal}|${f.fineness}`}>Custom {f.fineness}</SelectItem>}
              </SelectContent>
            </Select></div>
          <div><label className="text-xs">Fineness</label>
            <Input className="h-11 font-num" type="number" step="0.001" min="0.001" max="1" required value={f.fineness} onChange={set("fineness")} data-testid="old-gold-fineness-input" /></div>
          <div><label className="text-xs">Deduction %</label>
            <Input className="h-11 font-num" type="number" step="0.1" min="0" max="99" value={f.deduction_pct} onChange={set("deduction_pct")} data-testid="old-gold-deduction-input" /></div>
          <div><label className="text-xs">Gross g</label>
            <Input className="h-11 font-num" type="number" step="0.001" min="0.001" required value={f.gross_wt} onChange={set("gross_wt")} data-testid="old-gold-gross-input" /></div>
          <div><label className="text-xs">Stone g</label>
            <Input className="h-11 font-num" type="number" step="0.001" min="0" value={f.stone_wt} onChange={set("stone_wt")} data-testid="old-gold-stone-input" /></div>
          <Button type="submit" variant="outline" className="h-11 gap-1 col-span-2 md:col-span-1" data-testid="old-gold-add-button"><Plus className="w-4 h-4" /> Add</Button>
        </form>
        {entries.map((e, i) => {
          const p = priced?.[i];
          return (
            <div key={i} className="flex items-center gap-3 p-3 rounded-md border text-sm" style={{ borderColor: "var(--line)" }} data-testid={`old-gold-line-${i}`}>
              <div className="flex-1">
                <div className="font-medium">{e.description}</div>
                <div className="text-xs font-num" style={{ color: "var(--text-2)" }}>
                  {e.metal} {e.fineness} · gross {e.gross_wt.toFixed(3)} g · net {(p?.net_wt ?? e.gross_wt - e.stone_wt).toFixed(3)} g
                  {p && <> · fine {p.fine_wt.toFixed(3)} g @ {inr(p.rate_per_fine_gram)}</>} · less {e.deduction_pct}%
                </div>
              </div>
              <div className="font-num font-semibold">{p ? inr(-p.value) : "—"}</div>
              <Button size="icon" variant="ghost" onClick={() => setEntries(entries.filter((_, j) => j !== i))} data-testid={`old-gold-remove-${i}`}><X className="w-4 h-4" /></Button>
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}
