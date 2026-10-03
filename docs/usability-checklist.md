# Manual usability check

Status: **Focused Gemini checks passed; broader scenarios and user acceptance pending (2026-10-03).** This is
the acceptance checklist for JT-057 through JT-062. JT-057/JT-058/JT-059 have
implementation checks recorded in the recruiter and candidate test notes.
JT-061 owner access and JT-062 manual vacancies passed backend/local browser
checks, including persistence across restart (see TASKS.md). Live
OpenAI attempts returned `credit_balance_exhausted`. JT-064's actual Gemini
checks below cover one hiring flow and discovery extraction. Deployment stays paused.

Use fictional people and an approved test recruiter. Run the existing local
stack with `docker compose -f dev.docker-compose.yaml up -d`. Repeat the visible
flow on desktop and phone size. Record confusing steps as failures even if the
API succeeds.

## Quick local walkthrough

### Published edits and immediate discovery (JT-069)

1. Publish a role. Keep typing in its chat or edit a form value. Confirm the public
   listing changes only after **Publish changes**, and the same chat stays open.
2. Submit an application, then change a scored requirement and publish it. Check
   that the old application keeps its evidence and original score, is labelled
   **Earlier requirements**, and is excluded from the current comparison plot.
3. Choose **Find a different job**. Before sending anything, see guidance and up
   to two real **Available job** examples. Describe your background and check
   suggestions update. Try phone width too.
4. Close a role. The recruiter chat remains editable, while new applications are
   stopped. Reload and confirm the saved form is still present.

Automate the UI check with `scripts/local-signoff.ps1 -LiveEditingOnly` and
`-RecruiterEmail <approved-test-email>`. It closes its own fictional job and
deletes its test guest. Backend regressions use disposable SQLite only.

**Engineering checks (2026-10-03):** 118 isolated backend tests and frontend build
passed. The browser used configured Gemini without mocking and passed published
chat correction/republish/reload, initial examples, circuit/PCB discovery and
phone layout. Confirmed-target matching was corrected after the first discovery
check failed. These checks do not replace your usability approval; deployment
remains paused.

### Simple form and closing date (JT-068)

1. Check **Working hours**: one label and one input, without duplicate text or
   status/type/importance controls. Edit the value directly, save, then refresh.
2. Add/edit/remove a field using the labelled icon buttons; check phone width.
3. Say "Applications close on 30 November 2026" in chat. Change the captured date
   using the form, save and refresh. It must never appear as an applicant criterion.
4. Remove the date and use Done: publishing must still be available when the
   required job details are complete. Publish remains a separate action.

**Checks (2026-10-03):** 113 isolated backend tests, 10 final focused checks and
the frontend build passed.
The real browser verified actual Gemini chat date capture and value polishing,
direct input edits, the date picker, CRUD, Done, reload and phone layout. The
fictional job remains unpublished. Deterministic tests covered closing-day UTC
boundaries and rejection of late applications across candidate endpoints.
Your manual usability approval remains separate; deployment is paused.

### Recruiter form control (JT-067)

1. Describe a role in one message. Check that red fields mean missing/unclear
   answers and green fields mean confirmed/not required.
2. Ask chat to add a separate job-related requirement, such as soldering PCB
   components. Check the new label and description.
3. Use **Add a field**, then **Save** with a misspelled requirement.
   Edit it again; confirm its meaning is preserved. If AI is unavailable, the
   notice must say the original wording was saved.
4. Remove a field. Click **Done** or say "ready for publication": blank optional
   suggestions disappear; required job details and unclear answers remain.
5. Refresh and check the saved form. Only **Publish job** makes it public; the
   published jobs remain editable, with a separate **Publish changes** action.
   Try this at phone width too.

**Engineering checks, 2026-10-03:** The full 108-test backend suite passed, followed
by 20 final draft/history checks covering removal and numeric guards. The frontend
production build passed. Real Gemini
captured the reported Durban paragraph, added soldering through chat, polished
a misspelled form edit and stored an age restriction as an informational note
excluded from scoring. Done and explicit publication passed in disposable SQLite.
The real browser also passed emailed sign-in, add/polish, edit, remove, Done,
reload and phone layout; its dedicated fictional draft remains unpublished.
This is implementation evidence; the user's manual usability approval is pending.

Repeat the browser check with an approved test recruiter:

```powershell
./scripts/local-signoff.ps1 -RecruiterEmail draft-editor-check@example.com -DraftEditorOnly
```

The check makes three real AI requests when a provider is enabled. It creates
only its own fictional draft and leaves it unpublished.

### Local test data incident, 2026-10-03

During JT-064, an incorrectly isolated pytest run imported the application before
selecting SQLite. Its reset fixture reached development PostgreSQL and dropped
the application tables in `job_talk`. Existing jobs/chats/applications have **not
been recovered**. This was an assistant test setup error, not a Gemini action.

Tests now select SQLite before application imports and refuse to reset any
connection other than the disposable test database. A regression verifies that
PostgreSQL and the normal application SQLite filename are both rejected.

