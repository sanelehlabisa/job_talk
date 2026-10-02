# Job Talk tickets

## Product aim

> Help people explain what they can do and help small employers describe what
> they need, then turn both conversations into transparent job matches.

The current priority is a deployed, free experiment with manually approved
recruiters and accountless candidate applications. The product hypothesis is:

> Recruiters will find conversational applications and structured candidate
> comparison useful enough to try again or request continued access.

Deployment follows in stages: private staging, a small public candidate flow,
then an evidence-based decision about further investment.

## Core MVP v1 - current ordered work

The revised MVP has one contract and one loop: **Define -> Apply -> Score ->
Compare.** Complete these tickets in order before VM deployment. Existing work
is the foundation, but acceptance now depends on the same typed criterion keys
being visible and traceable through every step. The canonical product context is
in [`docs/core-mvp.md`](docs/core-mvp.md).

### JT-046 - Normalize one shared job criteria contract

- [x] Store every criterion with a stable `key`, `label`, `type`, `target`,
  optional `unit`, backend-owned `weight`, and short `description`.
- [x] Normalize existing drafts and seeded jobs at the service boundary without
  adding infrastructure solely for this change.
- [x] Update a criterion by stable key when a recruiter clarifies it; do not add
  wording variants as duplicates.
- [x] Show target, weight or importance, and description in recruiter review.
- [x] Preserve existing published jobs and deterministic demo behavior.

**Done when:** a recruiter can describe the plumber role, review measurable
targets for each criterion, correct one target, and publish without duplicate
criteria.

**Status:** Complete. A small service-boundary normalizer adds the canonical
fields to new drafts, seeded roles, API responses, publication, and matching
without a database migration. The recruiter review shows target and weight. The
plumber acceptance test changes the existing criterion from three to four years
without creating a duplicate. Focused backend tests and the frontend production
build pass (2026-10-02).

### JT-047 - Map candidate answers to the published criteria

- [x] Capture candidate `value` and supporting `evidence` under the exact
  published criterion key.
- [x] Collect name, location, and at least one contact method at review.
- [x] Use the current application chat and saved evidence to avoid repeated
  questions and ask only about material missing or unclear criteria.
- [x] Let candidates correct extracted values before consent and submission.

**Done when:** a candidate can apply to the plumber role without an account and
review evidence mapped to every answered job criterion.

**Status:** Complete. Candidate claims now carry `criterion_key`, typed `value`,
`evidence`, and assessment under the published job key. Gaps have a null value.
The final review displays job targets and extracted values, collects name,
location, and email or phone, and keeps the existing return-to-chat correction
path before consent. Focused application and evidence tests plus the frontend
production build pass (2026-10-02).

### JT-048 - Score typed candidate values against typed targets

- [x] Return candidate value, target value, score, weight, evidence, reason, and
  gap state for every criterion.
- [x] Keep scoring deterministic and backend-owned for number, skill, and text
  criteria.
- [x] Calculate the overall weighted score only from validated criterion results.
- [x] Cover strong, partial, explicit-gap, missing, and unrelated answers.

**Done when:** every displayed score can be traced from a candidate statement to
the shared criterion, target, scoring rule, and reason.

**Status:** Complete. Each saved match criterion now includes its label and type,
candidate and target values, score, weight, evidence, reason, and explicit
reported or missing gap state. Numeric criteria compare values directly with a
capped ratio, while legacy evidence snapshots remain readable through bounded
deterministic value extraction. The recruiter comparison shows candidate and
target values. Focused typed scoring, gap, compatibility, and plumber scenario
tests plus the frontend production build pass (2026-10-02).

### JT-049 - Recommend only useful job matches

- [x] Apply one documented minimum match threshold before calling a job a
  recommendation.
- [x] Return at most five jobs ordered by weighted score.
- [x] Keep weak jobs available to browse without presenting them as strong fits.

**Done when:** a plumber profile recommends the relevant jobs and an unrelated
profile receives no misleading recommendation.

**Status:** Complete. The backend applies a single 50% threshold and returns its
classification with each scored role. Results remain limited to five and sorted
by weighted score. Weak selected roles stay applyable, but the UI labels them as
below the recommendation threshold rather than as strong matches. The plumber
scenario verifies that its strong candidate qualifies while the unrelated
candidate does not (2026-10-02).

### JT-050 - Sign off the complete core loop

- [x] Show the recruiter up to five leading submitted candidates with contact,
  overall score, criterion values, evidence, reasons, and gaps.
- [x] Plot the ideal profile and up to five candidates on the existing parallel
  comparison using the shared criteria.
- [x] Run recruiter create, review, publish, candidate apply, submit, score, and
  recruiter compare on desktop and phone size.
- [x] Repeat the plumber scenario with strong, partial, and unrelated candidates.

**Done when:** one recruiter creates a job, one candidate applies through chat,
and the recruiter can clearly explain which candidate is closest and why.

**Status:** Complete. The updated browser workflow passed recruiter email-code
login, typed role creation, review, publication, accountless candidate chat,
contact review, consent, submission, typed score comparison, close, and deletion
on desktop and phone size. The comparison screenshots show the ideal plot and the
candidate card with contact, overall score, values, targets, evidence, reasons,
and gaps. The deterministic plumber test covers strong, partial, and unrelated
candidates. Browser automation now reports JavaScript details and safely waits
through controlled-input and phone reload updates (2026-10-02).

## Local usability and reliability - current priority

Production work is paused until the user resumes it. Fix only behavior that can
stop or confuse a recruiter or candidate in the local Core MVP flow.

### JT-051 - Keep the local app current and repeatable

- [x] Make backend source edits reload automatically in development Compose.
- [x] Make frontend source edits reload reliably from the Windows and OneDrive
  bind mount.
