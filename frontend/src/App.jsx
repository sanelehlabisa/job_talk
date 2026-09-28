import { useEffect, useRef, useState } from "react";
import {
  ArrowRight,
  BriefcaseBusiness,
  Check,
  ChevronRight,
  LogOut,
  MessageCircleMore,
  Plus,
  Send,
  Sparkles,
  UserRound,
  UserRoundSearch,
} from "lucide-react";
import { api } from "./api";

function Brand() {
  return (
    <div className="brand">
      <div className="brand-mark"><MessageCircleMore size={23} strokeWidth={2.2} /></div>
      <span>job talk</span>
    </div>
  );
}

function Login({ onLogin }) {
  const [email, setEmail] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(event) {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      onLogin(await api.login(email));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="login-page">
      <nav><Brand /><span className="nav-note">A better way to meet</span></nav>
      <section className="login-grid">
        <div className="hero-copy">
          <div className="eyebrow"><Sparkles size={15} /> Work starts with a conversation</div>
          <h1>Skip the forms.<br /><em>Tell your story.</em></h1>
          <p>Find your next opportunity—or the person who can shape it—through a natural conversation.</p>
          <div className="trust-row">
            <div><strong>No CV</strong><span>required</span></div>
            <div><strong>No forms</strong><span>to wrestle with</span></div>
            <div><strong>Real context</strong><span>behind every match</span></div>
          </div>
        </div>
        <form className="login-card" onSubmit={submit}>
          <div className="card-icon"><ArrowRight size={20} /></div>
          <h2>Let’s get talking</h2>
          <p>Enter your email to continue. New here? We’ll create your space automatically.</p>
          <label htmlFor="email">Email address</label>
          <input id="email" type="email" placeholder="you@example.com" value={email} onChange={(e) => setEmail(e.target.value)} required />
          {error && <div className="error">{error}</div>}
          <button className="primary full" disabled={loading}>{loading ? "Opening…" : "Continue"}<ArrowRight size={17} /></button>
          <small>No password needed for this demo.</small>
        </form>
      </section>
      <footer className="brand-credit">
        <img src="/branding/roventics-robot.svg" alt="" />
        <span>A Roventics project</span>
      </footer>
    </main>
  );
}

function Sidebar({ user, chats, activeId, onSelect, onNew, onLogout, open, onClose }) {
  return (
    <aside className={`sidebar ${open ? "open" : ""}`}>
      <div className="side-head"><Brand /><button className="mobile-close" onClick={onClose}>×</button></div>
      <button className="new-chat" onClick={onNew}><Plus size={18} /> New conversation</button>
      <div className="chat-list-label">YOUR CONVERSATIONS</div>
      <div className="chat-list">
        {chats.map((item, index) => (
          <button className={`chat-row ${item.id === activeId ? "active" : ""}`} key={item.id} onClick={() => onSelect(item.id)}>
            <span className="chat-type">{item.intent === "employer" ? <BriefcaseBusiness size={17} /> : item.intent === "candidate" ? <UserRoundSearch size={17} /> : <MessageCircleMore size={17} />}</span>
            <span><strong>{item.intent === "employer" ? "Hiring conversation" : item.intent === "candidate" ? "Job search" : "New conversation"}</strong><small>{index === 0 ? "Most recent" : new Date(item.created_at).toLocaleDateString()}</small></span>
          </button>
        ))}
        {!chats.length && <p className="empty-side">Your conversations will live here.</p>}
      </div>
      <div className="user-panel">
        <span>{user.email.slice(0, 1).toUpperCase()}</span>
        <div><strong>{user.email.split("@")[0]}</strong><small>{user.email}</small></div>
        <button aria-label="Log out" onClick={onLogout}><LogOut size={17} /></button>
      </div>
    </aside>
  );
}

function ProfileChips({ profile }) {
  const items = Object.keys(profile || {}).slice(0, 7);
  if (!items.length) return null;
  return <div className="profile-chips">{items.map((item) => <span key={item}>{item.replaceAll("_", " ")} <Check size={12} /></span>)}</div>;
}

