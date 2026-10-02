import { Component, useEffect, useRef, useState } from "react";
import {
  ArrowRight,
  Bot,
  BriefcaseBusiness,
  Check,
  ChevronRight,
  CircleMinus,
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
const SUPPORT_EMAIL = import.meta.env.VITE_SUPPORT_EMAIL || "support@example.com";

function PrivacyPage() {
  return (
    <main className="policy-page">
      <div className="policy-card">
        <a className="policy-back" href="/"><Brand /> <span>Back to Job Talk</span></a>
        <p className="eyebrow">EARLY EXPERIMENT</p>
        <h1>Privacy, safety, and acceptable use</h1>
        <p>Job Talk helps a candidate describe work experience for one role and helps that role's recruiter compare submitted evidence. It is an early, free experiment.</p>
        <h2>What we store</h2>
        <p>We store the conversation, its structured skills and experience, the selected job, and the match explanation. A candidate's name and contact details are collected only during final review and submission. Recruiter email addresses, hashed sign-in codes, and hashed session tokens are also stored.</p>
        <p>To measure this experiment, the browser creates a random identifier. The backend stores only its keyed hash with event names, dates, numeric job or application references, and optional yes-or-no feedback. Analytics do not contain names, contact details, chat text, skills, evidence, IP addresses, or user-agent strings, and are removed on the same 30-day demo schedule.</p>
        <h2>Who can see it</h2>
        <p>The recruiter for the selected role sees only a submitted application snapshot, contact details, evidence, and match breakdown. The full chat is not shown to the recruiter. Job Talk does not sell personal data.</p>
        <p>The deterministic local response generator is the default. If the hosted AI option is enabled, only the selected job, structured draft, and a bounded window from the current chat are sent to that provider.</p>
        <h2>Retention and deletion</h2>
        <p>The demo retention period for candidate records is 30 days, and the operator runs the documented cleanup command regularly. While the private guest session is open, a submitted candidate can use <strong>Delete my application data</strong>. After leaving, email <a href={`mailto:${SUPPORT_EMAIL}`}>{SUPPORT_EMAIL}</a> with the application reference. Recruiters can use the same address to request account or hiring-record deletion.</p>
        <h2>Acceptable use</h2>
        <p>Use Job Talk only for genuine job applications and hiring. Do not submit another person's private information, secrets, harmful content, automated traffic, or discriminatory job requirements. Candidate claims are unverified, and match scores are review aids rather than hiring decisions.</p>
        <h2>Questions or reports</h2>
        <p>Report privacy, safety, access, or removal concerns to <a href={`mailto:${SUPPORT_EMAIL}`}>{SUPPORT_EMAIL}</a>. Include only the minimum information needed to find the record.</p>
        <p className="policy-updated">Last updated: 1 October 2026</p>
      </div>
    </main>
  );
}

class ChatErrorBoundary extends Component {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  recover = async () => {
    this.setState({ failed: false });
    await this.props.onRecover();
  };

  render() {
    if (this.state.failed) {
      return (
        <section className="chat-error" role="alert">
          <MessageCircleMore size={28} />
          <h2>The conversation view could not load</h2>
          <p>Your saved conversation is still available. Reload this view to continue.</p>
          <button className="primary" type="button" onClick={this.recover}>Reload conversation</button>
        </section>
      );
    }
    return this.props.children;
  }
}

function ErrorNotice({ message, onRetry, onDismiss }) {
  return (
    <aside className="error-notice" role="alert" aria-live="assertive">
      <div><strong>Job Talk needs attention</strong><p>{message}</p></div>
      <button type="button" className="error-retry" onClick={onRetry}>Reload view</button>
      <button type="button" className="error-dismiss" aria-label="Dismiss error" onClick={onDismiss}>×</button>
    </aside>
  );
}

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
        <a href="/privacy">Privacy &amp; safety</a>
      </footer>
    </main>
  );
}

