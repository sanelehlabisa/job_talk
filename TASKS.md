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

## Completed foundation

### JT-001 - Local conversation and matching flow

- [x] Save users, chats, messages, candidate profiles, job posts, and applications.
- [x] Support candidate and employer conversations.
- [x] Publish sufficiently described jobs and rank up to five matches.
- [x] Return criterion scores, weights, reasons, and the weighted overall score.

### JT-002 - Deterministic mock response generator

- [x] Put response generation behind one `generate_reply` function.
- [x] Remove the external AI dependency from the local demo path.
- [x] Echo a ten-character current-message preview in every mock reply.
- [x] Include current-chat history count and previous-user-message context.
- [x] Cover message and context behavior with backend tests.

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

**Status:** Complete. Accounts use Argon2 password hashes and opaque, expiring
database sessions. Thirteen backend tests and a live PostgreSQL smoke test verify
session lifecycle and cross-account boundaries (2026-09-28).

### JT-006 - Mark the current Compose stack as development

- [x] Rename `docker-compose.yml` to `dev.docker-compose.yaml`.
- [x] Keep development host ports bound to `127.0.0.1` by default.
- [x] Update README commands and any scripts to use `docker compose -f
  dev.docker-compose.yaml ...` explicitly.
- [x] Confirm the clean development stack starts, becomes healthy, and retains data.

**Status:** Complete. Compose configuration validated and the renamed stack
restarted with healthy services while retaining the existing PostgreSQL volume
(2026-09-29).

### JT-007 - Production environment and secret contract

- [ ] Add a documented production environment template with placeholder values.
- [ ] Configure the Job Talk subdomain, public HTTPS origin, certificate email,
  trusted proxy addresses, and allowed hosts through production environment values.
- [ ] Require strong database and authentication secrets at startup.
- [ ] Keep environment files, certificates, private keys, and backups out of Git.
- [ ] Validate the public origin, trusted hosts, and subdomain configuration.
- [ ] Document secret rotation without rebuilding frontend assets.

### JT-008 - Database migrations, backups, and recovery

- [ ] Replace startup-only table creation with versioned migrations.
- [ ] Add a VM backup command and retention policy for PostgreSQL data.
- [ ] Test restoring the database into a clean stack.
- [ ] Document rollback for both application image and database migration.

### JT-009 - Production Compose package

- [ ] Add an explicit production Compose file with pinned image versions.
- [ ] Keep PostgreSQL, FastAPI, and the frontend container on the internal Compose
  network; use `expose` for service-to-service traffic without host bindings.
- [ ] Publish only reverse-proxy host ports `80:80` and `443:443` on the VM.
- [ ] Treat the browser frontend as an untrusted API client. Keep authentication,
  authorization, ownership, recruiter approval, input validation, matching,
  scoring, application state changes, and data filtering in FastAPI.
- [ ] Never place secrets or authoritative business rules in Vite build arguments,
  browser storage, or frontend-only checks.
- [ ] Add database-aware readiness checks, restart policies, resource limits, and
  persistent named volumes.
- [ ] Document build, start, health check, logs, upgrade, rollback, and shutdown.

### JT-010 - HTTPS ingress and staging access

- [ ] Add a root `nginx/` directory for the public reverse proxy.
- [ ] Listen publicly on port 80 only to redirect requests to HTTPS on port 443.
- [ ] Terminate TLS on port 443 for the configured Job Talk subdomain.
- [ ] Serve the internal frontend service at `/` and proxy `/api/` to the internal
  FastAPI service, preserving one browser origin.
- [ ] Confirm the VM exposes no frontend, backend, or PostgreSQL host port other
  than Nginx ports 80 and 443.
- [ ] Forward trusted proxy headers, set conservative security headers, limit API
  requests, and cap request body size.
- [ ] Keep staging behind proxy authentication or an IP allowlist until the guest
  application boundary and `JT-012` safety controls pass.
- [ ] Automate certificate issue and renewal, then test renewal without downtime.

### JT-011 - VM and subdomain deployment

- [ ] Choose the final subdomain and create its DNS record.
- [ ] Configure the VM firewall to allow SSH, HTTP, and HTTPS only as required.
- [ ] Deploy the production package and confirm only the reverse proxy is public.
- [ ] Verify TLS, private-demo access control, health checks, restart after reboot,
  logs, backups, and rollback from outside the VM network.

## P0-B - Build the recruiter experiment

### JT-018 - Manual recruiter access

- [ ] Disable open recruiter registration in the deployed experiment.
- [ ] Add an idempotent command for creating or approving a recruiter account.
- [ ] Keep recruiter login, logout, session expiry, and job ownership checks.
- [ ] Show a clear message explaining that recruiter access is currently by invite.
- [ ] Add tests proving an unapproved account cannot create jobs or view candidates.

**Done when:** only a manually approved recruiter can enter the recruiter flow,
and approval requires no database editing by hand.

### JT-019 - Seed three to five realistic jobs

- [ ] Define 3-5 realistic trade or entry level jobs with title, location,
  description, requirements, and criterion weights.
