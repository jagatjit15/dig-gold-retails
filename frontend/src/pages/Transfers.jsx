import React, { useEffect, useState } from "react";
import { api, errMsg } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { CameraScanButton } from "@/components/CameraScanner";
import { ArrowRight, CheckCircle2, Circle, Truck, AlertTriangle, X, PackageCheck, FilePlus2 } from "lucide-react";
import { toast } from "sonner";

const primary = { background: "var(--brand)", color: "var(--brand-fg)" };
const STATUS = {
  draft: { c: "var(--text-2)", i: FilePlus2, l: "Draft" },
  in_transit: { c: "var(--info)", i: Truck, l: "In transit" },
  received: { c: "var(--success)", i: PackageCheck, l: "Received" },
  received_with_variance: { c: "var(--warning)", i: AlertTriangle, l: "Received · items missing" },
  cancelled: { c: "var(--danger)", i: X, l: "Cancelled" },
};

function StatusBadge({ s }) {
  const m = STATUS[s] || STATUS.draft;
  return <Badge variant="outline" className="gap-1 text-[10px] uppercase" style={{ borderColor: m.c, color: m.c }} data-testid="transfer-status-badge"><m.i className="w-3 h-3" />{m.l}</Badge>;
}

function ScanBar({ onCode, placeholder, testId }) {
  const [code, setCode] = useState("");
  return (
    <form onSubmit={(e) => { e.preventDefault(); onCode(code); setCode(""); }} className="flex gap-2">
      <Input autoFocus value={code} onChange={(e) => setCode(e.target.value)} placeholder={placeholder}
        className="h-12 font-mono scan-input-active" data-testid={testId} />
      <CameraScanButton onDetect={onCode} continuous testId={`${testId}-camera`} />
    </form>
  );
}

