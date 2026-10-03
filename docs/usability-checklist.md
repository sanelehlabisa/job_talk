# Manual usability check

Status: **Pending actual LLM verification and user acceptance (2026-10-03).** This is
the acceptance checklist for JT-057 through JT-062. JT-057/JT-058/JT-059 have
implementation checks recorded in the recruiter and candidate test notes.
JT-061 owner access and JT-062 manual vacancies passed backend/local browser
checks, including persistence across restart (see TASKS.md). Live
OpenAI attempts returned `credit_balance_exhausted`; language quality remains
unverified. Deployment stays paused.

Use fictional people and an approved test recruiter. Run the existing local
stack with `docker compose -f dev.docker-compose.yaml up -d`. Repeat the visible
flow on desktop and phone size. Record confusing steps as failures even if the
API succeeds.

- [ ] **Create and correct a developer job.** Choose Junior Software Developer
  and paste: "junior dev for our Cape Town team, hybrid two days in office,
  JavaScript and Git needed, one year hands-on coding, 40 hours Mon-Fri,
  available next month, qualification requirement still unsure." Change
  experience to two years, then say "No degree needed." The live summary must
  update the same key, resolve qualifications as not required, stop asking about
  them, and exclude them from scoring. Resolve any other unclear fields, review,
  and publish explicitly.
- [ ] **Create two different roles.** Make a Plumber role, then use Generic Role
  for a shop assistant. No developer/plumber criteria or confirmed template
  guesses should appear in the other draft. Refresh each before publishing and
  confirm the saved answers remain.
- [ ] **Discover a different job.** With at least three distinct jobs open,
  ignore the two available-job cards. Use Find a different job, describe plumbing
  experience, and select a relevant real listing outside the initial cards.
  The application should now show that job's confirmed requirements.
- [ ] **Give several answers and an honest gap.** Supply skills, duration,
  location, and availability together. Correct one answer, give a short relevant
  reply, an unrelated reply, and say "I haven't installed geysers." Check that
  the right fields change, resolved questions stop, the gap remains explicit,
  and unsupported claims do not appear. Review contact details and consent;
  submit only when the summary is accurate.
- [ ] **Compare candidates.** Submit strong, partial, and unrelated fictional
  candidates. Read the short cards and explain the score differences. Check the
  values, evidence, weights, top-five comparison, and parallel plot against the
  exact confirmed job criteria; qualifications marked not required must be absent.
- [ ] **Review owner access.** Sign in with the configured, approved owner email
  and a code from Mailpit. In All jobs, select another recruiter's listing and
  inspect its submitted candidates and plot. Refresh and repeat on phone size.
  Sign in as an ordinary recruiter and confirm All jobs is absent and only their
  own applicants are available. Neither view should expose full candidate chats.
- [ ] **Use a manual vacancy.** With the approved owner email
  configured, paste one manually checked vacancy with its source, review and
  publish it, then submit a test application. Confirm who receives it is clear.
  Restart the local stack normally (preserving volumes) and confirm it remains.
  The owner sees submitted applications across jobs; another recruiter sees only
  theirs. A logged-out request must not expose any application.

Record the result in this table when executing JT-060:

| Evidence | Result |
| --- | --- |
| Revision tested | JT-058: `0b04303`; JT-059: `a39f333`; JT-061: `b45309c`; approved for master on 2026-10-03 |
| Deterministic/fallback scenarios | See [recruiter](recruiter-draft-checks.md) and [candidate](candidate-application-checks.md) engineering checks |
| Actual LLM: provider/model, date, scenarios, outcomes | OpenAI / `gpt-4o-mini`, 2026-10-03; recruiter and candidate attempts blocked by API credit |
| Live cases that fell back or failed | Both used guided fallback after HTTP 429 `credit_balance_exhausted` |
| Desktop/phone observations and remaining issues | Engineering screenshots reviewed; user acceptance pending |
| Owner/recruiter/guest access checks | JT-061: 78 backend tests and focused owner browser check passed; user acceptance pending |
| Manual vacancies and persistence | JT-062: 81 backend tests, build, guided browser flow and two backend/PostgreSQL restarts passed with fictional data; no live LLM calls |
| User decision: usable / needs fixes | Pending |

Do not put API keys, login codes, tokens, or real candidate details in this
record. Mark actual LLM checks not run when unavailable; mock success alone does
not establish language understanding. The user decides whether the flow is
usable and separately authorizes resuming deployment.