function Sidebar({ user, chats, activeId, onSelect, onNew, onBrowseJobs, onLogout, open, onClose }) {
  const statusLabel = (status) => ({ active: "In progress", draft: "Draft", published: "Published", closed: "Closed", submitted: "Submitted" }[status] || status);
  return (
    <aside className={`sidebar ${open ? "open" : ""}`} aria-label="Conversation navigation">
      <div className="side-head"><Brand /><button className="mobile-close" type="button" aria-label="Close conversation menu" onClick={onClose}>×</button></div>
      {user.role === "recruiter" && <button className="new-chat" type="button" onClick={onNew}><Plus size={18} /> New hiring conversation</button>}
      {user.role === "candidate" && <button className="new-chat" type="button" onClick={onBrowseJobs}><Plus size={18} /> Browse other jobs</button>}
      <div className="chat-list-label">YOUR CONVERSATIONS</div>
      <div className="chat-list">
        {chats.map((item) => (
          <button className={`chat-row ${item.id === activeId ? "active" : ""}`} type="button" aria-current={item.id === activeId ? "page" : undefined} key={item.id} onClick={() => onSelect(item.id)}>
            <span className="chat-type">{item.intent === "employer" ? <BriefcaseBusiness size={17} /> : item.intent === "candidate" ? <UserRoundSearch size={17} /> : <MessageCircleMore size={17} />}</span>
            <span><strong>{item.workspace_title || (item.intent === "employer" ? "New hiring conversation" : "Job application")}</strong><small>{statusLabel(item.status)} · {new Date(item.created_at).toLocaleDateString()}</small></span>
          </button>
        ))}
        {!chats.length && <p className="empty-side">Your conversations will live here.</p>}
      </div>
      <div className="user-panel">
        <span>{user.role === "candidate" ? <UserRound size={16} /> : user.email.slice(0, 1).toUpperCase()}</span>
        <div><strong>{user.role === "candidate" ? "Job seeker" : user.email.split("@")[0]}</strong><small>{user.role === "candidate" ? "Private guest session" : user.email}</small></div>
        <button type="button" aria-label={user.role === "candidate" ? "Leave session" : "Log out"} onClick={onLogout}><LogOut size={17} /></button>
      </div>
      <a className="privacy-link" href="/privacy">Privacy &amp; safety</a>
    </aside>
  );
}

function ProfileChips({ profile }) {
  const items = Object.entries(profile || {}).slice(0, 7);
  if (!items.length) return null;
  return <div className="profile-chips">{items.map(([key, value]) => {
    const isGap = value?.assessment === "gap";
    return <span className={isGap ? "gap" : ""} key={key}>{key.replaceAll("_", " ")} {isGap ? <CircleMinus size={12} /> : <Check size={12} />}</span>;
  })}</div>;
}

function JobReadiness({ job }) {
  const profile = job?.target_profile || {};
  const attributes = Object.entries(profile);
  const generalFields = ["availability", "education", "experience", "location", "working_arrangement"];
  const checks = [
    ["Job title", job?.title && job.title !== "Untitled role"],
    ["Essential skill", Object.keys(profile).some((key) => !generalFields.includes(key))],
    ["Experience", Boolean(profile.experience || Object.values(profile).some((value) => value.kind === "skill" && value.years_required))],
    ["Location or work setup", Boolean(profile.location || profile.working_arrangement)],
    ["Start availability", Boolean(profile.availability)],
  ];
  const completed = checks.filter(([, ready]) => ready).length;
  return (
    <>
      <section className="job-readiness" aria-label={`Role readiness ${completed} of ${checks.length}`}>
        <div><strong>Role readiness</strong><span>{completed}/{checks.length}</span></div>
        <ul>{checks.map(([label, ready]) => <li className={ready ? "ready" : ""} key={label}>{ready ? <Check size={11} /> : <i />}{label}</li>)}</ul>
      </section>
      <section className="role-summary" aria-label="Role attributes to confirm">
        <div><strong>Check the role before publishing</strong><span>{job.title}</span></div>
        <ul>{attributes.map(([key, value]) => {
          const label = value.label || key.replaceAll("_", " ");
          const needsClarity = value.kind === "skill" && value.confirmed === false;
          const target = value.type === "number"
            ? `${value.target} ${value.unit || ""}`.trim()
            : value.type === "skill"
              ? (value.target ? "Required" : "Preferred")
              : value.target;
          return <li className={needsClarity ? "needs-clarity" : ""} key={key}>
            <strong>{label}</strong>
            <div className="criterion-contract"><b>Target: {target || "Confirm"}</b><b>Weight: {Math.round((value.weight || 0.5) * 100)}%</b></div>
            <span>{needsClarity ? "Needs importance and experience" : value.description}</span>
          </li>;
        })}</ul>
        <small>See a mistake? Tell the assistant what to change before you publish.</small>
      </section>
    </>
  );
}