function Recommendation({ item, onApply, applied, skipped, onSkip }) {
  const score = Math.round(item.match_score * 100);
  if (skipped) return null;
  return (
    <article className="job-card">
      <div className="job-card-top">
        <div className="job-logo">{item.job.title.slice(0, 1)}</div>
        <div><h3>{item.job.title}</h3><span>New opportunity</span></div>
        <div className="score"><strong>{score}%</strong><span>match</span></div>
      </div>
      <p>{item.explanation}</p>
      <div className="criteria-row">
        {Object.entries(item.criteria || {}).slice(0, 4).map(([key, value]) => <span key={key}>{key.replaceAll("_", " ")} {Math.round(value.score * 100)}%</span>)}
      </div>
      <div className="job-actions">
        <button className="primary" disabled={applied} onClick={onApply}>{applied ? <><Check size={17} /> Applied</> : <>Apply now <ChevronRight size={17} /></>}</button>
        {!applied && <button className="ghost" onClick={onSkip}>Not for me</button>}
      </div>
    </article>
  );
}

function ChatView({ chat, recommendations, onSend, onPublish, onApply, onReload, onMenu }) {
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const [applied, setApplied] = useState({});
  const [skipped, setSkipped] = useState({});
  const bottomRef = useRef(null);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [chat?.messages, recommendations]);
  if (!chat) return <div className="loading-screen"><div className="pulse" />Opening conversation…</div>;

  async function sendPrompt(message) {
    if (sending) return;
    setSending(true);
    try { await onSend(message); } finally { setSending(false); }
  }

  async function submit(event) {
    event.preventDefault();
    if (!text.trim() || sending) return;
    const message = text.trim();
    setText("");
    await sendPrompt(message);
  }

  async function apply(jobId) {
    await onApply(jobId);
    setApplied((value) => ({ ...value, [jobId]: true }));
    await onReload();
  }

  return (
    <section className="chat-shell">
      <header className="chat-header">
        <button className="menu-button" onClick={onMenu}>☰</button>
        <div><span className={`intent-dot ${chat.intent || "new"}`} /> <strong>{chat.intent === "employer" ? "Build your role" : chat.intent === "candidate" ? "Find your next role" : "New conversation"}</strong><small>{chat.intent ? "Profile updates as you talk" : "Let’s work out where to begin"}</small></div>
        <div className="status-pill"><span /> Live profile</div>
      </header>
      <div className="messages">
        <div className="conversation-inner">
          <div className="date-rule"><span>Today</span></div>
          {chat.messages.map((message) => (
            <div className={`message-wrap ${message.sender}`} key={message.id}>
              {message.sender === "assistant" && <div className="avatar assistant-avatar" role="img" aria-label="Job Talk assistant"><img src="/branding/roventics-robot.svg" alt="" /></div>}
              <div className="message"><p>{message.content}</p><time>{new Date(message.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</time></div>
              {message.sender === "user" && <div className="avatar user-avatar" role="img" aria-label="You"><UserRound size={16} /></div>}
            </div>
          ))}
          {!chat.messages.some((message) => message.sender === "user") && (
            <div className="starter-prompts">
              <span>TRY AN EXAMPLE</span>
              <button type="button" disabled={sending} onClick={() => sendPrompt("I am looking for a job. I have three years of welding and forklift experience in Cape Town.")}>Find trade work</button>
              <button type="button" disabled={sending} onClick={() => sendPrompt("I am looking to hire a welder with welding and forklift experience in Cape Town, with two years of experience.")}>Hire a welder</button>
            </div>
          )}
          {sending && <div className="message-wrap assistant"><div className="avatar assistant-avatar" role="img" aria-label="Job Talk assistant"><img src="/branding/roventics-robot.svg" alt="" /></div><div className="typing"><i /><i /><i /></div></div>}
          <ProfileChips profile={chat.profile} />
          {!!recommendations.length && (
            <div className="recommendations">
              <div className="recommendation-heading"><span>YOUR BEST MATCHES</span><small>{recommendations.length} published role{recommendations.length === 1 ? "" : "s"}</small></div>
              {recommendations.map((item) => <Recommendation key={item.job.id} item={item} applied={applied[item.job.id]} skipped={skipped[item.job.id]} onApply={() => apply(item.job.id)} onSkip={() => setSkipped((value) => ({ ...value, [item.job.id]: true }))} />)}
            </div>
          )}
          <div ref={bottomRef} />
        </div>
      </div>
      {chat.can_publish && <div className="publish-bar"><div><strong>Your role is ready</strong><span>You can keep refining it after publishing.</span></div><button className="primary" onClick={onPublish}>Publish job <ArrowRight size={17} /></button></div>}
      <form className="composer" onSubmit={submit}>
        <div className="composer-box">
          <textarea rows="1" value={text} onChange={(e) => setText(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) submit(e); }} placeholder={chat.intent === "employer" ? "Describe the role or change a requirement…" : chat.intent === "candidate" ? "Tell me about your experience…" : "Type your answer…"} />
          <button aria-label="Send message" disabled={!text.trim() || sending}><Send size={18} /></button>
        </div>
        <small>Job Talk turns your conversation into a structured profile.</small>
      </form>
    </section>
  );
}

