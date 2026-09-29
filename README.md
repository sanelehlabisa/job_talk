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

- Password protected accounts with expiring sessions and saved conversations. A user can start either a job search or hiring chat.
- Rule based extraction of skills, experience, location, and work preferences from text, including trade examples.
- Employer job publishing once a title and two meaningful criteria are collected.
- Up to five published job recommendations with weighted scores and plain language explanations.
- One application per candidate chat and job, submitted without another form.
- A deterministic mock AI generator that displays a compact preview of the current message and the context from that specific chat.

## Stack

React and Vite provide the mobile friendly UI. FastAPI and SQLAlchemy provide the API. Docker Compose runs Nginx, FastAPI, and PostgreSQL. The backend uses SQLite by default when run outside Docker.

```text
Browser :3000 -> Nginx frontend -> /api/ -> FastAPI :8000 -> PostgreSQL
```

Accounts use Argon2 password hashes and opaque, expiring bearer sessions stored in the database. Chat, job-publishing, recommendation, and application endpoints derive the account from the session and enforce resource ownership. Rate limiting, password recovery, email verification, and production migrations are still pending, so use fictional data and keep the current release private.

## Run with Docker

You need Docker Desktop with Compose. Copy the example settings:

```powershell
Copy-Item .env.example .env
```

On macOS or Linux, use `cp .env.example .env`. Start the stack:

```bash
docker compose -f dev.docker-compose.yaml up --build
```

Open [the app](http://localhost:3000) or [the API docs](http://localhost:8000/docs). Both ports bind to localhost. Change `FRONTEND_PORT` or `BACKEND_PORT` in `.env` if needed. Demo data persists in the `job_talk_data` volume.

```bash
docker compose -f dev.docker-compose.yaml down
```

Run `docker compose -f dev.docker-compose.yaml down -v` only when you intend to delete the demo database. The sample PostgreSQL credentials are for local development. Keep `.env` out of Git.

## Run without Docker

Install Python 3.12+ and a Node version supported by the locked Vite release. In one terminal:

```bash
cd backend
python -m venv .venv
# Windows PowerShell: .\.venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

The backend creates `backend/job_talk.db` automatically. In another terminal:

```bash
cd frontend
npm ci
npm run dev
```

Open [the Vite app](http://localhost:5173). It calls `http://localhost:8000/api` by default.

## Five minute demo

1. Create an account such as `employer-demo@example.com` with a password of at least 12 characters, then start a chat.
2. Select **Hire a welder**, or say: "I am looking to hire a welder with welding and forklift experience in Cape Town, with two years of experience."
3. Publish the job.
4. Log out, create a separate account such as `candidate-demo@example.com`, and start a chat.
5. Select **Find trade work**, or say: "I am looking for a job. I have three years of welding and forklift experience in Cape Town."
6. Review the match and apply.

The earlier software example also works: publish a junior Python developer role requiring FastAPI and Docker, then describe a matching candidate.

Sessions last 24 hours by default and are kept in browser session storage, so closing the browser ends the browser-side session. Set `AUTH_SESSION_HOURS` in `.env` to change the server-side expiry. Accounts created by the older email-only build that already contain chats cannot be claimed through registration; use a new email for local testing or intentionally reset the local Docker volume.

## Tests

```bash
cd backend
pytest
```

For the frontend, run `npm run build` inside `frontend`.

## Match score data

Each recommendation includes a `criteria` object for a future multidimensional plot. Each criterion has a `score` between 0 and 1, a `weight`, and a plain language `reason`. The overall `match_score` is the weighted mean of the reported criterion scores: `sum(score * weight) / sum(weight)`, rounded to two decimals using half-up rounding (or 0 when there are no criteria).

## Mock AI mode

The app currently makes no external AI calls. `backend/app/services/ai.py` exposes one `generate_reply` function backed by a deterministic generator. Every reply starts with a preview of the current user message. Messages longer than ten characters show the first five and last five source characters. The reply also identifies the chat, reports how many saved messages were supplied as context, and previews the previous user message. This makes message and context flow visible while testing. The backend supplies at most the latest 12 earlier messages from the current chat. A real API or local model can later replace the function without changing the chat endpoint.

## Current limits and next steps

The app uses text only, a small rule based vocabulary, and heuristic scores. It does not verify email addresses, skills, or employers. Application data is visible to the candidate and the account that owns the relevant job. The brief proposes WhatsApp and voice notes, verified employers, anonymous top five candidate previews, privacy controls, and subscription plus placement fees; those are not implemented yet.

## Deployment goal

The next milestone is deployment to a user-owned VM under a subdomain. Staging
remains private while the production package and guest application boundary are
verified. The experiment then exposes published job pages and scoped guest
applications while recruiter data stays behind authenticated ownership checks.

The ordered implementation and launch backlog lives in [`TASKS.md`](TASKS.md). It separates the private VM demo from a later public pilot and includes the development Compose rename, production Nginx ingress, environment and secret packaging, safety controls, score visualization, and demo video with QR code.

## Project workflow

[`AGENTS.md`](AGENTS.md) records the product boundaries, mock AI contract, safety requirements, and completion checks used for future tickets. The small robot artwork used for assistant messages is existing Roventics branding; Job Talk remains the primary product name in the interface.
