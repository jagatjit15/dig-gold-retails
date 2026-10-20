import React, { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ScanLine, AlertTriangle, Check } from "lucide-react";
import { CameraScanButton } from "@/components/CameraScanner";

/* USB keyboard-wedge barcode & RFID scanners deliver characters to a focused
   input and submit on Enter. This page keeps the input focus-locked and
   streams scanned items with debouncing. Camera scanning can be plugged into
   this same handler via @zxing/library later. */

export default function ScanLookup() {
  const [code, setCode] = useState("");
  const [active, setActive] = useState(true);
  const [history, setHistory] = useState([]);
  const inputRef = useRef(null);
  const lastScan = useRef({ code: "", at: 0 });

  useEffect(() => { inputRef.current?.focus(); }, []);

  const lookup = async (raw) => {
    const code = raw.trim();
    if (!code) return;
    // debounce duplicates within 1200ms
    const now = Date.now();
    if (lastScan.current.code === code && now - lastScan.current.at < 1200) {
      return;
    }
    lastScan.current = { code, at: now };
    try {
      const { data } = await api.get(
        `/scan/lookup?code=${encodeURIComponent(code)}`
      );
      await api.post("/scan", { code, code_type: "barcode", context: "lookup" });
      setHistory((h) => [{ at: new Date(), code, ...data }, ...h].slice(0, 25));
    } catch (err) {
      setHistory((h) => [{
        at: new Date(), code, found: false,
        warnings: [err.response?.data?.detail || "Lookup failed"],
      }, ...h].slice(0, 25));
    }
  };

  const onSubmit = (e) => {
    e.preventDefault();
    lookup(code);
    setCode("");
  };

  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs uppercase tracking-[0.25em]" style={{ color: "var(--text-muted)" }}>
          Scan Service
        </p>
        <h1 className="text-3xl font-semibold tracking-tight mt-1">Barcode & RFID Lookup</h1>
      </div>

      <Card style={{ borderColor: "var(--border)", background: "var(--card)" }}>
        <CardContent className="p-6">
          <form onSubmit={onSubmit} className="space-y-3">
            <label className="text-xs uppercase tracking-widest flex items-center gap-2"
              style={{ color: "var(--text-muted)" }}>
              <ScanLine className="w-3.5 h-3.5" />
              Point USB scanner here · or type manually
            </label>
            <Input
              ref={inputRef}
              value={code}
              autoFocus
              onFocus={() => setActive(true)}
              onBlur={() => setActive(false)}
              onChange={(e) => setCode(e.target.value)}
              placeholder="Scan tag, barcode, HUID, or RFID EPC…"
              className={`h-14 text-lg font-mono tracking-wide ${active ? "scan-input-active" : ""}`}
              data-testid="barcode-scan-input"
            />
            <div className="flex items-center gap-2">
              <Button type="submit" style={{ background: "var(--primary)", color: "var(--primary-fg)" }}
                data-testid="scan-submit-button">
                Lookup
              </Button>
              <Button type="button" variant="outline" className="h-11"
                onClick={() => inputRef.current?.focus()}
                data-testid="focus-scanner-button">
                Focus USB scanner
              </Button>
              <CameraScanButton onDetect={lookup} continuous />
              <span className="text-xs ml-auto" style={{ color: "var(--text-muted)" }}>
                Duplicates within 1.2s are ignored
              </span>
            </div>
          </form>
        </CardContent>
      </Card>

      <div className="space-y-2">
        <div className="text-xs uppercase tracking-widest"
          style={{ color: "var(--text-muted)" }}>Recent scans</div>
        {history.length === 0 && (
          <div className="text-sm py-10 text-center"
            style={{ color: "var(--text-muted)" }}>
            Nothing yet. Scan an item above to begin.
          </div>
        )}
        {history.map((h, idx) => (
          <Card key={idx}
            style={{
              borderColor: h.found && (!h.warnings || h.warnings.length === 0)
                ? "var(--success)" : h.warnings?.length ? "var(--warning)" : "var(--danger)",
              background: "var(--card)",
            }}
            data-testid={`scan-result-${idx}`}>
            <CardContent className="p-4 flex items-start gap-4">
              <div className="pt-0.5">
                {h.found && !h.warnings?.length ? (
                  <Check className="w-5 h-5" style={{ color: "var(--success)" }} />
                ) : (
                  <AlertTriangle className="w-5 h-5"
                    style={{ color: h.warnings?.length ? "var(--warning)" : "var(--danger)" }} />
                )}
              </div>
              <div className="flex-1">
                <div className="flex items-center gap-3">
                  <span className="font-mono text-sm font-semibold">{h.code}</span>
                  <Badge variant="outline" className="text-[10px] uppercase font-mono"
                    style={{ borderColor: "var(--border)" }}>
                    {h.at.toLocaleTimeString()}
                  </Badge>
                </div>
                {h.item ? (
                  <div className="mt-2 grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                    <Kv label="Tag">{h.item.tag_id}</Kv>
                    <Kv label="HUID">{h.item.huid || "—"}</Kv>
                    <Kv label="Gross" mono>{h.item.gross_wt.toFixed(3)} g</Kv>
                    <Kv label="Net" mono>{h.item.net_wt.toFixed(3)} g</Kv>
                  </div>
                ) : !h.warnings?.length && (
                  <div className="mt-1 text-sm" style={{ color: "var(--text-2)" }}>
                    Item not found in database.
                  </div>
                )}
                {h.warnings?.map((w, i) => (
                  <div key={i} className="mt-1 text-xs" style={{ color: "var(--warning)" }}>
                    ⚠ {w}
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}

function Kv({ label, children, mono }) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-widest"
        style={{ color: "var(--text-muted)" }}>{label}</div>
      <div className={`${mono ? "font-num" : "font-medium"} mt-0.5`}>{children}</div>
    </div>
  );
}
