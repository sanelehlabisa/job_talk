import { useState } from "react";
import { Check, Pencil, Plus, Trash2, X } from "lucide-react";

const stateLabels = {
  unanswered: "Unanswered",
  needs_clarification: "Needs clarification",
  confirmed: "Confirmed",
  not_required: "Not required",
};

function displayValue(value, unit) {
  if (typeof value === "boolean") return value ? "Can demonstrate this skill" : "Not needed";
  return `${value}${unit ? ` ${unit}` : ""}`;
}

export function JobTemplatePicker({ templates, busy, onSelect, onCancel, isAdmin = false }) {
  const [curated, setCurated] = useState(false);
  const today = new Date().toLocaleDateString("sv-SE");
  function choose(event) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const source = curated ? {
      url: data.get("source_url"), employer: data.get("employer"),
      checked_on: data.get("checked_on"), original_text: data.get("original_text"),
    } : undefined;
    onSelect(event.nativeEvent.submitter.value, source);
  }
  return (
    <section className="template-picker" aria-labelledby="template-picker-title">
      <h1 id="template-picker-title">Start with a role</h1>
      <p>Choose a starting point, then describe what you need. Each job gets its own draft. Suggestions become requirements only when you confirm them.</p>
      <form onSubmit={choose}>
      {isAdmin && <label className="consent-check"><input id="curated-vacancy" type="checkbox" checked={curated} disabled={busy} onChange={(event) => setCurated(event.target.checked)} /><span>Add a vacancy I checked on another website</span></label>}
      {curated && <fieldset className="vacancy-source-form" disabled={busy}>
        <legend>Public vacancy source</legend>
        <p>Applicants will send interest to Job Talk. The advertised employer is not automatically onboarded or given their details.</p>
        <label htmlFor="source-url">Original advert URL</label><input id="source-url" name="source_url" type="url" maxLength="2000" required />
        <label htmlFor="source-employer">Advertised employer</label><input id="source-employer" name="employer" minLength="2" maxLength="160" required />
        <label htmlFor="source-checked">Date you checked the advert</label><input id="source-checked" name="checked_on" type="date" defaultValue={today} max={today} required />
        <label htmlFor="source-text">Paste the job description</label><textarea id="source-text" name="original_text" rows="6" minLength="20" maxLength="5000" required />
        <p>Choose a starter below, then use the pasted description to fill and review the draft.</p>
      </fieldset>}
      <div className="template-options">
        {templates.map((template) => (
          <button className="template-choice" data-template-id={template.template_id} value={template.template_id} key={template.template_id} type="submit" disabled={busy}>
            <strong>{template.label}</strong>
            <span>{template.description}</span>
          </button>
        ))}
      </div>
      </form>
      {busy && <p role="status">Opening your draft…</p>}
      <button className="ghost" type="button" disabled={busy} onClick={onCancel}>Cancel</button>
    </section>
  );
}

const essentialFields = new Set(["job_title", "role_description", "working_arrangement", "location"]);

function fieldValue(field) {
  if (field.key === "closing_date") return field.target || "";
  if (field.state === "not_required") return "Not required";
  if (field.target == null) return "";
  const value = field.type === "skill" ? field.description : displayValue(field.target, field.unit);
  return field.importance === "preferred" && !/\bpreferred\b/i.test(value) ? `Preferred: ${value}` : value;
}

