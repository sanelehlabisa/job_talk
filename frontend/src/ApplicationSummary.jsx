import { useState } from "react";
import { ArrowRight, Pencil, Trash2, X } from "lucide-react";
import { SourceNotice } from "./JobSources";
import { FieldLabel } from "./FieldLabel";
import { useAutoSave } from "./useAutoSave";

function answerText(field) {
  // Show the readable answer once, without repeating its extracted value.
  return (field.evidence || "").replace(/^(?:The candidate said: |The candidate reported a gap: |Reported gap: )/, "");
}

function requirementText(field) {
  if (field.type === "skill") return field.description;
  return `${field.target ?? ""}${field.unit ? ` ${field.unit}` : ""}`;
}

export function ApplicationSummary({ fields, job, profile, matchScore, ratingSource, submitted, closed, busy, onChange, onEditingChange, onSubmit, children }) {
  const [editing, setEditing] = useState(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [candidateName, setCandidateName] = useState("");
  const [candidateLocation, setCandidateLocation] = useState("");
  const [locationEdited, setLocationEdited] = useState(false);
  const [preferredContact, setPreferredContact] = useState("");
  const [consent, setConsent] = useState(false);
  const locked = submitted || closed;
  const location = locationEdited ? candidateLocation : String(profile?.location?.value || "");

  function edit(value) {
    setEditing(value); setError(""); setNotice("");
    onEditingChange(value !== null);
  }

  async function save(key, value) {
    if (busy || locked) return;
    setError(""); setNotice("");
    try {
      await onChange({ key, value, criteria_version: job.criteria_version });
      edit(null);
      setNotice(value.trim() ? "Answer saved." : "Answer cleared.");
    } catch (err) { setError(err.message); }
  }

  async function submit(event) {
    event.preventDefault();
    if (!consent || busy || editing || locked) return;
    setError(""); setNotice("");
    try { await onSubmit(candidateName.trim(), location.trim(), preferredContact.trim()); }
    catch (err) { setError(err.message); }
  }

  const dirty = editing && editing.value !== answerText(fields.find((field) => field.key === editing.key) || {});
  const saveNow = useAutoSave(editing, Boolean(dirty && !locked), busy, (value) => save(value.key, value.value));

  return (
    <details className="template-draft application-summary" open>
      <summary>Your application</summary>
      {(job.company_name || job.company_location) && <p className="company-details">{job.company_name || "Company"}{job.company_location && ` · Based in ${job.company_location}`}</p>}
      {(!closed || submitted) && <div className="application-match" aria-live="polite">
        <div><span>{submitted ? "Submitted match" : "Match so far"}</span><strong>{busy ? "Updating…" : Number.isFinite(matchScore) ? `${Math.round(Math.min(1, matchScore) * 100)}%` : "Unavailable"}</strong></div>
        <small>{ratingSource === "gemini" ? "AI estimate" : "Rule-based estimate"} from {submitted ? "submitted" : "saved"} answers. You can review and correct your answers.</small>
      </div>}
      <p>{submitted ? "Your submitted answers are saved." : closed ? "This job is no longer accepting applications." : "Edit an answer or describe it in chat. Changes save automatically after you pause typing. An honest skill gap is a valid answer."}</p>
      <SourceNotice source={job.source} />
      <ul>{fields.map((field) => (
        <li key={field.key} data-field-key={field.key} data-field-state={field.state}>
          <form className="draft-field-form" onSubmit={(event) => { event.preventDefault(); saveNow(); }}>
            <FieldLabel htmlFor={`answer-${field.key}`} label={field.label} description={`${field.description || `Role asks: ${requirementText(field)}`} Share your actual experience or explain any gap.`} />
            <input id={`answer-${field.key}`} name="value" aria-label={`${field.label} answer`}
              value={editing?.key === field.key ? editing.value : answerText(field)} maxLength="500"
              placeholder={`Role asks: ${requirementText(field)}`} title={`Role asks: ${requirementText(field)}`}
              readOnly={locked} disabled={busy || (editing !== null && editing.key !== field.key)}
              onChange={(event) => edit({ key: field.key, value: event.target.value })} />
            {!locked && <div className="draft-actions">{editing?.key === field.key ? <>
              <button type="button" disabled={busy} onClick={() => edit(null)}><X size={14} aria-hidden="true" />Cancel</button>
            </> : <>
              <button type="button" disabled={busy || editing !== null} onClick={() => edit({ key: field.key, value: answerText(field) })} aria-label={`Edit ${field.label}`}><Pencil size={14} aria-hidden="true" />Edit</button>
              {field.evidence && <button type="button" disabled={busy || editing !== null} onClick={() => save(field.key, "")} aria-label={`Clear ${field.label} answer`}><Trash2 size={14} aria-hidden="true" />Clear</button>}
            </>}</div>}
            {field.state === "needs_clarification" && <p className="draft-error">{field.type === "number" ? `Enter a clear amount${field.unit ? ` in ${field.unit}` : ""}, or describe a gap.` : "Please clarify this answer here or in chat."}</p>}
          </form>
        </li>
      ))}</ul>
      {notice && <p role="status">{notice}</p>}
      {editing && busy && <p role="status">Saving…</p>}
      {error && <p className="draft-error" role="alert">{error}</p>}
      {error && dirty && <button type="button" disabled={busy} onClick={saveNow}>Retry saving</button>}
      {!locked && <form className="application-review" onSubmit={submit}>
        <p>Review your answers, then add your contact details. Your full chat is not shared.</p>
        <FieldLabel htmlFor="candidate-name" label="Your name" description="The name the recruiter will see on your submitted application." />
        <input id="candidate-name" value={candidateName} onChange={(event) => setCandidateName(event.target.value)} minLength="2" maxLength="100" autoComplete="name" required disabled={busy} />
        <FieldLabel htmlFor="candidate-location" label="Your location" description="The town or city where you are currently based." />
        <input id="candidate-location" value={location} onChange={(event) => { setCandidateLocation(event.target.value); setLocationEdited(true); }} minLength="2" maxLength="100" autoComplete="address-level2" required disabled={busy} />
        <FieldLabel htmlFor="candidate-contact" label="Preferred email or phone number" description="The email address or phone number where you want to be contacted about this application." />
        <input id="candidate-contact" value={preferredContact} onChange={(event) => setPreferredContact(event.target.value)} minLength="3" maxLength="320" autoComplete="email" required disabled={busy} />
        <label className="consent-check">
          <input type="checkbox" checked={consent} onChange={(event) => setConsent(event.target.checked)} required disabled={busy} />
          <span>{job.source ? "I agree to send this application and my contact details to the Job Talk operator to record my interest. This does not authorize sharing my identifying details with the advertised employer; Job Talk must ask my permission separately." : "I agree to share this application and my contact details with the recruiter for this role and the Job Talk operator who runs and supports this experiment."}</span>
        </label>
        <p className="review-policy">Read how Job Talk uses and deletes data in <a href="/privacy" target="_blank" rel="noreferrer">Privacy &amp; safety</a>.</p>
        {editing && <p>Wait for your answer to save, or cancel the edit before submitting.</p>}
        <button className="primary full" disabled={!consent || busy || editing !== null}>Submit application <ArrowRight size={17} /></button>
      </form>}
      {children}
    </details>
  );
}
