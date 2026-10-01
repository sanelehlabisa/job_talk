import { useEffect, useRef, useState } from "react";
import {
  ArrowRight,
  Bot,
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

function Entry({ onAuthenticated, showJobsOnOpen = false }) {
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [mode, setMode] = useState("choose");
  const [notice, setNotice] = useState("");
  const [jobs, setJobs] = useState([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const jobId = Number(new URLSearchParams(window.location.search).get("job"));
    const request = Number.isInteger(jobId) && jobId > 0
      ? api.publicJob(jobId).then((job) => [job])
      : showJobsOnOpen ? api.publicJobs() : null;
    if (!request) return undefined;

    let cancelled = false;
    setLoading(true);
    request
      .then((availableJobs) => {
        if (!cancelled) {
          setJobs(availableJobs);
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
  }, [showJobsOnOpen]);

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
            <h2>Available jobs</h2>
            <p>Choose a job to start a new private conversation for that role.</p>
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

function Sidebar({ user, chats, activeId, onSelect, onNew, onBrowseJobs, onLogout, open, onClose }) {
  return (
    <aside className={`sidebar ${open ? "open" : ""}`}>
      <div className="side-head"><Brand /><button className="mobile-close" onClick={onClose}>×</button></div>
      {user.role === "recruiter" && <button className="new-chat" onClick={onNew}><Plus size={18} /> New hiring conversation</button>}
      {user.role === "candidate" && <button className="new-chat" onClick={onBrowseJobs}><Plus size={18} /> Browse other jobs</button>}
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
        <button className="primary" disabled={applied} onClick={onApply}>{applied ? <><Check size={17} /> Submitted</> : <>Review application <ChevronRight size={17} /></>}</button>
        {!applied && <button className="ghost" onClick={onSkip}>Not for me</button>}
      </div>
    </article>
  );
}

function ApplicationReview({ item, profile, onSubmit, onCancel }) {
  const [candidateName, setCandidateName] = useState("");
  const [preferredContact, setPreferredContact] = useState("");
  const [consent, setConsent] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const evidence = Object.entries(profile || {}).slice(0, 8);

  async function submit(event) {
    event.preventDefault();
    if (!consent || submitting) return;
    setSubmitting(true);
    try {
      await onSubmit(candidateName.trim(), preferredContact.trim());
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form className="application-review" onSubmit={submit}>
      <div className="review-heading">
        <div><span>REVIEW BEFORE SHARING</span><h3>{item.job.title}</h3></div>
        <button type="button" className="ghost" onClick={onCancel}>Cancel</button>
      </div>
      <p>The recruiter will receive the structured evidence below, your match breakdown, and the contact details you enter here. Your full chat is not shared.</p>
      <div className="review-evidence">
        {evidence.map(([key, value]) => (
          <div key={key}><strong>{key.replaceAll("_", " ")}</strong><span>{value.evidence || "Included in your structured profile"}</span></div>
        ))}
      </div>
      <label htmlFor="candidate-name">Your name</label>
      <input id="candidate-name" value={candidateName} onChange={(event) => setCandidateName(event.target.value)} minLength="2" maxLength="100" autoComplete="name" required />
      <label htmlFor="candidate-contact">Preferred email or phone number</label>
      <input id="candidate-contact" value={preferredContact} onChange={(event) => setPreferredContact(event.target.value)} minLength="3" maxLength="320" autoComplete="email" required />
      <label className="consent-check">
        <input type="checkbox" checked={consent} onChange={(event) => setConsent(event.target.checked)} required />
        <span>I agree to share this application and my contact details with the recruiter for this role.</span>
      </label>
      <button className="primary full" disabled={!consent || submitting}>{submitting ? "Submitting…" : "Submit application"}<ArrowRight size={17} /></button>
    </form>
  );
}

function CandidateComparison({ applications, status, onCloseJob }) {
  const visible = status === "closed" ? applications.slice(0, 5) : applications;
  let previousScore = null;
  let previousRank = 0;

  return (
    <section className="candidate-comparison">
      <div className="comparison-heading">
        <div>
          <span>SUBMITTED CANDIDATES</span>
          <h2>{applications.length} application{applications.length === 1 ? "" : "s"}</h2>
        </div>
        {status === "published" && <button className="close-job" type="button" onClick={onCloseJob}>Close recruitment</button>}
      </div>
      <p className="decision-support">Scores organize candidate-provided evidence against this role's weighted criteria. They support recruiter review and are not hiring decisions.</p>
      {!visible.length && <div className="candidate-empty">No submitted applications yet. Candidates will appear here in one comparable format.</div>}
      {!!visible.length && <div className="comparison-grid">
        {visible.map((application, index) => {
          const profile = application.candidate_profile || {};
          const details = profile.candidate_details || {};
          const criteria = Object.entries(application.match_result?.criteria || {});
          const score = Math.round((application.match_result?.overall_score || 0) * 100);
          const skillEvidence = Object.entries(profile)
            .filter(([key]) => !["candidate_details", "consent", "experience", "location", "availability", "working_arrangement", "education", "projects"].includes(key))
            .map(([key, value]) => `${key.replaceAll("_", " ")}: ${value.evidence}`)
            .join(" ");
          const evidence = [
            ["experience", profile.experience?.evidence],
            ["skills", skillEvidence],
            ["location", profile.location?.evidence],
            ["availability", profile.availability?.evidence],
          ];
          const contact = details.preferred_contact || "Contact not provided";
          const contactHref = contact.includes("@") ? `mailto:${contact}` : `tel:${contact.replace(/[^+\d]/g, "")}`;
          if (score !== previousScore) previousRank = index + 1;
          previousScore = score;
          return (
            <article className="candidate-card" key={application.id}>
              <div className="candidate-card-head">
                <div className="candidate-rank">{status === "closed" ? `#${previousRank}` : <UserRound size={17} />}</div>
                <div><h3>{details.name || "Candidate"}</h3><a href={contactHref}>{contact}</a></div>
                <div className="score"><strong>{score}%</strong><span>match</span></div>
              </div>
              <div className="candidate-evidence">
                <strong>Profile evidence</strong>
                {evidence.map(([key, value]) => (
                  <div key={key}><span>{key}</span><p>{value || "No direct evidence was provided."}</p></div>
                ))}
              </div>
              <div className="criterion-list">
                <strong>Criterion breakdown</strong>
                {criteria.map(([key, value]) => {
                  const criterionEvidence = profile[key]?.evidence;
                  return (
                    <div className={value.score < 0.5 ? "criterion-gap" : ""} key={key}>
                      <div><span>{key.replaceAll("_", " ")}</span><b>{Math.round(value.score * 100)}% · weight {Math.round(value.weight * 100)}%</b></div>
                      <p>{value.reason}</p>
                      <small>{criterionEvidence ? `Evidence: ${criterionEvidence}` : "Gap: no direct candidate evidence was captured."}</small>
                    </div>
                  );
                })}
              </div>
            </article>
          );
        })}
      </div>}
      {status === "closed" && applications.length > 0 && <p className="shortlist-note">Recruitment is closed. Showing up to five candidates ranked by the saved weighted scores; equal scores share a rank.</p>}
    </section>
  );
}

function ChatView({ chat, recommendations, applications, onSend, onPublish, onCloseJob, onApply, onReload, onMenu }) {
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const [applied, setApplied] = useState({});
  const [skipped, setSkipped] = useState({});
  const [reviewing, setReviewing] = useState(null);
  const bottomRef = useRef(null);
  const submitted = chat?.status === "submitted";
  const statusLabel = submitted ? "Application submitted" : chat?.status === "published" ? "Published" : chat?.status === "closed" ? "Closed" : chat?.status === "draft" ? "Draft" : "Live profile";

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

  async function apply(candidateName, preferredContact) {
    await onApply(reviewing.job.id, candidateName, preferredContact);
    setApplied((value) => ({ ...value, [reviewing.job.id]: true }));
    setReviewing(null);
    await onReload();
  }

  return (
    <section className="chat-shell">
      <header className="chat-header">
        <button className="menu-button" onClick={onMenu}>☰</button>
        <div><span className={`intent-dot ${chat.intent || "new"}`} /> <strong>{chat.intent === "employer" ? (chat.job_post?.title || "Build your role") : chat.intent === "candidate" ? (chat.target_job?.title || "Find your next role") : "New conversation"}</strong><small>{chat.intent ? "Profile updates as you talk" : "Let’s work out where to begin"}</small></div>
        <div className="status-pill"><span /> {statusLabel}</div>
      </header>
      <div className="messages">
        <div className="conversation-inner">
          <div className="date-rule"><span>Today</span></div>
          {chat.messages.map((message) => (
            <div className={`message-wrap ${message.sender}`} key={message.id}>
              {message.sender === "assistant" && <div className="avatar assistant-avatar" role="img" aria-label="Job Talk assistant"><Bot size={16} strokeWidth={2.2} aria-hidden="true" /></div>}
              <div className="message"><p>{message.content}</p><time>{new Date(message.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</time></div>
              {message.sender === "user" && <div className="avatar user-avatar" role="img" aria-label="You"><UserRound size={16} strokeWidth={2.2} aria-hidden="true" /></div>}
            </div>
          ))}
          {!chat.messages.some((message) => message.sender === "user") && (
            <div className="starter-prompts">
              <span>TRY AN EXAMPLE</span>
              {chat.intent === "candidate" && <button type="button" disabled={sending} onClick={() => sendPrompt("I have three years of welding and forklift experience in Cape Town.")}>Describe trade experience</button>}
              {chat.intent === "employer" && <button type="button" disabled={sending} onClick={() => sendPrompt("I am looking to hire a welder with welding and forklift experience in Cape Town, with two years of experience.")}>Describe a welder role</button>}
            </div>
          )}
          {sending && <div className="message-wrap assistant"><div className="avatar assistant-avatar" role="img" aria-label="Job Talk assistant"><Bot size={16} strokeWidth={2.2} aria-hidden="true" /></div><div className="typing"><i /><i /><i /></div></div>}
          <ProfileChips profile={chat.profile} />
          {chat.intent === "employer" && chat.job_post && <CandidateComparison applications={applications} status={chat.status} onCloseJob={onCloseJob} />}
          {!!recommendations.length && (
            <div className="recommendations">
              <div className="recommendation-heading"><span>YOUR BEST MATCHES</span><small>{recommendations.length} published role{recommendations.length === 1 ? "" : "s"}</small></div>
              {recommendations.map((item) => <Recommendation key={item.job.id} item={item} applied={submitted || applied[item.job.id]} skipped={skipped[item.job.id]} onApply={() => setReviewing(item)} onSkip={() => setSkipped((value) => ({ ...value, [item.job.id]: true }))} />)}
              {reviewing && !submitted && <ApplicationReview item={reviewing} profile={chat.profile} onSubmit={apply} onCancel={() => setReviewing(null)} />}
            </div>
          )}
          <div ref={bottomRef} />
        </div>
      </div>
      {chat.can_publish && <div className="publish-bar"><div><strong>Your role is ready</strong><span>Type “publish the job” or use this button.</span></div><button className="primary" onClick={onPublish}>Publish job <ArrowRight size={17} /></button></div>}
      {chat.status === "closed" ? <div className="submitted-bar"><Check size={17} /><span><strong>Recruitment closed</strong>New applications are stopped and submitted snapshots are preserved.</span></div> : submitted ? <div className="submitted-bar"><Check size={17} /><span><strong>Application submitted</strong>Your approved snapshot is now frozen for the recruiter.</span></div> : <form className="composer" onSubmit={submit}>
        <div className="composer-box">
          <textarea rows="1" value={text} onChange={(e) => setText(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) submit(e); }} placeholder={chat.intent === "employer" ? "Describe the role or change a requirement…" : chat.intent === "candidate" ? "Tell me about your experience…" : "Type your answer…"} />
          <button aria-label="Send message" disabled={!text.trim() || sending}><Send size={18} /></button>
        </div>
        <small>Job Talk turns your conversation into a structured profile.</small>
      </form>}
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
  const [applications, setApplications] = useState([]);
  const [error, setError] = useState("");
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [showJobsOnEntry, setShowJobsOnEntry] = useState(false);
  const user = session?.user;

  async function loadChat(id) {
    setError("");
    try {
      const selected = await api.getChat(id);
      setChat(selected);
      setRecommendations(selected.intent === "candidate" ? await api.recommendations(id) : []);
      setApplications(selected.intent === "employer" && selected.job_post ? await api.applications(selected.job_post.id) : []);
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
      setApplications([]);
      setShowJobsOnEntry(false);
    };
    window.addEventListener("job-talk:unauthorized", clearExpiredSession);
    return () => window.removeEventListener("job-talk:unauthorized", clearExpiredSession);
  }, []);

  useEffect(() => { if (user) loadChats().catch((err) => setError(err.message)); }, [user?.id]);

  function authenticate(nextSession) {
    localStorage.removeItem("job-talk-user");
    sessionStorage.setItem(SESSION_KEY, JSON.stringify(nextSession));
    setShowJobsOnEntry(false);
    setSession(nextSession);
  }

  async function newChat() {
    const created = await api.createChat();
    setChat(created);
    setRecommendations([]);
    setApplications([]);
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

  async function closeJob() {
    if (!window.confirm("Close this recruitment and stop new applications?")) return;
    try { await api.closeJob(chat.job_post.id); await loadChat(chat.id); } catch (err) { setError(err.message); }
  }

  async function apply(jobId, candidateName, preferredContact) {
    try { await api.apply(jobId, chat.id, candidateName, preferredContact); } catch (err) { setError(err.message); throw err; }
  }

  async function endSession(showJobs = false) {
    try { await api.logout(); } catch { /* Clear the browser session even when it already expired. */ }
    if (showJobs) window.history.replaceState({}, "", window.location.pathname);
    sessionStorage.removeItem(SESSION_KEY);
    setShowJobsOnEntry(showJobs);
    setSession(null);
    setChat(null);
    setChats([]);
    setRecommendations([]);
    setApplications([]);
  }

  if (!user) return <Entry onAuthenticated={authenticate} showJobsOnOpen={showJobsOnEntry} />;
  return (
    <main className="app-layout">
      <Sidebar user={user} chats={chats} activeId={chat?.id} onSelect={loadChat} onNew={newChat} onBrowseJobs={() => endSession(true)} open={sidebarOpen} onClose={() => setSidebarOpen(false)} onLogout={() => endSession(false)} />
      {sidebarOpen && <div className="backdrop" onClick={() => setSidebarOpen(false)} />}
      {error && <div className="toast" onClick={() => setError("")}>{error}<span>×</span></div>}
      {chat ? <ChatView chat={chat} recommendations={recommendations} applications={applications} onSend={send} onPublish={publish} onCloseJob={closeJob} onApply={apply} onReload={() => loadChat(chat.id)} onMenu={() => setSidebarOpen(true)} /> : <section className="welcome-empty"><Brand /><h1>Every opportunity starts with a conversation.</h1><p>Tell us whether you’re looking for your next role or your next great hire.</p><button className="primary" onClick={newChat}><Plus size={18} /> Start a conversation</button></section>}
    </main>
  );
}
