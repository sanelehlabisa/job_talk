function valueText(value, unit, target = false) {
  if (value === true) return target ? "Demonstrate this skill" : "Reported skill";
  if (value === null || value === undefined) return "Not yet provided";
  return `${value}${unit ? ` ${unit}` : ""}`;
}

export function ApplicationSummary({ fields, submitted }) {
  const labels = { captured: "Captured", gap: "Reported gap", needs_clarification: "Needs clarification", unanswered: "Unanswered" };
  const resolved = fields.filter((field) => ["captured", "gap"].includes(field.state)).length;
  return (
    <details className="template-draft application-summary" open>
      <summary>Your application</summary>
      <p>{resolved}/{fields.length} answers captured. {submitted ? "Your submitted answers are saved." : "You can correct an answer in chat. An honest skill gap is a valid answer."}</p>
      <ul>{fields.map((field) => (
        <li key={field.key} data-field-key={field.key} data-field-state={field.state}>
          <div><strong>{field.label}</strong><span className={`draft-state ${field.state}`}>{labels[field.state]}</span></div>
          <p><b>Role asks:</b> {valueText(field.target, field.unit, true)}</p>
          <p>{field.description}</p>
          <p><b>Your answer:</b> {field.state === "gap" ? "You reported a gap" : valueText(field.value, field.unit)}</p>
          {field.evidence && <p>{field.evidence}</p>}
        </li>
      ))}</ul>
    </details>
  );
}
