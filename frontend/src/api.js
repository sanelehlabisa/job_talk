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
    if (response.status === 401 && !path.startsWith("/auth/login")) {
      sessionStorage.removeItem(SESSION_KEY);
      window.dispatchEvent(new Event("job-talk:unauthorized"));
    }
    throw new Error(body.detail || "Something went wrong");
  }
  return response.status === 204 ? null : response.json();
}

export const api = {
  register: (email, password) =>
    request("/auth/register", { method: "POST", body: JSON.stringify({ email, password }) }),
  login: (email, password) =>
    request("/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }),
  me: () => request("/auth/me"),
  logout: () => request("/auth/logout", { method: "POST" }),
  listChats: () => request("/chats"),
  createChat: () => request("/chats", { method: "POST" }),
  getChat: (chatId) => request(`/chats/${chatId}`),
  sendMessage: (chatId, content) =>
    request(`/chats/${chatId}/messages`, { method: "POST", body: JSON.stringify({ content }) }),
  recommendations: (chatId) => request(`/chats/${chatId}/recommendations`),
  publish: (jobId) => request(`/jobs/${jobId}/publish`, { method: "POST" }),
  apply: (jobId, chatId) =>
    request(`/jobs/${jobId}/apply`, {
      method: "POST",
      body: JSON.stringify({ candidate_chat_id: chatId }),
    }),
};

export { SESSION_KEY };
