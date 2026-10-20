import React, { useEffect, useRef, useState } from "react";
import { Html5Qrcode, Html5QrcodeSupportedFormats as F } from "html5-qrcode";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Camera, AlertTriangle } from "lucide-react";

const FORMATS = [F.QR_CODE, F.CODE_128, F.CODE_39, F.CODE_93, F.EAN_13, F.EAN_8,
  F.UPC_A, F.UPC_E, F.ITF, F.DATA_MATRIX];
const REGION = "swarna-camera-region";

function CameraView({ onDetect, continuous, onClose }) {
  const [cams, setCams] = useState([]);
  const [camId, setCamId] = useState("");
  const [err, setErr] = useState("");
  const [lastCode, setLastCode] = useState("");
  const last = useRef({ c: "", t: 0 });
  const cb = useRef(onDetect);
  cb.current = onDetect;

  useEffect(() => {
    Html5Qrcode.getCameras().then((list) => {
      if (!list.length) { setErr("No camera found. Connect a camera and try again."); return; }
      setCams(list);
      const saved = localStorage.getItem("swarna_camera");
      const pick = list.find((c) => c.id === saved) ||
        list.find((c) => /back|rear|environment/i.test(c.label)) || list[0];
      setCamId(pick.id);
    }).catch(() => setErr("Camera access was blocked. Allow camera permission in the browser and retry."));
  }, []);

  useEffect(() => {
    if (!camId) return;
    localStorage.setItem("swarna_camera", camId);
    setErr("");
    const scanner = new Html5Qrcode(REGION, { formatsToSupport: FORMATS, verbose: false });
    const started = scanner.start(camId, { fps: 12, qrbox: { width: 300, height: 170 } }, (text) => {
      const now = Date.now();
      if (last.current.c === text && now - last.current.t < 1500) return;
      last.current = { c: text, t: now };
      setLastCode(text);
      if (navigator.vibrate) navigator.vibrate(60);
      cb.current(text);
      if (!continuous) onClose();
    }, () => {}).catch(() => setErr("Could not start this camera. Try another one."));
    return () => {
      started.then(() => scanner.isScanning && scanner.stop()).then(() => scanner.clear()).catch(() => {});
    };
  }, [camId]); // eslint-disable-line

  return (
    <div className="space-y-3">
      {cams.length > 1 && (
        <Select value={camId} onValueChange={setCamId}>
          <SelectTrigger className="h-11" data-testid="camera-device-select"><SelectValue /></SelectTrigger>
          <SelectContent>
            {cams.map((c, i) => <SelectItem key={c.id} value={c.id}>{c.label || `Camera ${i + 1}`}</SelectItem>)}
          </SelectContent>
        </Select>
      )}
      <div id={REGION} className="w-full rounded-md overflow-hidden bg-black min-h-[240px]" />
      {err && (
        <div className="flex items-center gap-2 text-sm" style={{ color: "var(--danger)" }} data-testid="camera-error">
          <AlertTriangle className="w-4 h-4" /> {err}
        </div>
      )}
      {continuous && lastCode && (
        <div className="text-sm" data-testid="camera-last-code">
          Last scanned: <span className="font-mono font-semibold">{lastCode}</span>
        </div>
      )}
      <p className="text-xs" style={{ color: "var(--text-muted)" }}>
        Hold the tag barcode or QR inside the box. Works with phone, laptop and USB/external cameras.
      </p>
    </div>
  );
}

export function CameraScanButton({ onDetect, continuous = false, testId = "camera-scan-trigger-button" }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <Button type="button" variant="outline" className="h-11 gap-2" onClick={() => setOpen(true)} data-testid={testId}>
        <Camera className="w-4 h-4" /> Camera
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader><DialogTitle>Scan with camera</DialogTitle></DialogHeader>
          {open && <CameraView onDetect={onDetect} continuous={continuous} onClose={() => setOpen(false)} />}
          {continuous && (
            <Button onClick={() => setOpen(false)} className="h-11" style={{ background: "var(--brand)", color: "var(--brand-fg)" }}
              data-testid="camera-done-button">Done</Button>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}
