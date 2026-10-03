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

export function JobTemplatePicker({ templates, busy, onSelect, onCancel }) {
  return (
    <section className="template-picker" aria-labelledby="template-picker-title">
      <h1 id="template-picker-title">Start with a role</h1>
      <p>Choose a starting point, then describe what you need. Each job gets its own draft. Suggestions become requirements only when you confirm them.</p>
      <div className="template-options">
        {templates.map((template) => (
          <button className="template-choice" data-template-id={template.template_id} key={template.template_id} type="button" disabled={busy} onClick={() => onSelect(template.template_id)}>
            <strong>{template.label}</strong>
            <span>{template.description}</span>
          </button>
        ))}
      </div>
      {busy && <p role="status">Opening your draft…</p>}
      <button className="ghost" type="button" disabled={busy} onClick={onCancel}>Cancel</button>
    </section>
  );
}

export function JobDraftSummary({ draft }) {
  return (
    <details className="template-draft" open>
      <summary>{draft.label} · starter fields</summary>
      <p>Describe or correct these fields in the chat. Suggestions are examples, not confirmed requirements.</p>
      <ul>
        {draft.fields.map((field) => (
          <li key={field.key} data-field-key={field.key} data-field-state={field.state}>
            <div><strong>{field.label}</strong><span className={`draft-state ${field.state}`}>{stateLabels[field.state]}</span></div>
            {field.state === "not_required" ? <p>Excluded from assessment.</p> : field.target !== null && field.target !== undefined ? (
              <p>{displayValue(field.target, field.unit)}</p>
            ) : field.suggestion !== null && field.suggestion !== undefined ? (
              <p className="draft-suggestion">Suggestion: {displayValue(field.suggestion, field.unit)}</p>
            ) : <p>{field.description}</p>}
          </li>
        ))}
      </ul>
    </details>
  );
}
