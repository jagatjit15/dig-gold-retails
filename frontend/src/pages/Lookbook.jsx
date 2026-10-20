import React, { useEffect, useState } from "react";
import { api, errMsg } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Sparkles, Send, Download } from "lucide-react";
import { toast } from "sonner";

const primary = { background: "var(--brand)", color: "var(--brand-fg)" };

function useBlob(fileId) {
  const [url, setUrl] = useState(null);
  useEffect(() => {
    if (!fileId) return;
    let u;
    api.get(`/files/${fileId}/download`, { responseType: "blob" })
      .then((r) => { u = URL.createObjectURL(r.data); setUrl(u); }).catch(() => {});
    return () => u && URL.revokeObjectURL(u);
  }, [fileId]);
  return url;
}

function Preview({ card, onSent }) {
  const url = useBlob(card.file_id);
  const [msg, setMsg] = useState(card.title);
  const [audience, setAudience] = useState("customers");
  const [phones, setPhones] = useState("");
  const [busy, setBusy] = useState(false);

  const send = async () => {
    setBusy(true);
    try {
      const { data } = await api.post(`/lookbook/${card.id}/broadcast`, {
        message: msg, audience, phones: audience === "custom" ? phones.split(/[\s,;]+/).filter(Boolean) : [],
      });
      toast.success(`Card sent to ${data.recipients} number(s)${data.mocked ? " (mock — not actually delivered)" : ""}`);
      onSent?.();
    } catch (err) { toast.error(errMsg(err, "Broadcast failed")); } finally { setBusy(false); }
  };

  return (
    <Card style={{ borderColor: "var(--line)", background: "var(--panel)" }} data-testid="lookbook-preview">
      <CardContent className="p-6 grid md:grid-cols-[minmax(0,360px),1fr] gap-6">
        <div>
          {url ? <img src={url} alt={card.title} className="w-full rounded-md border" style={{ borderColor: "var(--line)" }} data-testid="lookbook-card-image" />
            : <div className="aspect-[4/5] rounded-md animate-pulse" style={{ background: "var(--surface)" }} />}
          {url && <a href={url} download={`${card.title}.png`} className="mt-2 inline-flex items-center gap-1 text-sm" style={{ color: "var(--brand)" }} data-testid="lookbook-download-link"><Download className="w-4 h-4" /> Download PNG</a>}
        </div>
        <div className="space-y-4">
          <h3 className="font-semibold">Send on WhatsApp</h3>
          <div><Label>Caption</Label><Textarea rows={3} value={msg} onChange={(e) => setMsg(e.target.value)} data-testid="lookbook-caption-input" /></div>
          <RadioGroup value={audience} onValueChange={setAudience} className="space-y-1">
            <label className="flex items-center gap-2 text-sm"><RadioGroupItem value="customers" /> All customers of this branch</label>
            <label className="flex items-center gap-2 text-sm"><RadioGroupItem value="custom" data-testid="lookbook-audience-custom" /> Specific numbers</label>
          </RadioGroup>
          {audience === "custom" && <Textarea rows={3} value={phones} onChange={(e) => setPhones(e.target.value)} placeholder="9876543210, 9123456789" data-testid="lookbook-phones-input" />}
          <Button className="h-11 gap-2" style={primary} disabled={busy} onClick={send} data-testid="lookbook-broadcast-button"><Send className="w-4 h-4" /> {busy ? "Sending…" : "Broadcast card"}</Button>
        </div>
      </CardContent>
    </Card>
  );
}

