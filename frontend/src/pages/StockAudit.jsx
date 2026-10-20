import React, { useEffect, useRef, useState } from "react";
import { api, errMsg } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { CameraScanButton } from "@/components/CameraScanner";
import { CheckCircle2, AlertTriangle } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";

export default function StockAudit() {
  const { branchId } = useAuth();
  const [session, setSession] = useState(null);
  const [variance, setVariance] = useState(null);
  const [code, setCode] = useState("");
  const [scans, setScans] = useState([]);
  const inputRef = useRef(null);

  const start = async () => {
    if (!branchId) { toast.error("Choose a branch first"); return; }
    const { data } = await api.post(`/audit/sessions?branch_id=${branchId}`);
    setSession(data);
    setScans([]);
    setVariance(null);
    setTimeout(() => inputRef.current?.focus(), 100);
  };

  const addScan = async (e) => {
    e.preventDefault();
    await submitCode(code);
    setCode("");
  };

  const submitCode = async (raw) => {
    if (!session || !raw.trim()) return;
    try {
      const { data } = await api.post(
        `/audit/sessions/${session.id}/scan`,
        { code: raw.trim() }
      );
      setScans((s) => [{ ...data }, ...s].slice(0, 200));
      refreshVariance();
    } catch (err) {
      toast.error(errMsg(err, "Scan failed"));
    }
  };

  const refreshVariance = async () => {
    if (!session) return;
    const { data } = await api.get(`/audit/sessions/${session.id}/variance`);
    setVariance(data);
  };

  const close = async () => {
    if (!session) return;
    await api.post(`/audit/sessions/${session.id}/close`);
    toast.success("Audit session closed");
    setSession(null);
    setScans([]);
    setVariance(null);
  };

  useEffect(() => { if (session) refreshVariance(); }, [session?.id]);

  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs uppercase tracking-[0.25em]" style={{ color: "var(--text-muted)" }}>
          Audit
        </p>
        <h1 className="text-3xl font-semibold tracking-tight mt-1">Stock Audit & Variance</h1>
      </div>

      {!session && (
        <Card style={{ borderColor: "var(--line)", background: "var(--panel)" }}>
          <CardContent className="p-6 flex items-center justify-between">
            <div>
              <h2 className="font-semibold tracking-tight text-xl">Start a new audit session</h2>
              <p className="text-sm mt-1" style={{ color: "var(--text-2)" }}>
                Scan every item in the counter/tray/safe — unscanned stock will
                appear in the variance report for manager approval.
              </p>
            </div>
            <Button onClick={start} style={{ background: "var(--brand)", color: "var(--brand-fg)" }}
              data-testid="start-audit-button">
              Start audit
            </Button>
          </CardContent>
        </Card>
      )}

      {session && (
        <>
          <Card style={{ borderColor: "var(--line)", background: "var(--panel)" }}>
            <CardContent className="p-6 space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <div className="text-xs uppercase tracking-widest"
                    style={{ color: "var(--text-muted)" }}>
                    Session · {session.id.slice(0, 8)}
                  </div>
                  <div className="font-semibold tracking-tight text-lg">Audit in progress</div>
                </div>
                <Button variant="outline" onClick={close} data-testid="close-audit-button">
                  Close & archive
                </Button>
              </div>
              <form onSubmit={addScan} className="flex gap-2">
                <Input
                  ref={inputRef}
                  autoFocus
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                  placeholder="Scan item code…"
                  className="scan-input-active font-mono h-12"
                  data-testid="audit-scan-mode-toggle"
                />
                <CameraScanButton onDetect={submitCode} continuous testId="audit-camera-scan-button" />
                <Button type="submit" className="h-12"
                  style={{ background: "var(--brand)", color: "var(--brand-fg)" }}>Add scan</Button>
              </form>
            </CardContent>
          </Card>

          {variance && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <VarCard label="Expected" value={variance.expected_count} />
              <VarCard label="Scanned & found" value={variance.scanned_found}
                color="var(--success)" testId="audit-variance-found-count" />
              <VarCard label="Missing" value={variance.missing.length}
                color="var(--danger)" testId="audit-variance-missing-count" />
              <VarCard label="Unknown / cross-branch"
                value={variance.unknown_codes.length +
                       variance.wrong_branch_items.length +
                       variance.wrong_status_items.length}
                color="var(--warning)" />
            </div>
          )}

          <div className="grid md:grid-cols-2 gap-6">
            <Card style={{ borderColor: "var(--line)", background: "var(--panel)" }}>
              <CardContent className="p-5 space-y-3">
                <h3 className="font-semibold tracking-tight text-lg">Recent scans</h3>
                {scans.length === 0 && (
                  <div className="text-sm py-6 text-center"
                    style={{ color: "var(--text-muted)" }}>
                    No scans yet.
                  </div>
                )}
                {scans.map((s, idx) => {
                  const c = s.status === "found" ? "var(--success)" : s.status === "unknown" ? "var(--danger)" : "var(--warning)";
                  const Icon = s.status === "found" ? CheckCircle2 : AlertTriangle;
                  return (
                  <div key={idx} className="flex items-center gap-3 text-sm">
                    <Badge variant="outline" className="font-mono text-[10px] uppercase gap-1"
                      style={{ borderColor: c, color: c }}>
                      <Icon className="w-3 h-3" />
                      {s.status.replace("_", " ")}
                    </Badge>
                    <span className="font-mono">{s.code}</span>
                  </div>
                  );
                })}
              </CardContent>
            </Card>
            <Card style={{ borderColor: "var(--line)", background: "var(--panel)" }}>
              <CardContent className="p-5 space-y-3">
                <h3 className="font-semibold tracking-tight text-lg">Missing items</h3>
                {!variance || variance.missing.length === 0 ? (
                  <div className="text-sm py-6 text-center"
                    style={{ color: "var(--text-muted)" }}>
                    Nothing missing yet.
                  </div>
                ) : variance.missing.map((m) => (
                  <div key={m.id} className="flex items-center justify-between text-sm">
                    <span className="font-mono">{m.tag_id}</span>
                    <span className="font-num" style={{ color: "var(--text-2)" }}>
                      {m.net_wt?.toFixed(3)} g
                    </span>
                  </div>
                ))}
              </CardContent>
            </Card>
          </div>
        </>
      )}
    </div>
  );
}

function VarCard({ label, value, color, testId }) {
  return (
    <Card style={{ borderColor: color || "var(--line)", background: "var(--panel)" }}>
      <CardContent className="p-5">
        <div className="text-xs uppercase tracking-widest"
          style={{ color: "var(--text-muted)" }}>{label}</div>
        <div className="font-num text-3xl font-semibold mt-2"
          style={{ color: color || "var(--text)" }} data-testid={testId}>
          {value}
        </div>
      </CardContent>
    </Card>
  );
}
