import React, { useEffect, useRef, useState } from "react";
import { api, errMsg } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { CameraScanButton } from "@/components/CameraScanner";
import { OldGoldCard } from "@/components/OldGoldCard";
import { X, FileDown, MessageCircle } from "lucide-react";
import { toast } from "sonner";

const inr = (n) => (Number(n) < 0 ? "-" : "") + "₹" + Math.abs(Number(n || 0)).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const primary = { background: "var(--primary)", color: "var(--primary-fg)" };

async function openPdf(bill) {
  try {
    const r = await api.get(`/bills/${bill.id}/pdf`, { responseType: "blob" });
    const url = URL.createObjectURL(r.data);
    const a = document.createElement("a");
    a.href = url; a.download = `${bill.bill_no}.pdf`; a.click();
    setTimeout(() => URL.revokeObjectURL(url), 2000);
  } catch (_e) {
    toast.error("Could not download the invoice PDF");
  }
}

async function sendWa(bill, after) {
  try {
    const { data } = await api.post(`/whatsapp/invoices/${bill.id}`);
    toast.success(data.status === "mocked" ? "Recorded in outbox (no provider connected)" : `WhatsApp: ${data.status}`);
    after?.();
  } catch (err) { toast.error(errMsg(err, "WhatsApp send failed")); }
}

function Line({ item, line, override, setOverride, remove }) {
  const mt = override?.making_charge_type ?? item.making_charge_type;
  const mv = override?.making_charge_value ?? item.making_charge_value;
  return (
    <div className="p-3 rounded-md border space-y-2" style={{ borderColor: "var(--border)" }} data-testid={`billing-line-${item.tag_id}`}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="font-mono font-semibold">{item.tag_id}</div>
          <div className="text-xs font-num" style={{ color: "var(--text-2)" }}>
            Gross <span data-testid="billing-item-line-gross-weight">{item.gross_wt.toFixed(3)}</span> g ·
            Net <span data-testid="billing-item-line-net-weight">{item.net_wt.toFixed(3)}</span> g
            {line && <> · {line.purity_code} @ {inr(line.rate_per_gram)}/g</>}
          </div>
        </div>
        <div className="text-right">
          <div className="font-num font-semibold">{line ? inr(line.taxable) : "—"}</div>
          {line && <div className="text-xs font-num" style={{ color: "var(--text-muted)" }}>metal {inr(line.metal_value)} + making {inr(line.making_charge)}</div>}
        </div>
        <Button size="icon" variant="ghost" onClick={remove} data-testid={`billing-remove-${item.tag_id}`}><X className="w-4 h-4" /></Button>
      </div>
      <div className="flex items-center gap-2">
        <span className="text-xs w-16" style={{ color: "var(--text-muted)" }}>Making</span>
        <Select value={mt} onValueChange={(v) => setOverride({ making_charge_type: v, making_charge_value: Number(mv) || 0 })}>
          <SelectTrigger className="h-9 w-36"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="per_gram">₹ per gram</SelectItem>
            <SelectItem value="percent">% of metal</SelectItem>
            <SelectItem value="fixed">Fixed ₹</SelectItem>
          </SelectContent>
        </Select>
        <Input type="number" min="0" step="0.01" className="h-9 w-32 font-num" value={mv}
          onChange={(e) => setOverride({ making_charge_type: mt, making_charge_value: e.target.value === "" ? 0 : Number(e.target.value) })}
          data-testid="billing-making-charge-input" />
      </div>
    </div>
  );
}

function Totals({ q }) {
  const row = (l, v, tid, bold) => (
    <div className={`flex justify-between ${bold ? "text-lg font-semibold pt-2 border-t" : ""}`} style={{ borderColor: "var(--border)" }}>
      <span>{l}</span><span className="font-num" data-testid={tid}>{inr(v)}</span>
    </div>
  );
  return (
    <div className="space-y-1 text-sm">
      {row("Taxable value", q.subtotal, "billing-subtotal-val")}
      {q.inter_state ? row("IGST 3%", q.igst, "billing-gst-summary-igst") : (<>
        {row("CGST 1.5%", q.cgst, "billing-gst-summary-cgst")}
        {row("SGST 1.5%", q.sgst, "billing-gst-summary-sgst")}
      </>)}
      {row("Round off", q.round_off, "billing-round-off-val")}
      {row("Invoice total", q.grand_total, "billing-grand-total-val", !q.old_gold_total)}
      {q.old_gold_total > 0 && (<>
        {row("Less old gold", -q.old_gold_total, "billing-old-gold-total-val")}
        {row("Net payable", q.net_payable, "billing-net-payable-val", true)}
      </>)}
    </div>
  );
}

