# Job Talk

Job Talk is an early product experiment for people who can do the work but may not have a polished CV. Candidates describe their experience in a job-specific conversation. Recruiters receive structured evidence and explainable match differences that make candidates easier to compare.

The project brief focuses on informal, trade, and entry level job seekers and small employers seeking local talent. Its proposed product includes low data web or WhatsApp chat, voice notes, and anonymous candidate previews. **This repository currently implements a text only web demo.** WhatsApp, voice notes, identity checks, anonymous employer shortlists, and payments are future work.

## Why this project

The brief identifies three barriers: job seekers may not want a public search, practical skills can be missed by CV screening, and conventional applications often give little feedback. Job Talk explores a private conversation that draws out work experience and gives both sides a clearer reason for a match.

The experiment is free. Payments, subscriptions, recruiter-verification automation,
advanced job discovery, and external integrations are deferred until usage and
recruiter feedback show that the core workflow is useful.

## Current experiment

The question is: **will recruiters find conversational applications and
structured candidate comparison useful?** Recruiters will be manually approved.
Candidates will open a published job and apply without an account, using a secure
guest application session. The implementation subtasks and acceptance checks are
in [`TASKS.md`](TASKS.md); the pitch, demo, video, distribution, and measurement
plan are in [`docs/experiment-launch.md`](docs/experiment-launch.md).

The current build target is one complete loop: **Define -> Apply -> Score ->
Compare.** Recruiter criteria use one shared structure throughout the product;
candidate evidence and match explanations reference those same stable keys. The
contract and intentionally narrow scope are in
[`docs/core-mvp.md`](docs/core-mvp.md).

## Current status: deployment preparation and usability sign-off

