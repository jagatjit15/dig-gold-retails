import React, { useEffect, useState } from "react";
import { api, errMsg } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { UserPlus, Pencil, KeyRound, CheckCircle2, XCircle } from "lucide-react";
import { toast } from "sonner";

const ROLES = [
  { v: "admin", l: "Admin — all branches" },
  { v: "manager", l: "Manager" },
  { v: "billing", l: "Billing / counter" },
  { v: "auditor", l: "Auditor" },
];
const primary = { background: "var(--brand)", color: "var(--brand-fg)" };

function StaffDialog({ open, onClose, staff, branches, onSaved }) {
  const editing = Boolean(staff);
  const [f, setF] = useState({});
  useEffect(() => {
    setF(staff ? { name: staff.name, role: staff.role, branch_id: staff.branch_id || "" }
      : { name: "", email: "", password: "", role: "billing", branch_id: branches[0]?.id || "" });
  }, [staff, open, branches]);
  const set = (k, v) => setF((x) => ({ ...x, [k]: v }));

  const save = async (e) => {
    e.preventDefault();
    const branch_id = f.role === "admin" ? null : f.branch_id || null;
    try {
      if (editing) await api.patch(`/auth/users/${staff.id}`, { name: f.name, role: f.role, branch_id });
      else await api.post("/auth/users", { ...f, branch_id });
      toast.success(editing ? "Staff updated — they will need to sign in again" : "Staff account created");
      onSaved(); onClose();
    } catch (err) { toast.error(errMsg(err, "Could not save")); }
  };

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader><DialogTitle>{editing ? "Edit staff" : "New staff account"}</DialogTitle></DialogHeader>
        <form onSubmit={save} className="space-y-3">
          <div><Label>Full name *</Label>
            <Input required value={f.name || ""} onChange={(e) => set("name", e.target.value)} data-testid="staff-name-input" /></div>
          {!editing && (<>
            <div><Label>Email *</Label>
              <Input required type="email" value={f.email || ""} onChange={(e) => set("email", e.target.value)} data-testid="staff-email-input" /></div>
            <div><Label>Password *</Label>
              <Input required type="password" value={f.password || ""} onChange={(e) => set("password", e.target.value)} data-testid="staff-password-input" />
              <p className="text-xs mt-1" style={{ color: "var(--text-muted)" }}>At least 8 characters with letters and numbers.</p></div>
          </>)}
          <div><Label>Role *</Label>
            <Select value={f.role} onValueChange={(v) => set("role", v)}>
              <SelectTrigger data-testid="staff-role-select"><SelectValue /></SelectTrigger>
              <SelectContent>{ROLES.map((r) => <SelectItem key={r.v} value={r.v}>{r.l}</SelectItem>)}</SelectContent>
            </Select></div>
          {f.role !== "admin" && (
            <div><Label>Branch *</Label>
              <Select value={f.branch_id} onValueChange={(v) => set("branch_id", v)}>
                <SelectTrigger data-testid="staff-branch-select"><SelectValue placeholder="Select branch" /></SelectTrigger>
                <SelectContent>{branches.map((b) => <SelectItem key={b.id} value={b.id}>{b.name}</SelectItem>)}</SelectContent>
              </Select>
              <p className="text-xs mt-1" style={{ color: "var(--text-muted)" }}>They will only see this branch's stock and bills.</p></div>
          )}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
            <Button type="submit" style={primary} data-testid="staff-save-button">{editing ? "Save" : "Create account"}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function ResetDialog({ staff, onClose }) {
  const [pw, setPw] = useState("");
  const save = async (e) => {
    e.preventDefault();
    try {
      await api.post(`/auth/users/${staff.id}/reset-password`, { password: pw });
      toast.success("Password reset — share it with the staff member securely");
      setPw(""); onClose();
    } catch (err) { toast.error(errMsg(err, "Reset failed")); }
  };
  return (
    <Dialog open={Boolean(staff)} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="sm:max-w-sm">
        <DialogHeader><DialogTitle>Reset password · {staff?.name}</DialogTitle></DialogHeader>
        <form onSubmit={save} className="space-y-3">
          <Input required type="password" value={pw} onChange={(e) => setPw(e.target.value)} placeholder="New password" data-testid="staff-reset-password-input" />
          <Button type="submit" className="w-full" style={primary} data-testid="staff-reset-password-submit">Reset password</Button>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export default function Staff() {
  const { user, branches } = useAuth();
  const [list, setList] = useState([]);
  const [edit, setEdit] = useState(undefined);
  const [reset, setReset] = useState(null);
  const load = () => api.get("/auth/users").then((r) => setList(r.data)).catch(() => {});
  useEffect(() => { load(); }, []);
  const bname = (id) => branches.find((b) => b.id === id)?.name || "All branches";

  const toggle = async (s) => {
    try {
      await api.patch(`/auth/users/${s.id}`, { active: !s.active });
      toast.success(s.active ? `${s.name} deactivated` : `${s.name} reactivated`);
      load();
    } catch (err) { toast.error(errMsg(err)); }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between">
        <div>
          <p className="text-xs uppercase tracking-[0.25em]" style={{ color: "var(--text-muted)" }}>Admin</p>
          <h1 className="text-3xl font-semibold tracking-tight mt-1">Staff accounts</h1>
          <p className="text-sm mt-2" style={{ color: "var(--text-2)" }}>Each staff member only sees the branch they are assigned to.</p>
        </div>
        <Button className="gap-2 h-11" style={primary} onClick={() => setEdit(null)} data-testid="add-staff-button">
          <UserPlus className="w-4 h-4" /> New staff
        </Button>
      </div>
      <Card style={{ borderColor: "var(--line)", background: "var(--panel)" }}>
        <CardContent className="p-0 overflow-x-auto">
          <table className="w-full text-sm" data-testid="staff-table">
            <thead className="text-left text-[11px] uppercase tracking-widest" style={{ color: "var(--text-muted)", background: "var(--surface)" }}>
              <tr><th className="px-4 py-3">Name</th><th className="px-4 py-3">Role</th><th className="px-4 py-3">Branch</th><th className="px-4 py-3">Status</th><th className="px-4 py-3 text-right">Actions</th></tr>
            </thead>
            <tbody>
              {list.map((s) => (
                <tr key={s.id} className="border-t" style={{ borderColor: "var(--line)" }} data-testid={`staff-row-${s.email}`}>
                  <td className="px-4 py-3"><div className="font-medium">{s.name}</div><div className="text-xs font-mono" style={{ color: "var(--text-muted)" }}>{s.email}</div></td>
                  <td className="px-4 py-3"><Badge variant="outline" className="uppercase text-[10px]">{s.role}</Badge></td>
                  <td className="px-4 py-3">{bname(s.branch_id)}</td>
                  <td className="px-4 py-3">
                    <span className="inline-flex items-center gap-1.5 text-xs font-medium" style={{ color: s.active ? "var(--success)" : "var(--danger)" }}>
                      {s.active ? <CheckCircle2 className="w-3.5 h-3.5" /> : <XCircle className="w-3.5 h-3.5" />}{s.active ? "Active" : "Deactivated"}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right space-x-1 whitespace-nowrap">
                    <Button size="sm" variant="ghost" onClick={() => setEdit(s)} data-testid={`staff-edit-${s.email}`}><Pencil className="w-4 h-4" /></Button>
                    <Button size="sm" variant="ghost" onClick={() => setReset(s)} data-testid={`staff-reset-${s.email}`}><KeyRound className="w-4 h-4" /></Button>
                    {s.id !== user.id && (
                      <Button size="sm" variant="outline" onClick={() => toggle(s)} data-testid={`staff-toggle-${s.email}`}>
                        {s.active ? "Deactivate" : "Reactivate"}
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardContent>
      </Card>
      <StaffDialog open={edit !== undefined} staff={edit} branches={branches} onClose={() => setEdit(undefined)} onSaved={load} />
      <ResetDialog staff={reset} onClose={() => setReset(null)} />
    </div>
  );
}