function Recommendation({ item, onApply, applied }) {
  const score = Math.round(item.match_score * 100);
  return (
    <article className="job-card">
      <div className="job-card-top">
        <div className="job-logo">{item.job.title.slice(0, 1)}</div>
        <div><h3>{item.job.title}</h3><span>{item.recommended ? "Strong match" : "Selected role · below recommendation threshold"}</span></div>
        <div className="score"><strong>{score}%</strong><span>match</span></div>
      </div>
      <p>{item.explanation}</p>
      <div className="criteria-row">
        {Object.entries(item.criteria || {}).slice(0, 4).map(([key, value]) => <span key={key}>{key.replaceAll("_", " ")} {Math.round(value.score * 100)}%</span>)}
      </div>
      <div className="job-actions">
        <button className="primary" disabled={applied} onClick={onApply}>{applied ? <><Check size={17} /> Submitted</> : <>Review application <ChevronRight size={17} /></>}</button>
      </div>
    </article>
  );
}

function ApplicationReview({ item, profile, onSubmit, onCancel }) {
  const [candidateName, setCandidateName] = useState("");
  const [candidateLocation, setCandidateLocation] = useState(profile?.location?.value || "");
  const [preferredContact, setPreferredContact] = useState("");
  const [consent, setConsent] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const requirements = item.job.target_profile || {};
  const requirementKeys = new Set(Object.keys(requirements));
  const evidence = [
    ...Object.entries(requirements).map(([key, requirement]) => ({
      key,
      label: requirement.label || key.replaceAll("_", " "),
      requirement: requirement.description,
      target: requirement.type === "number" ? `${requirement.target} ${requirement.unit || ""}`.trim() : requirement.type === "skill" ? "Required" : requirement.target,
      profileItem: profile?.[key],
    })),
    ...Object.entries(profile || {})
      .filter(([key]) => !requirementKeys.has(key) && !["candidate_details", "consent"].includes(key))
      .map(([key, profileItem]) => ({
        key,
        label: key.replaceAll("_", " "),
        requirement: null,
        target: null,
        profileItem,
      })),
  ];

  async function submit(event) {
    event.preventDefault();
    if (!consent || submitting) return;
    setSubmitting(true);
    try {
      await onSubmit(candidateName.trim(), candidateLocation.trim(), preferredContact.trim());
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
        {evidence.map(({ key, label, requirement, target, profileItem }) => {
          const assessment = profileItem?.assessment;
          const state = assessment === "gap" ? "gap" : profileItem?.evidence ? "captured" : "missing";
          return (
            <div className={`review-evidence-item ${state}`} key={key}>
              <div><strong>{label}</strong><b>{state === "gap" ? "Reported gap" : state === "captured" ? "Evidence captured" : "Evidence missing"}</b></div>
              {requirement && <small>Target: {target || "Confirm with recruiter"} · {requirement}</small>}
              {profileItem?.value !== undefined && profileItem?.value !== null && <small>Your extracted value: {String(profileItem.value)}</small>}
              <span>{profileItem?.evidence || "You have not provided evidence for this requirement yet."}</span>
            </div>
          );
        })}
      </div>
      <p className="review-correction">See a mistake or missing item? <button type="button" onClick={onCancel}>Return to the chat</button> and describe the correction or evidence before submitting.</p>
      <label htmlFor="candidate-name">Your name</label>
      <input id="candidate-name" value={candidateName} onChange={(event) => setCandidateName(event.target.value)} minLength="2" maxLength="100" autoComplete="name" required />
      <label htmlFor="candidate-location">Your location</label>
      <input id="candidate-location" value={candidateLocation} onChange={(event) => setCandidateLocation(event.target.value)} minLength="2" maxLength="100" autoComplete="address-level2" required />
      <label htmlFor="candidate-contact">Preferred email or phone number</label>
      <input id="candidate-contact" value={preferredContact} onChange={(event) => setPreferredContact(event.target.value)} minLength="3" maxLength="320" autoComplete="email" required />
      <label className="consent-check">
        <input type="checkbox" checked={consent} onChange={(event) => setConsent(event.target.checked)} required />
        <span>I agree to share this application and my contact details with the recruiter for this role.</span>
      </label>
      <p className="review-policy">Read how Job Talk uses and deletes data in <a href="/privacy" target="_blank" rel="noreferrer">Privacy &amp; safety</a>.</p>
      <button className="primary full" disabled={!consent || submitting}>{submitting ? "Submitting…" : "Submit application"}<ArrowRight size={17} /></button>
    </form>
  );
}

function FeedbackPrompt({ kind, contextId }) {
  const storageKey = `job-talk-feedback-${kind}-${contextId}`;
  const [submitted, setSubmitted] = useState(() => localStorage.getItem(storageKey) === "done");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");

  async function answer(useful) {
    setSending(true);
    setError("");
    try {
      await api.feedback(kind, contextId, useful);
      localStorage.setItem(storageKey, "done");
      setSubmitted(true);
    } catch (err) {
      setError(err.message);
    } finally {
      setSending(false);
    }
  }

  if (submitted) return <div className="feedback-prompt complete" role="status"><Check size={14} /> Thank you for helping improve Job Talk.</div>;
  return (
    <section className="feedback-prompt" aria-label="One question feedback">
      <div><strong>{kind === "candidate" ? "Was applying through this conversation easy?" : "Was this candidate comparison useful?"}</strong><small>One question · no chat text or contact details are recorded</small></div>
      <div className="feedback-actions">
        <button type="button" disabled={sending} onClick={() => answer(true)}>Yes</button>
        <button type="button" disabled={sending} onClick={() => answer(false)}>No</button>
      </div>
      {error && <small className="feedback-error" role="alert">{error}</small>}
    </section>
  );
}

const PLOT_COLORS = ["#276749", "#d97745", "#4267a8", "#8a5aa6", "#9a7b25"];

function CandidateScorePlot({ applications, targetProfile }) {
  const [selectedId, setSelectedId] = useState(null);
  const criteria = Object.entries(targetProfile || {}).slice(0, 8);
  const candidates = applications.slice(0, 5);
  if (criteria.length < 2 || !candidates.length) return null;

  const width = Math.max(620, criteria.length * 105);
  const height = 245;
  const top = 34;
  const bottom = 174;
  const left = 50;
  const right = width - 38;
  const xAt = (index) => left + ((right - left) * index) / (criteria.length - 1);
  const yAt = (score) => bottom - Math.max(0, Math.min(1, score)) * (bottom - top);
  const idealPoints = criteria.map((_, index) => `${xAt(index)},${yAt(1)}`).join(" ");

  return (
    <section className="score-plot" aria-labelledby="score-plot-title">
      <div className="score-plot-heading">
        <div><span>CANDIDATE SHAPE</span><h3 id="score-plot-title">Ideal profile and top candidates</h3></div>
        <small>Scores are normalized to 0–100. Missing evidence is marked ×.</small>
      </div>
      <div className="plot-legend">
        <span><i className="ideal-line" />Ideal profile</span>
        {candidates.map((application, index) => (
          <button type="button" aria-pressed={selectedId === application.id} className={selectedId === application.id ? "selected" : ""} key={application.id} onClick={() => setSelectedId((current) => current === application.id ? null : application.id)}><i style={{ background: PLOT_COLORS[index] }} />{application.candidate_profile?.candidate_details?.name || `Candidate ${index + 1}`}</button>
        ))}
      </div>
      <div className="plot-scroll">
        <svg className="parallel-plot" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Parallel coordinates comparison of the ideal job profile and candidate evidence scores">
          {[0, 0.5, 1].map((score) => (
            <g key={score}>
              <line className="plot-grid" x1={left} x2={right} y1={yAt(score)} y2={yAt(score)} />
              <text className="plot-scale" x={left - 10} y={yAt(score) + 3}>{Math.round(score * 100)}</text>
            </g>
          ))}
          {criteria.map(([key, requirement], index) => (
            <g key={key}>
              <line className="plot-axis" x1={xAt(index)} x2={xAt(index)} y1={top} y2={bottom} />
              <text className="plot-label" x={xAt(index)} y={bottom + 25}>{key.replaceAll("_", " ").slice(0, 18)}</text>
              <text className="plot-weight" x={xAt(index)} y={bottom + 39}>weight {Math.round((requirement.weight || 0.5) * 100)}%</text>
            </g>
          ))}
          <polyline className="ideal-profile" points={idealPoints}><title>Ideal profile: 100 on every criterion</title></polyline>
          {candidates.map((application, candidateIndex) => {
            const points = criteria.map(([key], criterionIndex) => {
              const score = application.match_result?.criteria?.[key]?.score;
              const evidence = application.candidate_profile?.[key]?.evidence;
              return evidence && Number.isFinite(score)
                ? { x: xAt(criterionIndex), y: yAt(score), key, score }
                : null;
            });
            const segments = [];
            let current = [];
            points.forEach((point) => {
              if (point) current.push(point);
              else if (current.length) { segments.push(current); current = []; }
            });
            if (current.length) segments.push(current);
            const name = application.candidate_profile?.candidate_details?.name || `Candidate ${candidateIndex + 1}`;
            const color = PLOT_COLORS[candidateIndex];
            return (
              <g
                className={`plot-candidate ${selectedId && selectedId !== application.id ? "muted" : ""}`}
                key={application.id}
                role="button"
                tabIndex={0}
                aria-label={`${name} score line`}
                onClick={() => setSelectedId((current) => current === application.id ? null : application.id)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    setSelectedId((current) => current === application.id ? null : application.id);
                  }
                }}
              >
                {segments.filter((segment) => segment.length > 1).map((segment, segmentIndex) => (
                  <polyline key={segmentIndex} className="candidate-profile-line" style={{ stroke: color }} points={segment.map((point) => `${point.x},${point.y}`).join(" ")} />
                ))}
                {points.map((point, criterionIndex) => point ? (
                  <circle key={point.key} cx={point.x} cy={point.y} r="4" fill={color}>
                    <title>{name}: {point.key.replaceAll("_", " ")} {Math.round(point.score * 100)}%</title>
                  </circle>
                ) : (
                  <g key={criteria[criterionIndex][0]}>
                    <text className="missing-score" fill={color} x={xAt(criterionIndex) + (candidateIndex - (candidates.length - 1) / 2) * 7} y={bottom + 10}>×</text>
                    <title>{name}: no direct evidence for {criteria[criterionIndex][0].replaceAll("_", " ")}</title>
                  </g>
                ))}
              </g>
            );
          })}
        </svg>
      </div>
    </section>
  );
}

