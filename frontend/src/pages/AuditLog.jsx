import React, { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export default function AuditLog() {
  const [entries, setEntries] = useState([]);
  useEffect(() => {
    api.get("/audit-log?limit=200").then((r) => setEntries(r.data)).catch(() => {});
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs uppercase tracking-[0.25em]" style={{ color: "var(--text-muted)" }}>
          Security
        </p>
        <h1 className="text-3xl font-semibold tracking-tight mt-1">Audit Log (Hash-Chained)</h1>
      </div>
      <Card style={{ borderColor: "var(--line)", background: "var(--panel)" }}>
        <CardContent className="p-0">
          <table className="w-full text-sm" data-testid="audit-log-table">
            <thead
              className="text-left text-[11px] uppercase tracking-widest"
              style={{ color: "var(--text-muted)", background: "var(--surface)" }}
            >
              <tr>
                <th className="px-4 py-3">When</th>
                <th className="px-4 py-3">Entity</th>
                <th className="px-4 py-3">Action</th>
                <th className="px-4 py-3">User</th>
                <th className="px-4 py-3">Hash</th>
              </tr>
            </thead>
            <tbody>
              {entries.map((e) => (
                <tr key={e.id} className="border-t" style={{ borderColor: "var(--line)" }} data-testid={`audit-log-row-${e.id}`}>
                  <td className="px-4 py-2 font-mono text-xs">
                    {new Date(e.created_at).toLocaleString()}
                  </td>
                  <td className="px-4 py-2">
                    <Badge variant="outline" className="font-mono text-[10px] uppercase">
                      {e.entity}
                    </Badge>
                  </td>
                  <td className="px-4 py-2">{e.action}</td>
                  <td className="px-4 py-2 font-mono text-xs"
                    style={{ color: "var(--text-muted)" }}>
                    {e.user_id?.slice(0, 8) || "—"}
                  </td>
                  <td className="px-4 py-2 font-mono text-[10px]"
                    style={{ color: "var(--text-muted)" }}>
                    {e.hash?.slice(0, 16)}…
                  </td>
                </tr>
              ))}
              {entries.length === 0 && (
                <tr><td colSpan={5} className="text-center py-10"
                  style={{ color: "var(--text-muted)" }}>No entries yet.</td></tr>
              )}
            </tbody>
          </table>
        </CardContent>
      </Card>
    </div>
  );
}
