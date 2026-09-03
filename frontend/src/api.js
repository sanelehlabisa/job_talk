const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000/api";

async function request(path, options = {}) {
  const response = await fetch(`${API_URL}${path}`, {
    headers: { "Content-Type": "application/json", ...options.headers },
    ...options,
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || "Something went wrong");
  }
  return response.json();
}

export const api = {
  login: (email) => request("/auth/login", { method: "POST", body: JSON.stringify({ email }) }),
  listChats: (userId) => request(`/chats?user_id=${userId}`),
  createChat: (userId) => request(`/chats?user_id=${userId}`, { method: "POST" }),
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