function CandidateComparison({ applications, status, targetProfile, jobId, onCloseJob }) {
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
      <p className="decision-support">Scores organize unverified candidate-provided evidence against this role's weighted criteria. They support recruiter review and are not hiring decisions.</p>
      <CandidateScorePlot applications={applications} targetProfile={targetProfile} />
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
                  const criterionEvidence = value.evidence || profile[key]?.evidence;
                  const reportedGap = value.gap === "reported" || profile[key]?.assessment === "gap";
                  const candidateValue = value.candidate_value === null || value.candidate_value === undefined ? "No value" : String(value.candidate_value);
                  const targetValue = value.target_value === null || value.target_value === undefined ? "Not set" : String(value.target_value);
                  return (
                    <div className={value.score < 0.5 ? "criterion-gap" : ""} key={key}>
                      <div><span>{key.replaceAll("_", " ")}</span><b>{Math.round(value.score * 100)}% · weight {Math.round(value.weight * 100)}%</b></div>
                      <small>Candidate: {candidateValue} · Target: {targetValue}</small>
                      <p>{value.reason}</p>
                      <small>{reportedGap ? `Reported gap: ${criterionEvidence}` : criterionEvidence ? `Candidate claim: ${criterionEvidence}` : "Gap: no direct candidate evidence was captured."}</small>
                    </div>
                  );
                })}
              </div>
            </article>
          );
        })}
      </div>}
      {!!visible.length && jobId && <FeedbackPrompt kind="recruiter" contextId={jobId} />}
      {status === "closed" && applications.length > 0 && <p className="shortlist-note">Recruitment is closed. Showing up to five candidates ranked by the saved weighted scores; equal scores share a rank.</p>}
    </section>
  );
}

