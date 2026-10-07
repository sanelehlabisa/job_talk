# Job Talk Agent Guide

## Product direction

Job Talk is a small deployed experiment for informal, trade, and entry level
candidates and the recruiters who hire them. Its current question is narrow:
will recruiters find conversational applications and structured candidate
comparison useful?

Optimize for real usage and feedback. Keep the experiment free. Recruiters are
manually approved, then sign in with a short-lived code sent to their approved
email address. Candidates open a published job and apply without creating an
account; the backend must still issue an opaque guest token scoped to that
application. Do not weaken ownership checks to create an accountless flow.

Build one narrow loop before deployment or secondary features:

> Recruiter defines the ideal candidate -> candidate applies through chat ->
> backend scores the match -> recruiter compares the best candidates.

Every feature must help this loop. The shared job criteria are the product
contract: the recruiter defines them, the candidate supplies evidence against
them, Gemini rates each criterion and backend code validates and totals the ratings, and the recruiter compares the
results. See `docs/core-mvp.md` for the canonical shapes and acceptance flow.

Each job criterion must have a stable `key`, visible `label`, `type`, measurable
`target`, optional `unit`, backend-owned `weight`, and short `description`.
Candidate evidence and match results must reference that same criterion key.
Update an existing criterion when the recruiter clarifies it; do not create a
duplicate with different wording.

Keep the recruiter form to a readable label and one editable value per field.
Types, units, importance and descriptions remain in the backend contract; do not
reintroduce separate controls or duplicate text. Closing date is optional job
metadata, excluded from applicant scoring.

Recruiter and candidate field edits save automatically after a short typing pause.
Show saving/failure feedback and retain failed input for explicit retry. Field
help is available on hover and click. Recruiters may remove any draft field,
including template defaults; missing core job details must block publication
without breaking the editor or changing the live post. Candidate clearing still
clears their evidence; submitted applications remain frozen.

New recruiter drafts ask first for the hiring company name and company base.
Keep these as non-scoring job metadata, separate from the work location. Save
them in draft JSON and expose changes to candidates only after publication.

The comparison plot uses each criterion's saved values on its own axis: numeric
amounts/units, Yes/No, or unordered text categories. Mark the recruiter's target
on every axis; missing values must not become zero or No. Display scoring weights
as relative multipliers, not percentages or automatic rejection gates.
For fully met numeric criteria with direct evidence, ranking can use values above
the target. Rank by the uncapped weighted comparison score; cap the displayed
overall match at 100%. Number current candidate cards and preserve submitted scores.

Use the same label/value layout for the seeker's application answers. Keep one
editable answer per published criterion, with the requirement as an input hint.
Chat and direct edits update the same candidate profile. Clearing an answer does
not remove an employer requirement. Contact review, consent and Submit belong at
the bottom of that form; do not duplicate the application review inside chat.

Published recruiter chats and forms remain editable. Save changes in the existing
draft JSON and require explicit Publish changes before updating the live job.
Preserve submitted evidence, requirements and scores; distinguish applications
made against earlier criteria from the current comparison. Closing recruitment
still stops applications and does not hide the recruiter's chat.

## Current usability priority (2026-10-07)

The user confirmed deployment and admin email-code login work at
`https://jobtalk.roventics.com`. Prioritize a few real testers and feedback on the
core hiring loop. Follow `TASKS.md`; completed demos remain engineering evidence,
and full manual usability acceptance in JT-060 is still separate.
New recruiter access requests notify `ADMIN_EMAIL` through existing SMTP only
when the pending account is first created. Keep approval manual and never include
login codes or candidate data in those notifications. No notification queue or
automatic retry: failed email leaves the request in the existing recruiter list.

The current implementation uses three fixed templates and the existing database,
AI boundary, authentication, discovery chat, and comparison views. Templates are
suggestions, never assumed requirements. Track unanswered, unclear, confirmed,
and not-required fields; only confirmed assessment criteria are scored.
Distinguish an employer's not-required field from a candidate's reported gap.
Keep initial seeker cards labelled available jobs and search all published open
jobs before the seeker selects the job-specific application.