- [x] Run the complete deterministic backend flow twice without order-dependent
  failures.
- [x] Run the browser create, apply, compare, close, and delete workflow twice.
- [x] Fix only reproducible Core MVP blockers found by those runs.

**Done when:** the development URL consistently serves the current source and the
complete local flow passes twice without a manual container restart.

**Status:** Complete. Development Compose now runs Uvicorn reload through polling
and Vite uses polling for Docker Desktop and OneDrive bind mounts. Touching each
source tree produced a backend restart and frontend HMR update without a manual
container restart. Migration tests now resolve their scripts independently of
the working directory, and production-setting tests no longer inherit local demo
seeding. The complete backend suite passed twice with 57 tests per run, and the
live desktop and phone create, publish, apply, compare, close, and delete workflow
passed twice with fresh recruiters (2026-10-02).

### JT-052 - Freeze the published scoring contract

- [x] Reject recruiter chat edits after a job is published.
- [x] Hide the recruiter composer and explain that published criteria are locked.
- [x] Confirm rejected edits cannot change the public job criteria.
- [x] Keep candidate conversations and recruiter comparison available.

**Done when:** every applicant for a published job is evaluated against the same
reviewed criteria until the recruiter closes that recruitment.

**Status:** Complete. The API rejects recruiter messages once a job is published,
and the recruiter UI replaces the composer with a clear locked-criteria state.
The focused API test proves rejected edits leave the public profile unchanged.
The complete browser sign-off then passed publication, candidate conversation,
submission, recruiter comparison, close, and deletion on desktop and phone size
(2026-10-02).

### JT-053 - Preserve a message when sending fails

- [x] Keep the recruiter's or candidate's typed message in the composer when the
  API request fails.
- [x] Show the existing recoverable error notice without an unhandled promise.
- [x] Confirm the same message can be sent successfully after a temporary failure.

**Done when:** a temporary network or API failure cannot silently discard the
user's work, and retrying completes the normal conversation flow.

**Status:** Complete. The composer now clears only after the API accepts a
message. The browser sign-off injects a one-request network failure, verifies the
exact candidate text remains available, retries it, and completes the desktop
and phone create, apply, compare, close, and delete flow (2026-10-02).

### JT-054 - Stop drafts when recruitment closes

- [x] Mark every unsubmitted candidate chat closed when its recruiter closes the
  job.
- [x] Reject further messages and applications with a clear closed-recruitment
  response.
- [x] Keep already submitted application snapshots available to both sides.
- [x] Replace the candidate composer with a clear closed state and route them to
  Browse other jobs.

**Done when:** a candidate cannot spend time editing or submitting a draft after
the recruiter has stopped accepting applications.

**Status:** Complete. Closing a recruitment now closes all unfinished candidate
chats for that job while leaving submitted application snapshots intact. The API
returns a clear conflict for late messages or submissions, and the candidate UI
replaces its composer with a closed state that points to Browse other jobs. The
focused lifecycle test, all 57 backend tests, and the frontend production build
pass (2026-10-02).

### JT-055 - Add a small seeker discovery path

- [x] Show two available job suggestions when a seeker enters.
- [x] Let a seeker start a general matching conversation when neither visible job
  is suitable.
- [x] Return at most two ranked jobs for a general seeker conversation.
- [x] Scope the guest conversation to the selected job when an application is
  submitted.

**Done when:** a seeker can choose one of two quick options or describe their work
from scratch, then submit only one job-scoped application.

**Status:** Complete. Seeker entry shows at most two quick job choices and a
Start from scratch action. A general guest conversation ranks at most two
published jobs, uses clearer non-selected match wording, and becomes scoped to
the chosen job at submission so the same guest cannot apply elsewhere. Focused
discovery and ownership tests plus the frontend production build pass
(2026-10-02).

## Deployment after local reliability sign-off

`JT-046` through `JT-050` now pass. Resume `JT-044`; production packaging already
builds, and the remaining work is the real VM, DNS, SMTP, TLS, backup, rollback,
and public-boundary verification.

## Previous MVP foundation

### Remaining path to a usable pilot

The pilot answers one question: can one recruiter create a job, can one candidate
apply through chat, and can the recruiter compare candidates clearly? Finish the
local release sequence below before returning to VM and subdomain work.

The earlier create, apply, and compare scenario passes repeatedly. AI role
interpretation (`JT-045`) and the local desktop and phone sign-off (`JT-043`) are
complete. The revised core contract in `JT-046` through `JT-050` now comes before
deployment through the existing `JT-010` and `JT-011` package (`JT-044`).

The deterministic mock remains the safe default. A personal ChatGPT subscription
may support manual development and evaluation, but it is not an application
backend and does not include API usage. The optional OpenAI provider uses separate
API billing and must have an explicit project spend limit before public use.
Local model and visualization work remain demand-gated experiments and do not
block the first usable pilot.

## Revised minimal MVP release sequence

Every ticket in this sequence must directly help a recruiter create a job, a
candidate apply, or a recruiter compare applicants. Prefer existing components,
hardcoded examples, deterministic rules, and deletion of unused code.

### JT-032 - Keep recruiter access minimal

- [x] Require manual approval before recruiter access.
- [x] Sign approved recruiters in with a short-lived, single-use email code.
- [x] Keep local email testing on the same path through Mailpit.
- [x] Keep approval in the existing owner CLI; do not add an admin dashboard.
- [x] Do not require a recruiter profile or setup wizard before job creation.

**Status:** Complete through `JT-018`. An approved recruiter can request a code,
sign in, and create a job immediately. The MVP stores only the recruiter identity
needed for authorization; name and company profile fields remain deferred until
real recruiter use requires them (2026-10-02).

### JT-033 - Make conversational job creation reliable

- [x] Extract title, location or work setup, skills, experience, and availability
  from a recruiter conversation.
