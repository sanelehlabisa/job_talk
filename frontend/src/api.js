const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000/api";
const SESSION_KEY = "job-talk-session";
const VISITOR_KEY = "job-talk-visitor";

function visitorId() {
  let value = localStorage.getItem(VISITOR_KEY);
  if (!value || !/^[A-Za-z0-9_-]{16,100}$/.test(value)) {
    value = crypto.randomUUID?.() || `${Date.now()}-${Math.random().toString(36).slice(2)}`;
    localStorage.setItem(VISITOR_KEY, value);
  }
  return value;
}

function accessToken() {
  try {
    return JSON.parse(sessionStorage.getItem(SESSION_KEY) || "null")?.access_token;
  } catch {
    sessionStorage.removeItem(SESSION_KEY);
    return null;
  }
}

async function request(path, options = {}) {
  const token = accessToken();
  const response = await fetch(`${API_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      "X-Job-Talk-Visitor": visitorId(),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
    ...options,
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    if (response.status === 401 && (!path.startsWith("/auth/") || path === "/auth/me")) {
      sessionStorage.removeItem(SESSION_KEY);
      window.dispatchEvent(new Event("job-talk:unauthorized"));
    }
    const error = new Error(body.detail || "Something went wrong");
    error.status = response.status;
    throw error;
  }
  return response.status === 204 ? null : response.json();
}

export const api = {
  visit: () => request("/experiment/visit", { method: "POST" }),
  publicJobs: () => request("/public/jobs"),
  publicJob: (jobId) => request(`/public/jobs/${jobId}`),
  startGuest: (jobId) =>
    request("/auth/guest", { method: "POST", body: JSON.stringify({ job_id: jobId }) }),
  requestRecruiterCode: (email) =>
    request("/auth/recruiter/request-code", {
      method: "POST",
      body: JSON.stringify({ email }),
    }),
  verifyRecruiterCode: (email, code) =>
    request("/auth/recruiter/verify-code", {
      method: "POST",
      body: JSON.stringify({ email, code }),
    }),
  me: () => request("/auth/me"),
  jobInterest: (jobId) => request(`/admin/jobs/${jobId}/interest`),
  logout: () => request("/auth/logout", { method: "POST" }),
  deleteAccount: () => request("/account", { method: "DELETE" }),
  listChats: () => request("/chats"),
  jobTemplates: () => request("/job-templates"),
  createChat: (templateId, source) => request("/chats", {
    method: "POST",
    body: JSON.stringify(templateId ? { template_id: templateId, source } : {}),
  }),
  getChat: (chatId) => request(`/chats/${chatId}`),
  editApplicationField: (chatId, field) => request(`/chats/${chatId}/application/field`, { method: "PUT", body: JSON.stringify(field) }),
  editDraftField: (chatId, field) => request(`/chats/${chatId}/draft/field`, { method: "PUT", body: JSON.stringify(field) }),
  removeDraftField: (chatId, key) => request(`/chats/${chatId}/draft/fields/${encodeURIComponent(key)}`, { method: "DELETE" }),
  finishDraft: (chatId) => request(`/chats/${chatId}/draft/done`, { method: "POST" }),
  selectJob: (chatId, jobId) => request(`/chats/${chatId}/select-job`, {
    method: "POST", body: JSON.stringify({ job_id: jobId }),
  }),
  sendMessage: (chatId, content) =>
    request(`/chats/${chatId}/messages`, { method: "POST", body: JSON.stringify({ content }) }),
  recommendations: (chatId) => request(`/chats/${chatId}/recommendations`),
  publish: (jobId) => request(`/jobs/${jobId}/publish`, { method: "POST" }),
  closeJob: (jobId) => request(`/jobs/${jobId}/close`, { method: "POST" }),
  applications: (jobId) => request(jobId ? `/applications?job_id=${jobId}` : "/applications"),
  apply: (jobId, chatId, candidateName, candidateLocation, preferredContact, criteriaVersion) =>
    request(`/jobs/${jobId}/apply`, {
      method: "POST",
      body: JSON.stringify({
        candidate_chat_id: chatId,
        candidate_name: candidateName,
        candidate_location: candidateLocation,
        preferred_contact: preferredContact,
        consent_to_share: true,
        criteria_version: criteriaVersion,
      }),
    }),
  feedback: (kind, contextId, useful) =>
    request("/experiment/feedback", {
      method: "POST",
      body: JSON.stringify({ kind, context_id: contextId, useful }),
    }),
};

export { SESSION_KEY, VISITOR_KEY };
