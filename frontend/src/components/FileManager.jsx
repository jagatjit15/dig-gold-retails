import React, { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";
import { Upload, Download, Trash2, FileText } from "lucide-react";
import { toast } from "sonner";

const MAX = 25 * 1024 * 1024;

function fmtSize(b) {
  if (b > 1048576) return `${(b / 1048576).toFixed(1)} MB`;
  return `${Math.max(1, Math.round(b / 1024))} KB`;
}

function Thumb({ file }) {
  const [url, setUrl] = useState(null);
  useEffect(() => {
    if (!file.content_type.startsWith("image/")) return;
    let u;
    api.get(`/files/${file.id}/download`, { responseType: "blob" })
      .then((r) => { u = URL.createObjectURL(r.data); setUrl(u); })
      .catch(() => {});
    return () => u && URL.revokeObjectURL(u);
  }, [file.id, file.content_type]);
  if (url) return <img src={url} alt={file.original_filename} className="w-12 h-12 object-cover rounded" />;
  return (
    <div className="w-12 h-12 rounded flex items-center justify-center"
      style={{ background: "var(--gold-soft)", color: "var(--gold-text)" }}>
      <FileText className="w-5 h-5" />
    </div>
  );
}

export function FileManager({ ownerType, ownerId, category }) {
  const { user } = useAuth();
  const [files, setFiles] = useState([]);
  const [busy, setBusy] = useState(false);
  const input = useRef(null);
  const canUpload = ["admin", "manager", "billing"].includes(user?.role);
  const canDelete = ["admin", "manager"].includes(user?.role);

  const load = () =>
    api.get(`/files?owner_type=${ownerType}&owner_id=${ownerId}`)
      .then((r) => setFiles(r.data)).catch(() => {});
  useEffect(() => { if (ownerId) load(); }, [ownerType, ownerId]); // eslint-disable-line

  const upload = async (list) => {
    const chosen = Array.from(list || []);
    if (chosen.some((f) => f.size > MAX)) { toast.error("Each file must be 25 MB or less"); return; }
    setBusy(true);
    try {
      for (const f of chosen) {
        const fd = new FormData();
        fd.append("owner_type", ownerType);
        fd.append("owner_id", ownerId);
        if (category) fd.append("category", category);
        fd.append("file", f);
        await api.post("/files", fd);
      }
      toast.success(`${chosen.length} file(s) uploaded`);
      load();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Upload failed");
    } finally {
      setBusy(false);
      if (input.current) input.current.value = "";
    }
  };

  const download = async (f) => {
    try {
      const r = await api.get(`/files/${f.id}/download`, { responseType: "blob" });
      const url = URL.createObjectURL(r.data);
      const a = document.createElement("a");
      a.href = url; a.download = f.original_filename; a.click();
      setTimeout(() => URL.revokeObjectURL(url), 2000);
    } catch (_e) {
      toast.error("Download failed");
    }
  };

  const remove = async (f) => {
    if (!window.confirm(`Delete ${f.original_filename}?`)) return;
    try {
      await api.delete(`/files/${f.id}`);
      toast.success("File deleted");
      load();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Delete failed");
    }
  };

  return (
    <div className="space-y-3" data-testid={`file-manager-${ownerType}`}>
      {canUpload && (
        <div className="flex items-center gap-3">
          <input ref={input} type="file" multiple className="hidden"
            onChange={(e) => upload(e.target.files)} data-testid="file-upload-input" />
          <Button onClick={() => input.current?.click()} disabled={busy} className="gap-2"
            style={{ background: "var(--primary)", color: "var(--primary-fg)" }} data-testid="file-upload-button">
            <Upload className="w-4 h-4" /> {busy ? "Uploading…" : "Upload files"}
          </Button>
          <span className="text-xs" style={{ color: "var(--text-muted)" }}>
            Any file type · up to 25 MB each
          </span>
        </div>
      )}
      {files.length === 0 && (
        <div className="text-sm py-6 text-center" style={{ color: "var(--text-muted)" }}
          data-testid="file-list-empty">No files yet.</div>
      )}
      {files.map((f) => (
        <div key={f.id} className="flex items-center gap-3 p-2 rounded-md border"
          style={{ borderColor: "var(--border)" }} data-testid={`file-row-${f.id}`}>
          <Thumb file={f} />
          <div className="flex-1 min-w-0">
            <div className="text-sm font-medium truncate">{f.original_filename}</div>
            <div className="text-xs font-mono" style={{ color: "var(--text-muted)" }}>
              {fmtSize(f.size)} · {new Date(f.created_at).toLocaleString()}
            </div>
          </div>
          <Button size="icon" variant="ghost" onClick={() => download(f)}
            data-testid={`file-download-${f.id}`}><Download className="w-4 h-4" /></Button>
          {canDelete && (
            <Button size="icon" variant="ghost" onClick={() => remove(f)}
              data-testid={`file-delete-${f.id}`}>
              <Trash2 className="w-4 h-4" style={{ color: "var(--danger)" }} />
            </Button>
          )}
        </div>
      ))}
    </div>
  );
}