- [x] Ask only for important missing or unclear criteria.
- [x] Show the structured criteria and allow plain-language corrections.
- [x] Treat pasted job descriptions like ordinary recruiter input and verify the
  important criteria survive one long message.
- [x] Make the visible `Publish job` button the only final publication action;
  saying the role is done should prepare it for review without publishing it.
- [x] Cover pasted input, correction, readiness, explicit publication, and public
  visibility with focused tests.

**Done when:** a recruiter can paste or describe a role, answer only necessary
questions, review the result, and explicitly publish it.

**Status:** Complete. Long recruiter input preserves the plumber demo criteria,
completion phrases stop at final review, and the explicit publication endpoint is
idempotent so a repeated click cannot duplicate the public role (2026-10-02).

### JT-034 - Optional starter job templates

- [ ] Revisit only if a real recruiter cannot start a blank hiring conversation.
- [ ] If needed, hardcode a few editable examples; do not build template management.

**Status:** Deferred. Seeded jobs already support the demo and templates are not
required to test the core product question.

### JT-035 - Keep candidate entry accountless

- [x] List available published jobs before candidate entry.
- [x] Start a job-scoped private guest conversation without registration.
- [x] Allow the candidate to leave the guest session and choose another job.

**Status:** Complete through `JT-020` and `JT-027`.

### JT-036 - Keep candidate applications conversational

- [x] Summarize the selected job and ask only about its criteria.
- [x] Separate captured evidence, missing evidence, and reported gaps.
- [x] Review the structured application, contact details, and consent before submit.
- [x] Keep uploads, documents, certificates, and voice notes deferred.

**Status:** Complete through `JT-021`, `JT-028`, and `JT-031`.

### JT-037 - Keep matching deterministic and explainable

- [x] Score each criterion in backend-owned deterministic code.
- [x] Show requirement, evidence, score, weight, reason, and gap state.
- [x] Calculate one repeatable weighted score without LLM scoring.

**Status:** Complete through `JT-001`, `JT-014`, and `JT-028`.

### JT-038 - Keep recruiter comparison focused

- [x] Show submitted count, comparable candidate evidence, contact details, scores,
  and obvious gaps for one recruiter-owned job.
- [x] Limit the closed-job shortlist and comparison plot to five candidates.
- [x] Keep pipelines, interview scheduling, notes, and messaging deferred.

**Status:** Complete through `JT-022`. Reassess the parallel plot during `JT-040`;
hide it from the default view if it slows comparison.

### JT-039 - Minimal product simplification pass

- [x] Remove or hide UI and code that does not support create, apply, or compare.
- [x] Remove duplicate actions and development wording visible to pilot users.
- [x] Preserve privacy, authorization, guest isolation, consent, deletion, and rate limits.
- [x] Keep optional providers and future experiments out of the default user flow.

**Status:** Complete. Deterministic replies now show only the useful guided response,
without temporary mock, context, or draft diagnostics. A scoped candidate session
labels its one job as the selected role and has one clear review action. Optional
provider behavior remains backend-only and all user protection paths remain intact
(2026-10-02).

### JT-040 - Deterministic plumber demo scenario

- [x] Create and publish a Cape Town plumber role covering plumbing, leak repair,
  pipe fitting, geyser installation, location, and availability.
- [x] Submit a strong plumber, a partial handyman with no geyser experience, and
  an unrelated software candidate through separate guest sessions.
- [x] Confirm strong, medium, and very low results with evidence and gaps that make sense.
- [x] Compare all three through the recruiter comparison contract and verify the
  comparison UI on desktop and phone size.

**Status:** Complete. The deterministic flow creates the role through recruiter
chat, publishes explicitly, submits three isolated guest snapshots, and verifies
their score order plus the partial candidate's reported and missing trade evidence.
The scenario exposed and fixed generic experience words falsely filling unrelated
criteria. The browser walkthrough verifies candidate submission and recruiter
comparison layouts at desktop and phone sizes (2026-10-02).

### JT-041 - Fix only demo-blocking bugs

- [x] Record issues found during `JT-040`.
- [x] Fix only creation, state, scoring, isolation, submission, comparison, and
  mobile blockers.
- [x] Run the complete deterministic scenario twice without failure.

**Status:** Complete. `JT-040` found one blocker: generic experience wording could
fill unrelated trade criteria and produce a misleading high score. That matching
bug was fixed and regression tested. Two clean database runs of the plumber flow
passed consecutively, followed by another live Compose browser pass covering
emailed recruiter sign-in, candidate submission, recruiter comparison, and phone
and desktop layouts. No additional blocker was found (2026-10-02).

### JT-042 - Keep deterministic mode as the release default

- [x] Keep job readiness, extraction, follow-ups, and scoring usable without paid AI.
- [x] Keep OpenAI optional and behind the same bounded backend service.
- [x] Do not block the pilot on API credits or local model hosting.

**Status:** Complete. Provider experiments remain demand gated under `JT-023`.

### JT-045 - Validate and polish recruiter answers with AI

- [x] Return categorized role updates alongside the recruiter reply through one
  strict structured-output contract.
- [x] Use only the current authorized chat, current draft, backend weights, and
  the recruiter's latest message when interpreting an answer.
- [x] Require each saved update to quote supporting text from the latest message;
  leave the previous draft unchanged when an answer is unrelated or unclear.
- [x] Turn accepted requirements into concise, measurable descriptions while the
  backend remains responsible for weights and publication readiness.
- [x] Persist accepted updates to the job draft so the existing review UI shows
  exactly what matching will use.
- [x] Preserve the deterministic creation flow when the provider is disabled,
  unavailable, invalid, or over its per-chat call limit.
- [x] Cover categorization, unsupported updates, short follow-up answers, strict
  provider output, persistence, and fallback behavior with focused tests.