- [ ] Add an idempotent seed command owned by the approved demo recruiter.
- [ ] Publish a read-only public job list and job-detail endpoint.
- [ ] Add simple mobile job cards with one clear `Apply through chat` action.
- [ ] Keep search, filters, recommendations, and external job feeds out of scope.

**Done when:** a new environment can be seeded once and a candidate can open a
stable public URL for every job.

### JT-020 - Scoped guest candidate application

- [ ] Start an application from a published job without account registration.
- [ ] Issue a high-entropy, expiring guest token scoped to one application and job.
- [ ] Store only the guest token in browser session storage; store only its hash
  in the database.
- [ ] Reject reads or writes to another guest application, recruiter chat, or job.
- [ ] Collect candidate name and preferred contact only at review or submission.
- [ ] Explain what will be shared with the recruiter and capture explicit consent.
- [ ] Add expiry, replay, ownership, and cross-application boundary tests.

**Done when:** two candidates can use the same job link without accounts and
cannot see or change each other's conversation or application.

### JT-021 - Job-specific conversational application

- [ ] Anchor every candidate conversation to the selected job and its criteria.
- [ ] Extract skills, experience, location, availability, and evidence into a
  structured draft after each answer.
- [ ] Ask deterministic follow-up questions for missing job-relevant information.
- [ ] Show simple progress and let the candidate review the structured result.
- [ ] Require an explicit submit action and freeze the recruiter-visible snapshot.
- [ ] Preserve current-chat context across every follow-up and page refresh.
- [ ] Test strong, partial, unrelated, empty, and interrupted applications.

**Done when:** a candidate can finish a coherent application from one job page
without a CV, account, or separate form.

### JT-022 - Recruiter candidate comparison

- [ ] Add a recruiter-owned job view with submitted candidate count and status.
- [ ] Show every candidate in the same structure: experience, skills, location,
  availability, evidence, overall match, criterion scores, and clear gaps.
- [ ] Add a compact side-by-side comparison for at least two candidates.
- [ ] Link every score explanation to candidate-provided evidence.
- [ ] Reveal contact details only for submitted applications owned by that recruiter.
- [ ] Add empty, one-candidate, two-candidate, and unauthorized-access tests.

**Done when:** the stronger and weaker demo candidates are visibly comparable
without reading their full transcripts.

### JT-023 - Replace the mock for invited-user conversations

- [ ] Keep the existing provider function and deterministic test implementation.
- [ ] Add one configured API or local model provider for deployed conversations.
- [ ] Send the selected job, structured draft, and bounded current-chat history.
- [ ] Require structured output validation and fall back to deterministic prompts.
- [ ] Bound latency, retries, input size, output size, and per-application cost.
- [ ] Prevent secrets and other candidates' data from entering model context.
- [ ] Evaluate the same strong, partial, and unrelated candidate examples before release.

### JT-024 - Minimal experiment analytics and feedback

- [ ] Record unique anonymous visitors, application starts, application submissions,
  recruiter comparison opens, feedback submissions, and seven-day returns.
- [ ] Do not put names, contact details, chat text, or skill evidence in analytics events.
- [ ] Add a one-question candidate feedback prompt after submission.
- [ ] Add a one-question recruiter usefulness prompt after comparison.
- [ ] Provide a small protected report or documented query for experiment counts.
- [ ] Define the review date and evidence needed for continue, change, or stop.

**Done when:** the experiment can answer how many people started, completed,
compared, returned, and reported the workflow useful.

## P0-C - Protect invited users and their data

### JT-012 - Safety, privacy, and abuse controls

- [ ] Publish plain-language privacy, acceptable-use, and data-deletion information.
- [ ] Add rate limits for login, chat, publish, and apply operations.
- [ ] Limit field lengths and reject unsafe or malformed input consistently.
- [ ] Remove sensitive values from logs and define a short demo-data retention period.
- [ ] Disable or protect API documentation in the deployed environment.
- [ ] Add reporting and administrative removal paths before accepting unknown users.

## P1 - Improve the experiment after the core flow works

### JT-013 - Post-experiment model evaluation

- [ ] Start only after the core flow produces real recruiter and candidate feedback.
- [ ] Version prompts and structured-output schemas used by the deployed provider.
- [ ] Compare quality, latency, and cost on consented, de-identified examples.
- [ ] Test prompt injection, irrelevant content, unsupported claims, and biased output.
- [ ] Decide whether provider portability or a local model solves an observed problem.
- [ ] Keep the deterministic provider for repeatable tests.

### JT-014 - Match-score visualization

- [ ] Confirm the criterion names and weights used in the recruiter experiment.
- [ ] Add an accessible multidimensional plot with a readable text equivalent.
- [ ] Show why a criterion scored high or low without overstating certainty.
- [ ] Test empty, partial, and perfect-match profiles on mobile and desktop.

### JT-015 - Usability and accessibility pass

- [ ] Verify keyboard navigation, visible focus, labels, contrast, and screen-reader names.
- [ ] Add a recoverable error state around the chat view.
- [ ] Test the full recruiter-to-candidate demo on a small phone and desktop browser.
- [ ] Add a short in-product note that matching is guidance and skills are unverified.

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
- [ ] Branding work beyond a clear logo and usable mobile interface.
