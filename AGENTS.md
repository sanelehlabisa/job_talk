# Job Talk Agent Guide

## Product direction

Job Talk is a small deployed experiment for informal, trade, and entry level
candidates and the recruiters who hire them. Its current question is narrow:
will recruiters find conversational applications and structured candidate
comparison useful?

Optimize for real usage and feedback. Keep the experiment free. Recruiters are
manually approved and use authenticated accounts. Candidates open a published
job and apply without creating an account; the backend must still issue an
opaque guest token scoped to that application. Do not weaken ownership checks
to create an accountless flow.

## Demo contract

The primary experiment must support this sequence:

1. A manually approved recruiter signs in and opens a seeded or manually
   created job.
2. A candidate opens that job from a public link without creating an account.
3. The candidate applies through a job-specific conversation that extracts
   skills, experience, location, availability, and supporting evidence.
4. The candidate reviews and submits the structured application with contact
   details and clear consent.
5. The recruiter sees submitted candidates in one consistent, comparable view.
6. Match results show criterion scores, weights, evidence, and gaps without
   presenting the score as a hiring decision.

## AI boundary

- Keep all response generation behind `backend/app/services/ai.py`.
- Use the deterministic mock until a ticket explicitly introduces a real API or
  local model.
- Always pass only messages from the current chat as model context.
- Keep mock replies deterministic so local and automated tests are repeatable.
- Never place API keys in source code, Compose files, logs, or frontend builds.

## Engineering boundaries

- Keep React, Vite, FastAPI, SQLAlchemy, PostgreSQL, and Docker Compose.
- Prefer a small, understandable implementation over extra infrastructure.
- Keep public ports bound to localhost in the development stack.
- Treat the backend and database as private services in production. Only the
  HTTPS reverse proxy may publish host ports.
- Enforce recruiter authentication and ownership. Scope every guest candidate
  request to one unguessable, expiring application token.
- Keep secrets in ignored environment files or the VM secret store.
- Add focused tests for backend behavior and run the frontend production build
  for UI changes.
- Preserve deterministic seed and demo behavior.

## Experiment boundaries

Defer recruiter verification automation, payments, advanced dashboards, complex
job discovery, external integrations, and branding work beyond the visible
candidate and recruiter flow. Build only what helps test the current recruiter
value hypothesis or safely operate the experiment.

## Workflow

Use `TASKS.md` as the ordered source of truth. Work from the first unchecked P0
ticket unless the user changes priority. Mark a ticket complete only after its
acceptance checks pass, and update the README when commands or behavior change.

Local development currently uses `docker-compose.yml`. Ticket `JT-006` owns its
rename to `dev.docker-compose.yaml`; update every documented command in the same
change so there is no ambiguous default stack.