**Done when:** AI can interpret and polish recruiter answers without silently
accepting unrelated content or controlling weights/readiness, and the recruiter
can review the saved criteria before publishing.

**Status:** Complete. OpenAI turns now return a strict reply plus categorized role
updates. The backend accepts only updates with an exact quote from the current
message, owns criterion weights and readiness, and saves accepted measurable
requirements for the existing review UI. Empty, invalid, unavailable, and capped
provider results preserve the deterministic flow. The backend suite passes with
focused coverage for novel skills, short answers, unsupported fields, persistence,
strict output, and fallback behavior (2026-10-02).

### JT-043 - Local usability sign-off

- [x] Run manual approval, email-code login, job creation, publication, comparison,
  and close on desktop and phone size.
- [x] Run accountless job selection, conversation, review, consent, submission, and
  deletion on desktop and phone size.
- [x] Confirm the local app is reliable enough for one recruiter and one candidate.

**Status:** Complete. A repeatable Edge workflow manually approves and signs in a
recruiter, creates and publishes a fresh role, submits an evidence-backed guest
application with consent, compares it, closes recruitment, deletes the candidate
data, and verifies the deleted token is rejected. Desktop and phone screenshots
were inspected. Sign-off exposed and fixed a closed-role publication action and an
exact-location scoring error; the final candidate scored 91% with Cape Town shown
as a 95% location match. The backend suite and frontend production build pass
(2026-10-02).

### JT-044 - Deploy only after local sign-off

- [x] Validate the production Compose configuration and build the backend,
  frontend, and proxy images from the signed-off revision.
- [ ] Complete the VM work in `JT-010` and `JT-011` using the real subdomain and
  production secret values.
- [ ] Verify DNS, firewall, TLS renewal, backup, reboot, logs, rollback, and that
  only ports 80 and 443 are public.

**Status:** In progress. The production configuration resolves without exposing
secrets, and all three application images build successfully. Production now uses
the tested 1,000-token structured AI response bound. The preflight also requires
the immutable image tag to equal the checked-out Git commit. The remaining checks
require the real VM, subdomain, SMTP settings, and production secrets (2026-10-02).

## Completed foundation

### JT-001 - Local conversation and matching flow

- [x] Save users, chats, messages, candidate profiles, job posts, and applications.
- [x] Support candidate and employer conversations.
- [x] Publish sufficiently described jobs and rank up to five matches.
- [x] Return criterion scores, weights, reasons, and the weighted overall score.

### JT-002 - Deterministic mock response generator

- [x] Put response generation behind one `generate_reply` function.
- [x] Remove the external AI dependency from the local demo path.
- [x] Use temporary message and context diagnostics while stabilizing the send flow.
- [x] Remove those diagnostics from pilot-visible replies during `JT-039`.
- [x] Cover deterministic guided replies and current-chat context isolation with tests.

### JT-003 - Stable send-message UI

- [x] Keep API response handling consistent after a message is sent.
- [x] Preserve the active chat and reload its list entry without blanking the UI.
- [x] Verify first and later messages in the browser.

### JT-004 - Clear chat participants and light company credit

- [x] Show the Roventics robot face for assistant messages and typing state.
- [x] Show a distinct person icon for user messages.
- [x] Keep the company credit small so Job Talk remains the product identity.

## P0-A - Make deployment safe and repeatable

### JT-005 - Real authentication and resource ownership

- [x] Replace email-only account opening with a bounded authentication flow.
- [x] Require an authenticated identity on every user, chat, job, recommendation,
  and application endpoint.
- [x] Enforce user ownership of chats and candidate applications in backend queries.
- [x] Let only the account that owns a job list its applicants.
- [x] Add tests proving one account cannot read or change another account's data.

**Done when:** knowing another person's email or record ID cannot expose or alter
their data.

**Status:** Complete as the ownership and session foundation. Opaque, expiring
database sessions protect backend resources. The later passwordless entry work
removed password credentials while preserving these resource boundaries. Backend
tests and a live PostgreSQL smoke test verify session lifecycle and cross-account
access (updated 2026-09-29).

### JT-006 - Mark the current Compose stack as development

- [x] Rename `docker-compose.yml` to `dev.docker-compose.yaml`.
- [x] Keep development host ports bound to `127.0.0.1` by default.
- [x] Update README commands and any scripts to use `docker compose -f
  dev.docker-compose.yaml ...` explicitly.
- [x] Confirm the clean development stack starts, becomes healthy, and retains data.

**Status:** Complete. Compose configuration validated and the renamed stack
restarted with healthy services while retaining the existing PostgreSQL volume.
Development source now runs through bind mounts with cached dependency volumes,
so normal Compose startup does not send OneDrive reparse files through a BuildKit
context (updated 2026-09-30).

### JT-007 - Production environment and secret contract

- [x] Add a documented production environment template with placeholder values.
- [x] Configure the Job Talk subdomain, public HTTPS origin, certificate email,
  trusted proxy addresses, and allowed hosts through production environment values.
- [x] Require strong database and authentication secrets at startup.
- [x] Keep environment files, certificates, private keys, and backups out of Git.
- [x] Validate the public origin, trusted hosts, and subdomain configuration.
- [x] Document secret rotation without rebuilding frontend assets.

**Status:** Complete. FastAPI now loads one validated settings contract, rejects
unsafe production origins, database, session, and email sender settings, hashes
session tokens with a server-side pepper, and applies configured trusted hosts
and CORS origins. Production and development templates plus rotation instructions
are documented (2026-09-29).

### JT-008 - Database migrations, backups, and recovery

- [x] Replace startup-only table creation with versioned migrations.
- [x] Add a VM backup command and retention policy for PostgreSQL data.
- [x] Test restoring the database into a clean stack.
- [x] Document the clean-stack restore drill and rollback for both application
  image and database migration.

