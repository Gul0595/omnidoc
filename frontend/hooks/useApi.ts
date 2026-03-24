/**
 * hooks/useApi.ts — Complete API client for OmniDoc
 *
 * CREDENTIAL NOTE:
 * Set NEXT_PUBLIC_API_URL in frontend/.env.local
 *   Development:  NEXT_PUBLIC_API_URL=http://localhost:8000
 *   Production:   NEXT_PUBLIC_API_URL=https://your-app.onrender.com
 */
import axios from "axios";

const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export const api = axios.create({ baseURL: `${BASE}/api/v1` });

// Attach JWT to every request
api.interceptors.request.use((cfg) => {
  const token = typeof window !== "undefined"
    ? localStorage.getItem("omnidoc_token") : null;
  if (token) cfg.headers.Authorization = `Bearer ${token}`;
  return cfg;
});

// ── Auth ──────────────────────────────────────────────────────────────────────
export const login = async (email: string, password: string) => {
  const form = new FormData();
  form.append("username", email);
  form.append("password", password);
  const res = await api.post("/auth/token", form);
  localStorage.setItem("omnidoc_token", res.data.access_token);
  return res.data;
};

export const register = async (data: {
  email: string; password: string;
  full_name: string; organisation: string;
}) => {
  const res = await api.post("/auth/register", data);
  localStorage.setItem("omnidoc_token", res.data.access_token);
  return res.data;
};

export const logout = () => {
  localStorage.removeItem("omnidoc_token");
};

export const isLoggedIn = () =>
  typeof window !== "undefined" && !!localStorage.getItem("omnidoc_token");

export const getMe = () => api.get("/auth/me").then(r => r.data);

// ── Sectors ───────────────────────────────────────────────────────────────────
export const getSectors = () => api.get("/sectors").then(r => r.data);
export const getSectorConfig = (id: string) =>
  api.get(`/sectors/${id}`).then(r => r.data);

// ── Workspaces ────────────────────────────────────────────────────────────────
export const getWorkspaces = () => api.get("/workspaces").then(r => r.data);
export const createWorkspace = (data: {
  name: string; description: string; sector_id: string;
}) => api.post("/workspaces", data).then(r => r.data);
export const deleteWorkspace = (id: string) =>
  api.delete(`/workspaces/${id}`).then(r => r.data);
export const getWorkspaceStats = (id: string) =>
  api.get(`/workspaces/${id}/stats`).then(r => r.data);

// ── Members ───────────────────────────────────────────────────────────────────
export const getMembers = (wsId: string) =>
  api.get(`/workspaces/${wsId}/members`).then(r => r.data);
export const inviteMember = (wsId: string, email: string, role: string) =>
  api.post(`/workspaces/${wsId}/members`, { email, role }).then(r => r.data);
export const changeMemberRole = (wsId: string, userId: string, role: string) =>
  api.patch(`/workspaces/${wsId}/members/${userId}`, { role }).then(r => r.data);
export const removeMember = (wsId: string, userId: string) =>
  api.delete(`/workspaces/${wsId}/members/${userId}`).then(r => r.data);

// ── Documents ─────────────────────────────────────────────────────────────────
export const getDocuments = (wsId: string) =>
  api.get(`/documents/${wsId}`).then(r => r.data);

export const uploadDocument = async (
  wsId: string, file: File,
  onProgress?: (pct: number) => void
) => {
  const form = new FormData();
  form.append("file", file);
  return api.post(`/documents/${wsId}/upload`, form, {
    headers: { "Content-Type": "multipart/form-data" },
    onUploadProgress: e => {
      if (onProgress && e.total) {
        onProgress(Math.round((e.loaded / e.total) * 100));
      }
    },
  }).then(r => r.data);
};

export const deleteDocument = (wsId: string, docId: string) =>
  api.delete(`/documents/${wsId}/${docId}`).then(r => r.data);

// ── Streaming query ───────────────────────────────────────────────────────────
export const streamQuery = async (
  question:     string,
  workspaceId:  string,
  onStep:       (agent: string, detail: string) => void,
  onIntent:     (intent: string) => void,
  onToken:      (token: string) => void,
  onDone:       (queryId: string, llmUsed: boolean, provider: string) => void,
  onError:      (err: string) => void,
) => {
  const token = typeof window !== "undefined"
    ? localStorage.getItem("omnidoc_token") : null;

  try {
    const res = await fetch(`${BASE}/api/v1/query/ask`, {
      method:  "POST",
      headers: {
        "Content-Type":  "application/json",
        "Authorization": `Bearer ${token}`,
      },
      body: JSON.stringify({ question, workspace_id: workspaceId }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Request failed" }));
      onError(err.detail || "Query failed");
      return;
    }

    const reader = res.body?.getReader();
    if (!reader) { onError("Stream not available"); return; }

    const dec = new TextDecoder();
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      for (const line of dec.decode(value).split("\n")) {
        if (!line.startsWith("data: ")) continue;
        try {
          const e = JSON.parse(line.slice(6));
          if (e.type === "agent_step") onStep(e.agent, e.detail);
          if (e.type === "intent")     onIntent(e.intent);
          if (e.type === "token")      onToken(e.content);
          if (e.type === "done")       onDone(e.query_id || "", e.llm_used ?? true, e.llm_provider || "");
        } catch { /* ignore parse errors */ }
      }
    }
  } catch (err: any) {
    onError(err.message || "Network error");
  }
};

// ── History + Feedback ────────────────────────────────────────────────────────
export const getHistory = (wsId: string) =>
  api.get(`/query/history/${wsId}`).then(r => r.data);

export const submitFeedback = (queryId: string, rating: number) =>
  api.post("/query/feedback", { query_id: queryId, rating }).then(r => r.data);

// ── Admin ─────────────────────────────────────────────────────────────────────
export const getLLMStatus = () => api.get("/admin/llm-status").then(r => r.data);
export const getAuditLog  = () => api.get("/admin/audit").then(r => r.data);
export const getAdminStats = () => api.get("/admin/stats").then(r => r.data);
