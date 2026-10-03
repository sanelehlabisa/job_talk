# Candidate application checks — 2026-10-03

JT-059 improves the existing candidate loop. Deployment and user usability
sign-off remain paused. JT-058's live language acceptance is also still pending.

## What changed

- Two entry cards are labelled **Available jobs**. **Find a different job** starts
  accountless discovery across every published, open database job. Only useful
  matches appear as suggestions; otherwise the view says no useful match yet.
- **Apply to this job** explicitly binds the current guest conversation once.
  It reuses statements from that chat against the selected criteria and preserves
  ownership, token expiry and isolation. The model cannot invent vacancy records.
- **Your application** shows targets, captured values, unclear/missing answers
  and gaps. It shares criterion keys with saved profiles, scoring and comparison.
  Corrections replace values. A tools gap does not erase general experience.
- Candidate AI output contains only proposed evidence updates with source quotes.
  Server checks enforce keys, types, quoted numbers, denials and current-chat
  sources. Older quotes cannot overwrite saved corrections. Wording with new
  unsupported terms falls back to the source text. These guards do not prove
  complete semantic understanding; review and real-provider tests remain needed.
- Contact review, consent, explicit Submit, immutable snapshots, recruiter
  comparison and the parallel-axis plot remain. Unclear numeric evidence scores
  zero; location scoring uses stored targets rather than relying only on prose.

## Tests

- Full backend suite: **73 passed** with `AI_PROVIDER=mock`. Final validation
  guards were then checked with the focused candidate suite.
- Tests exercise a relevant third job beyond the initial two cards; multi-field
  mocked interpretation; corrections; honest gaps; source/quantity/type checks;
  private-chat isolation; single-job selection; closed jobs; consent; snapshots;
  identical criterion keys in the visible fields and submitted score breakdown.
- Frontend production build: **passed**.
- Browser: `scripts/local-signoff.ps1 -RecruiterEmail templates-check@example.com`
  passed against the local development stack using fictional data. It creates and
  publishes a role, retries a failed send without losing text, captures several
  answers, corrects experience, records a tools gap, reviews contact/consent,
  submits, views recruiter comparison, closes recruitment and deletes the test
  application. A second guest then discovers and explicitly selects a real job.
- Desktop/phone screenshots were reviewed. The first review caught a tools
  denial incorrectly clearing experience. The fix and an added browser assertion
  passed on the repeated run; the corrected phone summary retains two years.

The existing plumber fixture was clarified to explicitly state durations for each
assessed trade skill. The parser no longer distributes a single duration across
unrelated clauses or treats common words such as “is” as matching evidence.

## Actual model attempt

OpenAI / `gpt-4o-mini`, 2026-10-03. Fictional input: two years building Python
applications and no Git experience. The provider returned HTTP 429,
`credit_balance_exhausted`, producing **no candidate updates**. The browser also
used the guided fallback. Live interpretation and polishing are **unverified**.
No API key, login token, or real candidate details are recorded here.

## Quick manual check

1. Choose **Find a different job**, describe your background, select a suggested
   real job, and check that earlier answers appear under its requirements.
2. Answer several requirements together; correct one duration and report a skill
   gap. Check that only the intended fields change and resolved questions stop.
3. Refresh, review the application, give contact details and consent, then Submit.
   As the owning recruiter, compare the saved values, evidence, gaps and plot.

Repeat using the actual LLM after API credit is available. User acceptance, owner
access (JT-061), manual vacancy entry (JT-062) and full JT-060 sign-off remain open.
