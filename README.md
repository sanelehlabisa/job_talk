# Job Talk

Job Talk is a hackathon-ready proof of concept that replaces CVs and application forms with a conversation. A chat can independently become a candidate job search or an employer hiring flow; there are no permanent account roles.

## What works

- Email-only sign-in with automatic account creation
- Persisted chats and messages
- Per-chat candidate/employer intent detection
- Conversational candidate and job-profile extraction
- Employer job publishing when the role has enough detail
- Top-five published-job recommendations
- Explainable, weighted criterion-by-criterion matching
- One-click application submission in the chat
- Responsive React UI

The conversational engine is deterministic for a reliable demo and isolated in `backend/app/services/conversation.py`. It can later be replaced with an LLM adapter without changing the API or data model.

## Run everything with Docker

Docker Compose starts PostgreSQL, the FastAPI backend, and the React frontend. Natural chat replies use the OpenAI Responses API with `gpt-4o-mini`; deterministic profile extraction and fallback replies keep the demo reliable.

Create a local environment file and add your OpenAI API key:

```bash
cp .env.example .env
# Edit .env and replace OPENAI_API_KEY with your key.
```

Then start the app:

```bash
docker compose up --build
```

Open `http://localhost:3000`. The API documentation is available at `http://localhost:8000/docs`.

The database is stored in the `job_talk_data` Docker volume, so data survives container restarts. To stop the app:

```bash
docker compose down
```

To also remove the persisted PoC database, explicitly run `docker compose down -v`.

Never commit `.env`; it is already ignored by Git. You can also change `OPENAI_MODEL`, `FRONTEND_PORT`, `BACKEND_PORT`, or the PostgreSQL settings in that file. If the API key is missing or a request fails, the app automatically uses its deterministic fallback response.

## Run without Docker

The backend defaults to SQLite, so PostgreSQL is optional for the fastest demo setup.

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. API documentation is at `http://localhost:8000/docs`.

To use PostgreSQL, start it with `docker compose up -d postgres`, then export:

```bash
export DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/job_talk
```

## Demo path

1. Sign in as an employer and start a new conversation.
2. Say: “I’m looking to hire a junior Python developer with FastAPI, Docker, and at least two years of experience in Cape Town.”
3. Publish the job.
4. Sign out, use a different candidate email, and start a new conversation.
5. Say: “I’m looking for a job. I have three years of Python experience and built two FastAPI APIs with Docker.”
6. Review the recommendation and apply.

## Tests

```bash
cd backend
pytest
```