The affected volume was stopped and preserved in ignored local storage at
`backups/2026-10-03-test-incident/affected-postgres-volume.tar.gz`. This captures
the state **after** the loss; it is not a working pre-incident backup. The older
`job-talk_job_talk_data` Docker volume, last modified September 16, remains
untouched. No recent backup has been located. Recovery or permission to abandon
the earlier test records is pending the user's answer.

For UI testing, local `.env` now selects `POSTGRES_DB=job_talk_gemini_test`, a
separate database with three seeded jobs and the configured owner approved.
Sign in again or use a private window; earlier sessions refer to the affected
database. Do not remove the affected database, archive or older volume while
the recovery question remains open.

### Guided core loop

Use this first to check the core loop. The labelled recruiter text also works in
guided fallback; success here does not verify actual LLM understanding.

1. Open [Job Talk](http://localhost:3000), choose **I'm hiring**, and use your
   configured owner email or `recruiter@example.com`. Get the code from
   [Mailpit](http://localhost:8025).
2. Choose **New hiring conversation -> Plumber** and paste:

   ```text
   Job title: Plumber; Role description: Repair residential pipes; Work arrangement: on-site; Location: Cape Town; Experience: two years of plumbing experience; Plumbing required; Pipe fitting required; Tools: pipe cutters required; No degree needed; Working hours: weekdays; Start availability: immediately
   ```

3. Check **Who you're looking for**, then publish explicitly. Qualifications
   should be not required and absent from scoring. Copy the job link.
4. Open that link in a private browser window. Submit each fictional applicant
   below with fictional contact details and consent. Close **all** private
   windows between applicants to start a fresh guest session. Before submission,
   check **Your application** and try "I like pizza"; saved answers must stay intact.

   | Applicant | Message |
   | --- | --- |
   | Strong | I worked on-site in Cape Town. I have four years of plumbing experience. I repaired plumbing and fitted pipes. I used pipe cutters on residential jobs. I can work weekdays and start immediately. |
   | Partial | I have one year of plumbing experience in Cape Town. I cannot do pipe fitting. I have not used pipe cutters. I can work on-site on weekdays and start immediately. |
   | Unrelated | I have four years of Python experience in Johannesburg. I built Python websites. |

5. Return to the recruiter job. Strong should score above Partial and Unrelated.
   Partial must show the reported gaps. Unrelated must **not** receive plumbing
   experience credit or appear as a recommended match. Check the cards and plot
   against the published requirements, then refresh and check they persist.
6. Repeat the core screens at phone width. Report any confusing step, incorrect
   value or repeated question. Close the fictional job when finished.

Then try the natural-language scenarios below. Check whether the app says it is
using guided questions; record those runs as fallback, not actual AI success.

## Full acceptance scenarios

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
  and a code from Mailpit. Open another recruiter's draft from All hiring
  conversations; edit it, then sign in as its recruiter and check the same saved
  changes. Use the normal publish, compare and close controls. Refresh and repeat
  on phone size. Ordinary recruiters should see only their own conversations
  and applicants. Neither view should expose full candidate chats.
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
| JT-064 actual Gemini | `gemini-3.5-flash-lite`, 2026-10-03: browser developer draft from one paragraph (10/10 fields), numeric correction, no degree, publish, accountless multi-field application, Git gap, consent/submit and recruiter comparison passed without fallback. Candidate scored 77%, with 3 years against the corrected 2-year target. Separate live discovery extraction captured Cape Town/hybrid and stopped the repeated location question. |
| JT-064 failures and limits | 2.5 Flash-Lite returned 404 for this new project. Early 3.5 checks exposed rejected short source quotes, capitalized Hybrid, and descriptions converting written numbers to digits; prompt/validation fixes passed the final live developer flow. Plumber/Generic live conversations, broader ambiguity and user sign-off remain untested. |
| JT-064 test safety | 95 isolated backend tests passed, followed by focused checks after the last validation fixes (13 draft/provider checks and all 11 Gemini regressions). Earlier incorrectly isolated run caused the local data incident documented above. |
| Desktop/phone observations and remaining issues | Engineering screenshots reviewed; user acceptance pending |
| Owner/recruiter/guest access checks | JT-061: 78 backend tests and focused owner browser check passed; user acceptance pending |
| JT-065 shared owner workspace | 14 isolated admin/manual-vacancy/candidate tests and frontend build passed. Browser verified emailed login, all hiring chats with owner labels, another recruiter's editable draft, shared comparison/close controls, refresh and phone navigation. No LLM calls. Published criteria retain the normal lock. |
| Manual vacancies and persistence | JT-062: 81 backend tests, build, guided browser flow and two backend/PostgreSQL restarts passed with fictional data; no live LLM calls |
| JT-060 guided comparison follow-up | 2026-10-03: 84 backend tests passed in isolated SQLite; separate Plumber/Generic jobs, strong/partial/unrelated submissions, fields/targets/weights/scores and frozen comparison verified. Fixed singular-year draft validation and unrelated trade experience credit. No new browser or actual LLM run; visible plot and live language acceptance remain pending. |
| User decision: usable / needs fixes | Pending |

Do not put API keys, login codes, tokens, or real candidate details in this
record. Mark actual LLM checks not run when unavailable; mock success alone does
not establish language understanding. The user decides whether the flow is
usable and separately authorizes resuming deployment.
