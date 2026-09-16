# Job Talk

Job Talk is a hackathon proof of concept for people who can do the work but may not have a polished CV. Candidates describe their skills in a chat; employers describe a role the same way. The app builds structured profiles, ranks jobs, explains matches, and lets candidates apply from the chat.

The project brief focuses on informal, trade, and entry level job seekers and small employers seeking local talent. Its proposed product includes low data web or WhatsApp chat, voice notes, and anonymous candidate previews. **This repository currently implements a text only web demo.** WhatsApp, voice notes, identity checks, anonymous employer shortlists, and payments are future work.

## Why this project

The brief identifies three barriers: job seekers may not want a public search, practical skills can be missed by CV screening, and conventional applications often give little feedback. Job Talk explores a private conversation that draws out work experience and gives both sides a clearer reason for a match.

The proposed business model keeps candidate use free. For employers, the brief suggests R399 per month per active posting for access to a top five anonymous, verified candidate list, plus R500 after a confirmed placement. It estimates about R250 per month for a proof of concept using WhatsApp and AI. These are planning assumptions, not features or validated prices in this demo.

## What works

- Email based demo users and saved conversations. A user can start either a job search or hiring chat.
- Rule based extraction of skills, experience, location, and work preferences from text, including trade examples.
- Employer job publishing once a title and two meaningful criteria are collected.
- Up to five published job recommendations with weighted scores and plain language explanations.
- One application per candidate chat and job, submitted without another form.
- Optional OpenAI Responses API replies. Profile extraction, matching, and fallback replies work without an API key.

## Stack

React and Vite provide the mobile friendly UI. FastAPI and SQLAlchemy provide the API. Docker Compose runs Nginx, FastAPI, and PostgreSQL. The backend uses SQLite by default when run outside Docker.

```text
Browser :3000 -> Nginx frontend -> /api/ -> FastAPI :8000 -> PostgreSQL
```

**Demo only:** entering an email creates or opens an account without a password. The API has no access control. Use fictional data and run it locally.

## Run with Docker

You need Docker Desktop with Compose. Copy the example settings:

```powershell
Copy-Item .env.example .env
```

On macOS or Linux, use `cp .env.example .env`. Leave `OPENAI_API_KEY` empty for deterministic replies, or add a key for generated replies. Start the stack:

```bash
docker compose up --build
```

Open [the app](http://localhost:3000) or [the API docs](http://localhost:8000/docs). Both ports bind to localhost. Change `FRONTEND_PORT` or `BACKEND_PORT` in `.env` if needed. Demo data persists in the `job_talk_data` volume.

```bash
docker compose down
```

Run `docker compose down -v` only when you intend to delete the demo database. The sample PostgreSQL credentials are for local development. Keep `.env` out of Git.

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

The backend creates `backend/job_talk.db` automatically. Set `OPENAI_API_KEY` in this terminal if you want generated replies. In another terminal:

```bash
cd frontend
npm ci
npm run dev
```

Open [the Vite app](http://localhost:5173). It calls `http://localhost:8000/api` by default.

## Five minute demo

1. Enter `employer@example.com` and start a chat.
2. Select **Hire a welder**, or say: "I am looking to hire a welder with welding and forklift experience in Cape Town, with two years of experience."
3. Publish the job.
4. Log out, enter `candidate@example.com`, and start a chat.
5. Select **Find trade work**, or say: "I am looking for a job. I have three years of welding and forklift experience in Cape Town."
6. Review the match and apply.

The earlier software example also works: publish a junior Python developer role requiring FastAPI and Docker, then describe a matching candidate.

## Tests

```bash
cd backend
pytest
```

For the frontend, run `npm run build` inside `frontend`.

## Current limits and next steps

The app uses text only, a small rule based vocabulary, and heuristic scores. It does not verify skills or employers. Application data is not anonymous in the current API. The brief proposes WhatsApp and voice notes, verified employers, anonymous top five candidate previews, privacy controls, and subscription plus placement fees; those are not implemented yet.