function ChatView({ chat, recommendations, applications, onSend, onPublish, onCloseJob, onApply, onReload, onMenu, onDeleteAccount }) {
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const [applied, setApplied] = useState({});
  const [reviewing, setReviewing] = useState(null);
  const bottomRef = useRef(null);
  const submitted = chat?.status === "submitted";
  const statusLabel = submitted ? "Application submitted" : chat?.status === "published" ? "Published" : chat?.status === "closed" ? "Closed" : chat?.status === "draft" ? "Draft" : "Live profile";

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [chat?.messages, recommendations]);
  if (!chat) return <div className="loading-screen"><div className="pulse" />Opening conversation…</div>;

  async function sendPrompt(message) {
    if (sending) return false;
    setSending(true);
    try { return await onSend(message); } finally { setSending(false); }
  }

  async function submit(event) {
    event.preventDefault();
    if (!text.trim() || sending) return;
    const message = text.trim();
    if (await sendPrompt(message)) setText("");
  }

  async function apply(candidateName, candidateLocation, preferredContact) {
    await onApply(reviewing.job.id, candidateName, candidateLocation, preferredContact);
    setApplied((value) => ({ ...value, [reviewing.job.id]: true }));
    setReviewing(null);
    await onReload();
  }

  return (
    <section className="chat-shell">
      <header className="chat-header">
        <button className="menu-button" type="button" aria-label="Open conversation menu" onClick={onMenu}>☰</button>
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
          {chat.intent === "employer" && chat.job_post && <JobReadiness job={chat.job_post} />}
          {chat.intent === "employer" && chat.job_post && <CandidateComparison applications={applications} status={chat.status} targetProfile={chat.job_post.target_profile} jobId={chat.job_post.id} onCloseJob={onCloseJob} />}
          {!!recommendations.length && (
            <div className="recommendations">
              <div className="recommendation-heading"><span>YOUR APPLICATION</span><small>Selected role</small></div>
              <p className="decision-support">Match guidance uses the unverified information you provide. Recruiters make hiring decisions.</p>
              {recommendations.map((item) => <Recommendation key={item.job.id} item={item} applied={submitted || applied[item.job.id]} onApply={() => setReviewing(item)} />)}
              {reviewing && !submitted && <ApplicationReview item={reviewing} profile={chat.profile} onSubmit={apply} onCancel={() => setReviewing(null)} />}
            </div>
          )}
          {submitted && applications[0]?.id && <FeedbackPrompt kind="candidate" contextId={applications[0].id} />}
          <div ref={bottomRef} />
        </div>
      </div>
      {chat.status === "draft" && chat.can_publish && <div className="publish-bar"><div><strong>Your role is ready for final review</strong><span>Check the criteria above, then publish it explicitly.</span></div><button className="primary" onClick={onPublish}>Publish job <ArrowRight size={17} /></button></div>}
      {chat.status === "closed" && chat.intent === "candidate" ? <div className="submitted-bar"><CircleMinus size={17} /><span><strong>This recruitment is closed</strong>This job is no longer accepting applications. Use Browse other jobs to find another available role.</span></div> : chat.status === "closed" ? <div className="submitted-bar"><Check size={17} /><span><strong>Recruitment closed</strong>New applications are stopped and submitted snapshots are preserved.</span></div> : chat.intent === "employer" && chat.status === "published" ? <div className="submitted-bar"><Check size={17} /><span><strong>Job published · criteria locked</strong>Candidates are scored against the reviewed criteria above. Close this recruitment before creating a revised role.</span></div> : submitted ? <div className="submitted-bar"><Check size={17} /><span><strong>Application submitted{applications[0]?.id ? ` · Reference #${applications[0].id}` : ""}</strong>Your approved snapshot is now frozen for the recruiter.</span><button type="button" onClick={onDeleteAccount}>Delete my application data</button></div> : <form className="composer" onSubmit={submit}>
        <div className="composer-box">
          <textarea aria-label="Conversation message" rows="1" maxLength="5000" value={text} onChange={(e) => setText(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) submit(e); }} placeholder={chat.intent === "employer" ? "Describe the role or change a requirement…" : chat.intent === "candidate" ? "Tell me about your experience…" : "Type your answer…"} />
          <button aria-label="Send message" disabled={!text.trim() || sending}><Send size={18} /></button>
        </div>
        <small>Job Talk turns your conversation into a structured profile.</small>
      </form>}
    </section>
  );
}