**Status:** Complete. Alembic migration `20260929_01` adopts the existing schema
and runs before the API starts. Backup and guarded restore scripts use PostgreSQL
custom-format dumps, verification, checksums, and configurable retention. A live
drill restored the development database into an isolated Compose project and new
volume, started the API successfully, and matched the migration revision and row
counts across users, chats, messages, jobs, and applications (2026-09-29).

### JT-009 - Production Compose package

- [x] Add an explicit production Compose file with pinned image versions.
- [x] Keep PostgreSQL, FastAPI, and the frontend container on the internal Compose
  network; use `expose` for service-to-service traffic without host bindings.
- [x] Publish only reverse-proxy host ports `80:80` and `443:443` on the VM.
- [x] Treat the browser frontend as an untrusted API client. Keep authentication,
  authorization, ownership, recruiter approval, input validation, matching,
  scoring, application state changes, and data filtering in FastAPI.
- [x] Never place secrets or authoritative business rules in Vite build arguments,
  browser storage, or frontend-only checks.
- [x] Add database-aware readiness checks, restart policies, resource limits, and
  persistent named volumes.
- [x] Document build, start, health check, logs, upgrade, rollback, and shutdown.

**Status:** Complete. The production package pins infrastructure images by
digest and application images by Git commit tag, keeps application and database
services private, and publishes only Nginx ports 80 and 443. An isolated clean
stack passed migrations, database readiness, HTTPS frontend and API routing, and
published-port checks; operating commands are documented (2026-10-01).

### JT-010 - HTTPS ingress and staging access

- [x] Add a root `nginx/` directory for the public reverse proxy.
- [x] Listen publicly on port 80 only to redirect requests to HTTPS on port 443.
- [x] Terminate TLS on port 443 for the configured Job Talk subdomain.
- [x] Serve the internal frontend service at `/` and proxy `/api/` to the internal
  FastAPI service, preserving one browser origin.
- [x] Confirm the VM exposes no frontend, backend, or PostgreSQL host port other
  than Nginx ports 80 and 443.
- [x] Forward trusted proxy headers, set conservative security headers, limit API
  requests, and cap request body size.
- [x] Keep staging behind proxy authentication or an IP allowlist until the guest
  application boundary and `JT-012` safety controls pass.
- [ ] Automate certificate issue and renewal, then test renewal without downtime.

**Status:** Nginx now bootstraps ACME over HTTP, requires a staging password on
HTTPS, rate limits API bursts, forwards trusted headers, and isolates the browser
frontend from the backend network. Pinned Certbot issue and renewal automation is
in place, and a local certificate replacement reloaded Nginx with 60/60 readiness
requests succeeding. The checkbox remains open until `renew --dry-run` passes for
the real subdomain on the VM (updated 2026-10-01).

### JT-011 - VM and subdomain deployment

- [ ] Choose the final subdomain and create its DNS record.
- [x] Add a production preflight that checks required values without printing
  secrets, verifies origin consistency and DNS, and validates Compose.
- [ ] Configure the VM firewall to allow SSH, HTTP, and HTTPS only as required.
- [ ] Deploy the production package and confirm only the reverse proxy is public.
- [ ] Verify TLS, private-demo access control, health checks, restart after reboot,
  logs, backups, and rollback from outside the VM network.

## P0-B - Build the recruiter experiment

### JT-025 - Use consistent chat participant icons

- [x] Replace the Roventics robot image inside assistant chat bubbles and typing
  state with a simple circular assistant icon, such as Lucide `Bot`.
- [x] Keep the assistant and person icons the same shape and size while using
  distinct colors and accessible labels.
- [x] Keep the small Roventics project credit in the footer instead of using the
  company robot as the conversational assistant identity.
- [x] Check the icons at phone and desktop sizes.

**Done when:** assistant and user messages are immediately distinguishable and
both participants use the same simple avatar style.

**Status:** Complete. Assistant messages and typing use Lucide `Bot`, user
messages use `UserRound`, and both render in the same fixed circular avatar with
distinct colors and screen-reader labels. The Roventics robot remains only in
the small footer credit, and the frontend production build passes (2026-10-01).

### JT-018 - Manual recruiter approval and email-code sign-in

- [x] Let a recruiter submit an email access request without choosing a password.
- [x] Add an idempotent owner command to list, approve, or reject access requests;
  this approval is the only routine manual account action.
- [x] Return the same request-code response for unknown, pending, rejected, and
  approved addresses so the endpoint does not reveal approved recruiter emails.
- [x] For an approved recruiter, email a random short-lived code and store only its
  hash, expiry, attempt count, and consumed state.
- [x] Make each code single use, limit verification attempts, and invalidate an
  older code when a new one is issued.
- [x] Rate limit recruiter code requests before public deployment.
- [x] Issue the existing opaque recruiter session after successful verification;
  keep logout, session expiry, recruiter ownership, and job ownership checks.
- [x] Remove password registration, password hashes, and password fields from the
  recruiter API and UI after the migration is in place.
- [x] Add a pinned local Mailpit SMTP inbox to the development stack.
- [x] Add a seeded approved recruiter so local testing uses the real email-code
  path without an authentication bypass.
- [x] Show clear pending-approval, code-sent, invalid-code, and expired-code states.
- [x] Test approval boundaries, address enumeration responses, expiry, reuse,
  attempt limits, replacement codes, and cross-recruiter access.

**Done when:** a recruiter can request access, the owner can approve the request
without editing the database, and only that approved email can complete the same
email-code flow in development and production. Candidates never see a login flow.

**Status:** Complete. Approved addresses are limited to one code per 60 seconds
and five per hour by default while every approval state receives the same 202
response. Focused backend tests cover approval boundaries, expiry, single use,
attempt lockout, replacement codes, and cross-recruiter isolation (2026-10-01).