Discovery offers up to two numbered possible roles with a low exploratory cutoff
and a work-related connection; do not reuse the strong-candidate threshold here.
Recalculate with each message and name the same real vacancies in chat and cards.
Show introductory guidance only at entry and hide discovery percentages; the
selected application keeps its backend match score. Never invent a vacancy.

Owner access and manual vacancy entry are implemented in JT-061/JT-062. Use an
optional backend-only `ADMIN_EMAIL` with approved email-code login and existing
expiring session tokens; never authorize requests with a reusable login code.
Admin uses the same recruiter workspace and may access and manage all hiring
chats through existing edit, publish and close controls. Show owner emails in
the shared list; do not add a separate admin dashboard. Ordinary recruiters
retain ownership limits and guest candidate chats remain scoped to their session.
Operator-curated vacancies must
identify their source and who receives applications. Reuse existing storage and
views rather than adding administration or import infrastructure.

## Demo contract

The primary experiment must support this sequence:

1. A manually approved recruiter signs in and opens a seeded or manually
   created job.
2. A candidate opens that job from a public link without creating an account.
3. The candidate applies through a job-specific conversation that extracts
   values and supporting evidence against the published job criteria.
4. The candidate reviews and submits the structured application with contact
   details and clear consent.
5. The recruiter sees submitted candidates in one consistent, comparable view.
6. Match results show criterion scores, weights, evidence, and gaps without
   presenting the score as a hiring decision.
7. Recommendations and closed-job comparisons show at most five strong matches;
   weak matches must not be presented as recommendations.

## AI boundary

- Keep all response generation behind `backend/app/services/ai.py`.
- Use the configured `AI_PROVIDER`; JT-064 introduced Gemini and local testing
  uses it. Mock mode remains for deterministic tests and explicit offline work.
- Pass the complete authorized chat as model context; never mix chats or silently
  truncate individual messages/history. Oversized inputs use the bounded fallback.
- Recruiter updates may recover unanswered fields from earlier user quotes.
  Preserve later corrections and keep source quotes verbatim when polishing text.
- Let AI interpret, clarify, and polish user statements into the shared criteria
  contract. Gemini may rate candidate evidence against each confirmed criterion
  from 0 to 100 with a short reason. The backend validates ratings and owns weights,
  readiness and the weighted total. Missing/unclear application answers and explicit
  gaps score zero. Cache ratings against the exact evidence and requirements;
  freeze them on submission. Label unavailable-model fallback as a rule estimate.
- Ask only about an important missing or unclear criterion. Use previously saved
  answers and do not repeat a resolved question.
- Keep mock replies deterministic so local and automated tests are repeatable.
- Record actual LLM verification separately from deterministic fallback tests;
  do not claim language understanding is complete based only on mock responses.
- Never place API keys in source code, Compose files, logs, or frontend builds.

## Engineering boundaries

- Keep React, Vite, FastAPI, SQLAlchemy, PostgreSQL, and Docker Compose.
- Prefer a small, understandable implementation over extra infrastructure.
- Keep public ports bound to localhost in the development stack.
- Treat the backend and database as private services in production. Only the
  app gateway may publish a localhost port; the existing `roventics-nginx-1`
  container owns public 80/443.
- Production FastAPI binds only to the Unix socket shared with Nginx. Do not add
  a backend TCP listener or mount that socket into other application services.
  This prevents direct network access; public proxy URLs still require normal
  authentication/authorization for private operations.
- Keep production API origin checks, request limits and security headers in
  Nginx. Browser headers are not client authentication; preserve backend token,
  approval and ownership checks. Never add a shared secret to frontend code.
- Enforce recruiter authentication and ownership. Scope every guest candidate
  request to one unguessable, expiring application token.
- Check recruiter approval on every private request. Logout must revoke the
  presented server session; failed logout must remain visible and retryable.
  Redeem email login codes atomically so concurrent requests cannot reuse them.
- Recruiter authentication uses emailed, short-lived, single-use codes after
  manual approval. Do not add passwords, Keycloak, open recruiter registration,
  or a production authentication bypass.
- Keep local sign-in fast with a seeded approved recruiter and a local email
  inbox that exercises the same code path used in production.