function BillHistory({ bills, reload }) {
  return (
    <Card style={{ borderColor: "var(--border)", background: "var(--card)" }}>
      <CardContent className="p-5 space-y-2">
        <h3 className="font-semibold">Recent bills</h3>
        {bills.length === 0 && <div className="text-sm" style={{ color: "var(--text-muted)" }}>No bills yet.</div>}
        {bills.map((b) => (
          <div key={b.id} className="flex items-center gap-2 text-sm border-t pt-2" style={{ borderColor: "var(--border)" }} data-testid={`bill-row-${b.bill_no}`}>
            <div className="flex-1 min-w-0">
              <div className="font-mono font-semibold">{b.bill_no}</div>
              <div className="text-xs truncate" style={{ color: "var(--text-muted)" }}>{b.customer_name} · {b.lines.map((l) => l.tag_id).join(", ")}</div>
            </div>
            <div className="font-num font-semibold">{inr(b.net_payable ?? b.grand_total)}</div>
            <Button size="icon" variant="ghost" onClick={() => openPdf(b)} data-testid={`bill-pdf-${b.bill_no}`}><FileDown className="w-4 h-4" /></Button>
            {b.customer_phone && <Button size="icon" variant="ghost" onClick={() => sendWa(b, reload)} data-testid={`bill-whatsapp-${b.bill_no}`}><MessageCircle className="w-4 h-4" /></Button>}
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

const EMPTY_CUST = { name: "", phone: "", address: "", gstin: "", state: "" };

export default function Billing() {
  const { branchId, branches } = useAuth();
  const branch = branches.find((b) => b.id === branchId);
  const [code, setCode] = useState("");
  const [cart, setCart] = useState([]);
  const [overrides, setOverrides] = useState({});
  const [oldGold, setOldGold] = useState([]);
  const [cust, setCust] = useState(EMPTY_CUST);
  const [payment, setPayment] = useState("cash");
  const [quote, setQuote] = useState(null);
  const [bills, setBills] = useState([]);
  const [last, setLast] = useState(null);
  const [busy, setBusy] = useState(false);
  const inputRef = useRef(null);
  const cartRef = useRef(cart);
  cartRef.current = cart;

  const loadBills = () => branchId && api.get(`/bills?branch_id=${branchId}`).then((r) => setBills(r.data)).catch(() => {});
  useEffect(() => { loadBills(); setCart([]); setOverrides({}); }, [branchId]); // eslint-disable-line

  const payload = () => ({
    branch_id: branchId, item_ids: cart.map((i) => i.id), customer_name: cust.name,
    customer_phone: cust.phone || null, customer_address: cust.address || null,
    customer_gstin: cust.gstin || null, customer_state_code: cust.state || branch?.state_code || null,
    payment_mode: payment, making_overrides: overrides, old_gold: oldGold,
  });

  useEffect(() => {
    if (!cart.length) { setQuote(null); return; }
    const t = setTimeout(() => api.post("/bills/quote", payload()).then((r) => setQuote(r.data))
      .catch((err) => toast.error(errMsg(err, "Could not price items"))), 250);
    return () => clearTimeout(t);
  }, [cart, overrides, cust.state, oldGold]); // eslint-disable-line

  const addCode = async (raw) => {
    const c = raw.trim();
    if (!c) return;
    try {
      const { data } = await api.get(`/scan/lookup?code=${encodeURIComponent(c)}`);
      if (!data.found) return toast.error(data.warnings?.[0] || `No item for ${c}`);
      if (data.item.status !== "in_stock") return toast.error(`${data.item.tag_id} is ${data.item.status.replace("_", " ")}`);
      if (cartRef.current.some((i) => i.id === data.item.id)) return toast.info(`${data.item.tag_id} already added`);
      setCart((x) => [...x, data.item]);
      toast.success(`${data.item.tag_id} added`);
    } catch (err) { toast.error(errMsg(err, "Lookup failed")); }
  };

  const generate = async () => {
    setBusy(true);
    try {
      const { data } = await api.post("/bills", payload());
      toast.success(`Bill ${data.bill_no} generated · items marked sold`);
      setLast(data); setCart([]); setOverrides({}); setOldGold([]); setCust(EMPTY_CUST);
      loadBills();
    } catch (err) { toast.error(errMsg(err, "Billing failed")); } finally { setBusy(false); }
  };

  const setC = (k) => (e) => setCust({ ...cust, [k]: e.target.value });

  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs uppercase tracking-[0.25em]" style={{ color: "var(--text-muted)" }}>Counter</p>
        <h1 className="text-3xl font-semibold tracking-tight mt-1">Billing</h1>
        <p className="text-sm mt-2" style={{ color: "var(--text-2)" }}>Scan items, check the GST total and generate the bill — sold items leave stock automatically.</p>
      </div>
      <div className="grid xl:grid-cols-[1fr,400px] gap-6">
        <div className="space-y-6">
          <Card style={{ borderColor: "var(--border)", background: "var(--card)" }}>
            <CardContent className="p-6 space-y-3">
              <form onSubmit={(e) => { e.preventDefault(); addCode(code); setCode(""); }} className="flex gap-2">
                <Input ref={inputRef} autoFocus value={code} onChange={(e) => setCode(e.target.value)}
                  placeholder="Scan tag / barcode / HUID…" className="h-12 text-base font-mono scan-input-active"
                  data-testid="billing-counter-scan-box" />
                <CameraScanButton onDetect={addCode} continuous testId="billing-camera-scan-button" />
              </form>
              {cart.length === 0 && <div className="text-sm py-6 text-center" style={{ color: "var(--text-muted)" }}>No items scanned yet.</div>}
              {cart.map((i) => (
                <Line key={i.id} item={i} line={quote?.lines.find((l) => l.item_id === i.id)} override={overrides[i.id]}
                  setOverride={(o) => setOverrides((x) => ({ ...x, [i.id]: o }))}
                  remove={() => { setCart((x) => x.filter((y) => y.id !== i.id)); setOverrides(({ [i.id]: _, ...rest }) => rest); }} />
              ))}
            </CardContent>
          </Card>
          <Card style={{ borderColor: "var(--border)", background: "var(--card)" }}>
            <CardContent className="p-6 grid sm:grid-cols-2 gap-3">
              <div><Label>Customer name *</Label><Input className="h-11" value={cust.name} onChange={setC("name")} data-testid="billing-customer-name-input" /></div>
              <div><Label>WhatsApp / phone</Label><Input className="h-11" value={cust.phone} onChange={setC("phone")} placeholder="10-digit mobile" data-testid="billing-customer-phone-input" /></div>
              <div className="sm:col-span-2"><Label>Address</Label><Input className="h-11" value={cust.address} onChange={setC("address")} data-testid="billing-customer-address-input" /></div>
              <div><Label>Customer GSTIN</Label><Input className="h-11 font-mono" value={cust.gstin} onChange={setC("gstin")} data-testid="billing-customer-gstin-input" /></div>
              <div><Label>Customer state code</Label><Input className="h-11 font-mono" value={cust.state} onChange={setC("state")} placeholder={`${branch?.state_code || ""} (same state)`} data-testid="billing-customer-state-input" /></div>
              <div><Label>Payment mode</Label>
                <Select value={payment} onValueChange={setPayment}>
                  <SelectTrigger className="h-11" data-testid="billing-payment-mode-select"><SelectValue /></SelectTrigger>
                  <SelectContent>{["cash", "upi", "card", "bank", "mixed"].map((p) => <SelectItem key={p} value={p}>{p.toUpperCase()}</SelectItem>)}</SelectContent>
                </Select></div>
            </CardContent>
          </Card>
          <OldGoldCard entries={oldGold} setEntries={setOldGold} priced={quote?.old_gold} />
        </div>
        <div className="space-y-6">
          <Card style={{ borderColor: "var(--border)", background: "var(--card)" }}>
            <CardContent className="p-6 space-y-4">
              <h3 className="font-semibold">Bill summary</h3>
              {quote ? <Totals q={quote} /> : <div className="text-sm" style={{ color: "var(--text-muted)" }}>Scan items to see totals.</div>}
              <Button onClick={generate} disabled={busy || !cart.length || !cust.name.trim()} className="w-full h-12 text-base" style={primary} data-testid="generate-bill-button">
                {busy ? "Generating…" : `Generate bill (${cart.length})`}
              </Button>
              {last && (
                <div className="p-4 rounded-md border space-y-3" style={{ borderColor: "var(--success)" }} data-testid="last-bill-summary">
                  <div className="font-mono font-semibold">{last.bill_no} · {last.customer_name} · {inr(last.net_payable ?? last.grand_total)}</div>
                  {last.old_gold_total > 0 && <div className="text-xs font-num" style={{ color: "var(--text-2)" }}>Invoice {inr(last.grand_total)} − old gold {inr(last.old_gold_total)}</div>}
                  {last.whatsapp_status && <div className="text-xs" style={{ color: "var(--text-2)" }}>WhatsApp: {last.whatsapp_status === "mocked" ? "recorded (no provider connected)" : last.whatsapp_status.replace("_", " ")}</div>}
                  <div className="flex gap-2">
                    <Button variant="outline" className="gap-2 flex-1" onClick={() => openPdf(last)} data-testid="generate-gst-pdf-invoice-button"><FileDown className="w-4 h-4" /> PDF invoice</Button>
                    {last.customer_phone && <Button variant="outline" className="gap-2 flex-1" onClick={() => sendWa(last)} data-testid="send-invoice-whatsapp-button"><MessageCircle className="w-4 h-4" /> WhatsApp</Button>}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
          <BillHistory bills={bills} reload={loadBills} />
        </div>
      </div>
    </div>
  );
}