### JT-019 - Seed three to five realistic jobs

- [x] Define 3-5 realistic trade or entry level jobs with title, location,
  description, requirements, and criterion weights.
- [x] Add an idempotent seed command owned by the approved demo recruiter.
- [x] Publish a read-only public job list and job-detail endpoint.
- [x] Add simple mobile job cards with one clear `Apply through chat` action.
- [x] Keep search, filters, recommendations, and external job feeds out of scope.

**Done when:** a new environment can be seeded once and a candidate can open a
stable public URL for every job.

**Status:** Complete. Development startup publishes three deterministic roles
for the approved demo recruiter. The public API, `/?job=<id>` links, and seeker
job picker expose the same jobs, and repeated seed runs create no duplicates
(2026-09-29).

### JT-020 - Scoped guest candidate application

- [x] Let a job seeker start one private candidate conversation without an account,
  email address, or password.
- [x] Start an application from a published job without account registration.
- [x] Issue a high-entropy, expiring guest token scoped to one candidate chat and job.
- [x] Store only the guest token in browser session storage; store only its hash
  in the database.
- [x] Reject reads or writes to another guest application, recruiter chat, or job.
- [x] Collect candidate name and preferred contact only at review or submission.
- [x] Explain what will be shared with the recruiter and capture explicit consent.
- [x] Add expiry, replay, ownership, and cross-application boundary tests.

**Done when:** two candidates can use the same job link without accounts and
cannot see or change each other's conversation or application.

**Status:** Complete. Two independent guest sessions can apply to one job while
remaining isolated, expired and logged-out tokens cannot be replayed, and backend
tests cover cross-chat, cross-job, and cross-application access (2026-09-30).

### JT-021 - Job-specific conversational application

- [x] Anchor every candidate conversation to the selected job and its criteria.
- [x] Extract skills, experience, location, availability, and evidence into a
  structured draft after each answer.
- [x] Ask deterministic follow-up questions for missing job-relevant information.
- [x] Show simple progress and let the candidate review the structured result.
- [x] Require an explicit submit action and freeze the recruiter-visible snapshot.
- [x] Preserve current-chat context across every follow-up and page refresh.
- [x] Test strong, partial, unrelated, empty, and interrupted applications.

**Done when:** a candidate can finish a coherent application from one job page
without a CV, account, or separate form.

**Status:** Complete. Candidate replies ask about the highest-weight missing job
criterion, retain the structured draft across refreshes, and move to review when
the selected role's criteria have evidence. Tests cover strong, partial,
unrelated, empty, and interrupted conversations (2026-09-30).

### JT-028 - Ground candidate claims and follow-up reasoning

- [x] Treat candidate statements as unverified claims instead of confirmed facts.
- [x] Keep vague or unrelated replies from filling the requested criterion.
- [x] Record explicit denials and later corrections as gaps with a zero criterion
  score instead of positive evidence.
- [x] Score a general claim below a concrete work example and explain the difference.
- [x] Require the hosted provider to preserve the backend's missing-evidence or
  reported-gap next step.
- [x] Show reported gaps distinctly in candidate review and recruiter comparison.
- [x] Test vague answers, denials, concrete examples, corrections, and provider
  instructions alongside the complete backend flow suite.

**Status:** Complete. Candidate extraction now distinguishes claimed evidence,
reported gaps, and answers that need clarification. Backend scoring remains the
authority even when the hosted provider is enabled, and the UI labels gaps rather
than displaying them as confirmed skills (2026-10-01).

### JT-026 - Per-chat retrieval and context boundary

This is Job Talk's first RAG-like component. It is a small context assembler over
existing relational data, rather than a vector database or document search
system.

- [x] Build one backend context function that retrieves only the selected job's
  criteria, the current structured draft, and a bounded window of messages from
  the current chat.
- [x] Scope retrieval by the authenticated owner or guest session and the chat's
  job ID; reject cross-chat, cross-job, and cross-candidate context.
- [x] Use that same context for deterministic follow-up selection and any future
  model provider.
- [x] Keep recruiter job conversations and every candidate application in
  separate contexts, even when they refer to the same job.
- [x] Add tests proving refresh preserves the right context and that another
  chat's messages, contact details, and evidence never enter a response.
- [x] Do not add embeddings, a vector store, or external knowledge retrieval
  until a real source corpus and retrieval need exist.

**Done when:** every generated response can list exactly which current chat, job,
draft, and bounded messages supplied its context.

**Status:** Complete. One context assembler supplies the current authorized chat,
selected job criteria, structured draft, and last 12 messages to the deterministic
provider. Isolation tests cover two guests on one job, refresh continuity, bounded
history, and exclusion of submitted contact details (2026-09-30).

### JT-027 - Conversational job publishing and candidate re-entry

- [x] Keep each recruiter hiring conversation attached to one job draft.
- [x] Let the recruiter refine the title and criteria through multiple messages.
- [x] Recognize explicit completion commands such as `I am done` or
  `publish the job` without matching ordinary job-description text.
- [x] Use completion commands to request final review only when the role has a
  title and enough meaningful criteria; publish only from the explicit button.
- [x] Make the published job immediately available through the public job list
  and accountless candidate entry flow.
- [x] Show candidates the available job list and let an active guest leave their
  current scoped session to browse jobs and start another private conversation.
- [x] Keep the publish button as the single accessible publication action and run
  the frontend production build.
- [x] Test early completion, multi-message refinement, explicit publication,
  public visibility, and candidate guest entry.

**Done when:** a recruiter can describe one role, answer follow-up questions,
review it, and explicitly publish it for a candidate who can later return to the
job list for another application.

