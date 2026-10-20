import React from "react";
import { useAuth } from "@/context/AuthContext";
import { Card, CardContent } from "@/components/ui/card";
import { FileManager } from "@/components/FileManager";

export default function Documents() {
  const { branchId, branches } = useAuth();
  const branch = branches.find((b) => b.id === branchId);
  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs uppercase tracking-[0.25em]" style={{ color: "var(--text-muted)" }}>
          {branch?.name || "Branch"}
        </p>
        <h1 className="text-3xl font-semibold tracking-tight mt-1">Document Library</h1>
        <p className="text-sm mt-2" style={{ color: "var(--text-2)" }}>
          Purchase bills, KYC, licences and other files for this branch.
        </p>
      </div>
      <Card style={{ borderColor: "var(--line)", background: "var(--panel)" }}>
        <CardContent className="p-6">
          {branchId ? <FileManager ownerType="branch" ownerId={branchId} /> : "Select a branch"}
        </CardContent>
      </Card>
    </div>
  );
}