function Detail({ t, branchId, bname, onChange }) {
  const outgoing = t.from_branch_id === branchId;
  const incoming = t.to_branch_id === branchId;
  const act = async (fn, ok) => {
    try { const { data } = await fn(); onChange(data); if (ok) toast.success(ok); }
    catch (err) { toast.error(errMsg(err)); }
  };
  const scan = (path) => async (raw) => {
    if (!raw.trim()) return;
    try { onChange((await api.post(`/transfers/${t.id}/${path}`, { code: raw.trim() })).data); }
    catch (err) {
      toast.error(errMsg(err));
      api.get(`/transfers/${t.id}`).then((r) => onChange(r.data)).catch(() => {});
    }
  };
  const awaiting = ["in_transit", "received_with_variance"].includes(t.status);
  const got = t.items.filter((i) => i.received).length;
  const weight = t.items.reduce((s, i) => s + i.net_wt, 0);

  return (
    <Card style={{ borderColor: "var(--line)", background: "var(--panel)" }} data-testid="transfer-detail">
      <CardContent className="p-6 space-y-4">
        <div className="flex flex-wrap items-center gap-3">
          <span className="font-mono font-semibold text-lg">{t.transfer_no}</span>
          <StatusBadge s={t.status} />
          <span className="text-sm flex items-center gap-2" style={{ color: "var(--text-2)" }}>{bname(t.from_branch_id)} <ArrowRight className="w-4 h-4" /> {bname(t.to_branch_id)}</span>
          <span className="ml-auto text-sm font-num">{t.items.length} items · {weight.toFixed(3)} g</span>
        </div>
        {t.status === "draft" && outgoing && <ScanBar onCode={scan("scan-out")} placeholder="Scan out items to send…" testId="transfer-scan-out-input" />}
        {awaiting && incoming && (<>
          {t.status === "received_with_variance" && <p className="text-sm" style={{ color: "var(--warning)" }}>Found a missing item later? Scan it in and receive again.</p>}
          <ScanBar onCode={scan("scan-in")} placeholder="Scan in items as they arrive…" testId="transfer-scan-in-input" />
          <div className="text-sm font-num" data-testid="transfer-received-count">{got} of {t.items.length} scanned in</div>
        </>)}
        {t.status === "in_transit" && !incoming && <p className="text-sm" style={{ color: "var(--text-2)" }}>Waiting for {bname(t.to_branch_id)} to scan the items in.</p>}
        <div className="space-y-1">
          {t.items.length === 0 && <div className="text-sm py-4 text-center" style={{ color: "var(--text-muted)" }}>No items yet.</div>}
          {t.items.map((i) => {
            const missing = t.missing_item_ids.includes(i.item_id) && !i.received;
            return (
              <div key={i.item_id} className="flex items-center gap-3 p-2 rounded-md border text-sm" style={{ borderColor: missing ? "var(--danger)" : "var(--line)" }} data-testid={`transfer-item-${i.tag_id}`}>
                {t.status !== "draft" && (i.received ? <CheckCircle2 className="w-4 h-4" style={{ color: "var(--success)" }} /> : missing ? <AlertTriangle className="w-4 h-4" style={{ color: "var(--danger)" }} /> : <Circle className="w-4 h-4" style={{ color: "var(--text-muted)" }} />)}
                <span className="font-mono flex-1">{i.tag_id}</span>
                {missing && <span className="text-xs font-medium" style={{ color: "var(--danger)" }}>Missing</span>}
                <span className="font-num">{i.net_wt.toFixed(3)} g</span>
                {t.status === "draft" && outgoing && <Button size="icon" variant="ghost" onClick={() => act(() => api.delete(`/transfers/${t.id}/items/${i.item_id}`))} data-testid={`transfer-remove-${i.tag_id}`}><X className="w-4 h-4" /></Button>}
              </div>
            );
          })}
        </div>
        {t.unexpected_codes.length > 0 && (
          <div className="text-sm flex items-start gap-2" style={{ color: "var(--warning)" }} data-testid="transfer-unexpected">
            <AlertTriangle className="w-4 h-4 mt-0.5" /> Scanned but not on this transfer: <span className="font-mono">{t.unexpected_codes.join(", ")}</span>
          </div>
        )}
        <div className="flex gap-2">
          {t.status === "draft" && outgoing && (<>
            <Button className="h-11" style={primary} disabled={!t.items.length} onClick={() => act(() => api.post(`/transfers/${t.id}/dispatch`), "Dispatched — items are now in transit")} data-testid="transfer-dispatch-button">Dispatch {t.items.length} items</Button>
            <Button variant="outline" className="h-11" onClick={() => act(() => api.post(`/transfers/${t.id}/cancel`), "Transfer cancelled")} data-testid="transfer-cancel-button">Cancel</Button>
          </>)}
          {awaiting && incoming && (
            <Button className="h-11" style={primary} disabled={!got} data-testid="transfer-receive-button"
              onClick={() => (got === t.items.length || window.confirm(`${t.items.length - got} item(s) not scanned in will be flagged as missing. Continue?`)) &&
                act(() => api.post(`/transfers/${t.id}/receive`), "Stock received")}>
              Receive {got} items
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

export default function Transfers() {
  const { branchId, branches, user } = useAuth();
  const [list, setList] = useState([]);
  const [sel, setSel] = useState(null);
  const [allBranches, setAllBranches] = useState([]);
  const [dest, setDest] = useState("");
  const canManage = ["admin", "manager"].includes(user?.role);
  const bname = (id) => (allBranches.find((b) => b.id === id) || branches.find((b) => b.id === id))?.name || "Other branch";

  const load = () => branchId && api.get(`/transfers?branch_id=${branchId}`).then((r) => setList(r.data)).catch(() => {});
  useEffect(() => { load(); setSel(null); }, [branchId]); // eslint-disable-line
  useEffect(() => { api.get("/transfers/branches").then((r) => setAllBranches(r.data)).catch(() => setAllBranches(branches)); }, [branches]);

  const create = async () => {
    try {
      const { data } = await api.post("/transfers", { from_branch_id: branchId, to_branch_id: dest });
      toast.success(`${data.transfer_no} created — scan items to send`);
      setSel(data); setDest(""); load();
    } catch (err) { toast.error(errMsg(err)); }
  };
  const onChange = (t) => { setSel(t); load(); };

  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs uppercase tracking-[0.25em]" style={{ color: "var(--text-muted)" }}>Stock movement</p>
        <h1 className="text-3xl font-semibold tracking-tight mt-1">Branch transfers</h1>
        <p className="text-sm mt-2" style={{ color: "var(--text-2)" }}>Scan items out, dispatch, then the receiving branch scans them in. Anything not scanned in is flagged as missing.</p>
      </div>
      {canManage && (
        <Card style={{ borderColor: "var(--line)", background: "var(--panel)" }}>
          <CardContent className="p-5 flex flex-wrap items-center gap-3">
            <span className="text-sm font-medium">Send stock from {bname(branchId)} to</span>
            <Select value={dest} onValueChange={setDest}>
              <SelectTrigger className="w-64 h-11" data-testid="transfer-destination-select"><SelectValue placeholder="Choose branch" /></SelectTrigger>
              <SelectContent>{allBranches.filter((b) => b.id !== branchId).map((b) => <SelectItem key={b.id} value={b.id}>{b.name}</SelectItem>)}</SelectContent>
            </Select>
            <Button className="h-11" style={primary} disabled={!dest} onClick={create} data-testid="transfer-create-button">New transfer</Button>
          </CardContent>
        </Card>
      )}
      <div className="grid xl:grid-cols-[380px,1fr] gap-6 items-start">
        <Card style={{ borderColor: "var(--line)", background: "var(--panel)" }}>
          <CardContent className="p-3 space-y-1">
            {list.length === 0 && <div className="text-sm p-6 text-center" style={{ color: "var(--text-muted)" }}>No transfers yet.</div>}
            {list.map((t) => (
              <button key={t.id} onClick={() => setSel(t)} className="w-full text-left p-3 rounded-md border transition-colors"
                style={{ borderColor: sel?.id === t.id ? "var(--brand)" : "var(--line)" }} data-testid={`transfer-row-${t.transfer_no}`}>
                <div className="flex items-center justify-between gap-2">
                  <span className="font-mono font-semibold text-sm">{t.transfer_no}</span><StatusBadge s={t.status} />
                </div>
                <div className="text-xs mt-1" style={{ color: "var(--text-2)" }}>
                  {t.from_branch_id === branchId ? `Outgoing → ${bname(t.to_branch_id)}` : `Incoming ← ${bname(t.from_branch_id)}`} · {t.items.length} items
                </div>
              </button>
            ))}
          </CardContent>
        </Card>
        {sel ? <Detail t={sel} branchId={branchId} bname={bname} onChange={onChange} /> :
          <div className="text-sm p-10 text-center" style={{ color: "var(--text-muted)" }}>Select a transfer to see its items.</div>}
      </div>
    </div>
  );
}