**Status:** Complete. Explicit completion prepares ready recruiter-owned jobs for
final review, candidate entry lists public jobs, and `Browse other jobs` ends the current
guest session before opening a new job-specific conversation. Role readiness now
requires a title, essential skill, experience, location or work setup, and start
availability; the assistant asks for the next missing item and the UI shows all
five checks before publishing (updated 2026-10-01).

### JT-029 - Clarify and confirm recruiter criteria

- [x] Normalize detected skills and tool names into structured criteria.
- [x] Ask whether each skill is required or preferred and how many years of
  experience applicants should have.
- [x] Keep publishing disabled while a detected skill still needs clarification.
- [x] Show the recruiter every structured role attribute before publishing and
  explain that ordinary chat can correct a mistake.
- [x] Update an existing criterion in place when the recruiter corrects it.
- [x] Start each guest application with a plain summary of what the recruiter
  requested, then ask for evidence against those requirements.
- [x] Test clarification, correction, publication, candidate summary, ownership,
  and the complete recruiter-to-candidate flow.

**Status:** Complete. Each newly detected skill now carries a normalized label,
importance, requested experience, weight, and confirmation state. Recruiters see
the resulting role attributes before publishing and candidates receive the same
confirmed requirements at the start of their private application (2026-10-01).

### JT-030 - Distinguishable job workspaces

- [x] Label recruiter conversations with the role title as soon as it is known.
- [x] Label candidate conversations with the job being applied for.
- [x] Show each conversation's draft, active, published, submitted, or closed state.
- [x] Keep new untitled recruiter conversations clear without exposing message text.
- [x] Test recruiter and candidate summaries through the authenticated API.

**Status:** Complete. Conversation navigation now uses the linked job title and
lifecycle state, so recruiters can distinguish multiple role workspaces and
candidates can identify their current application (2026-10-02).

### JT-031 - Complete candidate evidence review

- [x] Show every requirement from the selected job before application submission.
- [x] Distinguish captured evidence, a candidate-reported gap, and missing evidence.
- [x] Include additional structured evidence that will be shared with the recruiter.
- [x] Give the candidate a clear way back to the chat to add or correct evidence.
- [x] Keep honest applications with missing experience possible after clear review.

**Status:** Complete. The final application review now mirrors the selected job's
requirements, identifies the evidence state for each one, and explains how to
correct the structured snapshot before consent and submission (2026-10-02).

### JT-022 - Recruiter candidate comparison

- [x] Treat each recruiter hiring chat as one job workspace with `draft`,
  `published`, and `closed` states.
- [x] Add a recruiter-owned job view with submitted candidate count and status.
- [x] Show every candidate in the same structure: experience, skills, location,
  availability, evidence, overall match, criterion scores, and clear gaps.
- [x] Add a compact side-by-side comparison for at least two candidates.
- [x] Link every score explanation to candidate-provided evidence.
- [x] Reveal contact details only for submitted applications owned by that recruiter.
- [x] Let the recruiter close recruitment, stop new applications, and preserve
  the submitted candidate snapshots used for comparison.
- [x] When a job closes, show up to five candidates ranked by the existing
  transparent weighted score, with ties and missing evidence handled explicitly.
- [x] Describe the shortlist as decision support and never as an automated hiring
  decision.
- [x] Add empty, one-candidate, two-candidate, and unauthorized-access tests.

**Done when:** the stronger and weaker demo candidates are visibly comparable
without reading their full transcripts.

**Status:** Complete. Recruiters see owned submitted applications side by side,
with consistent evidence rows, weighted criterion explanations, explicit gaps,
and consented contact details. Closing a role stops new applications and shows a
stable top-five decision-support shortlist while preserving every submitted
snapshot (2026-09-30).

### JT-023 - Demand-gated AI provider experiment

- [x] Keep the existing provider function and deterministic test implementation.
- [ ] Start this ticket only after candidate and recruiter usage shows that better
  conversational follow-ups would materially improve the experiment.
- [x] Keep personal ChatGPT subscription use outside the deployed application;
  record that ChatGPT subscriptions and API billing are separate products.
- [x] Complete `JT-026` and pass its context object to every provider.
- [ ] If a hosted provider is tested, use separately billed API access with a hard
  monthly spend limit, per-application usage limits, and no browser-visible key.
- [ ] Compare provider privacy and retention terms before sending invited-user data.
- [ ] Do not run a Llama model on the entry-level pilot VPS. Revisit one small,
  quantized, pinned Docker model only if demand justifies a larger server.
- [ ] On that larger server, benchmark CPU or GPU support, RAM use, startup time,
  tokens per second, concurrent requests, and operating effort.
- [ ] Compare the measured local model with the hosted API for response quality,
  latency, privacy, reliability, and total cost.
- [x] Send only the selected job, structured draft, and bounded current-chat history.
- [x] Require structured output validation and fall back to deterministic prompts.
- [x] Bound latency, retries, input size, output size, and per-application cost.
- [ ] Apply container memory and CPU limits so a local model cannot make the web
  app or database unavailable on a small VPS.
- [x] Prevent secrets and other candidates' data from entering model context.
- [ ] Evaluate the same strong, partial, and unrelated candidate examples before release.

**Done when:** real usage justifies the change and a measured provider improves
follow-up quality without weakening context isolation, privacy, cost control, or
application reliability.

**Status:** In progress. The opt-in OpenAI Responses provider, strict reply schema,
bounded current-chat input, `store: false`, call cap, and guided fallback are
implemented. OpenAI mode no longer shows mock response text when the provider is
unavailable. The configured local API project returned `credit_balance_exhausted`
on 2026-10-01. Add API credits, set a hard project spend limit, and run the strong,
partial, and unrelated live examples before enabling this provider publicly.

### JT-024 - Minimal experiment analytics and feedback

