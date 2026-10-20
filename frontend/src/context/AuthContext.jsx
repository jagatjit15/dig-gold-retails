import React, { createContext, useContext, useEffect, useState } from "react";
import { api } from "@/lib/api";

const AuthCtx = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    const raw = localStorage.getItem("swarna_user");
    return raw ? JSON.parse(raw) : null;
  });
  const [branchId, setBranchIdState] = useState(() =>
    localStorage.getItem("swarna_branch") || ""
  );
  const [branches, setBranches] = useState([]);

  const setBranchId = (id) => {
    setBranchIdState(id);
    if (id) localStorage.setItem("swarna_branch", id);
    else localStorage.removeItem("swarna_branch");
  };

  useEffect(() => {
    if (user) {
      api.get("/branches").then((r) => {
        setBranches(r.data);
        if (!branchId || !r.data.some((b) => b.id === branchId)) {
          const defaultBranch = user.branch_id || r.data[0]?.id || "";
          if (defaultBranch) setBranchId(defaultBranch);
        }
      }).catch(() => {});
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user]);

  useEffect(() => {
    localStorage.removeItem("swarna_access");
    localStorage.removeItem("swarna_refresh");
    if (!user) return;
    api.get("/auth/me").then((r) => {
      localStorage.setItem("swarna_user", JSON.stringify(r.data));
      setUser(r.data);
    }).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const login = async (email, password) => {
    const { data } = await api.post("/auth/login", { email, password });
    localStorage.setItem("swarna_user", JSON.stringify(data.user));
    setUser(data.user);
    if (data.user.branch_id) setBranchId(data.user.branch_id);
    return data.user;
  };

  const logout = () => {
    api.post("/auth/logout").catch(() => {});
    localStorage.removeItem("swarna_user");
    localStorage.removeItem("swarna_branch");
    setUser(null);
    setBranchIdState("");
  };

  return (
    <AuthCtx.Provider
      value={{ user, login, logout, branchId, setBranchId, branches, setBranches }}
    >
      {children}
    </AuthCtx.Provider>
  );
}

export const useAuth = () => useContext(AuthCtx);
