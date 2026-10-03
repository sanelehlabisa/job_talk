import { useEffect, useState } from "react";
import { api } from "./api";

export function SourceNotice({ source, compact = false, owner = false }) {
  if (!source) return null;
  if (compact) return <span className="source-label">Added by Job Talk · Applications go to Job Talk, not the advertised employer.</span>;
  return <section className="source-notice" aria-label="Vacancy source and recipient">
    <strong>Added by Job Talk from a public advert</strong>
    <p>{source.employer} · Checked {source.checked_on} · <a href={source.url} target="_blank" rel="noreferrer">Original advert</a></p>
    <p>{owner ? "Interest comes to Job Talk. Ask for separate candidate permission before sharing identifying details with the advertised employer." : "Your application goes to the Job Talk operator. The advertised employer has not joined through this listing and does not receive your application. We will ask your permission before sharing identifying details with them."}</p>
  </section>;
}

export function InterestSummary({ jobId }) {
  const [summary, setSummary] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let cancelled = false;
    setSummary(null);
    setError("");
    api.jobInterest(jobId).then((value) => { if (!cancelled) setSummary(value); })
      .catch((err) => { if (!cancelled) setError(err.message); });
    return () => { cancelled = true; };
  }, [jobId]);
  return <section className="interest-summary" aria-label="Interest summary">
    <h2>Interest summary</h2>
    <p>Only counts are shown here. Share this summary separately from the private candidate cards below. Evidence is self-reported and unverified.</p>
    {error ? <p className="error" role="alert">{error}</p> : !summary ? <p role="status">Loading summary…</p> : <>
      <strong>{summary.applications} applications · {summary.strong_matches} strong matches</strong>
      <ul>{summary.criteria.map((item) => <li key={item.key}>{item.label}: {item.strong_evidence} with strong evidence</li>)}</ul>
    </>}
  </section>;
}
