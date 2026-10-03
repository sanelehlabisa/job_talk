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

export function JobDraftSummary({ draft, locked = false }) {
  return (
    <details className="template-draft" open>
      <summary>Who you're looking for</summary>
      <p>{draft.fields.filter((field) => ["confirmed", "not_required"].includes(field.state)).length}/{draft.fields.length} fields answered · {draft.label}</p>
      <p>{locked ? "These published requirements are locked so applications stay comparable." : "Describe or correct these fields in the chat. Suggestions are examples, not confirmed requirements."}</p>
      <ul>
        {draft.fields.map((field) => (
          <li key={field.key} data-field-key={field.key} data-field-state={field.state}>
            <div><strong>{field.label}</strong><span className={`draft-state ${field.state}`}>{stateLabels[field.state]}</span></div>
            {field.state === "not_required" ? <p>Excluded from assessment.</p> : field.target !== null && field.target !== undefined ? (
              <><p>{displayValue(field.target, field.unit)}</p>{field.scope === "criterion" && <p>{field.importance === "preferred" ? "Preferred" : field.importance === "required" ? "Required" : ""}{field.importance !== "unspecified" ? " · " : ""}{field.description}</p>}</>
            ) : field.suggestion !== null && field.suggestion !== undefined ? (
              <p className="draft-suggestion">Suggestion: {displayValue(field.suggestion, field.unit)}</p>
            ) : <p>{field.description}</p>}
          </li>
        ))}
      </ul>
    </details>
  );
}
