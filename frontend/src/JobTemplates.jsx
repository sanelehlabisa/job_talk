import { useState } from "react";

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

function DraftFieldForm({ field, busy, onSave, onCancel }) {
  const [kind, setKind] = useState(field?.type || "text");
  async function save(event) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    await onSave({
      key: field?.key || null, label: data.get("label"), type: kind,
      target: kind === "skill" ? true : kind === "number" ? Number(data.get("target")) : data.get("target"),
      unit: kind === "number" ? data.get("unit") || null : null,
      importance: data.get("importance") || "unspecified",
      description: data.get("description") || `${data.get("label")}: ${data.get("target")} ${data.get("unit") || ""}`.trim(),
    });
  }
  return <form className="draft-field-form" onSubmit={save}>
    <fieldset disabled={busy}>
      <legend>{field ? `Edit ${field.label}` : "Add a requirement"}</legend>
      <label>Label<input name="label" defaultValue={field?.label || ""} minLength="2" maxLength="80" required autoFocus /></label>
      <label>Answer type<select value={kind} onChange={(event) => setKind(event.target.value)} disabled={field?.scope === "metadata"}>
        <option value="text">Text requirement</option><option value="number">Minimum amount</option><option value="skill">Skill to demonstrate</option>
      </select></label>
      {kind !== "skill" && <label>{kind === "number" ? "Minimum" : "Requirement"}<input name="target" type={kind === "number" ? "number" : "text"} min={kind === "number" ? "0" : undefined} max={kind === "number" ? "100000" : undefined} step="any" maxLength="500" defaultValue={field?.target ?? ""} required /></label>}
      {kind === "number" && <label>Unit<input name="unit" maxLength="40" defaultValue={field?.unit || ""} placeholder="e.g. years" /></label>}
      <label>Short description{kind !== "skill" ? " (optional)" : ""}<textarea name="description" rows="3" minLength="4" maxLength="500" defaultValue={field?.target != null ? field.description : ""} required={kind === "skill"} placeholder="What should the applicant demonstrate?" /></label>
      {field?.scope !== "metadata" && <label>Importance<select name="importance" defaultValue={field?.importance === "preferred" ? "preferred" : "required"}><option value="required">Required</option><option value="preferred">Preferred</option></select></label>}
      <div className="draft-actions"><button className="primary" type="submit">{busy ? "Saving…" : "Save & polish"}</button><button type="button" onClick={onCancel}>Cancel</button></div>
    </fieldset>
  </form>;
}

export function JobDraftSummary({ draft, locked = false, busy = false, onChange, onEditingChange }) {
  const [editing, setEditing] = useState(null);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  function edit(key) { setEditing(key); setError(""); onEditingChange?.(key !== null); }
  async function change(action, value) {
    setError(""); setNotice("");
    try {
      const result = await onChange(action, value);
      setNotice(result.notice);
      edit(null);
    } catch (err) { setError(err.message); }
  }
  return (
    <details className="template-draft" open>
      <summary>Who you're looking for</summary>
      <p>{draft.fields.filter((field) => ["confirmed", "not_required"].includes(field.state)).length}/{draft.fields.length} fields answered · {draft.label}</p>
      <p>{locked ? "These published requirements are locked so applications stay comparable." : "Edit the form or ask the chat to help. Save & polish checks the wording with AI. Review it before publishing."}</p>
      <ul>
        {draft.fields.map((field) => (
          <li key={field.key} data-field-key={field.key} data-field-state={field.state}>
            {editing === field.key ? <DraftFieldForm field={field} busy={busy} onSave={(value) => change("save", value)} onCancel={() => edit(null)} /> : <>
            <div><strong>{field.label}</strong><span className={`draft-state ${field.state}`}>{stateLabels[field.state]}</span></div>
            {field.state === "not_required" ? <p>Excluded from assessment.</p> : field.target !== null && field.target !== undefined ? (
              <><p>{displayValue(field.target, field.unit)}</p>{field.scope === "criterion" && <p>{field.importance === "preferred" ? "Preferred" : field.importance === "required" ? "Required" : ""}{field.importance !== "unspecified" ? " · " : ""}{field.description}</p>}</>
            ) : field.suggestion !== null && field.suggestion !== undefined ? (
              <p className="draft-suggestion">Suggestion: {displayValue(field.suggestion, field.unit)}</p>
            ) : <p>{field.description}</p>}
            {field.scope === "metadata" && !essentialFields.has(field.key) && <p>Informational only · Not scored or used to filter applicants</p>}
            {!locked && <div className="draft-actions"><button type="button" disabled={busy || editing !== null} onClick={() => edit(field.key)} aria-label={`Edit ${field.label}`}>Edit</button>{!essentialFields.has(field.key) && <button type="button" disabled={busy || editing !== null} onClick={() => change("remove", field.key)} aria-label={`Remove ${field.label}`}>Remove</button>}</div>}
            </>}
          </li>
        ))}
      </ul>
      {!locked && <>
        {editing === "new" ? <DraftFieldForm busy={busy} onSave={(value) => change("save", value)} onCancel={() => edit(null)} /> : <button type="button" disabled={busy || editing !== null} onClick={() => edit("new")}>Add a field</button>}
        <p>Done removes blank optional fields. Keep the role, work arrangement, location rules and at least one assessment criterion.</p>
        <button className="primary" type="button" disabled={busy || editing !== null} onClick={() => change("done")}>Done</button>
      </>}
      {busy && <p role="status">Saving your changes…</p>}
      {notice && <p role="status">{notice}</p>}
      {error && <p className="draft-error" role="alert">{error}</p>}
    </details>
  );
}
