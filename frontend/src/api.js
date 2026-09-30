const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000/api";
const SESSION_KEY = "job-talk-session";

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
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
    ...options,
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    if (response.status === 401 && !path.startsWith("/auth/")) {
      sessionStorage.removeItem(SESSION_KEY);
      window.dispatchEvent(new Event("job-talk:unauthorized"));
    }
    throw new Error(body.detail || "Something went wrong");
  }
  return response.status === 204 ? null : response.json();
}

export const api = {
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
  logout: () => request("/auth/logout", { method: "POST" }),
  listChats: () => request("/chats"),
  createChat: () => request("/chats", { method: "POST" }),
  getChat: (chatId) => request(`/chats/${chatId}`),
  sendMessage: (chatId, content) =>
    request(`/chats/${chatId}/messages`, { method: "POST", body: JSON.stringify({ content }) }),
  recommendations: (chatId) => request(`/chats/${chatId}/recommendations`),
  publish: (jobId) => request(`/jobs/${jobId}/publish`, { method: "POST" }),
  closeJob: (jobId) => request(`/jobs/${jobId}/close`, { method: "POST" }),
  applications: (jobId) => request(`/applications?job_id=${jobId}`),
  apply: (jobId, chatId, candidateName, preferredContact) =>
    request(`/jobs/${jobId}/apply`, {
      method: "POST",
      body: JSON.stringify({
        candidate_chat_id: chatId,
        candidate_name: candidateName,
        preferred_contact: preferredContact,
        consent_to_share: true,
      }),
    }),
};

export { SESSION_KEY };