export default function App() {
  const [user, setUser] = useState(() => JSON.parse(localStorage.getItem("job-talk-user") || "null"));
  const [chats, setChats] = useState([]);
  const [chat, setChat] = useState(null);
  const [recommendations, setRecommendations] = useState([]);
  const [error, setError] = useState("");
  const [sidebarOpen, setSidebarOpen] = useState(false);

  async function loadChat(id) {
    setError("");
    try {
      const selected = await api.getChat(id);
      setChat(selected);
      setRecommendations(selected.intent === "candidate" ? await api.recommendations(id) : []);
      setSidebarOpen(false);
    } catch (err) { setError(err.message); }
  }

  async function loadChats(currentUser, selectFirst = true) {
    const result = await api.listChats(currentUser.id);
    setChats(result);
    if (selectFirst && result.length) await loadChat(result[0].id);
  }

  useEffect(() => { if (user) loadChats(user).catch((err) => setError(err.message)); }, [user]);

  function login(nextUser) {
    localStorage.setItem("job-talk-user", JSON.stringify(nextUser));
    setUser(nextUser);
  }

  async function newChat() {
    const created = await api.createChat(user.id);
    setChat(created);
    setRecommendations([]);
    await loadChats(user, false);
  }

  async function send(content) {
    try {
      const response = await api.sendMessage(chat.id, content);
      setChat(response.chat);
      setRecommendations(response.recommendations);
      await loadChats(user, false);
    } catch (err) { setError(err.message); }
  }

  async function publish() {
    try { await api.publish(chat.job_post.id); await loadChat(chat.id); } catch (err) { setError(err.message); }
  }

  async function apply(jobId) {
    try { await api.apply(jobId, chat.id); } catch (err) { setError(err.message); throw err; }
  }

  if (!user) return <Login onLogin={login} />;
  return (
    <main className="app-layout">
      <Sidebar user={user} chats={chats} activeId={chat?.id} onSelect={loadChat} onNew={newChat} open={sidebarOpen} onClose={() => setSidebarOpen(false)} onLogout={() => { localStorage.removeItem("job-talk-user"); setUser(null); setChat(null); }} />
      {sidebarOpen && <div className="backdrop" onClick={() => setSidebarOpen(false)} />}
      {error && <div className="toast" onClick={() => setError("")}>{error}<span>×</span></div>}
      {chat ? <ChatView chat={chat} recommendations={recommendations} onSend={send} onPublish={publish} onApply={apply} onReload={() => loadChat(chat.id)} onMenu={() => setSidebarOpen(true)} /> : <section className="welcome-empty"><Brand /><h1>Every opportunity starts with a conversation.</h1><p>Tell us whether you’re looking for your next role or your next great hire.</p><button className="primary" onClick={newChat}><Plus size={18} /> Start a conversation</button></section>}
    </main>
  );
}