export function JobDraftSummary({ draft, locked = false, busy = false, onChange, onEditingChange }) {
  const [editing, setEditing] = useState(null);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  function edit(value) { setEditing(value); setError(""); onEditingChange?.(value !== null); }
  async function change(action, value) {
    setError(""); setNotice("");
    try {
      const result = await onChange(action, value);
      setNotice(result.notice);
      edit(null);
    } catch (err) { setError(err.message); }
  }
  function save(event) {
    event.preventDefault();
    if (!editing || locked || busy) return;
    change("save", { key: editing.key === "new" ? null : editing.key, label: editing.label, value: editing.value });
  }
  const fields = draft.fields.some((field) => field.key === "closing_date") || locked || draft.removed_keys?.includes("closing_date")
    ? draft.fields : [...draft.fields, { key: "closing_date", label: "Closing date", state: "unanswered", target: null }];
  return (
    <details className="template-draft" open>
      <summary>Who you're looking for</summary>
      <p>{locked ? "Published requirements" : "Edit a value or describe it in chat."}</p>
      <ul>
        {fields.map((field) => (
          <li key={field.key} data-field-key={field.key} data-field-state={field.state}>
            <form className="draft-field-form" onSubmit={save}>
              {editing?.key === field.key ? <input name="label" aria-label="Field label" value={editing.label} onChange={(event) => edit({ ...editing, label: event.target.value })} minLength="2" maxLength="80" required disabled={busy} /> : <label htmlFor={`draft-value-${field.key}`}>{field.label}{field.key === "closing_date" ? " (optional)" : ""}</label>}
              <input id={`draft-value-${field.key}`} name="value" aria-label={`${field.label} value`} type={field.key === "closing_date" ? "date" : "text"} value={editing?.key === field.key ? editing.value : fieldValue(field)} maxLength="500" required={editing?.key === field.key} readOnly={locked} disabled={busy || (editing !== null && editing.key !== field.key)} placeholder={field.suggestion != null ? `e.g. ${displayValue(field.suggestion, field.unit)}` : "Enter a value"} title={field.key === "closing_date" ? "Optional last day to apply (UTC)" : stateLabels[field.state]} onChange={(event) => edit({ key: field.key, label: editing?.label || field.label, value: event.target.value })} />
              {!locked && <div className="draft-actions">{editing?.key === field.key ? <>
                <button className="primary" type="submit" disabled={busy}><Check size={14} aria-hidden="true" />Save</button><button type="button" disabled={busy} onClick={() => edit(null)}><X size={14} aria-hidden="true" />Cancel</button>
              </> : <>
                <button type="button" disabled={busy || editing !== null} onClick={() => edit({ key: field.key, label: field.label, value: fieldValue(field) })} aria-label={`Edit ${field.label}`}><Pencil size={14} aria-hidden="true" />Edit</button>
                {!essentialFields.has(field.key) && <button type="button" disabled={busy || editing !== null} onClick={() => change("remove", field.key)} aria-label={`Remove ${field.label}`}><Trash2 size={14} aria-hidden="true" />Remove</button>}
              </>}</div>}
            </form>
          </li>
        ))}
      </ul>
      {!locked && <>
        {editing?.key === "new" ? <form className="draft-field-form draft-new-field" onSubmit={save}>
          <label>Label<input name="label" value={editing.label} onChange={(event) => edit({ ...editing, label: event.target.value })} minLength="2" maxLength="80" required autoFocus disabled={busy} /></label>
          <label>Value<input name="value" value={editing.value} onChange={(event) => edit({ ...editing, value: event.target.value })} minLength="2" maxLength="500" required disabled={busy} /></label>
          <div className="draft-actions"><button className="primary" type="submit" disabled={busy}><Check size={14} aria-hidden="true" />Save</button><button type="button" disabled={busy} onClick={() => edit(null)}><X size={14} aria-hidden="true" />Cancel</button></div>
        </form> : <button type="button" disabled={busy || editing !== null} onClick={() => edit({ key: "new", label: "", value: "" })}><Plus size={14} aria-hidden="true" />Add a field</button>}
        <p>Done removes unused fields.</p>
        <button className="primary" type="button" disabled={busy || editing !== null} onClick={() => change("done")}><Check size={14} aria-hidden="true" />Done</button>
      </>}
      {busy && <p role="status">Saving…</p>}
      {notice && <p role="status">{notice}</p>}
      {error && <p className="draft-error" role="alert">{error}</p>}
    </details>
  );
}
