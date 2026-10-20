import React, { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { Printer } from "lucide-react";
import { toast } from "sonner";

/* TSPL/ZPL preview — renders a scaled approximation of a dumbbell tag.
   Actual print is routed to a USB label printer by the shop OS; here we
   generate TSPL/ZPL text and download it. */

export default function LabelPrint() {
  const [items, setItems] = useState([]);
  const [selected, setSelected] = useState("");
  const [purities, setPurities] = useState([]);
  const [format, setFormat] = useState("TSPL");

  useEffect(() => {
    api.get("/items?status=in_stock").then((r) => setItems(r.data));
    api.get("/purities").then((r) => setPurities(r.data));
  }, []);

  const item = items.find((i) => i.id === selected);
  const purity = item && purities.find((p) => p.id === item.purity_id);

  const generatePayload = () => {
    if (!item) return "";
    const net = item.net_wt.toFixed(3);
    const gross = item.gross_wt.toFixed(3);
    if (format === "TSPL") {
      return [
        "SIZE 50 mm, 25 mm",
        "GAP 2 mm, 0 mm",
        "DIRECTION 1",
        "CLS",
        `TEXT 10,10,"3",0,1,1,"${item.tag_id}"`,
        `TEXT 10,45,"2",0,1,1,"Pur ${purity?.code || ''}"`,
        `TEXT 10,70,"2",0,1,1,"Net ${net}g"`,
        `TEXT 10,95,"2",0,1,1,"Gr ${gross}g"`,
        `BARCODE 10,130,"128",50,1,0,2,2,"${item.barcode || item.tag_id}"`,
        "PRINT 1,1",
      ].join("\n");
    }
    // ZPL
    return [
      "^XA",
      `^FO20,20^A0N,40,40^FD${item.tag_id}^FS`,
      `^FO20,70^A0N,25,25^FDPur ${purity?.code || ''}^FS`,
      `^FO20,100^A0N,25,25^FDNet ${net}g  Gr ${gross}g^FS`,
      `^FO20,140^BY2^BCN,60,Y,N,N^FD${item.barcode || item.tag_id}^FS`,
      "^XZ",
    ].join("\n");
  };

  const print = () => {
    if (!item) return;
    const payload = generatePayload();
    const blob = new Blob([payload], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${item.tag_id}.${format.toLowerCase()}.txt`;
    a.click();
    URL.revokeObjectURL(url);
    toast.success(`${format} label payload downloaded`);
  };

  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs uppercase tracking-[0.25em]"
          style={{ color: "var(--text-muted)" }}>Label Printing</p>
        <h1 className="text-3xl font-semibold tracking-tight mt-1">TSPL / ZPL Tag Generator</h1>
      </div>

      <Card style={{ borderColor: "var(--border)", background: "var(--card)" }}>
        <CardContent className="p-6 grid md:grid-cols-[1fr,340px] gap-6">
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-xs uppercase tracking-widest"
                  style={{ color: "var(--text-muted)" }}>Item</label>
                <Select value={selected} onValueChange={setSelected}>
                  <SelectTrigger data-testid="label-item-select">
                    <SelectValue placeholder="Pick an item…" />
                  </SelectTrigger>
                  <SelectContent>
                    {items.map((i) => (
                      <SelectItem key={i.id} value={i.id}>
                        {i.tag_id} · {i.net_wt.toFixed(3)}g
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <label className="text-xs uppercase tracking-widest"
                  style={{ color: "var(--text-muted)" }}>Format</label>
                <Select value={format} onValueChange={setFormat}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="TSPL">TSPL (TSC)</SelectItem>
                    <SelectItem value="ZPL">ZPL (Zebra)</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div>
              <label className="text-xs uppercase tracking-widest"
                style={{ color: "var(--text-muted)" }}>Payload preview</label>
              <pre
                className="mt-1 p-3 rounded-md text-xs font-mono overflow-auto h-56"
                style={{
                  background: "var(--surface)",
                  color: "var(--text)",
                  border: "1px solid var(--border)",
                }}
                data-testid="label-payload-preview"
              >
                {generatePayload() || "// Select an item to generate payload"}
              </pre>
            </div>
            <Button onClick={print} disabled={!item}
              style={{ background: "var(--primary)", color: "var(--primary-fg)" }}
              className="gap-2" data-testid="print-label-action-button">
              <Printer className="w-4 h-4" /> Download & send to printer
            </Button>
          </div>

          <div>
            <label className="text-xs uppercase tracking-widest"
              style={{ color: "var(--text-muted)" }}>Live tag preview</label>
            <div
              className="mt-1 rounded-md p-4 border aspect-[2/1] flex flex-col justify-between"
              style={{ background: "#FFFBEF", borderColor: "var(--border)" }}
              data-testid="label-print-preview-canvas"
            >
              <div>
                <div className="font-semibold tracking-tight text-2xl font-semibold text-neutral-900">
                  {item?.tag_id || "TAG-ID"}
                </div>
                <div className="text-[10px] uppercase tracking-widest text-neutral-500">
                  {purity?.label || "Purity"}
                </div>
              </div>
              <div className="font-mono text-xs text-neutral-900 leading-5">
                <div>Gross: <b>{item?.gross_wt?.toFixed(3) || "0.000"}</b> g</div>
                <div>Stone: <b>{item?.stone_wt?.toFixed(3) || "0.000"}</b> g</div>
                <div>Net: <b>{item?.net_wt?.toFixed(3) || "0.000"}</b> g</div>
                {item?.huid && <div>HUID: {item.huid}</div>}
              </div>
              <div className="mt-2 font-mono text-[10px] bg-neutral-900 text-white px-2 py-1 inline-block self-start">
                ▮▯▮▯▮▮▯▮▯▮▮▯▮ {item?.barcode || item?.tag_id || "—"}
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
