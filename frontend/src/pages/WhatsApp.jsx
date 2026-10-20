import React, { useEffect, useState } from "react";
import { api, errMsg } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Send, AlertTriangle } from "lucide-react";
import { toast } from "sonner";

const STATUS_COLOR = { sent: "var(--success)", delivered: "var(--success)", mocked: "var(--warning)", failed: "var(--danger)", invalid_number: "var(--danger)" };

export default function WhatsApp() {
  const { branchId, user } = useAuth();
  const [status, setStatus] = useState(null);
  const [msgs, setMsgs] = useState([]);
  const [text, setText] = useState("");
  const [audience, setAudience] = useState("customers");
  const [phones, setPhones] = useState("");
  const [busy, setBusy] = useState(false);
  const canBroadcast = ["admin", "manager"].includes(user?.role);

  const load = () => branchId && api.get(`/whatsapp/messages?branch_id=${branchId}`).then((r) => setMsgs(r.data)).catch(() => {});
  useEffect(() => { api.get("/whatsapp/status").then((r) => setStatus(r.data)).catch(() => {}); }, []);
  useEffect(() => { load(); }, [branchId]); // eslint-disable-line

  const send = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      const { data } = await api.post("/whatsapp/broadcast", {
        branch_id: branchId, message: text, audience,
        phones: audience === "custom" ? phones.split(/[\s,;]+/).filter(Boolean) : [],
      });
      toast.success(`Broadcast to ${data.recipients} number(s)${data.mocked ? " (mock — not actually sent)" : ""}`);
      setText(""); load();
    } catch (err) { toast.error(errMsg(err, "Broadcast failed")); } finally { setBusy(false); }
  };

  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs uppercase tracking-[0.25em]" style={{ color: "var(--text-muted)" }}>Messaging</p>
        <h1 className="text-3xl font-semibold tracking-tight mt-1">WhatsApp</h1>
        <p className="text-sm mt-2" style={{ color: "var(--text-2)" }}>Invoices go out automatically when a bill has a phone number. Use broadcasts for new launches.</p>
      </div>
      {status?.mocked && (
        <div className="flex items-start gap-3 p-4 rounded-md border" style={{ borderColor: "var(--warning)", background: "var(--panel)" }} data-testid="whatsapp-mock-banner">
          <AlertTriangle className="w-5 h-5 shrink-0" style={{ color: "var(--warning)" }} />
          <div className="text-sm"><b>No WhatsApp provider connected yet.</b> Messages are only recorded in the outbox below and are not delivered.
            Your tech team can plug a provider into <span className="font-mono">backend/whatsapp.py</span> and set <span className="font-mono">WHATSAPP_PROVIDER</span>.</div>
        </div>
      )}
      <div className="grid lg:grid-cols-[420px,1fr] gap-6">
        <Card style={{ borderColor: "var(--line)", background: "var(--panel)" }}>
          <CardContent className="p-6">
            {canBroadcast ? (
              <form onSubmit={send} className="space-y-4">
                <h3 className="font-semibold">New-launch broadcast</h3>
                <Textarea required rows={5} maxLength={1000} value={text} onChange={(e) => setText(e.target.value)}
                  placeholder="New bridal collection now at our store…" data-testid="broadcast-message-input" />
                <RadioGroup value={audience} onValueChange={setAudience} className="space-y-1">
                  <label className="flex items-center gap-2 text-sm"><RadioGroupItem value="customers" data-testid="broadcast-audience-customers" /> All customers of this branch (from bills)</label>
                  <label className="flex items-center gap-2 text-sm"><RadioGroupItem value="custom" data-testid="broadcast-audience-custom" /> Specific numbers</label>
                </RadioGroup>
                {audience === "custom" && (
                  <div><Label>Phone numbers (comma or new line)</Label>
                    <Textarea rows={3} value={phones} onChange={(e) => setPhones(e.target.value)} data-testid="broadcast-phones-input" /></div>
                )}
                <Button type="submit" disabled={busy} className="w-full h-11 gap-2" style={{ background: "var(--brand)", color: "var(--brand-fg)" }} data-testid="broadcast-send-button">
                  <Send className="w-4 h-4" /> {busy ? "Sending…" : "Send broadcast"}
                </Button>
              </form>
            ) : <p className="text-sm" style={{ color: "var(--text-2)" }}>Only managers and admins can send broadcasts.</p>}
          </CardContent>
        </Card>
        <Card style={{ borderColor: "var(--line)", background: "var(--panel)" }}>
          <CardContent className="p-0 overflow-x-auto">
            <table className="w-full text-sm" data-testid="whatsapp-outbox-table">
              <thead className="text-left text-[11px] uppercase tracking-widest" style={{ color: "var(--text-muted)", background: "var(--surface)" }}>
                <tr><th className="px-4 py-3">When</th><th className="px-4 py-3">Type</th><th className="px-4 py-3">To</th><th className="px-4 py-3">Message</th><th className="px-4 py-3">Status</th></tr>
              </thead>
              <tbody>
                {msgs.length === 0 && <tr><td colSpan={5} className="text-center py-10" style={{ color: "var(--text-muted)" }}>Outbox is empty.</td></tr>}
                {msgs.map((m) => (
                  <tr key={m.id} className="border-t align-top" style={{ borderColor: "var(--line)" }}>
                    <td className="px-4 py-2 text-xs whitespace-nowrap">{new Date(m.created_at).toLocaleString()}</td>
                    <td className="px-4 py-2 capitalize">{m.kind}</td>
                    <td className="px-4 py-2 font-mono text-xs">{m.to}</td>
                    <td className="px-4 py-2 text-xs max-w-xs truncate" title={m.text}>{m.text || m.error}</td>
                    <td className="px-4 py-2"><Badge variant="outline" className="uppercase text-[10px]" style={{ borderColor: STATUS_COLOR[m.status], color: STATUS_COLOR[m.status] }}>{m.status.replace("_", " ")}</Badge></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
