import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API_BASE = `${BACKEND_URL}/api`;

export const api = axios.create({ baseURL: API_BASE, withCredentials: true });

export function errMsg(err, fallback = "Something went wrong") {
  const d = err?.response?.data?.detail;
  if (!d) return fallback;
  if (typeof d === "string") return d;
  if (Array.isArray(d)) return d.map((e) => e?.msg || JSON.stringify(e)).join(" ");
  return d.msg || String(d);
}

let refreshing = null;
const NO_RETRY = ["/auth/login", "/auth/refresh", "/auth/logout"];

api.interceptors.response.use(
  (r) => r,
  async (err) => {
    const original = err.config || {};
    if (err.response?.status !== 401 || original._retry || NO_RETRY.some((p) => original.url?.includes(p))) {
      return Promise.reject(err);
    }
    original._retry = true;
    try {
      refreshing = refreshing || api.post("/auth/refresh").finally(() => { setTimeout(() => { refreshing = null; }, 1500); });
      await refreshing;
      return api(original);
    } catch (_e) {
      localStorage.removeItem("swarna_user");
      if (window.location.pathname !== "/login") window.location.href = "/login";
      return Promise.reject(err);
    }
  }
);