- Keep secrets in ignored environment files or the VM secret store.
- Add focused tests for backend behavior and run the frontend production build
  for UI changes.
- Run database-reset tests in disposable SQLite with `DATABASE_URL` selected
  before Python starts. Use the isolated Compose command in README. Never run
  reset fixtures against development PostgreSQL; preserve the refusal guard.
- Preserve deterministic seed and demo behavior.

## Experiment boundaries

Defer recruiter verification automation, payments, advanced dashboards, complex
job discovery, external integrations, and branding work beyond the visible
candidate and recruiter flow. Build only what helps test the current recruiter
value hypothesis or safely operate the experiment.

Before adding scope, ask whether it directly helps a recruiter define criteria, a
candidate supply evidence, the backend score a match, or a recruiter compare
applicants. If it does not, defer it until real usage shows a need. Prefer
hardcoded examples, manual approval, deterministic rules, existing components,
and deletion over new infrastructure or generalized frameworks.

## Workflow

Use `TASKS.md` as the ordered source of truth. Work from the first unchecked P0
ticket unless the user changes priority. Mark a ticket complete only after its
acceptance checks pass, and update the README when commands or behavior change.

Develop completed tickets on feature branches and keep those branches pushed.
Merge completed work into `master` only after the user explicitly approves the
merge. After approval, include the final workflow or ticket documentation,
fast-forward `master` when the history permits, push `master`, and verify that the
working tree and remote tracking branch are clean. A request to commit and push a
feature branch does not by itself approve merging it.

Local development uses `dev.docker-compose.yaml`. Always pass it explicitly with
`docker compose -f dev.docker-compose.yaml ...` so development and production
commands cannot be confused.
Production uses `docker compose --env-file .env -f prod.docker-compose.yaml ...`.
Each app owns its Compose project. Job Talk's gateway binds `127.0.0.1:8081` for
VPS checks and joins only the external `roventics_proxy` network so the existing
`roventics-nginx-1` public proxy can reach it by alias. This small proxy network
is the sole cross-project resource. TLS and renewal belong to the VPS's existing
Certbot installation. The backend socket is shared only with Job Talk's own
gateway; the database stays private.
Follow `docs/production-operations.md`. Preserve existing app environments/data
and other websites. Live DNS, certificates and VM listener changes are operator
steps. Use isolated disposable resources for production tests.
Use one `.env` per installation and one `.env.example`. Set VM values in its
`.env`; preserve the local development credentials and database. Candidate follow-up
messaging is deferred until explicitly requested.

Keep environment setup small: `APP_DOMAIN` is the single public host setting.
Compose derives origins and sets ports; the browser uses relative `/api` URLs.
Do not require image tags or duplicated API URLs in `.env`. Email settings are
`SMTP_HOST`, `SMTP_PORT`, `SMTP_SECURE`, `SMTP_USER`, `SMTP_PASSWORD`, `EMAIL_FROM`.
`SMTP_SECURE=false` uses STARTTLS when available; true uses implicit TLS.
Never send SMTP credentials without encryption. Local Mailpit needs no credentials.

Use one short comment per `.env` section. Keep only app/admin, database, session
pepper, SMTP and Gemini settings there. Support links use `info@roventics.com`;
certificate registration reuses `ADMIN_EMAIL`. The webpage opens directly; do not
reintroduce proxy Basic Auth, a staging password file or extra login credentials.
Production credentials come from `.env`; never substitute development passwords.
Production Compose environment substitutions must require explicit values; do
not add fallback values for SMTP, Gemini or other installation settings. Reuse
the existing VPS certificate; extend its names only when Job Talk is not covered.
Keep session/AI tuning defaults in backend code instead of duplicate production
Compose overrides. Generate private random session peppers, never commit them.
Development startup seeds only `recruiter@example.com` if missing; preserve
existing approvals and jobs. Production seeds nothing automatically. The explicit
`python -m app.recruiters seed` operator command creates the configured admin
if missing, with normal email login. Reuse existing users, hashed expiring sessions
and login-code tables; do not add a second token store or bypass authentication.
