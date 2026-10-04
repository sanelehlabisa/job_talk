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
import { JobDraftSummary, JobTemplatePicker } from "./JobTemplates";
import { ApplicationSummary } from "./ApplicationSummary";
import { SourceNotice, InterestSummary } from "./JobSources";

function Brand() {
  return (
    <div className="brand">
      <img className="brand-mark" src="/branding/jobtalk-logo.png" alt="" width="37" height="37" />
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
        <p>The recruiter for the selected role and the Job Talk operator can review your submitted application snapshot, contact details, evidence, and match breakdown. Recruiters see applications only for their own jobs; the operator can review applications across jobs to run and support this experiment. These views do not expose your full chat. Job Talk does not sell personal data.</p>
        <p>The Job Talk operator can also view and manage recruiters' job-creation conversations to run and support the experiment.</p>
        <p>Vacancies marked Added by Job Talk come from manually checked public adverts. Interest in these vacancies is received by the Job Talk operator. The advertised employer does not receive your application; sharing identifying details with them requires your separate permission. A public advert does not mean that employer has joined Job Talk.</p>
        <p>The deterministic local response generator is the default. If the hosted AI option is enabled, only the selected job, structured draft, and a bounded window from the current chat are sent to that provider.</p>
        <h2>Retention and deletion</h2>
        <p>The demo retention period for candidate records is 30 days, and the operator runs the documented cleanup command regularly. While the private guest session is open, a submitted candidate can use <strong>Delete my application data</strong>. After leaving, email <a href={`mailto:${SUPPORT_EMAIL}`}>{SUPPORT_EMAIL}</a> with the application reference. Recruiters can use the same address to request account or hiring-record deletion.</p>
        <h2>Acceptable use</h2>
        <p>Use Job Talk only for genuine job applications and hiring. Do not submit another person's private information, secrets, harmful content, automated traffic, or discriminatory job requirements. Candidate claims are unverified, and match scores are review aids rather than hiring decisions.</p>
        <h2>Questions or reports</h2>
        <p>Report privacy, safety, access, or removal concerns to <a href={`mailto:${SUPPORT_EMAIL}`}>{SUPPORT_EMAIL}</a>. Include only the minimum information needed to find the record.</p>
        <p className="policy-updated">Last updated: 3 October 2026</p>
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

function ErrorNotice({ message, onRetry, onDismiss, retryLabel = "Reload view" }) {
  return (
    <aside className="error-notice" role="alert" aria-live="assertive">
      <div><strong>Job Talk needs attention</strong><p>{message}</p></div>
      <button type="button" className="error-retry" onClick={onRetry}>{retryLabel}</button>
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
            <p>Here are two available jobs. To find others, describe your background in a new chat.</p>
            <div className="entry-jobs">
              {jobs.slice(0, 2).map((job) => (
                <button className="entry-job" type="button" disabled={loading} key={job.id} onClick={() => continueAsSeeker(job.id)}>
                  <span className="entry-job-copy">
                    <strong>{job.title}</strong>
                    <small>{job.description}</small>
                    {job.closing_date && <small>Apply by {job.closing_date} (UTC)</small>}
                    <SourceNotice source={job.source} compact />
                    <span className="entry-job-action">Apply through chat</span>
                  </span>
                  <ChevronRight size={18} />
                </button>
              ))}
              {!jobs.length && <div className="error">No published jobs are available yet.</div>}
            </div>
            <button className="primary full" type="button" disabled={loading} onClick={() => continueAsSeeker()}>
              Find a different job <ArrowRight size={17} />
            </button>
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
      <div className="chat-list-label">{user.is_admin ? "ALL HIRING CONVERSATIONS" : "YOUR CONVERSATIONS"}</div>
      <div className="chat-list">
        {chats.map((item) => (
          <button className={`chat-row ${item.id === activeId ? "active" : ""}`} data-chat-id={item.id} type="button" aria-current={item.id === activeId ? "page" : undefined} key={item.id} onClick={() => onSelect(item.id)}>
            <span className="chat-type">{item.intent === "employer" ? <BriefcaseBusiness size={17} /> : item.intent === "candidate" ? <UserRoundSearch size={17} /> : <MessageCircleMore size={17} />}</span>
            <span><strong>{item.workspace_title || (item.intent === "employer" ? "New hiring conversation" : "Job application")}</strong><small>{statusLabel(item.status)} · {new Date(item.created_at).toLocaleDateString()}</small>{user.is_admin && item.recruiter_email && <small className="chat-owner">{item.recruiter_email}</small>}</span>
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

function Recommendation({ item, number, onSelect, busy }) {
  return (
    <article className="job-card">
      <div className="job-card-top">
        <div className="job-logo" aria-label={`Job ${number}`}>{number}</div>
        <div><h3>{item.job.title}</h3><span>{item.available_example ? "Available job · example" : "Possible role"}</span></div>
      </div>
      <p>{item.explanation}</p>
      <SourceNotice source={item.job.source} compact />
      <div className="job-actions">
        <button className="primary" disabled={busy} onClick={onSelect}>Apply to this job <ChevronRight size={17} /></button>
      </div>
    </article>
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

function joinLabels(labels) {
  if (labels.length < 2) return labels[0] || "";
  return `${labels.slice(0, -1).join(", ")} and ${labels.at(-1)}`;
}

function candidateCardSummary(criteria, location) {
  const sorted = [...criteria].sort((left, right) => (right[1].score * right[1].weight) - (left[1].score * left[1].weight));
  const strengths = sorted.filter(([, value]) => value.score >= 0.75 && value.evidence).slice(0, 2).map(([key, value]) => value.label || key.replaceAll("_", " "));
  const gaps = sorted.filter(([, value]) => value.gap || value.score < 0.5).slice(0, 2).map(([key, value]) => value.label || key.replaceAll("_", " "));
  const locationText = location ? `${location}. ` : "";
  if (strengths.length && gaps.length) return `${locationText}Strongest evidence: ${joinLabels(strengths)}. Review gaps: ${joinLabels(gaps)}.`;
  if (strengths.length) return `${locationText}Strong evidence across ${joinLabels(strengths)}; no major evidence gaps were identified.`;
  if (gaps.length) return `${locationText}Limited direct evidence so far. Review ${joinLabels(gaps)}.`;
  return `${locationText}Review the criterion evidence below before making a decision.`;
}

function formatCriterionValue(value, unit) {
  if (value === null || value === undefined || value === "") return "Not provided";
  if (typeof value === "boolean") return value ? "Confirmed" : "Not confirmed";
  return `${String(value)}${unit ? ` ${unit}` : ""}`;
}

function CandidateComparison({ applications, status, targetProfile, jobId, onCloseJob }) {
  const current = applications.filter((item) => !item.earlier_requirements);
  const earlier = applications.filter((item) => item.earlier_requirements);
  const visible = [...(status === "closed" ? current.slice(0, 5) : current), ...earlier];
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
      {!!earlier.length && <p className="decision-support">Applications marked Earlier requirements keep their original scores and are excluded from the current comparison plot and ranking.</p>}
      <CandidateScorePlot applications={current} targetProfile={targetProfile} />
      {!visible.length && <div className="candidate-empty">No submitted applications yet. Candidates will appear here in one comparable format.</div>}
      {!!visible.length && <div className="comparison-grid">
        {visible.map((application, index) => {
          const profile = application.candidate_profile || {};
          const details = profile.candidate_details || {};
          const criteria = Object.entries(application.match_result?.criteria || {});
          const score = Math.round((application.match_result?.overall_score || 0) * 100);
          const contact = details.preferred_contact || "Contact not provided";
          const contactHref = contact.includes("@") ? `mailto:${contact}` : `tel:${contact.replace(/[^+\d]/g, "")}`;
          if (score !== previousScore) previousRank = index + 1;
          previousScore = score;
          return (
            <article className="candidate-card" key={application.id}>
              <div className="candidate-card-head">
                <div className="candidate-rank">{status === "closed" && !application.earlier_requirements ? `#${previousRank}` : <UserRound size={17} />}</div>
                <div><h3>{details.name || "Candidate"}</h3><a href={contactHref}>{contact}</a></div>
                <div className="score"><strong>{score}%</strong><span>{application.earlier_requirements ? "original match" : application.match_result?.rating_source === "gemini" ? "AI estimate" : "rule estimate"}</span></div>
              </div>
              {application.earlier_requirements && <p className="earlier-requirements">Earlier requirements · Submitted before the job criteria changed.</p>}
              <p className="candidate-summary"><strong>Quick summary</strong>{candidateCardSummary(criteria, details.location)}</p>
              <div className="criterion-list">
                <strong>Evidence by criterion</strong>
                {criteria.map(([key, value]) => {
                  const criterionEvidence = value.evidence || profile[key]?.evidence;
                  const reportedGap = value.gap === "reported" || profile[key]?.assessment === "gap";
                  const missing = value.gap === "missing" || !criterionEvidence;
                  const criterionScore = Math.round(value.score * 100);
                  return (
                    <article className={`criterion-item ${value.score < 0.5 ? "criterion-gap" : ""}`} key={key}>
                      <div className="criterion-title"><span>{value.label || key.replaceAll("_", " ")}</span><b>{criterionScore}% match</b></div>
                      <div className="criterion-values">
                        <div><small>Candidate</small><strong>{formatCriterionValue(value.candidate_value, value.unit)}</strong></div>
                        <div><small>Role needs</small><strong>{formatCriterionValue(value.target_value, value.unit)}</strong></div>
                        <div><small>Importance</small><strong>{Math.round(value.weight * 100)}%</strong></div>
                      </div>
                      <p className="criterion-comment">{value.reason}</p>
                      <p className="criterion-evidence"><strong>{reportedGap ? "Reported gap" : missing ? "Evidence gap" : "Evidence"}</strong>{criterionEvidence || "No direct evidence was provided."}</p>
                    </article>
                  );
                })}
              </div>
            </article>
          );
        })}
      </div>}
      {!!visible.length && jobId && <FeedbackPrompt kind="recruiter" contextId={jobId} />}
      {status === "closed" && applications.length > 0 && <p className="shortlist-note">Recruitment is closed. Showing up to five candidates for the current requirements; equal scores share a rank. Earlier applications remain available for review.</p>}
    </section>
  );
}

function ChatView({ chat, recommendations, applications, isAdmin, onSend, onDraftChange, onAnswerChange, onPublish, onCloseJob, onApply, onSelectJob, onReload, onMenu, onDeleteAccount }) {
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const sendingRef = useRef(false);
  const [editingDraft, setEditingDraft] = useState(false);
  const [selecting, setSelecting] = useState(false);
  const bottomRef = useRef(null);
  const submitted = chat?.status === "submitted";
  const applicationScore = submitted
    ? applications.find((item) => item.candidate_chat_id === chat?.id)?.match_result?.overall_score
    : recommendations.find((item) => item.job.id === chat?.target_job_id)?.match_score;
  const ratingSource = submitted
    ? applications.find((item) => item.candidate_chat_id === chat?.id)?.match_result?.rating_source
    : recommendations.find((item) => item.job.id === chat?.target_job_id)?.rating_source;
  const statusLabel = submitted ? "Application submitted" : chat?.status === "published" ? "Published" : chat?.status === "closed" ? "Closed" : chat?.status === "draft" ? "Draft" : "Live profile";

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [chat?.messages, recommendations]);
  if (!chat) return <div className="loading-screen"><div className="pulse" />Opening conversation…</div>;

  async function sendPrompt(message) {
    if (!message.trim() || sendingRef.current) return false;
    sendingRef.current = true;
    setSending(true);
    setText("");
    try {
      const sent = await onSend(message);
      if (!sent) setText(message);
      return sent;
    } finally {
      sendingRef.current = false;
      setSending(false);
    }
  }

  async function submit(event) {
    event.preventDefault();
    if (!text.trim() || sending) return;
    const message = text.trim();
    await sendPrompt(message);
  }

  async function apply(candidateName, candidateLocation, preferredContact) {
    if (sendingRef.current) return;
    sendingRef.current = true;
    setSending(true);
    try {
      await onApply(chat.target_job.id, candidateName, candidateLocation, preferredContact, chat.target_job.criteria_version);
      await onReload();
    } finally { sendingRef.current = false; setSending(false); }
  }

  async function selectJob(jobId) {
    setSelecting(true);
    try { await onSelectJob(jobId); } finally { setSelecting(false); }
  }

  async function changeDraft(action, value) {
    if (sendingRef.current) throw new Error("Wait for the current change to finish.");
    sendingRef.current = true;
    setSending(true);
    try { return await onDraftChange(action, value); }
    finally { sendingRef.current = false; setSending(false); }
  }

  async function changeAnswer(value) {
    if (sendingRef.current) throw new Error("Wait for the current change to finish.");
    sendingRef.current = true;
    setSending(true);
    try { return await onAnswerChange(value); }
    finally { sendingRef.current = false; setSending(false); }
  }

  return (
    <section className="chat-shell">
      <header className="chat-header">
        <button className="menu-button" type="button" aria-label="Open conversation menu" onClick={onMenu}>☰</button>
        <div><span className={`intent-dot ${chat.intent || "new"}`} /> <strong>{chat.intent === "employer" ? (chat.job_post?.title || "Build your role") : chat.intent === "candidate" ? (chat.target_job?.title || "Find your next role") : "New conversation"}</strong><small>{chat.intent ? "Profile updates as you talk" : "Let’s work out where to begin"}</small></div>
        <div className="status-pill"><span /> {statusLabel}</div>
      </header>
      <div className={chat.job_draft || chat.intent === "candidate" ? "chat-workspace with-draft" : "chat-workspace"}>
      <div className="messages">
        <div className="conversation-inner">
          {chat.intent === "employer" && <SourceNotice source={chat.job_post?.source} owner />}
          {isAdmin && chat.job_post?.source && <InterestSummary key={`${chat.id}-${applications.length}`} jobId={chat.job_post.id} />}
          {chat.status === "draft" && chat.job_draft?.source && !chat.messages.some((message) => message.sender === "user") && <section className="source-notice">
            <details><summary>Pasted job description</summary><p className="source-original">{chat.job_draft.source.original_text}</p></details>
            <button className="primary" type="button" disabled={sending} onClick={() => sendPrompt(chat.job_draft.source.original_text)}>Fill draft from pasted text</button>
          </section>}
          <div className="date-rule"><span>Today</span></div>
          {chat.messages.map((message) => (
            <div className={`message-wrap ${message.sender}`} key={message.id}>
              {message.sender === "assistant" && <div className="avatar assistant-avatar" role="img" aria-label="Job Talk assistant"><Bot size={16} strokeWidth={2.2} aria-hidden="true" /></div>}
              <div className="message"><p>{message.content}</p><time>{message.pending ? "Sending…" : new Date(message.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</time></div>
              {message.sender === "user" && <div className="avatar user-avatar" role="img" aria-label="You"><UserRound size={16} strokeWidth={2.2} aria-hidden="true" /></div>}
            </div>
          ))}
          {!submitted && chat.status !== "closed" && !chat.job_draft && !chat.target_job && !chat.messages.some((message) => message.sender === "user") && (
            <div className="starter-prompts">
              <span>TRY AN EXAMPLE</span>
              {chat.intent === "candidate" && <button type="button" disabled={sending} onClick={() => sendPrompt("I have three years of welding and forklift experience in Cape Town.")}>Describe trade experience</button>}
              {chat.intent === "employer" && !chat.job_draft && <button type="button" disabled={sending} onClick={() => sendPrompt("I am looking to hire a welder with welding and forklift experience in Cape Town, with two years of experience.")}>Describe a welder role</button>}
            </div>
          )}
          {sending && <div className="message-wrap assistant"><div className="avatar assistant-avatar" role="img" aria-label="Job Talk assistant"><Bot size={16} strokeWidth={2.2} aria-hidden="true" /></div><div className="typing"><i /><i /><i /></div></div>}
          {chat.intent !== "candidate" && !chat.job_draft && !chat.target_job && <ProfileChips profile={chat.profile} />}
          {chat.intent === "employer" && chat.job_post && !chat.job_draft && <JobReadiness job={chat.job_post} />}
          {chat.intent === "employer" && chat.job_post && chat.status !== "draft" && <CandidateComparison applications={applications} status={chat.status} targetProfile={chat.job_post.target_profile} jobId={chat.job_post.id} onCloseJob={onCloseJob} />}
          <div ref={bottomRef} />
        </div>
      </div>
      {chat.job_draft && <aside className="draft-sidebar" aria-label="Who you're looking for"><JobDraftSummary draft={chat.job_draft} busy={sending} onChange={changeDraft} onEditingChange={setEditingDraft} /></aside>}
      {chat.target_job && <aside className="draft-sidebar" aria-label="Your application"><ApplicationSummary key={chat.id} fields={chat.application_fields || []} job={chat.target_job} profile={chat.profile} matchScore={applicationScore} ratingSource={ratingSource} submitted={submitted} closed={chat.status === "closed"} busy={sending} onChange={changeAnswer} onEditingChange={setEditingDraft} onSubmit={apply}>
        {submitted && applications[0]?.id && <FeedbackPrompt kind="candidate" contextId={applications[0].id} />}
      </ApplicationSummary></aside>}
      {chat.intent === "candidate" && !chat.target_job_id && <aside className="draft-sidebar discovery-sidebar" aria-label="Job suggestions">
        {!chat.messages.some((message) => message.sender === "user") ? <section className="discovery-empty"><strong>Find a job</strong><p>Describe the work you can do, your experience and location. We search all published, open jobs as you chat.</p>{recommendations.length > 0 && <p>These are available-job examples. Keep chatting to narrow your search, or choose one to apply.</p>}</section>
          : <h3 className="discovery-heading">{!recommendations.length ? "No open jobs right now" : recommendations.some((item) => !item.available_example) ? "Possible roles" : "Available jobs"}</h3>}
        {recommendations.map((item, index) => <Recommendation key={item.job.id} item={item} number={index + 1} busy={selecting || sending} onSelect={() => selectJob(item.job.id)} />)}
      </aside>}
      </div>
      {chat.can_publish && <div className="publish-bar"><div><strong>{chat.job_post?.published ? "Your edits are ready" : "Your role is ready for final review"}</strong><span>{chat.job_post?.published ? "Publish changes to update the live post." : "Check the criteria above, then publish it explicitly."}</span></div><button className="primary" disabled={sending || editingDraft} onClick={onPublish}>{chat.job_post?.published ? "Publish changes" : "Publish job"} <ArrowRight size={17} /></button></div>}
      {chat.intent === "employer" && chat.status === "closed" && <div className="submitted-bar"><Check size={17} /><span><strong>Recruitment closed</strong>You can keep editing here. Recruitment remains closed.</span></div>}
      {chat.intent === "employer" && chat.status === "published" && !chat.can_publish && <div className="submitted-bar"><Check size={17} /><span><strong>{chat.has_unpublished_changes ? "Changes saved for review" : "Your job is live"}</strong>{chat.has_unpublished_changes ? "Complete the missing details, then publish your changes." : "Keep chatting or edit the form to update your post."}</span></div>}
      {chat.status === "closed" && chat.intent === "candidate" ? <div className="submitted-bar"><CircleMinus size={17} /><span><strong>This recruitment is closed</strong>This job is no longer accepting applications. Use Browse other jobs to find another available role.</span></div> : submitted ? <div className="submitted-bar"><Check size={17} /><span><strong>Application submitted{applications[0]?.id ? ` · Reference #${applications[0].id}` : ""}</strong>{chat.target_job?.source ? "Your interest is saved with Job Talk. It has not been sent to the advertised employer." : "Your approved snapshot is now frozen for the recruiter."}</span><button type="button" onClick={onDeleteAccount}>Delete my application data</button></div> : <form className="composer" onSubmit={submit}>
        <div className="composer-box">
          <textarea aria-label="Conversation message" rows="1" maxLength="5000" disabled={sending || editingDraft} value={text} onChange={(e) => setText(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) submit(e); }} placeholder={chat.intent === "employer" ? "Describe the role or change a requirement…" : chat.intent === "candidate" ? "Tell me about your experience…" : "Type your answer…"} />
          <button aria-label="Send message" disabled={!text.trim() || sending || editingDraft}><Send size={18} /></button>
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
  const [templateChoices, setTemplateChoices] = useState(null);
  const [creatingChat, setCreatingChat] = useState(false);
  const user = session?.user;
  const activeChatId = useRef(chat?.id);
  const logoutRetry = useRef(null);

  useEffect(() => { activeChatId.current = chat?.id; }, [chat?.id]);

  useEffect(() => { api.visit().catch(() => {}); }, []);

  async function loadChat(id) {
    setTemplateChoices(null);
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
      setTemplateChoices(null);
    };
    window.addEventListener("job-talk:unauthorized", clearExpiredSession);
    return () => window.removeEventListener("job-talk:unauthorized", clearExpiredSession);
  }, []);

  useEffect(() => {
    if (!user) return undefined;
    let cancelled = false;
    async function restore() {
      const verified = await api.me();
      if (cancelled) return;
      setSession((current) => current ? { ...current, user: verified } : null);
      await loadChats();
    }
    restore().catch((err) => { if (!cancelled) setError(err.message); });
    return () => { cancelled = true; };
  }, [user?.id]);

  function authenticate(nextSession) {
    localStorage.removeItem("job-talk-user");
    sessionStorage.setItem(SESSION_KEY, JSON.stringify(nextSession));
    setShowJobsOnEntry(false);
    setSession(nextSession);
    setTemplateChoices(null);
  }

  async function newChat() {
    setError("");
    try {
      setTemplateChoices(await api.jobTemplates());
      setSidebarOpen(false);
    } catch (err) { setError(err.message); }
  }

  async function createFromTemplate(templateId, source) {
    if (creatingChat) return;
    setCreatingChat(true);
    setError("");
    try {
      const created = await api.createChat(templateId, source);
      setChat(created);
      setRecommendations([]);
      setApplications([]);
      setTemplateChoices(null);
      await loadChats(false);
    } catch (err) { setError(err.message); }
    finally { setCreatingChat(false); }
  }

  async function send(content) {
    const chatId = chat.id;
    const pendingId = `pending-${crypto.randomUUID()}`;
    setError("");
    setChat((current) => current?.id === chatId ? {
      ...current,
      messages: [...current.messages, { id: pendingId, sender: "user", content, created_at: new Date().toISOString(), pending: true }],
    } : current);
    let response;
    try {
      response = await api.sendMessage(chatId, content);
    } catch (err) {
      setChat((current) => current?.id === chatId ? {
        ...current, messages: current.messages.filter((message) => message.id !== pendingId),
      } : current);
      setError(err.message);
      return false;
    }
    setChat((current) => current?.id === chatId ? response.chat : current);
    // A late reply must not replace another conversation's results.
    setRecommendations((current) => chatId === activeChatId.current ? response.recommendations : current);
    try { await loadChats(false); } catch (err) { setError(err.message); }
    return true;
  }

  async function publish() {
    try { await api.publish(chat.job_post.id); await loadChat(chat.id); await loadChats(false); } catch (err) { setError(err.message); }
  }

  async function changeDraft(action, value) {
    const chatId = chat.id;
    const result = action === "done" ? await api.finishDraft(chatId)
      : action === "remove" ? await api.removeDraftField(chatId, value)
      : await api.editDraftField(chatId, value);
    setChat((current) => current?.id === chatId ? result.chat : current);
    try { await loadChats(false); } catch (err) { setError(err.message); }
    return result;
  }

  async function changeAnswer(value) {
    const chatId = chat.id;
    const updated = await api.editApplicationField(chatId, value);
    setChat((current) => current?.id === chatId ? updated : current);
    if (chatId === activeChatId.current) setRecommendations([]);
    try {
      const items = await api.recommendations(chatId);
      if (chatId === activeChatId.current) setRecommendations(items);
    } catch {
      if (chatId === activeChatId.current) setError("Your answer was saved, but the match score could not refresh. Reload the view to try again.");
    }
    return updated;
  }

  async function closeJob() {
    if (!window.confirm("Close this recruitment and stop new applications?")) return;
    try { await api.closeJob(chat.job_post.id); await loadChat(chat.id); await loadChats(false); } catch (err) { setError(err.message); }
  }

  async function apply(jobId, candidateName, candidateLocation, preferredContact, criteriaVersion) {
    try { await api.apply(jobId, chat.id, candidateName, candidateLocation, preferredContact, criteriaVersion); } catch (err) { setError(err.message); throw err; }
  }

  async function selectJob(jobId) {
    try { await api.selectJob(chat.id, jobId); await loadChat(chat.id); await loadChats(false); }
    catch (err) { setError(err.message); }
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
    try { await api.logout(); }
    catch (err) {
      if (err.status !== 401) {
        logoutRetry.current = () => endSession(showJobs);
        setError("Sign out could not finish. Check your connection and try again.");
        return;
      }
      // An expired or already revoked token can safely be removed locally.
    }
    logoutRetry.current = null;
    setError("");
    if (showJobs) window.history.replaceState({}, "", window.location.pathname);
    sessionStorage.removeItem(SESSION_KEY);
    setShowJobsOnEntry(showJobs);
    setSession(null);
    setChat(null);
    setChats([]);
    setRecommendations([]);
    setApplications([]);
    setTemplateChoices(null);
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
      {error && <ErrorNotice message={error} onRetry={error.startsWith("Sign out could not finish.") ? logoutRetry.current : recoverView} retryLabel={error.startsWith("Sign out could not finish.") ? "Retry sign out" : "Reload view"} onDismiss={() => setError("")} />}
      {templateChoices ? <JobTemplatePicker templates={templateChoices} busy={creatingChat} onSelect={createFromTemplate} isAdmin={user.is_admin} onCancel={() => setTemplateChoices(null)} /> : chat ? (
        <ChatErrorBoundary key={chat.id} onRecover={() => loadChat(chat.id)}>
          <ChatView key={chat.id} chat={chat} recommendations={recommendations} applications={applications} isAdmin={user.is_admin} onSend={send} onDraftChange={changeDraft} onAnswerChange={changeAnswer} onPublish={publish} onCloseJob={closeJob} onApply={apply} onSelectJob={selectJob} onReload={() => loadChat(chat.id)} onMenu={() => setSidebarOpen(true)} onDeleteAccount={deleteCandidateAccount} />
        </ChatErrorBoundary>
      ) : <section className="welcome-empty"><Brand /><h1>Every opportunity starts with a conversation.</h1><p>Tell us whether you’re looking for your next role or your next great hire.</p><button className="primary" type="button" onClick={newChat}><Plus size={18} /> Start a conversation</button></section>}
    </main>
  );
}

export default function App() {
  return window.location.pathname === "/privacy" ? <PrivacyPage /> : <JobTalkApp />;
}
