/**
 * Secure API client for SplitLang React Frontend.
 *
 * - Control #1  : Zero API keys or DB credentials stored in client code
 * - Control #6  : All requests rely on server-verified HttpOnly session cookie
 * - Control #9  : Sends `credentials: "include"` + `X-CSRF-Token` on mutations
 * - Control #16 : Uploads `.split` scripts to server-side `/api/upload` validator
 */

let csrfToken = "";

export function setCsrfToken(token) {
  csrfToken = token || "";
}

async function apiFetch(url, { method = "GET", body = null, isFormData = false } = {}) {
  const headers = {};
  if (!isFormData && body !== null) {
    headers["Content-Type"] = "application/json";
  }
  if (method !== "GET" && csrfToken) {
    headers["X-CSRF-Token"] = csrfToken;
  }

  const res = await fetch(url, {
    method,
    credentials: "include",
    headers,
    body: body === null ? undefined : isFormData ? body : JSON.stringify(body),
  });

  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail =
      typeof data.detail === "string"
        ? data.detail
        : Array.isArray(data.detail)
        ? data.detail.map((d) => d.msg).join("; ")
        : `Request failed (${res.status})`;
    const err = new Error(detail);
    err.status = res.status;
    throw err;
  }
  return data;
}

export const api = {
  getChallenge: () => apiFetch("/api/auth/challenge"),
  getMe: () => apiFetch("/api/auth/me"),
  register: (payload) => apiFetch("/api/auth/register", { method: "POST", body: payload }),
  login: (payload) => apiFetch("/api/auth/login", { method: "POST", body: payload }),
  logout: () => apiFetch("/api/auth/logout", { method: "POST" }),
  getState: () => apiFetch("/api/state"),
  selectGroup: (groupId) => apiFetch(`/api/groups/${groupId}/select`, { method: "POST" }),
  execute: (code, groupId = null) =>
    apiFetch("/api/execute", {
      method: "POST",
      body: groupId ? { code, group_id: groupId } : { code },
    }),
  runDemo: (name) => apiFetch("/api/demo", { method: "POST", body: { name } }),
  uploadSplitFile: (file) => {
    const fd = new FormData();
    fd.append("file", file);
    return apiFetch("/api/upload", { method: "POST", body: fd, isFormData: true });
  },
};
