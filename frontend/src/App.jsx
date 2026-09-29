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
import { api, SESSION_KEY } from "./api";

function Brand() {
  return (
    <div className="brand">
      <div className="brand-mark"><MessageCircleMore size={23} strokeWidth={2.2} /></div>
      <span>job talk</span>
    </div>
  );
}

const DEV_MAILBOX_URL = import.meta.env.VITE_DEV_MAILBOX_URL;

function Entry({ onAuthenticated }) {
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [mode, setMode] = useState("choose");
  const [notice, setNotice] = useState("");
  const [jobs, setJobs] = useState([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const jobId = Number(new URLSearchParams(window.location.search).get("job"));
    if (!Number.isInteger(jobId) || jobId < 1) return undefined;

    let cancelled = false;
    setLoading(true);
    api.publicJob(jobId)
      .then((job) => {
        if (!cancelled) {
          setJobs([job]);
          setMode("jobs");
        }
      })
      .catch((err) => {
        if (!cancelled) setError(err.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => { cancelled = true; };
  }, []);

  async function showJobs() {
    setLoading(true);
    setError("");
    try {
      const availableJobs = await api.publicJobs();
      setJobs(availableJobs);
      setMode("jobs");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function continueAsSeeker(jobId) {
    setLoading(true);
    setError("");
    try {
      onAuthenticated(await api.startGuest(jobId));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function requestCode(event) {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      const response = await api.requestRecruiterCode(email);
      setNotice(response.message);
      setMode("code");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function verifyCode(event) {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      onAuthenticated(await api.verifyRecruiterCode(email, code));
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
          <p>Find your next opportunity or the person who can shape it through a natural conversation.</p>
          <div className="trust-row">
            <div><strong>No CV</strong><span>required</span></div>
            <div><strong>No passwords</strong><span>to remember</span></div>
            <div><strong>Real context</strong><span>behind every match</span></div>
          </div>
        </div>
        <section className="login-card">
          <div className="card-icon"><ArrowRight size={20} /></div>
          {mode === "choose" && <>
            <h2>How are you using Job Talk?</h2>
            <p>Job seekers can begin immediately. Recruiters use an approved email address.</p>
            <div className="entry-actions">
              <button className="entry-choice" type="button" disabled={loading} onClick={showJobs}>
                <UserRoundSearch size={22} /><span><strong>I'm looking for work</strong><small>No account or password</small></span><ChevronRight size={18} />
              </button>
              <button className="entry-choice" type="button" onClick={() => setMode("recruiter")}>
                <BriefcaseBusiness size={22} /><span><strong>I'm hiring</strong><small>Sign in with an email code</small></span><ChevronRight size={18} />
              </button>
            </div>
            {error && <div className="error">{error}</div>}
          </>}
          {mode === "jobs" && <>
            <h2>Choose a role</h2>
            <p>Select a job to start a private, job-specific conversation.</p>
            <div className="entry-jobs">
              {jobs.map((job) => (
                <button className="entry-job" type="button" disabled={loading} key={job.id} onClick={() => continueAsSeeker(job.id)}>
                  <span className="entry-job-copy">
                    <strong>{job.title}</strong>
                    <small>{job.description}</small>
                    <span className="entry-job-action">Apply through chat</span>
                  </span>
                  <ChevronRight size={18} />
                </button>
              ))}
              {!jobs.length && <div className="error">No published jobs are available yet.</div>}
            </div>
            {error && <div className="error">{error}</div>}
            <button className="auth-toggle" type="button" onClick={() => { setMode("choose"); setError(""); }}>Back</button>
          </>}
          {mode === "recruiter" && <form onSubmit={requestCode}>
            <h2>Recruiter access</h2>
            <p>Enter your work email. Approved recruiters receive a short-lived sign-in code.</p>
            <label htmlFor="email">Email address</label>
            <input id="email" type="email" autoComplete="email" placeholder="you@company.com" value={email} onChange={(event) => setEmail(event.target.value)} required />
            {error && <div className="error">{error}</div>}
            <button className="primary full" disabled={loading}>{loading ? "Sending..." : "Send sign-in code"}<ArrowRight size={17} /></button>
            <button className="auth-toggle" type="button" onClick={() => { setMode("choose"); setError(""); }}>Back</button>
          </form>}
          {mode === "code" && <form onSubmit={verifyCode}>
            <h2>Check your email</h2>
            <p>{notice}</p>
            <label htmlFor="code">Six-digit code</label>
            <input id="code" className="code-input" inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]{6}" maxLength="6" placeholder="000000" value={code} onChange={(event) => setCode(event.target.value.replace(/\D/g, ""))} required />
            {DEV_MAILBOX_URL && <a className="mailbox-link" href={DEV_MAILBOX_URL} target="_blank" rel="noreferrer">Open the local email inbox</a>}
            {error && <div className="error">{error}</div>}
            <button className="primary full" disabled={loading || code.length !== 6}>{loading ? "Checking..." : "Continue as recruiter"}<ArrowRight size={17} /></button>
            <button className="auth-toggle" type="button" onClick={() => { setMode("recruiter"); setCode(""); setError(""); }}>Use another email</button>
          </form>}
        </section>
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
      {user.role === "recruiter" && <button className="new-chat" onClick={onNew}><Plus size={18} /> New hiring conversation</button>}
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
        <span>{user.role === "candidate" ? <UserRound size={16} /> : user.email.slice(0, 1).toUpperCase()}</span>
        <div><strong>{user.role === "candidate" ? "Job seeker" : user.email.split("@")[0]}</strong><small>{user.role === "candidate" ? "Private guest session" : user.email}</small></div>
        <button aria-label={user.role === "candidate" ? "Leave session" : "Log out"} onClick={onLogout}><LogOut size={17} /></button>
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
              {chat.intent === "candidate" && <button type="button" disabled={sending} onClick={() => sendPrompt("I have three years of welding and forklift experience in Cape Town.")}>Describe trade experience</button>}
              {chat.intent === "employer" && <button type="button" disabled={sending} onClick={() => sendPrompt("I am looking to hire a welder with welding and forklift experience in Cape Town, with two years of experience.")}>Describe a welder role</button>}
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
  const [session, setSession] = useState(() => {
    try { return JSON.parse(sessionStorage.getItem(SESSION_KEY) || "null"); }
    catch { sessionStorage.removeItem(SESSION_KEY); return null; }
  });
  const [chats, setChats] = useState([]);
  const [chat, setChat] = useState(null);
  const [recommendations, setRecommendations] = useState([]);
  const [error, setError] = useState("");
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const user = session?.user;

  async function loadChat(id) {
    setError("");
    try {
      const selected = await api.getChat(id);
      setChat(selected);
      setRecommendations(selected.intent === "candidate" ? await api.recommendations(id) : []);
      setSidebarOpen(false);
    } catch (err) { setError(err.message); }
  }

  async function loadChats(selectFirst = true) {
    const result = await api.listChats();
    setChats(result);
    if (selectFirst && result.length) await loadChat(result[0].id);
  }

  useEffect(() => {
    const clearExpiredSession = () => {
      setSession(null);
      setChat(null);
      setChats([]);
      setRecommendations([]);
    };
    window.addEventListener("job-talk:unauthorized", clearExpiredSession);
    return () => window.removeEventListener("job-talk:unauthorized", clearExpiredSession);
  }, []);

  useEffect(() => { if (user) loadChats().catch((err) => setError(err.message)); }, [user?.id]);

  function authenticate(nextSession) {
    localStorage.removeItem("job-talk-user");
    sessionStorage.setItem(SESSION_KEY, JSON.stringify(nextSession));
    setSession(nextSession);
  }

  async function newChat() {
    const created = await api.createChat();
    setChat(created);
    setRecommendations([]);
    await loadChats(false);
  }

  async function send(content) {
    try {
      const response = await api.sendMessage(chat.id, content);
      setChat(response.chat);
      setRecommendations(response.recommendations);
      await loadChats(false);
    } catch (err) { setError(err.message); }
  }

  async function publish() {
    try { await api.publish(chat.job_post.id); await loadChat(chat.id); } catch (err) { setError(err.message); }
  }

  async function apply(jobId) {
    try { await api.apply(jobId, chat.id); } catch (err) { setError(err.message); throw err; }
  }

  async function logout() {
    try { await api.logout(); } catch { /* Clear the browser session even when it already expired. */ }
    sessionStorage.removeItem(SESSION_KEY);
    setSession(null);
    setChat(null);
    setChats([]);
    setRecommendations([]);
  }

  if (!user) return <Entry onAuthenticated={authenticate} />;
  return (
    <main className="app-layout">
      <Sidebar user={user} chats={chats} activeId={chat?.id} onSelect={loadChat} onNew={newChat} open={sidebarOpen} onClose={() => setSidebarOpen(false)} onLogout={logout} />
      {sidebarOpen && <div className="backdrop" onClick={() => setSidebarOpen(false)} />}
      {error && <div className="toast" onClick={() => setError("")}>{error}<span>×</span></div>}
      {chat ? <ChatView chat={chat} recommendations={recommendations} onSend={send} onPublish={publish} onApply={apply} onReload={() => loadChat(chat.id)} onMenu={() => setSidebarOpen(true)} /> : <section className="welcome-empty"><Brand /><h1>Every opportunity starts with a conversation.</h1><p>Tell us whether you’re looking for your next role or your next great hire.</p><button className="primary" onClick={newChat}><Plus size={18} /> Start a conversation</button></section>}
    </main>
  );
}
