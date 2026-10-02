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

## What works

- Passwordless entry: job seekers start a private guest conversation immediately,
  while approved recruiters sign in with a short-lived email code.
- Three realistic demo jobs, public links and a job picker, and a guest
  conversation anchored to the selected role.
- Rule based extraction of skills, experience, location, and work preferences from text, including trade examples.
- Deterministic follow-up questions that ask for the selected job's highest-weight
  missing evidence and resume from the saved draft after a refresh.
- Conversational job drafting that asks whether each detected skill or tool is
  required or preferred and how much experience applicants should have.
- A structured role summary before publishing. Recruiters can correct an
  attribute in ordinary chat, then say `I am done` or `publish the job` when all
  required details are confirmed.
- Candidate conversations open with a plain summary of the confirmed recruiter
  requirements before collecting job-specific examples.
- Up to five published job recommendations with weighted scores and plain language explanations.
- A review and consent step that collects contact details only when the candidate
  submits, then freezes the structured application snapshot.
- Candidates can leave one scoped guest application, browse available jobs, and
  start a separate private conversation for another role.
- Recruiters can compare submitted candidates in one consistent evidence view,
  then close recruitment to stop applications and review a ranked top-five shortlist.
- A deterministic mock AI generator that displays a compact preview of the current message and the context from that specific chat.
- One bounded context assembler for response generation: selected job criteria,
  the structured draft, and only the last 12 messages from the authorized chat.

## Stack

React and Vite provide the mobile friendly UI. FastAPI and SQLAlchemy provide the API. Development Compose runs Vite, FastAPI, PostgreSQL, and Mailpit. The backend uses SQLite by default when run outside Docker. The production Dockerfiles retain the Nginx frontend image for the later production Compose package.

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

Copy `.env.production.example` to an ignored VM environment file and replace
every placeholder. FastAPI refuses to start in `APP_ENV=production` unless:

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
production Compose and deployment tickets will provide the exact VM commands.

To rotate the SMTP password, replace `SMTP_PASSWORD` in the VM environment file
and recreate the backend service. Existing recruiter sessions remain valid;
new sign-in codes use the updated SMTP credentials.

## Production Compose

[`production.docker-compose.yaml`](production.docker-compose.yaml) builds backend
and frontend images under one Git commit tag. PostgreSQL, FastAPI, and the
frontend have no host port bindings. The public Nginx proxy is the only service
that publishes ports, on `80:80` and `443:443`, and it sends `/api/` directly to
FastAPI while serving the frontend at `/`.

The production package keeps staging behind HTTP basic authentication, obtains
TLS certificates through a pinned Certbot container, checks renewal twice a day,
and reloads changed certificates without restarting Nginx. Exact password,
certificate, build, start, health, log, upgrade, rollback, and shutdown commands
are in [`docs/production-operations.md`](docs/production-operations.md).

## Database migrations and recovery

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

For the frontend, run `npm run build` inside `frontend`.

With the development stack running on its default ports, Windows users with
Microsoft Edge can repeat the public-job-to-recruiter browser walkthrough:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/browser-smoke.ps1
```

The script submits a fresh guest application to seeded job 2, signs in through
the Mailpit code, verifies the recruiter comparison, and writes desktop and phone
screenshots under `%TEMP%\jobtalk-browser-smoke`.

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

For the VM, run the same module with `production.docker-compose.yaml`. The report
shows unique visitors, starts, submissions, comparison opens, recruiters who
compared, seven-day returns, and feedback response/usefulness totals.

## Match score data

Each recommendation includes a `criteria` object. Every criterion has a `score`
between 0 and 1, a `weight`, and a plain-language reason. The recruiter comparison
shows the top five candidates on a parallel-axis plot against an ideal 100% profile;
missing evidence is marked rather than drawn as a confirmed zero. The evidence
cards remain the readable source for each score and gap. The overall `match_score`
is the weighted mean: `sum(score * weight) / sum(weight)`, rounded to two decimals
using half-up rounding, or 0 when there are no criteria.

Candidate statements remain unverified. An explicit denial or correction is
stored as a reported gap and scores zero for that criterion. A vague answer does
not fill the requested criterion, and a general skill claim scores below a
concrete work example. The backend owns these decisions; provider wording cannot
turn a missing criterion or reported gap into a positive match.

Recruiter conversation navigation uses each role title and its current state
(`Draft`, `Published`, or `Closed`). Candidate navigation uses the selected job
title and application state, making multiple hiring workspaces easy to identify.

Before submitting, a candidate sees every requirement from the selected job.
The review marks captured evidence, reported gaps, and missing evidence, includes
any additional structured claims, and links back to the conversation for corrections.

## AI provider

`backend/app/services/ai.py` keeps response generation behind one function and
supports `mock` and `openai` providers. Mock mode remains the example default so
tests are deterministic and a missing provider cannot stop the application.

To use OpenAI locally, place these values in the ignored `.env` file and rebuild
the backend:

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
and at most the latest 12 messages from that authorized chat. Contact details and
other chats are excluded. Each request has input, output, and timeout bounds, and
each chat can make at most 12 provider calls. Invalid, unavailable, limited, or
over-budget provider responses use the current guided question without adding
mock response text, so the application remains usable while OpenAI mode is
selected. The backend logs the HTTP status and safe provider error code without
logging the API key or response data.

## Current limits and next steps

The app uses text only, a small rule based vocabulary, and heuristic scores. It
does not verify candidate skills or automate employer identity checks.
Application data is visible to the candidate guest session and the recruiter
that owns the relevant job. The brief proposes WhatsApp and voice notes, verified
employers, anonymous top five candidate previews, privacy controls, and
subscription plus placement fees; those are not implemented yet.

## Deployment goal

The next milestone is deployment to a user-owned VM under a subdomain. Staging
remains private while the production package and guest application boundary are
verified. The experiment then exposes published job pages and scoped guest
applications while recruiter data stays behind authenticated ownership checks.

The ordered implementation and launch backlog lives in [`TASKS.md`](TASKS.md). It separates the private VM demo from a later public pilot and includes the development Compose rename, production Nginx ingress, environment and secret packaging, safety controls, score visualization, and demo video with QR code.

## Project workflow

[`AGENTS.md`](AGENTS.md) records the product boundaries, mock AI contract, safety requirements, and completion checks used for future tickets. The small robot artwork used for assistant messages is existing Roventics branding; Job Talk remains the primary product name in the interface.
