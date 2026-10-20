import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API_BASE = `${BACKEND_URL}/api`;

export const api = axios.create({
  baseURL: API_BASE,
});

export function errMsg(err, fallback = "Something went wrong") {
  const d = err?.response?.data?.detail;
  if (!d) return fallback;
  if (typeof d === "string") return d;
  if (Array.isArray(d)) return d.map((e) => e?.msg || JSON.stringify(e)).join(" ");
  return d.msg || String(d);
}

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("swarna_access");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (r) => r,
  async (err) => {
    const original = err.config;
    if (err.response?.status === 401 && !original._retry) {
      const refresh = localStorage.getItem("swarna_refresh");
      if (refresh) {
        original._retry = true;
        try {
          const { data } = await axios.post(`${API_BASE}/auth/refresh`, {
            refresh_token: refresh,
          });
          localStorage.setItem("swarna_access", data.access_token);
          localStorage.setItem("swarna_refresh", data.refresh_token);
          original.headers.Authorization = `Bearer ${data.access_token}`;
          return api(original);
        } catch (_e) {
          localStorage.removeItem("swarna_access");
          localStorage.removeItem("swarna_refresh");
          localStorage.removeItem("swarna_user");
          window.location.href = "/login";
        }
      }
    }
    return Promise.reject(err);
  }
);