function JobTalkApp() {
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

  useEffect(() => { api.visit().catch(() => {}); }, []);

  async function loadChat(id) {
    setError("");
    try {
      const selected = await api.getChat(id);
      setChat(selected);
      setRecommendations(selected.intent === "candidate" ? await api.recommendations(id) : []);
      setApplications(
        selected.intent === "employer" && selected.job_post
          ? await api.applications(selected.job_post.id)
          : selected.intent === "candidate"
            ? await api.applications()
            : [],
      );
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
    let response;
    try {
      response = await api.sendMessage(chat.id, content);
    } catch (err) {
      setError(err.message);
      return false;
    }
    setChat(response.chat);
    setRecommendations(response.recommendations);
    try { await loadChats(false); } catch (err) { setError(err.message); }
    return true;
  }

  async function publish() {
    try { await api.publish(chat.job_post.id); await loadChat(chat.id); } catch (err) { setError(err.message); }
  }

  async function closeJob() {
    if (!window.confirm("Close this recruitment and stop new applications?")) return;
    try { await api.closeJob(chat.job_post.id); await loadChat(chat.id); } catch (err) { setError(err.message); }
  }

  async function apply(jobId, candidateName, candidateLocation, preferredContact) {
    try { await api.apply(jobId, chat.id, candidateName, candidateLocation, preferredContact); } catch (err) { setError(err.message); throw err; }
  }

  async function deleteCandidateAccount() {
    if (!window.confirm("Permanently delete this application, conversation, contact details, and guest session?")) return;
    try {
      await api.deleteAccount();
      sessionStorage.removeItem(SESSION_KEY);
      window.location.assign("/");
    } catch (err) {
      setError(err.message);
    }
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

  async function recoverView() {
    setError("");
    if (chat?.id) await loadChat(chat.id);
    else await loadChats();
  }

  if (!user) return <Entry onAuthenticated={authenticate} showJobsOnOpen={showJobsOnEntry} />;
  return (
    <main className="app-layout">
      <Sidebar user={user} chats={chats} activeId={chat?.id} onSelect={loadChat} onNew={newChat} onBrowseJobs={() => endSession(true)} open={sidebarOpen} onClose={() => setSidebarOpen(false)} onLogout={() => endSession(false)} />
      {sidebarOpen && <button className="backdrop" type="button" aria-label="Close conversation menu" onClick={() => setSidebarOpen(false)} />}
      {error && <ErrorNotice message={error} onRetry={recoverView} onDismiss={() => setError("")} />}
      {chat ? (
        <ChatErrorBoundary key={chat.id} onRecover={() => loadChat(chat.id)}>
          <ChatView chat={chat} recommendations={recommendations} applications={applications} onSend={send} onPublish={publish} onCloseJob={closeJob} onApply={apply} onReload={() => loadChat(chat.id)} onMenu={() => setSidebarOpen(true)} onDeleteAccount={deleteCandidateAccount} />
        </ChatErrorBoundary>
      ) : <section className="welcome-empty"><Brand /><h1>Every opportunity starts with a conversation.</h1><p>Tell us whether you’re looking for your next role or your next great hire.</p><button className="primary" type="button" onClick={newChat}><Plus size={18} /> Start a conversation</button></section>}
    </main>
  );
}

export default function App() {
  return window.location.pathname === "/privacy" ? <PrivacyPage /> : <JobTalkApp />;
}