**Planned production address:** [https://jobtalk.roventics.com](https://jobtalk.roventics.com).
This is the chosen destination, not confirmation that the service is live.

The core hiring loop works locally. Completed work through JT-077 is merged into
the default branch, `master`, including the editable candidate form, discovery
and Gemini ratings. JT-076 verifies token access, recruiter approval and logout.
JT-077 adds production Nginx origin/host checks, request limits and security headers.
JT-078 now uses one `.env` file and a private Nginx/backend Unix socket. JT-079
passed a browser run with an approved recruiter and five fictional candidates
using actual Gemini. Relevant candidates discovered the job and ranked above
unrelated applicants; saved scores and the comparison plot agreed. See the
[results and manual checklist](docs/usability-checklist.md#five-candidate-browser-exercise-jt-079).
JT-070 prepared `prod.docker-compose.yaml` and verified Nginx/HTTPS
in an isolated local stack. Production preparation is authorized; VM deployment
and the user's final usability sign-off are still pending.

The [current P0 tickets](TASKS.md#p0---current-ordered-usability-work) track progress:

- JT-057 adds three fixed templates and separate saved drafts. JT-058 implements
  validated field updates, explicit not-required answers, and a live **Who you're
  looking for** summary. JT-064 verified a developer draft, correction and
  publication with actual Gemini responses on 2026-10-03.
- JT-059 implements two available-job cards, **Find a different job** across all
  open listings, explicit job selection, and a live **Your application** summary.
  Deterministic/browser checks cover corrections and honest gaps. JT-064 also
  verified one live Gemini application and a focused discovery extraction.
- JT-072 simplifies **Your application** to the recruiter form's label/value
  layout. Edit or clear your answers directly, or fill them through chat. Review
  contact details, consent and **Submit application** at the bottom of this form.
  Application cards and the separate review panel are removed from the chat.
- JT-073 adds a shared chat-bubble logo/browser icon and **Match so far** above
  the application form. The backend score refreshes after chat replies and saved
  edits; submitted applications show their original saved match percentage.
- JT-074 makes discovery replies name real numbered job suggestions. A 15%
  exploratory cutoff plus a work-related connection shows possible roles earlier.
  Scores refresh after every message but percentages appear only after selecting
  a job. The introductory guidance appears once, and raw profile chips are hidden.
- JT-075 uses Gemini for criterion ratings and short reasons, with backend
  validation, weights and totals. Saved ratings persist through submission.
- JT-076 checks every private API route against unusable tokens, preserves
  approval/ownership checks, makes email codes atomic and verifies logout/retry.
- JT-077 keeps the backend private behind Nginx, rejects foreign browser requests,
  limits API/auth traffic and adds a browser content policy. Public API URLs remain
  reachable; private actions require tokens and backend permissions. See the
  [proxy policies and isolated check](docs/production-operations.md#proxy-request-policies-jt-077).
- JT-061 implements owner access through backend `ADMIN_EMAIL` and existing
  email-code sessions. JT-065 uses the same recruiter workspace for admin, with
  all job-creation chats, owner labels and editing controls. Ordinary recruiters
  keep access to their own chats and applications. JT-062 adds manual entry of
  source-labelled vacancies through the existing draft/review/publish flow.
- JT-069: published recruiter chats remain editable; **Publish changes** updates
  the live job while preserving submitted scores. Discovery shows real examples
  immediately and updates suggestions using confirmed job requirements.
- JT-070: production images build; isolated HTTP bootstrap, HTTPS routing and
  Bearer-token access passed. Real DNS, certificates and SMTP still need VM checks.
- JT-060: broader conversations, separately recorded actual LLM and fallback
  results, and the user's [manual acceptance checklist](docs/usability-checklist.md).
  The latest guided comparison checks fixed unrelated experience being counted
  toward a trade requirement and singular "one year" blocking a draft. Broader
  live language scenarios and user sign-off remain open.

**Local data incident:** A JT-064 test setup error dropped the earlier development
database tables. Those records are not recovered. The UI currently uses a
separate seeded `job_talk_gemini_test` database; sign in again or use a private
window. The affected volume is preserved and recovery is pending the user's
answer. See the [incident record](docs/usability-checklist.md#local-test-data-incident-2026-10-03).

Ready for a local hands-on check: the
[cleaned admin workspace](docs/usability-checklist.md#current-local-workspace-jt-080-2026-10-04)
contains five jobs. Open Junior Software Developer for five saved applicants and
their comparison plot, or follow the
[quick walkthrough](docs/usability-checklist.md#quick-local-walkthrough) with a new job.

Jobs, criteria, chats, and submitted applications already persist in PostgreSQL
in the development stack. Protected endpoints already use expiring bearer
sessions issued after sign-in; the single-use login code is not an API token.
Manually entered vacancies retain their source details in the existing job draft.
Deployment resumes only after user acceptance and an explicit request to resume.

### Deployment readiness

Ready for a controlled VM setup once its environment is configured; **not yet
verified for a public launch**. Before inviting candidates:

- Point `jobtalk.roventics.com` to the VM and allow Nginx ports 80/443.
- Prepare ignored `.env` with strong database/session secrets, working
  SMTP, the selected LLM key, monitored contact addresses and `ADMIN_EMAIL`.
  The local `.env` is configured for development; configure the VM's `.env`
  separately using the production values in the guide.
- Issue the real certificate, run the renewal dry-run, verify backups and test
  email-code login plus create/apply/compare on the live domain.
- Complete the [manual usability check](docs/usability-checklist.md) on the live
  domain before inviting users. The default branch is named `master`; the user
  approved merging the completed work and this access review on 2026-10-04.

The [production guide](docs/production-operations.md) contains the commands.

### Protection of private information

| Information or action | Server-side protection |
| --- | --- |
| Chats, messages, drafts and job edits | Expiring Bearer token plus chat/job ownership; approved admin can manage hiring chats. |
| Create or publish a job | Manually approved recruiter, checked on every request; candidates and pending/rejected recruiters cannot post. |
| Submitted applications and contact details | The candidate's own session, the owning approved recruiter, or the configured approved admin. |
| Admin-only vacancy-interest totals | Approved recruiter matching backend `ADMIN_EMAIL`, checked on each request. |
| Public listings, guest entry, code sign-in and health checks | Intentionally public; they do not expose candidate chats or applications. |

Tokens are random, stored as hashes on the backend, checked for expiry (24 hours
by default, configured with `AUTH_SESSION_HOURS`), and revoked immediately after
a successful logout. Only that browser session is revoked; other signed-in
sessions stay active. If logout cannot reach the server, the UI shows a retry
message instead of pretending the session was revoked. Email codes are short-lived
and single-use even under simultaneous verification requests; the code itself
cannot authorize API calls. Nginx is the only production service with host ports,
and requests to private API routes still require app authentication through it.
The staging webpage password is an extra webpage gate, not the API's data guard.
See [privacy and access details](docs/privacy-and-safety.md).

**Checked 2026-10-04:** 84 focused backend checks passed across isolated SQLite
runs after fixing the atomic update's SQLite timezone handling and a test email
fixture. These include every private route's missing/forged/expired/logged-out
token rejection, recruiter approval, ownership, concurrent code attempts and
production settings. Frontend build and actual local email-code login plus
browser logout failure/retry/replay passed. Production Compose validation confirms
only Nginx publishes 80/443. No VPS environment or public TLS/SMTP was verified.

## Existing implementation

- **New hiring conversation** offers Junior Software Developer, Plumber, and
  Generic Role starters. Suggestions are labelled separately from saved answers;
  choosing a template creates no confirmed requirements or public job.
- Template conversations can fill multiple fields in one answer and correct an
  existing field. Qualifications can be explicitly not required; text and
  practical skill targets do not need years. The backend only publishes once
  every remaining field is resolved, location rules are clear, and at least one meaningful
  assessment criterion is confirmed. Review the summary, then click **Publish**.
- Recruiters see a label and one editable value per row, with icon buttons for
  **Add a field**, **Edit**, **Remove**, **Save** and **Cancel**. **Save** asks AI
  to refine wording; if unavailable, the entered value is saved with a notice.
  Types, units and importance remain behind the form. Red borders mark gaps;
  green marks resolved fields. **Done** (or "ready for publication" in chat)
  removes blank optional suggestions. Essential job details and partially answered
  requirements remain. Review the result and use the separate **Publish job** button.
  Personal characteristics such as age are informational only, excluded from
  candidate scores and filters. Published jobs keep the same editable chat and form.
- **Closing date** is optional. Set it in chat (include the year) or with the date
  input; remove it to leave the draft open-ended. It is stored with the job, never
  scored, and applications remain open through that day in UTC. The backend hides
  expired jobs and rejects late applications without a scheduler or new database table.
- When AI is unavailable, the chat explains guided mode once per conversation.
  Later replies go straight to the next question. Use explicit answers
  such as `Location: Cape Town`, `Working hours: weekdays`, or `No degree needed`.
  This fallback is limited; it does not establish natural-language understanding.
- Sending a message immediately shows your bubble and clears the composer while
  the reply loads. Failed sends restore the text for retry; successful replies
  replace the temporary bubble with the saved message.
- Passwordless entry: job seekers start a private guest conversation immediately,
  while approved recruiters sign in with a short-lived email code.
- Three realistic demo jobs, public links and a job picker, and a guest
  conversation anchored to the selected role.
- Seeker entry labels its two cards **Available jobs**. **Find a different job**
  opens a discovery chat with guidance and up to two real available-job examples
  immediately. As context arrives it searches all published open jobs and shows
  up to two numbered possible roles; otherwise examples remain labelled as
  examples. Chat names these same jobs and explains their relevance. **Apply
  to this job** binds the guest conversation to that role and reuses earlier answers.
- **Your application** shows the employer's criteria, captured answers, questions
  still needing clarification, and reported gaps. Corrections replace the same
  criterion's answer. A gap does not prevent review, consent or submission.
- Rule based extraction of skills, experience, location, and work preferences from text, including trade examples.
- Deterministic follow-up questions that ask for the selected job's highest-weight
  missing evidence and resume from the saved draft after a refresh.
- Conversational job drafting that asks whether each detected skill or tool is
  required or preferred and how much experience applicants should have.
- A structured role summary before publishing. Recruiters can paste a description
  or correct an attribute in ordinary chat. Completion phrases prepare the role
  for review; only the visible `Publish job` button makes it public.
- Recruiters can keep editing a published job in its chat or form. **Publish
  changes** updates the live post; until then candidates see the previous version.
  Submitted applications keep their original requirements, evidence and scores.
  Cards labelled **Earlier requirements** remain reviewable but are excluded from
  the current comparison plot/ranking. Closing recruitment stops applications
  while keeping the recruiter chat available.
- One canonical job-criterion shape with a stable key, type, measurable target,
  optional unit, backend-owned weight, and description. The recruiter form
  shows an editable label/value, and clarifications update the existing key.
- Candidate conversations collect job-specific examples. **Your application**
  shows the confirmed requirements as input hints and one editable answer per
  field; direct edits keep the typed answer and refresh its assessment.
- A failed message request leaves the exact typed text in the composer so the
  recruiter or candidate can retry without rewriting it.
- Up to two published job suggestions during discovery; recruiter comparisons
  show up to five strong candidates with weighted scores and explanations.
- A review and consent step that collects contact details only when the candidate
  submits, including name, location, and email or phone, then freezes the
  structured application snapshot.
- Candidate evidence is stored under the exact published criterion key with an
  extracted typed value. Review answers and contact details, consent and submit
  at the bottom of the form. Form edits do not add duplicate chat messages.
- The model proposes evidence with source quotes from the current conversation.
  Backend checks reject unsupported fields/types/quantities and fall back to the
  quoted wording when a polished sentence adds new terms. Unclear measurable
  answers receive no score until clarified. Gemini rates criterion fit; the backend
  validates ratings, owns weights and calculates the weighted total.
- Candidates can leave one scoped guest application, browse available jobs, and
  start a separate private conversation for another role.
- Recruiters can compare submitted candidates in one consistent evidence view,
  then close recruitment to stop applications and review a ranked top-five shortlist.
  Closing also stops unfinished candidate chats with a clear prompt to browse
  other jobs while preserving submitted application snapshots.
- Each candidate card starts with a short strengths-and-gaps summary, followed by
  readable criterion cards showing candidate value, target, importance,
  assessment, and supporting evidence.
- A deterministic guided fallback plus optional Gemini and OpenAI providers for recruiter
  answer classification and polished, measurable role criteria.
- One context assembler for response generation: selected job criteria,
  the structured draft, and the complete authorized chat. Earlier messages are
  neither cut to 800 characters nor dropped after 12 messages. An oversized
  request falls back at 128,000 serialized characters instead of silently
  discarding history; output and per-chat call caps still apply.
- Recruiter answers can fill unanswered fields from earlier user messages.
  Spelling repairs and natural wording can map to existing fields without
  requiring literal labels. Exact source quotes, quantities, types and explicit
  exclusions remain checked; older evidence cannot overwrite saved corrections.

## Stack

React and Vite provide the mobile friendly UI. FastAPI and SQLAlchemy provide the API. Development Compose runs Vite, FastAPI, PostgreSQL, and Mailpit. The backend uses SQLite by default when run outside Docker. Production Compose serves the built frontend and private API through Nginx.

```text
Browser :3000 -> Vite frontend -> FastAPI :8000 -> PostgreSQL
```

Opaque, expiring bearer sessions are stored in the database. Chat, job-publishing,
recommendation, and application endpoints derive the user and role from the
session and enforce resource ownership. Versioned Alembic migrations run before
FastAPI starts. Broad abuse rate limiting is still pending, so use fictional data
and keep the current release private.

## Run with Docker

You need Docker Desktop with Compose. Copy the example settings:

```powershell
Copy-Item .env.example .env
```

On macOS or Linux, use `cp .env.example .env`. Start the stack:

```bash
docker compose -f dev.docker-compose.yaml up -d
```

The development services mount the source directly and cache Python and Node
dependencies in named volumes. This avoids Docker BuildKit trying to archive
Microsoft OneDrive reparse files. The first start installs dependencies; later
starts reuse them unless `requirements.txt` or `package-lock.json` changes.
Running the command with `--build` is also safe, although the development services
do not require custom image builds.

FastAPI reload and Vite file watching use polling in the development containers
so edits on Docker Desktop and OneDrive bind mounts are picked up without a
manual service restart. Set `WATCHFILES_FORCE_POLLING=false` or
`VITE_USE_POLLING=false` only when native file events are reliable on the host.
The complete deterministic backend suite and browser Core MVP workflow have each
passed twice with this setup.

Open [the app](http://localhost:3000), [the API docs](http://localhost:8000/docs),
or [the Mailpit inbox](http://localhost:8025). All published development ports
bind to localhost. Change `FRONTEND_PORT`, `BACKEND_PORT`, or
`MAILPIT_UI_PORT` in `.env` if needed. The browser calls `VITE_API_URL`, which
defaults to `http://localhost:8000/api`. Demo data persists in the
`job_talk_data` volume; local email is disposable.

```bash
docker compose -f dev.docker-compose.yaml down
```

Run `docker compose -f dev.docker-compose.yaml down -v` only when you intend to
delete the demo database and both dependency caches. The sample PostgreSQL
credentials are for local development. Keep `.env` out of Git.

## Run without Docker

Install Python 3.12+ and a Node version supported by the locked Vite release. In one terminal:

```bash
cd backend
python -m venv .venv
# Windows PowerShell: .\.venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

Alembic creates or upgrades `backend/job_talk.db`. In another terminal:

```bash
cd frontend
npm ci
npm run dev
```

Open [the Vite app](http://localhost:5173). It calls `http://localhost:8000/api` by default.

## Five minute demo

1. Select **I'm hiring** and enter `recruiter@example.com`.
2. Open [Mailpit](http://localhost:8025), copy the six-digit code, and finish signing in.
3. Confirm the seeded **Welder and Forklift Operator** job is available, then leave the recruiter session.
4. Select **I'm looking for work** and choose that role. No email, account, or password is required.
   You can also open a job directly at `http://localhost:3000/?job=<job-id>`.
5. Say: "I have three years of welding and forklift experience in Cape Town."
6. Review the extracted evidence, add a name and preferred contact, consent to
   sharing the structured application, and submit it.

The earlier software example also works: publish a junior Python developer role requiring FastAPI and Docker, then describe a matching candidate.

Sessions last 24 hours by default and are kept in browser session storage, so
closing the browser ends the browser-side session. Set `AUTH_SESSION_HOURS` in
`.env` to change the server-side expiry.

The development stack seeds `DEMO_RECRUITER_EMAIL` as an approved recruiter,
publishes three demo jobs, and runs Mailpit as its inbox. FastAPI sends to
`mailpit:1025` inside Compose and messages appear immediately at
`http://localhost:8025`; no external SMTP account is needed locally. To review or
approve another recruiter request:

```bash
docker compose -f dev.docker-compose.yaml exec backend python -m app.recruiters list
docker compose -f dev.docker-compose.yaml exec backend python -m app.recruiters approve recruiter@company.com
```

### Owner access

Set `ADMIN_EMAIL` to your email in ignored `.env`, approve that same address
using the command above, then reload the backend configuration:

```bash
docker compose -f dev.docker-compose.yaml up -d --no-deps backend
```

Sign in through **I'm hiring** with that email and the code in
[local Mailpit](http://localhost:8025). Admin opens the same workspace as a
recruiter. **All hiring conversations** lists every recruiter's job chats, with
their email below the job title. Open any draft to continue its conversation,
edit requirements and publish; open a published job to compare applicants or
close recruitment. The original recruiter keeps ownership and sees the same
saved changes. Both can edit published jobs and explicitly **Publish changes**.

There is no separate admin dashboard. Ordinary recruiters see only their own
chats; candidate conversations remain scoped to their guest session.

`ADMIN_EMAIL` is optional and backend-only; empty disables owner access. It
does not approve the email automatically. The backend checks the configured
address and current recruiter approval on every request using the existing
expiring bearer session. Changing this setting takes effect after recreating
the backend; refresh the browser to update the navigation.

To repeat the focused browser check with a configured, approved local owner:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/local-signoff.ps1 -RecruiterEmail owner@example.com -AdminOnly
```

Replace the example address with your configured owner email. The check needs
another recruiter's draft and published local job. It uses Mailpit, creates and
removes one fictional application, and checks shared chat navigation, edit/close
controls, comparison, refresh and desktop/phone views. It makes no LLM requests.

### Add a manually checked vacancy

1. Sign in as the configured owner and choose **New hiring conversation**.
2. Tick **Add a vacancy I checked on another website**. Enter its URL, advertised
   employer, date checked and pasted description. Choose a starter template.
3. Click **Fill draft from pasted text**. Review the saved criteria, answer
   missing questions and correct mistakes in the chat, then explicitly publish.
4. Open the public job link as a candidate. **Added by Job Talk** explains that
   interest goes to the operator; the advertised employer receives no application.
5. Open the job's hiring conversation to review candidate cards, the comparison plot and an
   **Interest summary** containing only counts. Use the job's hiring conversation
   to close it when the advert is stale or filled.

No URL is fetched. The original advert text is private to the owner's draft;
public views show the source link, employer and date checked. The saved source
is separate from criteria and cannot create score axes. Duplicate source URLs
are rejected, including common tracking-parameter/fragment variants and closed
listings. Source details are fixed for that job; review them before creating it.

Curated-job submission authorizes the operator to record candidate interest.
Before sharing identifying details with a prospective employer, contact the
candidate for separate permission and approve that recruiter through the existing
process. There is no automatic outreach, transfer or export. Share only the
aggregate summary while demonstrating interest; keep private candidate cards out
of screenshots sent to prospective recruiters.

With the configured owner, the focused local check is:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/local-signoff.ps1 -RecruiterEmail owner@example.com -VacancyOnly
```

It uses fictional source text and candidate details, checks consent, and restarts
the local backend and PostgreSQL without removing volumes. It closes the test job
and removes the test candidate afterward. Use the deterministic provider for a
repeatable guided check; live LLM language acceptance is a separate gate.

### Email-code limits

Code requests always return the same response, whether the address is approved,
pending, rejected, or unknown. For an approved recruiter, the backend sends at
most one code per 60 seconds and five codes per hour by default. A request made
during the cooldown leaves the current code valid. Configure these limits with
`RECRUITER_CODE_REQUEST_COOLDOWN_SECONDS` and
`RECRUITER_CODE_REQUEST_MAX_PER_HOUR`.

Re-run `python -m app.seed_jobs` inside the backend container whenever you want
to restore the three demo job definitions. The command updates them without
creating duplicates.

## Production environment contract

Use one ignored `.env` per installation; `.env.example` is the only example.
Both Compose files and operator scripts read `.env`. Its defaults are for local
development. On the VM set production domain, secrets, SMTP and release settings
as described in [production operations](docs/production-operations.md#prepare-a-release).
Compose derives the database URL from `POSTGRES_DB`, `POSTGRES_USER` and
`POSTGRES_PASSWORD`. FastAPI refuses to start in `APP_ENV=production` unless:

- `PUBLIC_ORIGIN` is the HTTPS root of `APP_DOMAIN`;
- `ALLOWED_HOSTS` contains the configured subdomain;
- `CORS_ORIGINS` contains the public origin;
- `TLS_EMAIL` is a monitored, non-placeholder address;
- SMTP host, credentials, and sender address are non-placeholder values;
- PostgreSQL uses a non-placeholder password of at least 16 characters; and
- `SESSION_TOKEN_PEPPER` is a non-placeholder value of at least 32 characters.

The session pepper is used only by FastAPI to hash opaque session tokens before
database storage. Keep it out of frontend build arguments and browser code.

Production Compose also requires `SUPPORT_EMAIL`. Set it to the monitored address
shown on the privacy and safety page before building the frontend.
Production FastAPI listens only on a Unix socket shared with Nginx, with no TCP
listener. The frontend and other containers cannot connect directly to the API.
Nginx's public `/api/` route still accepts outside clients; private actions always
require backend tokens and permissions. An IP allowlist cannot prove that a
request came from our browser app.
The backend and development example now default `AI_MAX_OUTPUT_TOKENS` to 3000
to allow a whole template's structured updates in one response. Existing `.env`
overrides are retained; raise an older 1000-token value to 3000 and recreate the
backend with `docker compose -f dev.docker-compose.yaml up -d backend` before
testing long descriptions. Invalid or truncated responses use the guided fallback.

The public `/privacy` page explains collection, sharing, acceptable use,
retention, reporting, and deletion. Candidates can delete a submitted guest
application from the active session. Cleanup and operator deletion commands,
logging rules, and rate limits are documented in
[`docs/privacy-and-safety.md`](docs/privacy-and-safety.md).

### Rotate secrets

Rotating `SESSION_TOKEN_PEPPER` invalidates existing sessions. Replace it in the
VM environment file and recreate only the backend service; users then sign in
again. The frontend image does not need rebuilding.

To rotate the PostgreSQL password, first take a backup, change the `job_talk`
database role password in PostgreSQL, update both `POSTGRES_PASSWORD` and the
URL-encoded password in `DATABASE_URL`, then recreate the backend service. The
production commands are in [production operations](docs/production-operations.md).

To rotate the SMTP password, replace `SMTP_PASSWORD` in the VM environment file
and recreate the backend service. Existing recruiter sessions remain valid;
new sign-in codes use the updated SMTP credentials.

## Production Compose

Production Compose/HTTPS preparation is authorized in JT-070. VM deployment
remains paused pending user acceptance and an explicit deployment request.

[`prod.docker-compose.yaml`](prod.docker-compose.yaml) builds backend
and frontend images under one Git commit tag. PostgreSQL, FastAPI, and the
frontend have no host port bindings. The public Nginx proxy is the only service
that publishes ports, on `80:80` and `443:443`, and it sends `/api/` directly to
FastAPI while serving the frontend at `/`.
Open `http://jobtalk.roventics.com` on port 80; after certificate setup it redirects
to `https://jobtalk.roventics.com` on port 443. The production project is `job_talk_prod`,
separate from the development containers and data.

The production package keeps the staging webpage behind HTTP basic authentication, obtains
TLS certificates through a pinned Certbot container, checks renewal twice a day,
and reloads changed certificates without restarting Nginx. Exact password,
certificate, build, start, health, log, upgrade, rollback, and shutdown commands
are in [`docs/production-operations.md`](docs/production-operations.md).
API routes use the application's existing Bearer-token, ownership and guest
scope checks; the webpage password gate does not replace those checks. Public
API routes remain public through Nginx. Gemini and `ADMIN_EMAIL` are configured
in the ignored production environment file, never in frontend build arguments.
Environment files are grouped into database, backend, authentication, email,
LLM and frontend settings; production also has release and Nginx/TLS sections.
Local `.env` stays ignored and retains its local settings. Copy the production
example for the VM; its domain/origin fields already target `jobtalk.roventics.com`.

## Database migrations and recovery

Template draft storage adds one nullable JSON field to the existing jobs table;
existing jobs are retained. When updating an already running development stack,
run `docker compose -f dev.docker-compose.yaml restart backend` once to apply
pending migrations before testing the new picker.

The backend container runs `alembic upgrade head` before Uvicorn. If a migration
fails, the API does not start. Create a verified backup before each deployment
and keep a copy outside the VM. The backup, restore drill, retention, upgrade,
and rollback commands are documented in
[`docs/database-operations.md`](docs/database-operations.md).

## Tests

```bash
cd backend
pytest
```

Tests select disposable SQLite before importing the app, and the reset fixture
refuses any other database. In Docker, use a separate container and select the
test database before Python starts (never run database-reset tests against the
development backend's PostgreSQL connection):

```bash
docker compose -f dev.docker-compose.yaml run --rm --no-deps -T -w /tmp -e PYTHONPATH=/app -e DATABASE_URL=sqlite:///./test_job_talk.db -e AI_PROVIDER=mock -e SEED_DEMO_JOBS=false --entrypoint /opt/venv/bin/pytest backend /app/app/tests -q -o cache_dir=/tmp/pytest-jobtalk
```

For the frontend, run `npm run build` inside `frontend`.

With the development stack running on its default ports, Windows users with
Microsoft Edge can repeat the public-job-to-recruiter browser walkthrough:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/browser-smoke.ps1
```

The script submits a fresh guest application to seeded job 2, signs in through
the Mailpit code, verifies the recruiter comparison, and writes candidate and
recruiter desktop and phone screenshots under `%TEMP%\jobtalk-browser-smoke`.

For the existing automated local regression walkthrough, first approve a
dedicated recruiter and then run the full create, publish, apply, compare,
close, and delete workflow:

```powershell
docker compose -f dev.docker-compose.yaml exec backend python -m app.recruiters approve local-signoff@example.com
powershell -ExecutionPolicy Bypass -File scripts/local-signoff.ps1 -RecruiterEmail local-signoff@example.com
```

The workflow uses the real email-code path through Mailpit, verifies captured
candidate evidence and a nonzero score, checks that a closed job cannot be
published or opened publicly, verifies candidate deletion invalidates the guest
token, and writes desktop and phone screenshots under
`%TEMP%\jobtalk-local-signoff`. Wait for the configured login-code cooldown before
reusing the same recruiter address.

This scripted walkthrough does not establish usability or actual LLM quality.
JT-060 adds varied conversations and separate live-provider evidence, followed
by the user's [manual usability check](docs/usability-checklist.md).

To check only template selection and saved drafts, append `-TemplatesOnly` to
the `scripts/local-signoff.ps1` command. It opens all three templates, checks
refresh persistence and unconfirmed fields, and captures desktop and phone
screenshots without sending AI messages.

Use `-RecruiterDraftOnly` to check a labelled role description, an experience
correction, an ambiguous acknowledgement, saved summary, phone layout, explicit
publication, and continued editing. It uses the configured provider and may fall
back; it does not certify live AI quality. See the recorded
[recruiter draft checks](docs/recruiter-draft-checks.md).

Use `-LiveEditingOnly` to check post-publication chat edits, **Publish changes**,
refresh, immediate seeker examples and changing suggestions at desktop and phone
widths. Use a dedicated approved test recruiter. It creates and then closes its
own fictional job and deletes its test guest; it never resets the database.

The backend flow suite also includes the fixed plumber pilot scenario: a strong
plumber, a partial handyman with an explicit geyser gap, and an unrelated software
candidate. It verifies isolated guest submissions, sensible score ordering, and
the recruiter comparison contract on every test run.

## Experiment report

Job Talk records privacy-safe pilot events using a keyed hash of a random browser
identifier. Events contain no names, contact details, chat text, extracted skills,
evidence, IP addresses, or user-agent strings. Candidate and recruiter feedback is
one yes-or-no answer. The existing 30-day cleanup also removes old experiment
events.

Read the aggregate report from an operator shell:

```bash
docker compose -f dev.docker-compose.yaml exec -T backend python -m app.experiment_report
```

For the VM, run the same module with `prod.docker-compose.yaml`. The report
shows unique visitors, starts, submissions, comparison opens, recruiters who
compared, seven-day returns, and feedback response/usefulness totals.

## Match score data

Each job criterion has a stable key, label, type, target, optional unit, weight,
and short description. Candidate values, evidence, and match results refer to
that same key. Each match criterion has a `score` between 0 and 1, its target and
candidate values, a `weight`, and a plain-language reason. The recruiter comparison
shows the top five candidates on a parallel-axis plot against an ideal 100% profile;
missing evidence is marked rather than drawn as a confirmed zero. The evidence
cards remain the readable source for each score and gap. The overall `match_score`
is the weighted mean: `sum(score * weight) / sum(weight)`, rounded to two decimals
using half-up rounding, or 0 when there are no criteria.

With `AI_PROVIDER=gemini`, Gemini rates each criterion from 0–100 with a short
reason, after evidence has been validated. The backend checks ranges, criterion
keys and supporting answer references, converts to 0–1 and applies its weights.
Discovery rates all published open jobs in one bounded batch. A selected application
uses only that job's criteria. Ratings are stored in the existing chat JSON and
reused on refresh; changing answers or requirements invalidates them. Submission
freezes the reviewed ratings for recruiter cards and the plot.

The UI labels **AI estimate** versus **Rule-based estimate**. If Gemini is unavailable,
over its call/output/input limit, or returns invalid data, saved answers still work
and scoring falls back to the existing rules. No new service or database migration
is required. Scoring adds at most one batch call after each changed answer, including
form edits; no call per criterion and no calls on page refresh or submission.

For a small actual-model check with fictional data and no database access:

```powershell
docker compose -f dev.docker-compose.yaml exec -T -e PYTHONPATH=/app backend python /app/scripts/check_live_ratings.py
```

The rating request uses [Gemini structured output](https://ai.google.dev/gemini-api/docs/generate-content/structured-output).
Its small schema describes the response; strict bounds and evidence checks also
run in Python before anything is saved.

Candidate statements remain unverified. An explicit denial or correction is
stored as a reported gap and scores zero for that criterion. A vague answer does
not fill the requested criterion. Gemini compares the meaning of the evidence
with the requirement; detailed but unrelated answers should score low. Provider wording cannot
turn a missing criterion or reported gap into a positive match.

Recruiter conversation navigation uses each role title and its current state
(`Draft`, `Published`, or `Closed`). Candidate navigation uses the selected job
title and application state, making multiple hiring workspaces easy to identify.

Before submitting, a candidate sees every requirement from the selected job.
The review marks captured evidence, reported gaps, and missing evidence, includes
any additional structured claims, and links back to the conversation for corrections.

## AI provider

`backend/app/services/ai.py` keeps response generation behind one function and
supports `mock`, `gemini` and `openai` providers. Mock mode remains the example default so
tests are deterministic and a missing provider cannot stop the application. It
shows the same concise guided questions used by the backend, without development
context or message diagnostics.

### Gemini for local testing

Put the key from Google AI Studio in the ignored `.env` file:

```dotenv
AI_PROVIDER=gemini
GEMINI_API_KEY=your-gemini-api-key
GEMINI_MODEL=gemini-3.5-flash-lite
AI_MAX_OUTPUT_TOKENS=3000
AI_MAX_CALLS_PER_CHAT=12
```

Apply the settings, then open [the local UI](http://localhost:3000) and start a
new conversation:

```bash
docker compose -f dev.docker-compose.yaml up -d --no-deps backend
```

`gemini-3.5-flash-lite` accepted live requests from the configured free-tier
project on 2026-10-03. Google's older 2.5 Flash-Lite endpoint rejected generation
for this new project. See [model availability](https://ai.google.dev/gemini-api/docs/models/gemini-2.5-flash-lite)
and [current pricing and free-tier data use](https://ai.google.dev/gemini-api/docs/pricing).
Use fictional data for these checks. Free-tier quotas still apply; no billing
change, retry loop, search tool, or automatic upgrade is configured.

The backend calls `generateContent` with minimal thinking and a JSON schema,
using the existing bounded chat context and validation. Gemini proposes fields;
the backend validates them, chooses the next question and calculates scores.
The key is sent in a backend HTTP header, never in the browser or request URL.
Provider failures use the guided fallback. Set `AI_PROVIDER=mock` and recreate
the backend to return to deterministic testing.

### OpenAI

To use OpenAI locally, place these values in the ignored `.env` file and recreate
the backend with the same Compose command:

```dotenv
AI_PROVIDER=openai
OPENAI_API_KEY=your-project-api-key
OPENAI_MODEL=gpt-4o-mini
```

A ChatGPT subscription does not supply application API usage. Create a project
API key and configure separate API billing plus a hard monthly spend limit before
enabling it for invited users. The key is passed only to the backend container.

OpenAI requests use the Responses API with strict JSON output validation and
`store: false`. They contain the selected job, structured draft, current message,
and the complete message history from that authorized chat. Submission contact details and
other chats are excluded. For recruiter turns, the model returns a reply and
categorized role updates with exact quotes from the latest message. The backend
rejects updates without that support, assigns all weights, recalculates readiness,
and saves accepted measurable descriptions for review before publication.

Template-based recruiter updates can also quote earlier user messages to fill
unanswered fields. If an older draft missed details, continue the same chat with
"Use everything I already told you and ask only for missing details." JT-066
verified this recovery with the misspelled Durban graduate-electronics example;
hours, start availability and any tools still need answers if never specified.

Each request has input, output, and timeout bounds. Evidence generation is limited
to the first 12 chat turns; Gemini scoring has a separate maximum of 12 batch calls
per chat (including direct form edits). Unchanged evidence reuses saved ratings.
Invalid, unavailable, limited, or over-budget provider responses
use the current guided question and deterministic extraction, so job creation stays
available while a real provider is selected. Guided extraction remains limited
and is not evidence of successful LLM understanding. The backend logs the HTTP status and safe
provider error code without logging the API key or response data.

## Current limits and next steps

The app uses text chat with a configured LLM (Gemini in local testing), a limited
guided fallback, and Gemini criterion ratings with backend weighted totals. It does not verify candidate
skills or automate employer identity checks.
Submitted application data is visible to the candidate guest session, the recruiter
that owns the relevant job, and the configured approved Job Talk operator, as
explained during submission and on the privacy page. These recruiter/operator
views do not expose full chats. The brief proposes WhatsApp and voice notes, verified
employers, anonymous top five candidate previews, privacy controls, and
subscription plus placement fees; those are not implemented yet.

The scripted local core loop passes with shared typed criteria, but usability
remains unapproved. The current tickets improve the existing creation,
application, and comparison flows. Advanced discovery, dashboards, integrations,
and branding remain deferred.

## Deployment goal: jobtalk.roventics.com

The next milestone is the user's local usability acceptance. Deployment to a
user-owned VM at `https://jobtalk.roventics.com` waits for that acceptance and an
explicit request to resume. The production package is prepared and locally
checked. Its staging webpage remains password-gated while the live domain,
email and certificate are verified. The experiment then exposes
published job pages and scoped guest applications while recruiter data stays
behind authenticated ownership checks.

The ordered implementation and launch backlog lives in [`TASKS.md`](TASKS.md). It separates the private VM demo from a later public pilot and includes the development Compose rename, production Nginx ingress, environment and secret packaging, safety controls, score visualization, and demo video with QR code.

## Project workflow

[`AGENTS.md`](AGENTS.md) records product boundaries, AI behavior, access controls,
and completion checks. Chat participants use matching circular robot/person
icons; Roventics branding appears in the footer. Job Talk is the primary product name.
