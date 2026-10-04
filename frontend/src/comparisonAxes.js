// Plot saved criterion values. Scores and ranking remain owned by the backend.
export function comparisonAxis(key, requirement, applications) {
  const numeric = requirement.type === "number" && Number.isFinite(requirement.target);
  const boolean = typeof requirement.target === "boolean";
  const kind = numeric ? "number" : boolean ? "boolean" : "text";
  const values = applications.map((application) => {
    const field = application.match_result?.criteria?.[key];
    if (!field?.evidence || field.gap === "missing") return null;
    if (field.gap === "reported") return boolean ? false : null;
    const value = field.candidate_value;
    if (numeric) return Number.isFinite(value) ? value : null;
    if (boolean) return typeof value === "boolean" ? value : null;
    return typeof value === "string" && value.trim() ? value.trim() : null;
  });
  const target = requirement.target;
  const format = (value) => typeof value === "boolean" ? (value ? "Yes" : "No")
    : `${value}${numeric && requirement.unit ? ` ${requirement.unit}` : ""}`;
  let ticks, position;
  if (numeric) {
    const available = values.filter((value) => value !== null);
    const low = Math.min(0, target, ...available);
    const high = Math.max(0, target, ...available);
    ticks = [...new Set([low, target, high])].sort((a, b) => a - b);
    position = (value) => high === low ? .5 : (value - low) / (high - low);
  } else if (boolean) {
    ticks = [false, true];
    position = (value) => value ? 1 : 0;
  } else {
    // Categorical positions show distinct answers, not an order of suitability.
    const category = (value) => String(value).trim().toLowerCase();
    ticks = [target, ...values.filter((value) => value !== null)]
      .filter((value, index, all) => all.findIndex((other) => category(other) === category(value)) === index);
    position = (value) => ticks.length === 1 ? 1
      : 1 - ticks.findIndex((other) => category(other) === category(value)) / (ticks.length - 1);
  }
  return { key, label: requirement.label || key.replaceAll("_", " "), kind, target, values, ticks, position, format };
}