- [x] Record unique anonymous visitors, application starts, application submissions,
  recruiter comparison opens, feedback submissions, and seven-day returns.
- [x] Do not put names, contact details, chat text, or skill evidence in analytics events.
- [x] Add a one-question candidate feedback prompt after submission.
- [x] Add a one-question recruiter usefulness prompt after comparison.
- [x] Provide a small protected report or documented query for experiment counts.
- [x] Define the review date and evidence needed for continue, change, or stop.

**Done when:** the experiment can answer how many people started, completed,
compared, returned, and reported the workflow useful.

**Status:** Complete. Backend-owned events count visits, application starts and
submissions, recruiter comparison opens, seven-day returns, and yes-or-no feedback.
Only a keyed random visitor hash, event metadata, and numeric context IDs are
stored; the 30-day cleanup removes old events. Candidate and recruiter prompts are
visible at the completed workflow steps, the operator report is documented, and
the first review is set for 15 October 2026 (2026-10-01).

## P0-C - Protect invited users and their data

### JT-012 - Safety, privacy, and abuse controls

- [x] Publish plain-language privacy, acceptable-use, and data-deletion information.
- [x] Add rate limits for login, chat, publish, and apply operations.
- [x] Limit field lengths and reject unsafe or malformed input consistently.
- [x] Remove sensitive values from logs and define a short demo-data retention period.
- [x] Disable or protect API documentation in the deployed environment.
- [x] Add reporting and administrative removal paths before accepting unknown users.

**Status:** Complete. The app publishes a plain-language privacy and safety page,
uses bounded and normalized user input, provides candidate self-deletion and
guarded operator cleanup commands, and caps guest data retention at 30 days.
Nginx applies general and write-operation limits, recruiter email issuance has a
separate per-address limit, production API documentation is disabled, and the
operator runbook defines reporting and sensitive-log rules (2026-10-01).

## P1 - Improve the experiment after the core flow works

### JT-013 - Post-experiment model evaluation

- [ ] Start only after the core flow produces real recruiter and candidate feedback.
- [ ] Version prompts and structured-output schemas used by the deployed provider.
- [ ] Compare quality, latency, and cost on consented, de-identified examples.
- [ ] Test prompt injection, irrelevant content, unsupported claims, and biased output.
- [ ] Decide whether provider portability or a local model solves an observed problem.
- [ ] Keep the deterministic provider for repeatable tests.

### JT-014 - Match-score visualization

- [x] Confirm the criterion names and weights used in the recruiter experiment.
- [x] Add a parallel coordinates plot for no more than the top five candidates,
  with one normalized 0-100 axis per criterion.
- [x] Draw the job's ideal criterion profile as a clearly labelled reference line
  and each candidate as a separate selectable line.
- [x] Keep the score table, evidence, criterion weights, and gaps as the readable
  text equivalent; the plot must not be the only source of information.
- [x] Show why a criterion scored high or low without overstating certainty.
- [x] Handle missing evidence explicitly rather than drawing it as a confirmed zero.
- [x] Test empty, partial, and perfect-match profiles on mobile and desktop.

**Status:** Complete. The recruiter comparison draws the saved job criteria as
normalized axes, an ideal 100% dashed line, and up to five labelled candidate
lines. Missing evidence uses a separate × marker, while the existing evidence,
weight, reason, and gap cards remain available. Empty, partial, perfect, desktop,
and horizontally scrollable phone states were checked (2026-10-01).

### JT-015 - Usability and accessibility pass

- [x] Verify keyboard navigation, visible focus, labels, contrast, and screen-reader names.
- [x] Add a recoverable error state around the chat view.
- [x] Test the full recruiter-to-candidate demo on a small phone and desktop browser.
- [x] Add a short in-product note that matching is guidance and skills are unverified.

**Status:** Complete. Candidate application loading no longer sends an undefined
job ID, which caused the unexplained red error notification. Errors now identify
their purpose and provide reload and dismiss controls, while unexpected render
failures show a recoverable conversation screen. Interactive controls have visible
keyboard focus and accessible names, and both match views state that evidence is
unverified guidance. Focused end-to-end tests pass, and a real browser walkthrough
now covers the public job, guest application and feedback at 390 x 760, emailed
recruiter sign-in, and desktop candidate comparison (2026-10-01).

## P2 - Launch material

### JT-016 - Demo video and social launch kit

- [x] Draft the three-slide problem, live-demo, and try-it deck in
  `docs/experiment-launch.md`.
- [x] Write a 30-to-60-second script: problem, recruiter flow, candidate flow,
  explainable match, application, and invitation to try the demo.
- [ ] Record a clean demo using fictional people and data.
- [ ] Generate a QR code from the live HTTPS URL and verify it on a second phone.
- [ ] End the video with the QR code, Job Talk URL, creator name, and chosen contact.
- [ ] Draft concise LinkedIn and Reddit posts with the early-experiment context and a clear
  request for feedback.
- [ ] Avoid claims about verified skills, guaranteed work, or production readiness.

### JT-017 - Public pilot decision

- [ ] Review `JT-005` through `JT-012` and `JT-018` through `JT-024` evidence.
- [ ] Run a backup-and-restore drill and a cross-account authorization test.
- [ ] Decide whether to remain a private demo or open a small monitored pilot.
- [ ] Document monitoring, incident response, support contact, and shutdown criteria.

## Deferred until the experiment shows demand

- [ ] Automated recruiter verification.
- [ ] Payments, subscriptions, placement fees, or billing infrastructure.
- [ ] Advanced recruiter dashboards beyond job and candidate comparison.
- [ ] Complex job discovery, search, recommendations, or external job feeds.
- [ ] WhatsApp, voice notes, third-party HR integrations, and identity providers.
- [ ] Keycloak or another external authentication platform.
- [ ] Branding work beyond a clear logo and usable mobile interface.
