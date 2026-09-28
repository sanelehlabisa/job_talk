# Job Talk Agent Guide

## Product direction

Job Talk is a conversation-first job matching demo for informal, trade, and
entry level candidates and the small employers who hire them. Keep the product
simple enough to explain in a short video: an employer describes a job, a
candidate describes their experience, and the app shows an explainable match.

The current milestone is a reliable local demo. The next milestone is a private
deployment on a user-owned VM and subdomain. Do not present the current
email-only account flow as production authentication.

## Demo contract

The core demo must continue to support this sequence:

1. An employer opens a conversation and describes a role.
2. The app extracts job criteria and lets the employer publish the role.
3. A candidate opens a separate conversation and describes their experience.
4. The app ranks published roles, explains each score, and lets the candidate
   apply without another form.
5. Every reported score retains its criterion scores and weights for a future
   multidimensional plot.

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
- Enforce authentication, authorization, and chat ownership before a public
  launch. Email address knowledge must not grant access to an account.
- Keep secrets in ignored environment files or the VM secret store.
- Add focused tests for backend behavior and run the frontend production build
  for UI changes.
- Preserve deterministic seed and demo behavior.

## Workflow

Use `TASKS.md` as the ordered source of truth. Work from the first unchecked P0
ticket unless the user changes priority. Mark a ticket complete only after its
acceptance checks pass, and update the README when commands or behavior change.

Local development currently uses `docker-compose.yml`. Ticket `JT-006` owns its
rename to `dev.docker-compose.yaml`; update every documented command in the same
change so there is no ambiguous default stack.