export default function Lookbook() {
  const { branchId, user } = useAuth();
  const [items, setItems] = useState([]);
  const [photoIds, setPhotoIds] = useState(new Set());
  const [picked, setPicked] = useState([]);
  const [title, setTitle] = useState("New Collection");
  const [subtitle, setSubtitle] = useState("");
  const [cards, setCards] = useState([]);
  const [current, setCurrent] = useState(null);
  const [busy, setBusy] = useState(false);
  const canCreate = ["admin", "manager"].includes(user?.role);

  const loadCards = () => api.get(`/lookbook?branch_id=${branchId}`).then((r) => setCards(r.data)).catch(() => {});
  useEffect(() => {
    if (!branchId) return;
    setPicked([]); setCurrent(null);
    api.get(`/items?branch_id=${branchId}&status=in_stock`).then((r) => setItems(r.data)).catch(() => {});
    api.get(`/lookbook/photo-items?branch_id=${branchId}`).then((r) => setPhotoIds(new Set(r.data))).catch(() => {});
    loadCards();
  }, [branchId]); // eslint-disable-line

  const toggle = (id) => setPicked((p) => (p.includes(id) ? p.filter((x) => x !== id) : p.length >= 6 ? p : [...p, id]));

  const create = async () => {
    setBusy(true);
    try {
      const { data } = await api.post("/lookbook", { branch_id: branchId, title, subtitle: subtitle || null, item_ids: picked });
      toast.success("Lookbook card ready");
      setCurrent(data); loadCards();
    } catch (err) { toast.error(errMsg(err, "Could not create card")); } finally { setBusy(false); }
  };

  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs uppercase tracking-[0.25em]" style={{ color: "var(--text-muted)" }}>Marketing</p>
        <h1 className="text-3xl font-semibold tracking-tight mt-1">Launch lookbook</h1>
        <p className="text-sm mt-2" style={{ color: "var(--text-2)" }}>Pick up to 6 items. Photos come from each item's Files; prices use today's rate incl. GST.</p>
      </div>
      {canCreate ? (
        <Card style={{ borderColor: "var(--line)", background: "var(--panel)" }}>
          <CardContent className="p-6 space-y-4">
            <div className="grid md:grid-cols-2 gap-3">
              <div><Label>Card title *</Label><Input className="h-11" maxLength={60} value={title} onChange={(e) => setTitle(e.target.value)} data-testid="lookbook-title-input" /></div>
              <div><Label>Subtitle</Label><Input className="h-11" maxLength={80} value={subtitle} onChange={(e) => setSubtitle(e.target.value)} placeholder="Now at our store" data-testid="lookbook-subtitle-input" /></div>
            </div>
            <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-2 max-h-80 overflow-y-auto">
              {items.length === 0 && <div className="text-sm" style={{ color: "var(--text-muted)" }}>No in-stock items in this branch.</div>}
              {items.map((i) => (
                <label key={i.id} className="flex items-center gap-3 p-3 rounded-md border cursor-pointer text-sm"
                  style={{ borderColor: picked.includes(i.id) ? "var(--brand)" : "var(--line)" }} data-testid={`lookbook-item-${i.tag_id}`}>
                  <Checkbox checked={picked.includes(i.id)} onCheckedChange={() => toggle(i.id)} />
                  <div className="flex-1 min-w-0">
                    <div className="font-medium truncate">{i.description || i.tag_id}</div>
                    <div className="text-xs font-mono" style={{ color: "var(--text-muted)" }}>{i.tag_id} · {i.net_wt.toFixed(3)} g</div>
                  </div>
                  <span className="text-[10px] uppercase" style={{ color: photoIds.has(i.id) ? "var(--success)" : "var(--text-muted)" }}>{photoIds.has(i.id) ? "Photo" : "No photo"}</span>
                </label>
              ))}
            </div>
            <Button className="h-11 gap-2" style={primary} disabled={busy || !picked.length || !title.trim()} onClick={create} data-testid="lookbook-create-button">
              <Sparkles className="w-4 h-4" /> {busy ? "Building card…" : `Create card (${picked.length}/6)`}
            </Button>
          </CardContent>
        </Card>
      ) : <p className="text-sm" style={{ color: "var(--text-2)" }}>Only managers and admins can create lookbook cards.</p>}
      {current && <Preview key={current.id} card={current} />}
      {cards.length > 0 && (
        <div className="space-y-2">
          <h3 className="text-xs uppercase tracking-widest" style={{ color: "var(--text-muted)" }}>Previous cards</h3>
          <div className="flex flex-wrap gap-2">
            {cards.map((c) => (
              <Button key={c.id} variant="outline" size="sm" onClick={() => setCurrent(c)} data-testid={`lookbook-history-${c.id}`}>
                {c.title} · {new Date(c.created_at).toLocaleDateString()}
              </Button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
